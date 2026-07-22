"""
Tests for igris.core.preview — multi-modal testing system.
Tests web (Playwright), CLI, API, media, and project detection.
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.core.preview import (
    TestConfig, TestResult,
    detect_project_type,
    WebTester, CLITester, APITester, DesktopTester,
    LibraryTester, MediaTester, DockerTester,
    MultiTester, PreviewSystem,
)

# ── project detection ─────────────────────────────────────────────────────────

def test_detect_web_from_index_html(tmp_path: Path):
    (tmp_path / "index.html").write_text("<h1>hi</h1>")
    assert detect_project_type(tmp_path) == "web"


def test_detect_web_from_vite(tmp_path: Path):
    (tmp_path / "vite.config.ts").write_text("")
    assert detect_project_type(tmp_path) == "web"


def test_detect_api_from_fastapi(tmp_path: Path):
    (tmp_path / "main.py").write_text('from fastapi import APIRouter; router = APIRouter()')
    assert detect_project_type(tmp_path) == "api"


def test_detect_cli(tmp_path: Path):
    (tmp_path / "cli.py").write_text("")
    assert detect_project_type(tmp_path) == "cli"


def test_detect_docker(tmp_path: Path):
    (tmp_path / "docker-compose.yml").write_text("")
    assert detect_project_type(tmp_path) == "docker"


def test_detect_media(tmp_path: Path):
    (tmp_path / "video.mp4").write_text("fake mp4")
    assert detect_project_type(tmp_path) == "media"


def test_detect_python_lib(tmp_path: Path):
    (tmp_path / "setup.py").write_text("")
    assert detect_project_type(tmp_path) == "python_lib"


def test_detect_unknown(tmp_path: Path):
    (tmp_path / "random.txt").write_text("")
    assert detect_project_type(tmp_path) == "unknown"


# ── CLI Tester ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cli_tester_python_help(tmp_path: Path):
    (tmp_path / "cli.py").write_text(
        '#!/usr/bin/env python\nif __name__ == "__main__":\n    print("OK")\n'
    )
    tester = CLITester()
    result = await tester.test(tmp_path)
    assert result.tester_name == "CLI"
    assert isinstance(result.success, bool)


@pytest.mark.asyncio
async def test_cli_tester_empty_project(tmp_path: Path):
    tester = CLITester()
    result = await tester.test(tmp_path)
    assert result.tester_name == "CLI"
    assert "No runnable commands" in " ".join(result.details)


@pytest.mark.asyncio
async def test_cli_tester_with_pyproject(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project.scripts]\nigris = "igris.cli:main"\n'
    )
    (tmp_path / "igris").mkdir()
    (tmp_path / "igris" / "cli.py").write_text("def main(): pass\n")
    tester = CLITester()
    result = await tester.test(tmp_path)
    assert result.tester_name == "CLI"


# ── API Tester ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_tester_discover_endpoints(tmp_path: Path):
    (tmp_path / "routes.py").write_text(
        '@app.get("/users")\ndef list_users(): pass\n'
        '@router.post("/items")\ndef create(): pass\n'
    )
    tester = APITester()
    result = await tester.test(tmp_path)
    # No server running, but endpoint discovery should work
    assert result.tester_name == "API (httpx)"
    assert not result.success  # connection refused


@pytest.mark.asyncio
async def test_api_tester_no_endpoints(tmp_path: Path):
    (tmp_path / "dummy.py").write_text("x = 1\n")
    tester = APITester()
    result = await tester.test(tmp_path)
    assert result.tester_name == "API (httpx)"


# ── Library Tester ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_library_tester_python(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\nversion='0.1'\n")
    (tmp_path / "test_sample.py").write_text("def test_ok(): assert True\n")
    tester = LibraryTester()
    result = await tester.test(tmp_path)
    assert result.tester_name == "pytest"


@pytest.mark.asyncio
async def test_library_tester_node(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts":{"test":"echo ok"}}\n')
    tester = LibraryTester()
    result = await tester.test(tmp_path)
    assert result.tester_name in ("npm test", "pytest")


# ── Media Tester ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_media_tester_no_files(tmp_path: Path):
    tester = MediaTester()
    result = await tester.test(tmp_path)
    assert not result.success
    assert any("No media files" in e for e in result.errors)


# ── Desktop Tester ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_desktop_tester_no_exe(tmp_path: Path):
    tester = DesktopTester()
    result = await tester.test(tmp_path)
    assert not result.success
    assert any("No executable" in e for e in result.errors)


# ── Docker Tester ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_docker_tester_no_compose(tmp_path: Path):
    tester = DockerTester()
    result = await tester.test(tmp_path)
    assert not result.success
    assert any("No docker-compose" in e for e in result.errors)


# ── MultiTester ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_multi_tester_detects_and_runs(tmp_path: Path):
    (tmp_path / "index.html").write_text("<h1>test</h1>")
    (tmp_path / "cli.py").write_text("print('ok')\n")
    config = TestConfig(project_root=tmp_path)
    mt = MultiTester(config)
    results = await mt.test_all()
    assert len(results) >= 1
    for r in results:
        assert isinstance(r, TestResult)
        assert r.tester_name
    await mt.close()


@pytest.mark.asyncio
async def test_multi_tester_unknown(tmp_path: Path):
    config = TestConfig(project_root=tmp_path)
    mt = MultiTester(config)
    results = await mt.test_all()
    assert len(results) >= 1
    await mt.close()


# ── Web Tester (requires playwright + http-server) ───────────────────────────

@pytest.mark.asyncio
async def test_web_tester_static_site():
    pytest.importorskip("playwright")
    site = Path(tempfile.mkdtemp(prefix="igris_test_web_"))
    (site / "index.html").write_text("<!DOCTYPE html><html><body><h1>Web Test</h1></body></html>")
    config = TestConfig(project_root=site)
    tester = WebTester(config)
    try:
        result = await tester.test(site)
        assert result.tester_name == "web (Playwright)"
        if not result.success:
            # May fail if http-server not installed, that's OK
            assert any("playwright" in e.lower() or "server" in e.lower() or "launch" in e.lower() for e in result.errors)
    finally:
        await tester.close()
        await asyncio.sleep(0.3)


@pytest.mark.asyncio
async def test_preview_system_detects_web():
    site = Path(tempfile.mkdtemp(prefix="igris_test_ps_"))
    (site / "index.html").write_text("<h1>Preview System</h1>")
    ps = PreviewSystem(site)
    try:
        result = await ps.start_preview()
        assert result.tester_name == "multi-tester"
    finally:
        await ps.close()
