"""Optional real Vault integration: VAULT_BIN=/path/to/vault pytest -q tests/test_vault_live.py."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("VAULT_BIN"), reason="Optional native Vault executable not supplied")

def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]

def test_real_vault_approle_policy_agent_rotation_and_snapshot(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("ops", repo / "scripts/ops.py")
    ops = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ops)
    ops.ROOT = tmp_path
    port, cluster_port = free_port(), free_port()
    ops.VAULT = f"http://127.0.0.1:{port}"
    (tmp_path / "infra/vault").mkdir(parents=True)
    shutil.copy(repo / ".env.example", tmp_path / ".env.example")
    shutil.copy(repo / "infra/vault/api-policy.hcl", tmp_path / "infra/vault/api-policy.hcl")
    ops.setup()
    (tmp_path / "data").mkdir()
    config = tmp_path / "server.hcl"
    config.write_text(f'''disable_mlock = true
api_addr = "{ops.VAULT}"
cluster_addr = "http://127.0.0.1:{cluster_port}"
storage "raft" {{ path = "{tmp_path}/data" node_id = "test" }}
listener "tcp" {{ address = "127.0.0.1:{port}" cluster_address = "127.0.0.1:{cluster_port}" tls_disable = true }}
''')
    # The native test uses an audit path under its isolated temporary directory.
    original_vault_call = ops.vault_call
    def vault_call(path, method="GET", data=None, token=None):
        if path == "sys/audit/file" and data:
            data = {"type":"file", "options":{"file_path":str(tmp_path / "audit.jsonl")}}
        return original_vault_call(path, method, data, token)
    ops.vault_call = vault_call
    with (tmp_path / "vault-process.log").open("w") as output:
        server = subprocess.Popen([os.environ["VAULT_BIN"], "server", "-config="+str(config)], stdout=output, stderr=output)
        agent = None
        try:
            ops.bootstrap()
            role = (tmp_path / ".secrets/role-id").read_text().strip()
            sid = (tmp_path / ".secrets/secret-id").read_text().strip()
            login = ops.vault_call("auth/approle/login", "POST", {"role_id":role, "secret_id":sid})
            token = login["auth"]["client_token"]
            initial = (tmp_path / ".secrets/api-key").read_text().strip()
            assert ops.vault_call("secret/data/atlasops", token=token)["data"]["data"]["api_key"] == initial
            for path, method, data in (("secret/data/atlasops", "POST", {"data":{"api_key":"forbidden"}}),
                                       ("secret/data/unrelated", "GET", None)):
                code, _ = ops.request(ops.VAULT+"/v1/"+path, method, data, {"X-Vault-Token":token})
                assert code == 403
            rendered = tmp_path / "rendered-key"
            agent_config = (repo / "infra/vault/agent.hcl").read_text()
            for old,new in (("http://vault:8200",ops.VAULT), ("/tmp/vault-agent.pid",str(tmp_path/"agent.pid")),
                            ("/run/secrets/role_id",str(tmp_path/".secrets/role-id")),
                            ("/run/secrets/secret_id",str(tmp_path/".secrets/secret-id")),
                            ("/run/atlasops/api-key",str(rendered))):
                agent_config=agent_config.replace(old,new)
            (tmp_path/"agent.hcl").write_text(agent_config)
            agent = subprocess.Popen([os.environ["VAULT_BIN"], "agent", "-config="+str(tmp_path/"agent.hcl")], stdout=output, stderr=output)
            def wait_render(value):
                for _ in range(60):
                    if rendered.exists() and rendered.read_text().strip()==value: return
                    time.sleep(.5)
                raise AssertionError("Vault Agent did not render within 30 seconds")
            wait_render(initial)
            replacement = "b"*64
            ops.vault_call("secret/data/atlasops", "POST", {"data":{"api_key":replacement}}, ops.root_token())
            wait_render(replacement)
            ops.snapshot()
            assert next((tmp_path/".backups").glob("vault-*.snap")).stat().st_size > 0
            ops.vault_call("sys/seal", "PUT", {}, ops.root_token())
            assert ops.vault_call("sys/seal-status")["sealed"] is True
            ops.bootstrap(unseal_only=True)
            assert ops.vault_call("sys/seal-status")["sealed"] is False
        finally:
            if agent:
                agent.terminate(); agent.wait(timeout=10)
            server.terminate(); server.wait(timeout=10)
