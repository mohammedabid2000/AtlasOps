#!/usr/bin/env python3
"""Local operations without third-party Python dependencies. Never log secrets."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VAULT = "http://127.0.0.1:8200"
BASE = "https://localhost:8443"


def request(url, method="GET", data=None, headers=None, timeout=10, context=None):
    payload = None if data is None else json.dumps(data).encode()
    headers = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def write_private(path, value, mode=0o600):
    # Write in place: Compose secrets are bind-mounted and preserve an inode.
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(value)
    os.chmod(path, mode)


def setup():
    os.umask(0o077)
    for directory in (".secrets", ".certs", ".state", ".backups"):
        (ROOT / directory).mkdir(exist_ok=True, mode=0o700)
        os.chmod(ROOT / directory, 0o700)
    if not (ROOT / ".env").exists():
        shutil.copyfile(ROOT / ".env.example", ROOT / ".env")
    for name in ("db-password", "db-admin-password", "grafana-password", "api-key"):
        path = ROOT / ".secrets" / name
        if not path.exists():
            write_private(path, secrets.token_hex(32) + "\n")
        # Individual nonroot containers must read bind-mounted Compose secrets.
        # The host parent directory remains 0700.
        if name != "api-key":
            os.chmod(path, 0o444)
    for name in ("role-id", "secret-id"):
        path = ROOT / ".secrets" / name
        if not path.exists():
            write_private(path, "", 0o444)
    cert, key = ROOT / ".certs/server.crt", ROOT / ".certs/server.key"
    if not cert.exists() or not key.exists():
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-sha256",
                        "-nodes", "-days", "30", "-keyout", str(key), "-out", str(cert),
                        "-subj", "/C=MA/O=AtlasOps Lab/CN=localhost",
                        "-addext", "subjectAltName=DNS:localhost,DNS:nginx,IP:127.0.0.1"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.chmod(cert, 0o644)
    print("Local configuration and credentials are ready. Existing values were preserved.")


def vault_call(path, method="GET", data=None, token=None):
    status, body = request(VAULT + "/v1/" + path, method, data,
                           {"X-Vault-Token": token} if token else {})
    if status >= 400:
        raise RuntimeError(f"Vault {method} {path} returned HTTP {status}; inspect Vault logs locally")
    return json.loads(body) if body else {}


def root_token():
    return json.loads((ROOT / ".secrets/vault-init.json").read_text())["root_token"]


def bootstrap(unseal_only=False):
    for attempt in range(90):
        try:
            initialized = vault_call("sys/init")["initialized"]
            break
        except (OSError, RuntimeError):
            if attempt == 89:
                raise RuntimeError("Vault did not start within 180 seconds")
            time.sleep(2)
    path = ROOT / ".secrets/vault-init.json"
    if not initialized:
        if path.exists():
            raise RuntimeError("Vault data is empty but existing recovery material exists. Stop and investigate; do not overwrite it.")
        result = vault_call("sys/init", "PUT", {"secret_shares": 1, "secret_threshold": 1})
        write_private(path, json.dumps(result, indent=2) + "\n")
    if not path.exists():
        raise RuntimeError("Existing Vault requires its original .secrets/vault-init.json recovery material")
    recovery = json.loads(path.read_text())
    if vault_call("sys/seal-status")["sealed"]:
        vault_call("sys/unseal", "PUT", {"key": recovery["keys_base64"][0]})
    token = recovery["root_token"]
    # Unseal may return before single-node Raft leader activation finishes.
    for _ in range(60):
        status, _body = request(VAULT + "/v1/sys/health")
        if status == 200:
            break
        time.sleep(1)
    else:
        raise RuntimeError("Vault unsealed but active leader did not become ready")
    if unseal_only:
        print("Vault unsealed.")
        return
    mounts = vault_call("sys/mounts", token=token)
    if "secret/" not in mounts:
        vault_call("sys/mounts/secret", "POST", {"type": "kv", "options": {"version": "2"}}, token)
    auth = vault_call("sys/auth", token=token)
    if "approle/" not in auth:
        vault_call("sys/auth/approle", "POST", {"type": "approle"}, token)
    policy = (ROOT / "infra/vault/api-policy.hcl").read_text()
    vault_call("sys/policies/acl/atlasops-read", "PUT", {"policy": policy}, token)
    vault_call("auth/approle/role/atlasops", "POST", {
        "token_policies": ["atlasops-read"], "token_ttl": "10m", "token_max_ttl": "1h",
        "secret_id_ttl": "24h", "secret_id_num_uses": 0, "token_num_uses": 0}, token)
    status, body = request(VAULT + "/v1/secret/data/atlasops", headers={"X-Vault-Token": token})
    if status == 404:
        vault_call("secret/data/atlasops", "POST", {"data": {"api_key": (ROOT / ".secrets/api-key").read_text().strip()}}, token)
    elif status == 200:
        write_private(ROOT / ".secrets/api-key", json.loads(body)["data"]["data"]["api_key"] + "\n")
    else:
        raise RuntimeError(f"Reading KV returned HTTP {status}")
    role = vault_call("auth/approle/role/atlasops/role-id", token=token)["data"]["role_id"]
    secret = vault_call("auth/approle/role/atlasops/secret-id", "POST", {}, token)["data"]["secret_id"]
    # Host chmod temporarily permits updating read-only credential files.
    for name, value in (("role-id", role), ("secret-id", secret)):
        p = ROOT / ".secrets" / name
        os.chmod(p, 0o600)
        write_private(p, value + "\n", 0o444)
    audit = vault_call("sys/audit", token=token)
    if "file/" not in audit:
        vault_call("sys/audit/file", "PUT", {"type": "file", "options": {"file_path": "/vault/data/audit.jsonl"}}, token)
    print("Vault initialized/unsealed; read-only AppRole issued for 24 hours. No credentials were printed.")


def app_request(path, method="GET", data=None, key=None):
    ctx = ssl.create_default_context(cafile=str(ROOT / ".certs/server.crt"))
    return request(BASE + path, method, data, {"X-API-Key": key} if key else {}, context=ctx)


def wait_ready():
    for attempt in range(90):
        try:
            if app_request("/health/ready")[0] == 200:
                return
        except OSError:
            pass
        time.sleep(2)
    raise RuntimeError("HTTPS readiness did not succeed within 180 seconds")


def smoke():
    wait_ready()
    key = (ROOT / ".secrets/api-key").read_text().strip()
    assert app_request("/api/tasks")[0] == 401, "Unauthenticated access must be rejected"
    assert app_request("/metrics")[0] == 404, "Metrics must not be exposed through ingress"
    code, body = app_request("/api/tasks", "POST", {"title": "AtlasOps smoke test"}, key)
    assert code == 201, f"Create failed: HTTP {code}"
    task_id = json.loads(body)["id"]
    try:
        code, body = app_request("/api/tasks?limit=100", key=key)
        assert code == 200 and any(t["id"] == task_id for t in json.loads(body)), "Created task not readable"
        assert app_request("/api/tasks/" + task_id, "PATCH", {"done": True}, key)[0] == 200
        payload = urllib.parse.quote("<script>alert(1)</script>")
        assert app_request("/?probe=" + payload)[0] == 403, "CRS XSS probe was not blocked"
        payload = urllib.parse.quote("1' OR '1'='1' --")
        assert app_request("/?id=" + payload)[0] == 403, "CRS SQLi probe was not blocked"
    finally:
        app_request("/api/tasks/" + task_id, "DELETE", key=key)
    print("PASS: trusted TLS, readiness, auth, CRUD, hidden metrics, XSS and SQLi WAF probes.")


def rotate():
    old = (ROOT / ".secrets/api-key").read_text().strip()
    new = secrets.token_hex(32)
    vault_call("secret/data/atlasops", "POST", {"data": {"api_key": new}}, root_token())
    # Keep the new credential even if the Agent is unavailable; recovery must not lose it.
    write_private(ROOT / ".secrets/api-key", new + "\n")
    for _ in range(45):
        try:
            if app_request("/api/tasks", key=new)[0] == 200:
                assert app_request("/api/tasks", key=old)[0] == 401, "Old key still accepted"
                print("PASS: new key accepted; old key rejected; API was not restarted.")
                return
        except OSError:
            pass
        time.sleep(2)
    raise RuntimeError("Key saved in Vault and .secrets/api-key but render not confirmed. Refresh AppRole with make vault-refresh.")


def elastic_setup():
    policy = {"policy": {"phases": {"hot": {"actions": {}}, "delete": {"min_age": "7d", "actions": {"delete": {}}}}}}
    template = {"index_patterns": ["atlasops-*"], "template": {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0, "index.lifecycle.name": "atlasops-7d"},
        "mappings": {"properties": {"@timestamp": {"type": "date"}, "status": {"type": "integer"},
                                   "service": {"type": "keyword"}, "request_id": {"type": "keyword"},
                                   "route": {"type": "keyword"}, "duration_ms": {"type": "float"}}}}}
    for path, data in (("/_ilm/policy/atlasops-7d", policy), ("/_index_template/atlasops", template)):
        code, _ = request("http://127.0.0.1:9200" + path, "PUT", data)
        if code >= 400:
            raise RuntimeError(f"Elasticsearch setup failed: {path}: HTTP {code}")
    code, _ = request("http://127.0.0.1:9200/atlasops-*/_settings?allow_no_indices=true", "PUT",
                      {"index": {"lifecycle.name": "atlasops-7d", "number_of_replicas": 0}})
    if code >= 400:
        raise RuntimeError(f"Could not apply retention to existing indices: HTTP {code}")
    for _ in range(90):
        try:
            code, _ = request("http://127.0.0.1:5601/api/data_views/data_view", "POST", {
                "data_view": {"id": "atlasops", "title": "atlasops-*", "timeFieldName": "@timestamp"}, "override": True},
                {"kbn-xsrf": "atlasops-setup"})
            if code in (200, 201):
                print("ELK index policy (7 days) and Kibana data view are ready.")
                return
        except OSError:
            pass
        time.sleep(2)
    raise RuntimeError("Kibana did not become ready; retry make elastic-setup")


def verify_observability(logs=False):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            code, raw = request("http://127.0.0.1:9090/api/v1/query?query=" + urllib.parse.quote('probe_success{job="https-probe"}'))
            result = json.loads(raw).get("data", {}).get("result", [])
            if code == 200 and result and all(x["value"][1] == "1" for x in result):
                break
        except (OSError, ValueError):
            pass
        time.sleep(3)
    else:
        raise RuntimeError("Prometheus HTTPS probe did not report success")
    code, raw = request("http://127.0.0.1:3000/api/health")
    assert code == 200 and json.loads(raw).get("database") == "ok", "Grafana not healthy"
    if logs:
        key = (ROOT / ".secrets/api-key").read_text().strip()
        app_request("/api/tasks", key=key)
        for _ in range(60):
            code, raw = request("http://127.0.0.1:9200/atlasops-*/_count")
            if code == 200 and json.loads(raw).get("count", 0) > 0:
                break
            time.sleep(3)
        else:
            raise RuntimeError("No documents reached Elasticsearch")
    print("PASS: Prometheus TLS probe and Grafana" + ("; Elasticsearch ingestion" if logs else ""))


def snapshot():
    path = ROOT / ".backups" / ("vault-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".snap")
    code, body = request(VAULT + "/v1/sys/storage/raft/snapshot", headers={"X-Vault-Token": root_token()})
    if code != 200:
        raise RuntimeError(f"Vault snapshot failed with HTTP {code}")
    path.write_bytes(body)
    path.chmod(0o600)
    print(path.relative_to(ROOT))


if __name__ == "__main__":
    os.chdir(ROOT)
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "vault-bootstrap", "vault-unseal", "smoke", "rotate", "elastic-setup", "verify", "verify-full", "vault-snapshot"])
    command = parser.parse_args().command
    try:
        {"init": setup, "vault-bootstrap": bootstrap, "vault-unseal": lambda: bootstrap(True),
         "smoke": smoke, "rotate": rotate, "elastic-setup": elastic_setup,
         "verify": verify_observability, "verify-full": lambda: verify_observability(True),
         "vault-snapshot": snapshot}[command]()
    except (OSError, RuntimeError, AssertionError, KeyError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
