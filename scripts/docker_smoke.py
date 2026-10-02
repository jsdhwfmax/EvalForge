"""Exercise the built image against disposable PostgreSQL and live HTTP services."""

import os
import secrets
import subprocess
import time
import uuid

IMAGE = "evalforge:ci"
PREFIX = "evalforge-smoke-" + uuid.uuid4().hex[:12]
PASSWORD, ACCESS_KEY = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
ENV = {
    **os.environ,
    "POSTGRES_PASSWORD": PASSWORD,
    "EVALFORGE_ACCESS_KEY": ACCESS_KEY,
    "EVALFORGE_ENVIRONMENT": "production",
    "EVALFORGE_DATABASE_URL": (
        "postgresql+psycopg://evalforge:%s@postgres:5432/evalforge" % PASSWORD
    ),
    "EVALFORGE_API_BASE_URL": "http://api:8000",
}
CONTAINERS = []


def docker(*args, check=True, source=None):
    result = subprocess.run(
        ["docker", *args], input=source, text=True, capture_output=True, env=ENV, timeout=180
    )
    if check and result.returncode:
        output = (result.stdout + result.stderr).replace(PASSWORD, "[redacted]")
        raise RuntimeError(output.replace(ACCESS_KEY, "[redacted]"))
    return result


def start(name, *args):
    container = PREFIX + "-" + name
    CONTAINERS.append(container)
    docker("run", "--detach", "--name", container, "--network", PREFIX, *args)
    return container


def wait_for(container, *command):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if docker("exec", container, *command, check=False).returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("Service did not become ready: " + container)


def wait_http(container, url):
    wait_for(container, "python", "-c", "import urllib.request; "
             "urllib.request.urlopen(%r, timeout=3).close()" % url)


def main():
    docker("image", "inspect", IMAGE)  # Fail early if the build was not loaded locally.
    docker("network", "create", PREFIX)
    try:
        postgres = start(
            "postgres", "--network-alias", "postgres", "--tmpfs", "/var/lib/postgresql/data",
            "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_USER=evalforge",
            "--env", "POSTGRES_DB=evalforge", "pgvector/pgvector:pg16",
        )
        wait_for(postgres, "pg_isready", "-h", "127.0.0.1", "-U", "evalforge", "-d", "evalforge")
        api = start(
            "api", "--network-alias", "api", "--env", "EVALFORGE_DATABASE_URL",
            "--env", "EVALFORGE_ENVIRONMENT", "--env", "EVALFORGE_ACCESS_KEY", IMAGE,
        )
        wait_http(api, "http://127.0.0.1:8000/health")
        docker("exec", api, "python", "-c", "import os; assert os.getuid() != 0; "
               "assert os.access('/data', os.W_OK); "
               "assert os.access('/app/dashboard/app.py', os.R_OK)")
        docker("exec", api, "evalforge", "seed")
        docker("exec", api, "evalforge", "check", "hybrid_top3", "--report-dir", "/tmp/gate")
        vector = docker("exec", postgres, "psql", "-U", "evalforge", "-d", "evalforge", "-tAc",
                        "SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        assert vector.stdout.strip(), "The native pgvector extension was not created"
        print("Non-root image, PostgreSQL/pgvector seed, and offline quality gate passed.")
        docker("restart", api)
        wait_http(api, "http://127.0.0.1:8000/health")
        docker("exec", "-i", api, "python", "-", source='''
import os
import httpx
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10) as client:
    assert client.get("/health").json()["database"] == "postgresql"
    assert client.get("/api/v1/documents").status_code == 401
    bad = client.get("/api/v1/documents", headers={"Authorization": "Bearer wrong"})
    assert bad.status_code == 401
    client.headers["Authorization"] = "Bearer " + os.environ["EVALFORGE_ACCESS_KEY"]
    for path in ["documents", "test-cases", "configs", "experiments"]:
        response = client.get("/api/v1/" + path)
        assert response.status_code == 200 and response.json(), path
    assert client.get("/api/v1/experiments").json()[0]["status"] == "completed"
''')
        print("Live API auth and PostgreSQL data persistence after API restart passed.")
        dashboard = start(
            "dashboard", "--env", "EVALFORGE_ENVIRONMENT", "--env", "EVALFORGE_ACCESS_KEY",
            "--env", "EVALFORGE_API_BASE_URL", IMAGE, "streamlit", "run", "dashboard/app.py",
            "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true",
        )
        wait_http(dashboard, "http://127.0.0.1:8501/_stcore/health")
        docker("exec", "-i", dashboard, "python", "-", source='''
import os
from streamlit.testing.v1 import AppTest
app = AppTest.from_file("/app/dashboard/app.py", default_timeout=30).run()
assert not app.exception and not app.tabs
assert app.title[0].value == "Sign in to EvalForge"
app.text_input(key="_access_key_input").set_value(os.environ["EVALFORGE_ACCESS_KEY"])
next(button for button in app.button if button.label == "Sign in").click().run()
assert not app.exception and not app.error and len(app.tabs) == 5
assert any(item.value == "API online · postgresql" for item in app.success)
assert "_access_key_input" not in app.session_state
''')
        print("Dashboard health and authenticated UI against the live API passed.")
    except Exception:
        for container in CONTAINERS:
            output = docker("logs", "--tail", "60", container, check=False)
            log = (output.stdout + output.stderr).replace(PASSWORD, "[redacted]")
            print(container + ":\n" + log.replace(ACCESS_KEY, "[redacted]"))
        raise
    finally:
        for container in reversed(CONTAINERS):
            docker("rm", "--force", "--volumes", container, check=False)
        docker("network", "rm", PREFIX, check=False)


if __name__ == "__main__":
    main()
