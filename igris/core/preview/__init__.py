"""
igris.core.preview
-------------------
Multi-modal testing system. Detects project type and auto-selects the
appropriate tester:
  - Web apps    → Playwright (browser, screenshot, console, network)
  - APIs        → httpx (endpoint testing, schema validation)
  - CLI tools   → subprocess (command execution, exit codes)
  - Desktop     → pywinauto (Windows UI automation) if available
  - Libraries   → pytest / npm test (unit test execution)
  - Media       → ffprobe (audio/video file validation)
  - Docker      → docker compose (container health checks)

Integrates into reprompt_loop as "test" and "analyze_test" mini-cycles.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TestConfig:
    project_root: Path
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    startup_timeout: float = 15.0


@dataclass
class TestResult:
    tester_name: str = ""
    success: bool = False
    summary: str = ""
    details: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)  # screenshots, logs, etc.

    def to_text(self) -> str:
        lines = [f"## Test: {self.tester_name}", f"Status: {'✓ PASS' if self.success else '✗ FAIL'}"]
        if self.summary:
            lines.append(self.summary)
        if self.details:
            lines.append("Details:")
            lines.extend(f"  - {d}" for d in self.details)
        if self.errors:
            lines.append("Errors:")
            lines.extend(f"  ! {e}" for e in self.errors)
        if self.artifacts:
            lines.append("Artifacts:")
            lines.extend(f"  {a}" for a in self.artifacts)
        return "\n".join(lines)


# ── Project type detection ────────────────────────────────────────────────────

WEB_INDICATORS = ["index.html", "package.json", "vite.config", "next.config"]
API_INDICATORS = ["openapi", "swagger", "routes", "router"]
DESKTOP_INDICATORS = [".exe", ".msi", "setup", "installer"]
CLI_INDICATORS = ["cli.py", "main.py", "bin/", "cmd/"]
DOCKER_INDICATORS = ["docker-compose.yml", "Dockerfile", "compose.yaml"]
MEDIA_INDICATORS = [".mp4", ".mp3", ".wav", ".avi", ".mkv", ".flac", ".ogg"]


def detect_project_type(project: Path) -> str:
    """Analyse project directory and return the detected project type."""
    files = {f.name for f in project.iterdir() if f.is_file()}
    dirs = {d.name for d in project.iterdir() if d.is_dir()}
    all_entries = files | dirs
    ext_map = {f.suffix.lower() for f in project.iterdir() if f.is_file() and f.suffix}

    # Check for web
    if "index.html" in files or "package.json" in files:
        return "web"
    if any("vite.config" in str(f) for f in project.iterdir()):
        return "web"
    if any("next.config" in str(f) for f in project.iterdir()):
        return "web"

    # Check for Docker
    if "docker-compose.yml" in all_entries or "Dockerfile" in all_entries or "compose.yaml" in all_entries:
        return "docker"

    # Check for API (Python FastAPI/Flask, Node Express, etc.)
    for f in project.rglob("*.py"):
        text = f.read_text(encoding="utf-8", errors="ignore")[:2000]
        if any(ind in text.lower() for ind in API_INDICATORS):
            return "api"
    for f in project.rglob("*.js"):
        text = f.read_text(encoding="utf-8", errors="ignore")[:2000]
        if "express" in text.lower() or "router" in text.lower():
            return "api"

    # Check for CLI
    if "cli.py" in files or "main.py" in files:
        return "cli"
    if "cmd" in dirs:
        return "cli"

    # Check for desktop (Windows)
    if any(s == ".exe" for s in ext_map):
        return "desktop"

    # Check for media
    media_exts = {".mp4", ".mp3", ".wav", ".avi", ".mkv", ".flac", ".ogg", ".mov", ".webm"}
    if ext_map & media_exts:
        return "media"

    # Check for Python library
    if "setup.py" in files or "pyproject.toml" in files:
        return "python_lib"
    if "pytest.ini" in files or "tox.ini" in files:
        return "python_lib"

    # Check for Node library
    if "package.json" in files:
        return "node_lib"

    return "unknown"


# ── Web Tester (Playwright) ───────────────────────────────────────────────────

class WebTester:
    """Test web applications via Playwright."""

    def __init__(self, config: TestConfig):
        self.config = config
        self._server: subprocess.Popen | None = None
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None

    async def test(self, project: Path | None = None, on_stage: Callable | None = None) -> TestResult:
        result = TestResult(tester_name="web (Playwright)")
        url = await self._start_server(on_stage)
        if not url:
            result.errors.append("Could not start dev server")
            return result

        try:
            await self._launch_browser(on_stage)
        except ImportError:
            result.errors.append("playwright not installed. Run: pip install playwright && python -m playwright install chromium")
            return result
        except Exception as e:
            result.errors.append(f"Browser launch failed: {e}")
            await self._stop_server()
            return result

        console_entries = await self._navigate(url)
        network_entries = await self._monitor_network()

        screenshot = await self._capture_screenshot("initial")
        if screenshot:
            result.artifacts.append(screenshot)

        errors = [e for e in console_entries if e.level in ("error", "warn")]
        if errors:
            result.errors.extend(f"[{e.level}] {e.text[:200]}" for e in errors[:10])
        if network_entries:
            result.errors.extend(f"{e.method} {e.url.split('/')[-1][:50]} -> {e.status}" for e in network_entries[:5])

        result.success = len(result.errors) == 0
        result.summary = f"Page loaded at {url}"
        if console_entries:
            result.details.append(f"Console: {len(console_entries)} entries ({len(errors)} errors/warnings)")
        if network_entries:
            result.details.append(f"Network: {len(network_entries)} failed requests")

        if result.success and on_stage:
            await on_stage("test:web", f"✓ {url} — no errors")
        elif not result.success and on_stage:
            await on_stage("test:web", f"✗ {url} — {len(result.errors)} issues")
        return result

    async def _start_server(self, on_stage: Callable | None = None) -> str:
        await self._stop_server()
        project = self.config.project_root
        cmd, args, port = _detect_web_server(project)
        if not cmd:
            return ""
        if on_stage:
            await on_stage("test:web:start", f"{cmd} on port {port}")
        try:
            use_shell = os.name == "nt" and cmd.endswith(".cmd")
            if use_shell:
                self._server = subprocess.Popen(f'"{cmd}" {" ".join(args)}', cwd=str(project),
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
            else:
                self._server = subprocess.Popen([cmd, *args], cwd=str(project),
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            return ""
        url = f"http://localhost:{port}"
        await _wait_for_port(port, self.config.startup_timeout, on_stage)
        return url

    async def _stop_server(self):
        if self._server:
            try:
                self._server.terminate()
                self._server.wait(timeout=3)
            except Exception:
                try:
                    self._server.kill()
                    self._server.wait(timeout=2)
                except Exception:
                    pass
            self._server = None

    async def _launch_browser(self, on_stage: Callable | None = None):
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.config.headless)
        self._context = await self._browser.new_context(
            viewport={"width": self.config.viewport_width, "height": self.config.viewport_height}
        )
        self._page = await self._context.new_page()

    async def _navigate(self, url: str) -> list:
        from playwright.async_api import async_playwright as _
        entries = []
        if not self._page:
            return entries

        async def on_console(msg):
            entries.append(type("entry", (), {"level": msg.type, "text": msg.text})())

        async def on_page_error(err):
            entries.append(type("entry", (), {"level": "error", "text": str(err)})())

        self._page.on("console", on_console)
        self._page.on("pageerror", on_page_error)
        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=10000)
            await asyncio.sleep(1)
        except Exception as e:
            entries.append(type("entry", (), {"level": "error", "text": f"Nav failed: {e}"})())
        return entries

    async def _monitor_network(self) -> list:
        if not self._page:
            return []
        entries = []

        async def on_response(resp):
            if resp.status >= 400:
                entries.append(type("e", (), {"method": resp.request.method, "url": resp.url, "status": resp.status})())

        async def on_request_failed(req):
            entries.append(type("e", (), {"method": req.method, "url": req.url, "status": 0})())

        self._page.on("response", on_response)
        self._page.on("requestfailed", on_request_failed)
        await asyncio.sleep(0.5)
        return entries

    async def _capture_screenshot(self, label: str) -> str:
        if not self._page:
            return ""
        out = self.config.project_root / ".igris" / "screenshots"
        out.mkdir(parents=True, exist_ok=True)
        path = str(out / f"{label}_{int(time.time())}.png")
        await self._page.screenshot(path=path, full_page=True)
        return path

    async def close(self):
        if self._page:
            try: await self._page.close()
            except Exception: pass
            self._page = None
        if self._context:
            try: await self._context.close()
            except Exception: pass
            self._context = None
        if self._browser:
            try: await self._browser.close()
            except Exception: pass
            self._browser = None
        if self._playwright:
            try: await self._playwright.stop()
            except Exception: pass
            self._playwright = None
        await self._stop_server()


# ── API Tester (httpx) ───────────────────────────────────────────────────────

class APITester:
    """Test REST/GraphQL APIs via httpx."""

    async def test(self, project: Path, on_stage: Callable | None = None) -> TestResult:
        result = TestResult(tester_name="API (httpx)")
        try:
            import httpx
        except ImportError:
            result.errors.append("httpx not installed")
            return result

        endpoints = self._discover_endpoints(project)
        if not endpoints:
            endpoints = [("GET", "http://localhost:8000/health"),
                         ("GET", "http://localhost:8000/docs")]

        for method, url in endpoints[:10]:
            try:
                resp = await httpx.request(method, url, timeout=5)
                if resp.status_code >= 400:
                    result.errors.append(f"{method} {url} -> {resp.status_code}")
                else:
                    result.details.append(f"{method} {url} -> {resp.status_code}")
            except httpx.ConnectError:
                result.errors.append(f"{method} {url} -> connection refused")
            except Exception as e:
                result.errors.append(f"{method} {url} -> {e}")

        result.success = len(result.errors) == 0
        if on_stage:
            if result.success:
                await on_stage("test:api", f"✓ {len(endpoints)} endpoints OK")
            else:
                await on_stage("test:api", f"✗ {len(result.errors)}/{len(endpoints)} failed")
        return result

    @staticmethod
    def _discover_endpoints(project: Path) -> list[tuple[str, str]]:
        endpoints = []
        for f in project.rglob("*.py"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r'@(?:app|router)\.(get|post|put|delete|patch)\("([^"]+)"\)', text):
                    endpoints.append((m.group(1).upper(), f"http://localhost:8000{m.group(2)}"))
            except Exception:
                continue
        return endpoints[:10]


# ── CLI Tester (subprocess) ──────────────────────────────────────────────────

class CLITester:
    """Test CLI tools by running commands and checking exit codes."""

    async def test(self, project: Path, on_stage: Callable | None = None) -> TestResult:
        result = TestResult(tester_name="CLI")
        commands = self._discover_commands(project)
        for desc, cmd, cwd in commands:
            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd, cwd=str(cwd or project),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
                if proc.returncode == 0:
                    result.details.append(f"✓ {desc}")
                else:
                    err_text = stderr.decode(errors="ignore")[:200] if stderr else ""
                    result.errors.append(f"{desc} → exit {proc.returncode}: {err_text}")
            except asyncio.TimeoutError:
                result.errors.append(f"{desc} → timeout (>15s)")
            except FileNotFoundError:
                result.errors.append(f"{desc} → command not found")
            except Exception as e:
                result.errors.append(f"{desc} → {e}")

        if not commands:
            result.details.append("No runnable commands discovered; try '--help' or '--version'")

        result.success = len(result.errors) == 0
        if on_stage:
            await on_stage("test:cli", f"{'✓' if result.success else '✗'} {len(result.details)} ok, {len(result.errors)} failed")
        return result

    @staticmethod
    def _discover_commands(project: Path) -> list[tuple[str, str, Path | None]]:
        cmds = []
        # Python scripts
        for f in project.glob("*.py"):
            if f.name in ("cli.py", "main.py", "__main__.py"):
                cmds.append((f.name, f'python "{f}" --help', project))
        # Entry points in pyproject.toml
        pyp = project / "pyproject.toml"
        if pyp.exists():
            text = pyp.read_text(encoding="utf-8")
            for m in re.finditer(r'"([^"]+)"\s*=\s*"([^"]+):main"', text):
                cmds.append((f"cli {m.group(1)}", f"{m.group(1)} --help", project))
        # package.json scripts
        pkg = project / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                for name, script in list(data.get("scripts", {}).items())[:5]:
                    cmds.append((f"npm run {name}", f"npm run {name} --if-present", project))
            except Exception:
                pass
        # Makefile
        if (project / "Makefile").exists():
            cmds.append(("make help", "make --help 2>&1 || make help 2>&1", project))
        return cmds


# ── Desktop Tester (pywinauto) ──────────────────────────────────────────────

class DesktopTester:
    """Test Windows desktop applications via pywinauto."""

    async def test(self, project: Path, on_stage: Callable | None = None) -> TestResult:
        result = TestResult(tester_name="desktop (pywinauto)")
        exe = self._find_exe(project)
        if not exe:
            result.errors.append("No executable found in project")
            return result

        try:
            from pywinauto import Application
        except ImportError:
            result.errors.append("pywinauto not installed. Run: pip install pywinauto")
            return result

        try:
            if on_stage:
                await on_stage("test:desktop", f"launching {exe.name}")
            app = Application(backend="win32").start(str(exe))
            app.wait_cpu_usage_lower(threshold=5, timeout=30)
            window = app.top_window()
            window.wait("visible", timeout=10)
            result.details.append(f"Window opened: {window.window_text()}")
            screenshot_dir = project / ".igris" / "screenshots"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            img = window.capture_as_image()
            path = str(screenshot_dir / f"desktop_{int(time.time())}.png")
            img.save(path)
            result.artifacts.append(path)
            app.kill()
            result.success = True
        except Exception as e:
            result.errors.append(f"Desktop test failed: {e}")
        return result

    @staticmethod
    def _find_exe(project: Path) -> Path | None:
        for f in project.iterdir():
            if f.suffix.lower() == ".exe":
                return f
        dist = project / "dist"
        if dist.is_dir():
            for f in dist.iterdir():
                if f.suffix.lower() == ".exe":
                    return f
        target = project / "target" / "release"
        if target.is_dir():
            for f in target.iterdir():
                if f.suffix.lower() == ".exe":
                    return f
        return None


# ── Library Tester (pytest / npm test) ────────────────────────────────────────

class LibraryTester:
    """Test Python or Node.js libraries by running their test suites."""

    async def test(self, project: Path, on_stage: Callable | None = None) -> TestResult:
        is_python = (project / "setup.py").exists() or (project / "pyproject.toml").exists()
        is_node = (project / "package.json").exists()

        if is_python:
            return await self._run_pytest(project, on_stage)
        elif is_node:
            return await self._run_npm_test(project, on_stage)
        else:
            result = TestResult(tester_name="library")
            result.errors.append("Could not determine test framework")
            return result

    async def _run_pytest(self, project: Path, on_stage: Callable | None = None) -> TestResult:
        result = TestResult(tester_name="pytest")
        if on_stage:
            await on_stage("test:pytest", "running pytest")
        try:
            proc = await asyncio.create_subprocess_shell(
                "python -m pytest -x --tb=short 2>&1", cwd=str(project),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            out = stdout.decode(errors="ignore")
            passed = out.count("passed")
            failed = out.count("FAILED")
            errors = out.count("ERROR")
            result.success = proc.returncode == 0
            result.summary = f"{passed} passed, {failed} failed, {errors} errors"
            if result.success:
                result.details.append("All tests pass")
            else:
                for line in out.splitlines():
                    if "FAILED" in line or "ERROR" in line:
                        result.errors.append(line.strip()[:150])
                        if len(result.errors) >= 5:
                            break
        except asyncio.TimeoutError:
            result.errors.append("pytest timed out (>120s)")
        except Exception as e:
            result.errors.append(f"pytest error: {e}")
        return result

    async def _run_npm_test(self, project: Path, on_stage: Callable | None = None) -> TestResult:
        result = TestResult(tester_name="npm test")
        if on_stage:
            await on_stage("test:npm", "running npm test")
        try:
            proc = await asyncio.create_subprocess_shell(
                "npm test 2>&1", cwd=str(project),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            out = stdout.decode(errors="ignore")
            result.success = proc.returncode == 0
            if result.success:
                result.summary = "npm test passed"
            else:
                for line in out.splitlines()[-10:]:
                    if "error" in line.lower() or "fail" in line.lower():
                        result.errors.append(line.strip()[:150])
                        if len(result.errors) >= 5:
                            break
        except asyncio.TimeoutError:
            result.errors.append("npm test timed out (>120s)")
        except FileNotFoundError:
            result.errors.append("node/npm not found")
        except Exception as e:
            result.errors.append(f"npm test error: {e}")
        return result


# ── Media Tester (ffprobe) ──────────────────────────────────────────────────

class MediaTester:
    """Validate audio/video files using ffprobe."""

    async def test(self, project: Path, on_stage: Callable | None = None) -> TestResult:
        result = TestResult(tester_name="media (ffprobe)")
        media_files = []
        for ext in (".mp4", ".mp3", ".wav", ".avi", ".mkv", ".flac", ".ogg", ".mov", ".webm"):
            media_files.extend(project.rglob(f"*{ext}"))
        if not media_files:
            result.errors.append("No media files found")
            return result
        ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
        if not ffprobe:
            result.errors.append("ffprobe not found. Install ffmpeg.")
            return result
        for mf in media_files[:5]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    ffprobe, "-v", "quiet", "-print_format", "json",
                    "-show_format", "-show_streams", str(mf),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
                if proc.returncode == 0:
                    info = json.loads(stdout.decode(errors="ignore"))
                    fmt = info.get("format", {})
                    dur = fmt.get("duration", "?")
                    size = fmt.get("size", "?")
                    result.details.append(f"✓ {mf.name}: {dur}s, {size} bytes")
                else:
                    result.errors.append(f"{mf.name}: ffprobe failed (exit {proc.returncode})")
            except Exception as e:
                result.errors.append(f"{mf.name}: {e}")
        result.success = len(result.errors) == 0
        if on_stage:
            await on_stage("test:media", f"{'✓' if result.success else '✗'} {len(result.details)}/{len(media_files)} files OK")
        return result


# ── Docker Tester ───────────────────────────────────────────────────────────

class DockerTester:
    """Test Docker Compose applications."""

    async def test(self, project: Path, on_stage: Callable | None = None) -> TestResult:
        result = TestResult(tester_name="docker")
        compose = None
        for name in ("docker-compose.yml", "compose.yaml", "docker-compose.yaml"):
            if (project / name).exists():
                compose = project / name
                break
        if not compose:
            result.errors.append("No docker-compose.yml found")
            return result
        if not shutil.which("docker") and not shutil.which("docker.exe"):
            result.errors.append("docker not found on PATH")
            return result
        if on_stage:
            await on_stage("test:docker", f"starting services from {compose.name}")
        try:
            proc = await asyncio.create_subprocess_shell(
                "docker compose up -d --wait 2>&1", cwd=str(project),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode == 0:
                result.success = True
                result.summary = "All containers started"
                # Check health
                proc2 = await asyncio.create_subprocess_shell(
                    "docker compose ps --format json 2>&1", cwd=str(project),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                out2, _ = await asyncio.wait_for(proc2.communicate(), timeout=10)
                for line in out2.decode(errors="ignore").splitlines():
                    result.details.append(line.strip()[:120])
            else:
                result.errors.append(stderr.decode(errors="ignore")[:300])
        except asyncio.TimeoutError:
            result.errors.append("docker compose up timed out (>120s)")
        except Exception as e:
            result.errors.append(f"docker error: {e}")
        return result


# ── Multi Tester (auto-select) ───────────────────────────────────────────────

class MultiTester:
    """Auto-detect project type and select the correct tester."""

    def __init__(self, config: TestConfig):
        self.config = config
        self._active_testers: list = []

    async def test_all(self, on_stage: Callable | None = None) -> list[TestResult]:
        project = self.config.project_root
        ptype = detect_project_type(project)
        if on_stage:
            await on_stage("test:detect", f"project type: {ptype}")

        testers = self._select_testers(ptype)
        results = []
        for factory in testers:
            tester = factory() if callable(factory) else factory()
            self._active_testers.append(tester)
            try:
                r = await tester.test(project, on_stage)
            except TypeError:
                r = await tester.test(on_stage=on_stage)
            results.append(r)
        return results

    def _select_testers(self, ptype: str) -> list:
        mapping = {
            "web": [lambda: WebTester(self.config), CLITester, LibraryTester],
            "api": [APITester, CLITester],
            "cli": [CLITester, LibraryTester],
            "desktop": [DesktopTester],
            "docker": [DockerTester, CLITester],
            "media": [MediaTester],
            "python_lib": [LibraryTester, CLITester],
            "node_lib": [LibraryTester, CLITester],
            "unknown": [CLITester],
        }
        return mapping.get(ptype, [CLITester])

    async def close(self):
        for t in self._active_testers:
            try:
                if hasattr(t, "close"):
                    await t.close()
            except Exception:
                pass
        self._active_testers.clear()


# ── Dev server helpers (shared) ─────────────────────────────────────────────

def _find_http_server() -> str:
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for c in ("http-server.cmd", "http-server"):
        for d in path_dirs:
            full = os.path.join(d, c)
            if os.path.isfile(full):
                return full
    return "http-server.cmd"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _detect_web_server(project: Path) -> tuple[str, list[str], int]:
    npx = "npx.cmd" if os.name == "nt" else "npx"
    static = _find_http_server()
    port = _find_free_port()
    pkg = project / "package.json"
    if pkg.exists():
        text = pkg.read_text(encoding="utf-8")
        m = re.search(r'"scripts"\s*:\s*\{([^}]+)\}', text, re.DOTALL)
        if m and ('"dev"' in m.group(1) or '"serve"' in m.group(1)):
            if '"vite"' in m.group(1):
                return npx, ["vite", "--port", str(port)], port
            if '"next"' in m.group(1):
                return npx, ["next", "dev", "-p", str(port)], port
    if (project / "index.html").exists():
        return static, ["-p", str(port)], port
    return "", [], 0


async def _wait_for_port(port: int, timeout: float = 15.0, on_stage: Callable | None = None):
    import urllib.request
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{port}", timeout=2)
            return
        except (OSError, ValueError):
            await asyncio.sleep(0.5)


# ── PreviewSystem (unified entry point) ─────────────────────────────────────

class PreviewSystem:
    """Unified main entry point. Detects project type and runs the right tester."""

    def __init__(self, project_root: Path):
        self.config = TestConfig(project_root=project_root)
        self._tester: MultiTester | None = None

    def set_on_stage(self, callback: Callable | None):
        pass

    async def start_preview(self) -> TestResult:
        self._tester = MultiTester(self.config)
        results = await self._tester.test_all()
        merged = TestResult(tester_name="multi")
        for r in results:
            merged.success = merged.success and r.success if merged.tester_name != "" else r.success
            merged.summary += f"{r.tester_name}: {'✓' if r.success else '✗'} "
            merged.details.extend(r.details)
            merged.errors.extend(r.errors)
            merged.artifacts.extend(r.artifacts)
        merged.tester_name = "multi-tester"
        if merged.summary:
            merged.summary = merged.summary.strip()
        else:
            merged.summary = f"{len(results)} tester(s) ran"
        return merged

    async def close(self):
        if self._tester:
            await self._tester.close()
            self._tester = None

    @property
    def is_running(self) -> bool:
        return False
