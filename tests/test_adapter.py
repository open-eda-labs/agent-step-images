"""Testes do n2-adapter: harness falso (contrato de saída, prompt, tempo, passos, recusa) e, com CLINE_BIN, o Cline de verdade contra um modelo falso."""

import importlib.machinery
import importlib.util
import json
import os
import pathlib
import socket
import subprocess
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "n2-adapter"
loader = importlib.machinery.SourceFileLoader("n2_adapter", str(ADAPTER))
n2 = importlib.util.module_from_spec(importlib.util.spec_from_loader("n2_adapter", loader))
loader.exec_module(n2)

# Harness falso: `auth` grava os argumentos; a execução faz o que FAKE manda e emite o stream JSON do Cline (iteration_start, content_start).
FAKE = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, time
a = sys.argv[1:]
out = pathlib.Path(os.environ["FAKE_OUT"])
if a[0] == "auth":
    (out / "auth.json").write_text(json.dumps(a))
    sys.exit(1 if os.environ["FAKE"] == "authfail" else 0)
work = pathlib.Path(a[a.index("-c") + 1])
(out / "task.txt").write_text(a[-1])
(out / "env.json").write_text(json.dumps(dict(os.environ)))
(out / "agents.txt").write_text((work / "AGENTS.md").read_text())
def step(i, tool):
    print(json.dumps({"type": "agent_event", "event": {"type": "iteration_start", "iteration": i}}))
    print(json.dumps({"type": "agent_event", "event": {"type": "content_start", "contentType": "tool", "toolName": tool}}), flush=True)
mode = os.environ["FAKE"]
if mode == "loop":
    for i in range(1, 10000):
        step(i, "editor"); time.sleep(0.01)
if mode == "hang":
    time.sleep(60)
if mode.startswith("write:"):
    path, text = mode[6:].split("=", 1)
    (work / path).parent.mkdir(parents=True, exist_ok=True)
    (work / path).write_text(text)
    step(1, "editor"); step(2, "submit_and_exit")
if mode == "delete-test":
    (work / "src/test/T.java").unlink(); step(1, "run_commands")
'''


@pytest.fixture
def world(tmp_path, monkeypatch):
    repo = tmp_path / "in" / "repo"
    (repo / "src" / "test").mkdir(parents=True)
    (repo / "src" / "A.java").write_text("class A { quebrado }\n")
    (repo / "src" / "test" / "T.java").write_text("class T {}\n")
    (repo / "pom.xml").write_text("<project>\n  <version>1.0.0</version>\n</project>\n")
    (repo / "target").mkdir()
    (repo / "target" / "lixo.class").write_text("x")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)  # o .git do repositório original não vai para a cópia
    (tmp_path / "in" / "error.log").write_text("[ERROR] cannot find symbol\n")
    (tmp_path / "out").mkdir()
    (tmp_path / "fake").mkdir()
    fake = tmp_path / "harness"
    fake.write_text(FAKE)
    fake.chmod(0o755)
    for k, v in {"N2_HARNESS": str(fake), "FAKE_OUT": str(tmp_path / "fake"), "OPENAI_BASE_URL": "http://gw/v1", "MODEL": "fix-n2",
                 "OPENAI_API_KEY": "sk-falsa", "GITHUB_PACKAGES_TOKEN": "ghp-falso", "MAVEN_ARGS": "-s /etc/maven/settings.xml"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(n2, "VERIFY", ["grep", "-q", "ok", "src/A.java"])  # verify falso: verde se o agente escreveu "ok"
    return tmp_path


def adapter(world, mode, monkeypatch):
    monkeypatch.setenv("FAKE", mode)
    return n2.main(["n2-adapter", str(world / "in"), str(world / "out")])


def test_green_writes_patch_that_applies_on_the_input_repo(world, monkeypatch):
    assert adapter(world, "write:src/A.java=class A { ok }\n", monkeypatch) == 0
    patch = (world / "out" / "patch.diff").read_text()
    assert patch.startswith("diff --git a/src/A.java b/src/A.java") and "AGENTS.md" not in patch and "target" not in patch
    subprocess.run(["git", "apply", "--check", str(world / "out" / "patch.diff")], cwd=world / "in" / "repo", check=True)
    assert os.listdir(world / "out") == ["patch.diff"]


def test_prompt_carries_the_log_and_the_agent_gets_no_secret(world, monkeypatch):
    adapter(world, "write:src/A.java=ok", monkeypatch)
    fake = world / "fake"
    task = (fake / "task.txt").read_text()
    assert "[ERROR] cannot find symbol" in task and "{error_log}" not in task and task.startswith(n2.PROMPT.read_text()[:60])
    env = json.loads((fake / "env.json").read_text())
    assert not {"GITHUB_PACKAGES_TOKEN", "OPENAI_API_KEY"} & env.keys() and env["MAVEN_ARGS"] == "-s /etc/maven/settings.xml -o"
    assert env["DISABLE_TELEMETRY"] == "1" and "AGENTS.md" in n2.AGENTS.name and (fake / "agents.txt").read_text() == n2.AGENTS.read_text()
    auth = json.loads((fake / "auth.json").read_text())
    assert auth[:8] == ["auth", "-p", "openai-compatible", "-k", "sk-falsa", "-m", "fix-n2", "-b"] and auth[8] == "http://gw/v1"


def test_red_verify_writes_nothing(world, monkeypatch):
    assert adapter(world, "write:src/A.java=class A { ainda quebrado }", monkeypatch) == 4
    assert not (world / "out" / "patch.diff").exists()


@pytest.mark.parametrize("mode", ["write:.github/workflows/ci.yml=ok", "write:Dockerfile=ok", "write:build.sh=ok",
                                  "write:pom.xml=<project>\n  <version>9.9.9</version>\n</project>\n",
                                  "write:src/test/T.java=@Disabled class T { ok }", "delete-test"])
def test_forbidden_diff_is_refused(world, monkeypatch, mode):
    monkeypatch.setattr(n2, "VERIFY", ["true"])  # verde de propósito: a recusa vem antes
    assert adapter(world, mode, monkeypatch) == 6
    assert not (world / "out" / "patch.diff").exists()


def test_empty_diff(world, monkeypatch):
    assert adapter(world, "noop", monkeypatch) == 5


def test_step_limit_and_timeout_stop_the_harness(world, monkeypatch):
    monkeypatch.setenv("N2_MAX_STEPS", "3")
    t = time.monotonic()
    assert adapter(world, "loop", monkeypatch) == 3 and time.monotonic() - t < 10
    monkeypatch.setenv("N2_TIMEOUT", "1")
    t = time.monotonic()
    assert adapter(world, "hang", monkeypatch) == 3 and time.monotonic() - t < 10


def test_usage_env_and_auth_errors(world, monkeypatch):
    assert n2.main(["n2-adapter"]) == 2
    assert adapter(world, "authfail", monkeypatch) == 3
    monkeypatch.delenv("MODEL")
    assert adapter(world, "noop", monkeypatch) == 2


def test_forbidden_rule_matches_publish():
    publish = ROOT.parent / "agent-workflows" / "steps" / "publish" / "publish.py"
    if not publish.exists():
        pytest.skip("agent-workflows não está clonado ao lado")
    assert f're.compile(r"{n2.FORBIDDEN.pattern}")' in publish.read_text()


@pytest.mark.skipif(not os.environ.get("CLINE_BIN"), reason="CLINE_BIN (binário do Cline CLI) não definido")
def test_real_cline_against_fake_model(world, monkeypatch):
    """Cline de verdade, modelo falso roteirizado: editor → run_commands → submit_and_exit. Prova a ligação, não a qualidade do modelo."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    script = world / "script.json"
    script.write_text(json.dumps([
        # caminho relativo à raiz do workspace: o da cópia de trabalho só existe na hora
        {"tool": "editor", "args": {"path": "src/A.java", "old_text": "quebrado", "new_text": "ok"}},
        {"tool": "run_commands", "args": {"commands": ["grep -q ok src/A.java"]}},
        {"tool": "submit_and_exit", "args": {"summary": "migração feita e verificada", "verified": True}}]))
    srv = subprocess.Popen([sys.executable, str(ROOT / "tests" / "fake_openai.py"), str(port), str(script)])
    try:
        time.sleep(1)
        monkeypatch.setenv("N2_HARNESS", os.environ["CLINE_BIN"])
        monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{port}/v1")
        monkeypatch.setenv("HOME", str(world / "home"))
        monkeypatch.setenv("N2_TIMEOUT", "60")
        assert n2.main(["n2-adapter", str(world / "in"), str(world / "out")]) == 0
    finally:
        srv.kill()
    assert "+class A { ok }" in (world / "out" / "patch.diff").read_text()
    reqs = [json.loads(l) for l in (world / "requests.jsonl").read_text().splitlines()]
    assert len(reqs) == 3 and {r["model"] for r in reqs} == {"fix-n2"} and reqs[0]["auth"] == "Bearer sk-falsa"
    sent = json.dumps([r["messages"] for r in reqs])
    assert "[ERROR] cannot find symbol" in sent and "ghp-falso" not in sent  # D3: o token do pod não chega ao modelo
