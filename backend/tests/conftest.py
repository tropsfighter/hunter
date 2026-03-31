"""Shared fixtures and Markdown report hook for API tests."""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.report_md import write_api_test_markdown


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "test.db"
    monkeypatch.setenv("HUNTER_DB_PATH", str(p))
    return p


@pytest.fixture
def client(db_path: Path):
    """FastAPI TestClient with temp SQLite DB and discovery background task mocked."""
    with patch("hunter.api.main._run_discovery_background"):
        from hunter.api.main import app

        with TestClient(app) as c:
            yield c


def pytest_configure(config: pytest.Config) -> None:
    config._hunter_all_results = []  # type: ignore[attr-defined]
    config._hunter_api_results = []  # type: ignore[attr-defined]
    config._hunter_session_start = None  # type: ignore[attr-defined]


def pytest_sessionstart(session: pytest.Session) -> None:
    session.config._hunter_session_start = time.perf_counter()  # type: ignore[attr-defined]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):  # noqa: ANN001
    outcome = yield
    rep = outcome.get_result()
    if rep.when != "call":
        return
    cfg = item.config
    row = {
        "nodeid": item.nodeid,
        "outcome": rep.outcome,
        "longrepr": str(rep.longrepr) if rep.failed else "",
    }
    cfg._hunter_all_results.append(row)  # type: ignore[attr-defined]
    for mark in item.iter_markers(name="endpoint"):
        if not mark.args:
            continue
        ep = str(mark.args[0])
        cfg._hunter_api_results.append({**row, "endpoint": ep})  # type: ignore[attr-defined]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if os.environ.get("HUNTER_WRITE_TEST_REPORT") != "1":
        return
    cfg = session.config
    all_results = getattr(cfg, "_hunter_all_results", [])
    api_results = getattr(cfg, "_hunter_api_results", [])
    started = getattr(cfg, "_hunter_session_start", None)
    ts = time.strftime("%Y%m%d_%H%M%S")
    report_path = Path(__file__).resolve().parent.parent / "reports" / f"api_test_report_{ts}.md"
    write_api_test_markdown(
        report_path=report_path,
        all_results=list(all_results),
        api_results=list(api_results),
        session=session,
        exitstatus=exitstatus,
        started_perf=started,
    )
