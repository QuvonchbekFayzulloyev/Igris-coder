"""§2 Project Discovery — project turini, tuzilishini aniqlash."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProjectInfo:
    """Project haqida to'liq ma'lumot."""
    root: str = ""
    project_type: str = "unknown"  # python, node, rust, go, java, etc.
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    package_manager: str = ""
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    env_files: list[str] = field(default_factory=list)
    dependency_files: list[str] = field(default_factory=list)
    test_framework: str = ""
    build_command: str = ""
    run_command: str = ""
    test_command: str = ""
    scripts: dict[str, str] = field(default_factory=dict)
    is_git: bool = False
    os_type: str = "unknown"
    # Constraints
    constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "project_type": self.project_type,
            "languages": self.languages,
            "frameworks": self.frameworks,
            "package_manager": self.package_manager,
            "entry_points": self.entry_points,
            "config_files": self.config_files,
            "dependency_files": self.dependency_files,
            "test_framework": self.test_framework,
            "build_command": self.build_command,
            "run_command": self.run_command,
            "test_command": self.test_command,
            "is_git": self.is_git,
            "os_type": self.os_type,
        }


# File patterns for detection
PYTHON_FILES = {".py", ".pyi"}
JS_FILES = {".js", ".jsx", ".mjs", ".cjs"}
TS_FILES = {".ts", ".tsx"}
RUST_FILES = {".rs"}
GO_FILES = {".go"}
JAVA_FILES = {".java"}
CSHARP_FILES = {".cs"}
CPP_FILES = {".cpp", ".c", ".h", ".hpp"}
SWIFT_FILES = {".swift"}
RUBY_FILES = {".rb"}
PHP_FILES = {".php"}

CONFIG_PATTERNS = {
    "python": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
               "Pipfile", "poetry.lock", "conda.yaml", "environment.yml"],
    "node": ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
             "tsconfig.json", ".babelrc", "webpack.config.js", "vite.config.ts"],
    "rust": ["Cargo.toml", "Cargo.lock"],
    "go": ["go.mod", "go.sum"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"],
    "csharp": ["*.csproj", "*.sln", "Directory.Build.props"],
    "cpp": ["CMakeLists.txt", "Makefile", "meson.build", "conanfile.txt"],
    "ruby": ["Gemfile", "Gemfile.lock", "*.gemspec"],
    "php": ["composer.json", "composer.lock"],
}

TEST_FRAMEWORKS = {
    "python": ["pytest", "unittest", "nose2"],
    "node": ["jest", "mocha", "vitest", "jasmine"],
    "rust": ["cargo test"],
    "go": ["go test"],
    "java": ["junit", "testng"],
    "csharp": ["nunit", "xunit", "mstest"],
}


class ProjectDiscovery:
    """Project aniqlash va tahlil qilish."""

    def __init__(self, root: str = ""):
        self.root = root or os.getcwd()

    def discover(self) -> ProjectInfo:
        """To'liq project discovery."""
        info = ProjectInfo(root=self.root)
        info.os_type = self._detect_os()
        info.is_git = self._is_git_repo()
        info.languages = self._detect_languages()
        info.project_type = self._detect_project_type(info.languages)
        info.frameworks = self._detect_frameworks()
        info.package_manager = self._detect_package_manager()
        info.config_files = self._find_config_files()
        info.env_files = self._find_env_files()
        info.dependency_files = self._find_dependency_files()
        info.entry_points = self._find_entry_points()
        info.test_framework = self._detect_test_framework()
        info.build_command = self._detect_build_command()
        info.run_command = self._detect_run_command()
        info.test_command = self._detect_test_command()
        info.scripts = self._find_scripts()
        info.constraints = self._detect_constraints()
        return info

    def _detect_os(self) -> str:
        import sys
        if sys.platform == "win32":
            return "windows"
        elif sys.platform == "darwin":
            return "macos"
        return "linux"

    def _is_git_repo(self) -> bool:
        return os.path.isdir(os.path.join(self.root, ".git"))

    def _detect_languages(self) -> list[str]:
        """Fayl kengaymalari bo'yicha tillarni aniqlash."""
        extensions = set()
        for _, _, files in os.walk(self.root):
            for f in files:
                _, ext = os.path.splitext(f)
                if ext:
                    extensions.add(ext.lower())

        languages = []
        if extensions & PYTHON_FILES:
            languages.append("python")
        if extensions & (JS_FILES | TS_FILES):
            languages.append("javascript" if extensions & JS_FILES else "typescript")
        if extensions & TS_FILES:
            languages.append("typescript")
        if extensions & RUST_FILES:
            languages.append("rust")
        if extensions & GO_FILES:
            languages.append("go")
        if extensions & JAVA_FILES:
            languages.append("java")
        if extensions & CSHARP_FILES:
            languages.append("csharp")
        if extensions & CPP_FILES:
            languages.append("cpp")
        if extensions & SWIFT_FILES:
            languages.append("swift")
        if extensions & RUBY_FILES:
            languages.append("ruby")
        if extensions & PHP_FILES:
            languages.append("php")
        return languages or ["unknown"]

    def _detect_project_type(self, languages: list[str]) -> str:
        if not languages or languages == ["unknown"]:
            return "unknown"
        return languages[0]

    def _detect_frameworks(self) -> list[str]:
        frameworks = []
        # Python frameworks
        if os.path.exists(os.path.join(self.root, "manage.py")):
            frameworks.append("django")
        if os.path.exists(os.path.join(self.root, "app.py")) or \
           os.path.exists(os.path.join(self.root, "wsgi.py")):
            frameworks.append("flask")
        # Node frameworks
        pkg_json = os.path.join(self.root, "package.json")
        if os.path.exists(pkg_json):
            try:
                import json
                with open(pkg_json) as f:
                    pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "react" in deps:
                    frameworks.append("react")
                if "vue" in deps:
                    frameworks.append("vue")
                if "angular" in deps:
                    frameworks.append("angular")
                if "next" in deps:
                    frameworks.append("nextjs")
                if "express" in deps:
                    frameworks.append("express")
            except Exception:
                pass
        return frameworks

    def _detect_package_manager(self) -> str:
        if os.path.exists(os.path.join(self.root, "poetry.lock")):
            return "poetry"
        if os.path.exists(os.path.join(self.root, "Pipfile.lock")):
            return "pipenv"
        if os.path.exists(os.path.join(self.root, "requirements.txt")):
            return "pip"
        if os.path.exists(os.path.join(self.root, "yarn.lock")):
            return "yarn"
        if os.path.exists(os.path.join(self.root, "pnpm-lock.yaml")):
            return "pnpm"
        if os.path.exists(os.path.join(self.root, "package-lock.json")):
            return "npm"
        if os.path.exists(os.path.join(self.root, "Cargo.toml")):
            return "cargo"
        if os.path.exists(os.path.join(self.root, "go.mod")):
            return "go"
        if os.path.exists(os.path.join(self.root, "Gemfile.lock")):
            return "bundler"
        if os.path.exists(os.path.join(self.root, "composer.lock")):
            return "composer"
        return ""

    def _find_config_files(self) -> list[str]:
        configs = []
        for _, _, files in os.walk(self.root):
            for f in files:
                if f.endswith((".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf")):
                    configs.append(f)
        return configs[:20]

    def _find_env_files(self) -> list[str]:
        envs = []
        for f in os.listdir(self.root):
            if f.startswith(".env") or f == "env.yaml":
                envs.append(f)
        return envs

    def _find_dependency_files(self) -> list[str]:
        deps = []
        dep_files = [
            "requirements.txt", "Pipfile", "pyproject.toml",
            "package.json", "Cargo.toml", "go.mod", "pom.xml",
            "build.gradle", "Gemfile", "composer.json",
        ]
        for f in dep_files:
            if os.path.exists(os.path.join(self.root, f)):
                deps.append(f)
        return deps

    def _find_entry_points(self) -> list[str]:
        entries = []
        # Python
        for name in ["main.py", "app.py", "run.py", "manage.py", "__main__.py"]:
            if os.path.exists(os.path.join(self.root, name)):
                entries.append(name)
        # Node
        pkg_json = os.path.join(self.root, "package.json")
        if os.path.exists(pkg_json):
            try:
                import json
                with open(pkg_json) as f:
                    pkg = json.load(f)
                main = pkg.get("main", "")
                if main:
                    entries.append(main)
            except Exception:
                pass
        return entries

    def _detect_test_framework(self) -> str:
        # Python
        if os.path.exists(os.path.join(self.root, "pytest.ini")) or \
           os.path.exists(os.path.join(self.root, "setup.cfg")):
            return "pytest"
        # Node
        pkg_json = os.path.join(self.root, "package.json")
        if os.path.exists(pkg_json):
            try:
                import json
                with open(pkg_json) as f:
                    pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "jest" in deps:
                    return "jest"
                if "vitest" in deps:
                    return "vitest"
            except Exception:
                pass
        return ""

    def _detect_build_command(self) -> str:
        # Check package.json scripts
        pkg_json = os.path.join(self.root, "package.json")
        if os.path.exists(pkg_json):
            try:
                import json
                with open(pkg_json) as f:
                    pkg = json.load(f)
                scripts = pkg.get("scripts", {})
                if "build" in scripts:
                    return "npm run build"
            except Exception:
                pass
        # Python
        if os.path.exists(os.path.join(self.root, "setup.py")):
            return "python setup.py build"
        if os.path.exists(os.path.join(self.root, "pyproject.toml")):
            return "python -m build"
        # Rust
        if os.path.exists(os.path.join(self.root, "Cargo.toml")):
            return "cargo build"
        # Go
        if os.path.exists(os.path.join(self.root, "go.mod")):
            return "go build"
        return ""

    def _detect_run_command(self) -> str:
        if os.path.exists(os.path.join(self.root, "manage.py")):
            return "python manage.py runserver"
        pkg_json = os.path.join(self.root, "package.json")
        if os.path.exists(pkg_json):
            try:
                import json
                with open(pkg_json) as f:
                    pkg = json.load(f)
                scripts = pkg.get("scripts", {})
                if "start" in scripts:
                    return "npm start"
                if "dev" in scripts:
                    return "npm run dev"
            except Exception:
                pass
        if os.path.exists(os.path.join(self.root, "Cargo.toml")):
            return "cargo run"
        return ""

    def _detect_test_command(self) -> str:
        if os.path.exists(os.path.join(self.root, "pytest.ini")):
            return "pytest"
        pkg_json = os.path.join(self.root, "package.json")
        if os.path.exists(pkg_json):
            try:
                import json
                with open(pkg_json) as f:
                    pkg = json.load(f)
                scripts = pkg.get("scripts", {})
                if "test" in scripts:
                    return "npm test"
            except Exception:
                pass
        if os.path.exists(os.path.join(self.root, "Cargo.toml")):
            return "cargo test"
        if os.path.exists(os.path.join(self.root, "go.mod")):
            return "go test ./..."
        return ""

    def _find_scripts(self) -> dict[str, str]:
        scripts = {}
        pkg_json = os.path.join(self.root, "package.json")
        if os.path.exists(pkg_json):
            try:
                import json
                with open(pkg_json) as f:
                    pkg = json.load(f)
                scripts = pkg.get("scripts", {})
            except Exception:
                pass
        return scripts

    def _detect_constraints(self) -> list[str]:
        constraints = []
        if not self._is_git_repo():
            constraints.append("not_a_git_repo")
        return constraints
