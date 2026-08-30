import os
import shutil
import tempfile
from pathlib import Path

import pytest

TEST_DIR = Path(tempfile.mkdtemp(prefix="evalforge-test-"))
TEST_DB = TEST_DIR / "evalforge_test.db"
os.environ["EVALFORGE_DATABASE_URL"] = "sqlite:///%s" % TEST_DB

from evalforge.database import Base, engine, init_db  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    engine.dispose()
    shutil.rmtree(TEST_DIR, ignore_errors=True)


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from evalforge.api import app

    with TestClient(app) as test_client:
        yield test_client
