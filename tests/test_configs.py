from pathlib import Path
import json
import subprocess
import hcl2
import yaml

ROOT = Path(__file__).resolve().parents[1]

def test_yaml_and_json_parse():
    for path in list(ROOT.rglob("*.yml")) + list(ROOT.rglob("*.yaml")):
        if ".venv" in path.parts: continue
        with path.open() as stream: list(yaml.safe_load_all(stream))
    for path in (ROOT / "infra/grafana/dashboards").glob("*.json"):
        json.loads(path.read_text())

def test_hcl_parse():
    for path in list((ROOT / "terraform").rglob("*.tf")) + list((ROOT / "infra/vault").glob("*.hcl")):
        with path.open() as stream: hcl2.load(stream)

def test_no_public_management_ports_or_docker_socket():
    data = yaml.safe_load((ROOT / "compose.yaml").read_text())
    for service in data["services"].values():
        for port in service.get("ports", []):
            assert port.startswith("127.0.0.1:"), port
        for volume in service.get("volumes", []):
            assert "docker.sock" not in volume
    assert not data["services"]["api"].get("ports")
    assert not data["services"]["db"].get("ports")
    assert not data["services"]["waf"].get("ports")

def test_shell_syntax():
    for path in (ROOT / "scripts").glob("*.sh"):
        subprocess.run(["bash", "-n", str(path)], check=True)
