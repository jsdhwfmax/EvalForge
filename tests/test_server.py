import json
import os
import select
import signal
import subprocess
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "src"


def _environment(tmp_path, port=None):
    for module in ("uvicorn", "streamlit"):
        (tmp_path / (module + ".py")).write_text(
            "import json, os, signal, sys\n"
            "print(json.dumps({'module': %r, 'args': sys.argv[1:], 'pid': os.getpid()}), "
            "flush=True)\n"
            "if os.environ.get('EVALFORGE_TEST_WAIT_FOR_SIGNAL'):\n"
            "    signal.pause()\n" % module,
            encoding="utf-8",
        )
    env = dict(os.environ)
    env.pop("PORT", None)
    env.pop("EVALFORGE_TEST_WAIT_FOR_SIGNAL", None)
    env["PYTHONPATH"] = os.pathsep.join((str(SOURCE), str(tmp_path)))
    if port is not None:
        env["PORT"] = port
    return env


@pytest.mark.parametrize("role,port,expected", [
    ("api", None, "8000"), ("api", "", "8000"), ("api", "18080", "18080"),
    ("dashboard", None, "8501"), ("dashboard", "", "8501"),
    ("dashboard", "18501", "18501"),
])
def test_module_command_starts_selected_server_on_configured_port(tmp_path, role, port, expected):
    with subprocess.Popen(
        [sys.executable, "-m", "evalforge.server", role],
        cwd=tmp_path, env=_environment(tmp_path, port), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ) as process:
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
        started = json.loads(stdout)
        assert started["pid"] == process.pid
    if role == "api":
        assert started["module"] == "uvicorn"
        assert started["args"] == [
            "evalforge.api:app", "--host", "0.0.0.0", "--port", expected,
        ]
    else:
        assert started["module"] == "streamlit"
        assert started["args"] == [
            "run", "dashboard/app.py", "--server.address=0.0.0.0",
            "--server.port=" + expected, "--server.headless=true",
        ]


@pytest.mark.parametrize("port", ["not-a-port", "0", "-1", "65536", "8000; echo unexpected"])
def test_invalid_port_exits_before_starting_server(tmp_path, port):
    result = subprocess.run(
        [sys.executable, "-m", "evalforge.server", "api"],
        cwd=tmp_path, env=_environment(tmp_path, port), text=True,
        capture_output=True, timeout=10,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "PORT must be an integer between 1 and 65535" in result.stderr


@pytest.mark.parametrize("argument,code", [("--help", 0), ("unknown", 2)])
def test_help_and_invalid_role_do_not_start_server(tmp_path, argument, code):
    result = subprocess.run(
        [sys.executable, "-m", "evalforge.server", argument],
        cwd=tmp_path, env=_environment(tmp_path), text=True,
        capture_output=True, timeout=10,
    )
    assert result.returncode == code
    assert '"module"' not in result.stdout


@pytest.mark.skipif(os.name != "posix", reason="Container signal delivery uses POSIX semantics")
@pytest.mark.parametrize("role", ["api", "dashboard"])
def test_server_replaces_launcher_and_receives_sigterm(tmp_path, role):
    env = _environment(tmp_path, "19000")
    env["EVALFORGE_TEST_WAIT_FOR_SIGNAL"] = "1"
    process = subprocess.Popen(
        [sys.executable, "-m", "evalforge.server", role],
        cwd=tmp_path, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        assert process.stdout is not None
        ready, _, _ = select.select([process.stdout], [], [], 10)
        assert ready, "Server module did not start"
        started = json.loads(process.stdout.readline())
        assert started["pid"] == process.pid
        process.terminate()
        process.communicate(timeout=10)
        assert process.returncode == -signal.SIGTERM
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
