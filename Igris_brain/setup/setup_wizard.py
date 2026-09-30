"""
IGRIS BRAIN — First-Time Setup Wizard
=====================================
Interactive setup wizard for configuring IGRIS and all MCP servers.

Run: python setup_wizard.py

Features:
    - Prerequisites check (Python, Node.js, Ollama, Git)
    - Dependency installation
    - .env configuration
    - Database setup (optional)
    - Connection testing
    - MCP server validation
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"


# ---------------------------------------------------------------- #
# Terminal Colors
# ---------------------------------------------------------------- #

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {text}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.END}\n")


def print_step(num: int, text: str):
    print(f"\n{Colors.CYAN}{Colors.BOLD}Step {num}:{Colors.END} {Colors.BOLD}{text}{Colors.END}")


def print_success(text: str):
    print(f"  {Colors.GREEN}✓{Colors.END} {text}")


def print_warning(text: str):
    print(f"  {Colors.YELLOW}⚠{Colors.END} {text}")


def print_error(text: str):
    print(f"  {Colors.RED}✗{Colors.END} {text}")


def print_info(text: str):
    print(f"  {Colors.BLUE}ℹ{Colors.END} {text}")


def ask_question(question: str, default: str = "") -> str:
    """Foydalanuvchidan savol so'rash."""
    if default:
        prompt = f"\n  {question} [{default}]: "
    else:
        prompt = f"\n  {question}: "
    
    try:
        answer = input(prompt).strip()
        return answer if answer else default
    except (EOFError, KeyboardInterrupt):
        return default


def ask_yes_no(question: str, default: bool = True) -> bool:
    """Ha/Yo'q savoli."""
    suffix = "[Y/n]" if default else "[y/N]"
    prompt = f"\n  {question} {suffix}: "
    
    try:
        answer = input(prompt).strip().lower()
        if not answer:
            return default
        return answer in ("y", "yes", "ha")
    except (EOFError, KeyboardInterrupt):
        return default


# ---------------------------------------------------------------- #
# Prerequisites Check
# ---------------------------------------------------------------- #

def check_python() -> tuple[bool, str]:
    """Python versiyasini tekshirish."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    return False, f"Python {version.major}.{version.minor}.{version.micro} (need 3.10+)"


def check_node() -> tuple[bool, str]:
    """Node.js mavjudligini tekshirish."""
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "Not found"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, "Not installed"


def check_npm() -> tuple[bool, str]:
    """npm mavjudligini tekshirish."""
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "Not found"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, "Not installed"


def check_git() -> tuple[bool, str]:
    """Git mavjudligini tekshirish."""
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "Not found"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, "Not installed"


def check_ollama() -> tuple[bool, str]:
    """Ollama mavjudligini tekshirish."""
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "Not found"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, "Not installed"


def check_redis() -> tuple[bool, str]:
    """Redis server mavjudligini tekshirish."""
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, socket_connect_timeout=2)
        r.ping()
        return True, "Connected"
    except Exception:
        return False, "Not running or not installed"


def check_postgresql() -> tuple[bool, str]:
    """PostgreSQL mavjudligini tekshirish."""
    try:
        import psycopg2
        return True, "psycopg2 installed"
    except ImportError:
        return False, "psycopg2 not installed"


def check_mongodb() -> tuple[bool, str]:
    """MongoDB mavjudligini tekshirish."""
    try:
        import pymongo
        return True, "pymongo installed"
    except ImportError:
        return False, "pymongo not installed"


# ---------------------------------------------------------------- #
# Installation
# ---------------------------------------------------------------- #

def install_python_deps() -> bool:
    """Python kutubxonalarni o'rnatish."""
    print_info("Installing Python dependencies...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            print_success("Python dependencies installed")
            return True
        else:
            print_error(f"Failed: {result.stderr[:200]}")
            return False
    except Exception as exc:
        print_error(f"Installation failed: {exc}")
        return False


def install_optional_deps() -> bool:
    """Ixtiyoriy kutubxonalarni o'rnatish."""
    optional = [
        ("redis", "Redis support"),
        ("psycopg2-binary", "PostgreSQL support"),
        ("pymongo", "MongoDB support"),
    ]
    
    installed = 0
    for package, description in optional:
        if ask_yes_no(f"Install {description} ({package})?", default=False):
            print_info(f"Installing {package}...")
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", package],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    print_success(f"{package} installed")
                    installed += 1
                else:
                    print_warning(f"Failed to install {package} (optional)")
            except Exception:
                print_warning(f"Failed to install {package} (optional)")
    
    return True


def install_ollama_model(model: str = "qwen3:8b") -> bool:
    """Ollama modelini yuklab olish."""
    print_info(f"Pulling Ollama model: {model}...")
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            print_success(f"Model {model} installed")
            return True
        else:
            print_warning(f"Failed to pull model: {result.stderr[:200]}")
            return False
    except Exception as exc:
        print_warning(f"Ollama pull failed: {exc}")
        return False


# ---------------------------------------------------------------- #
# Configuration
# ---------------------------------------------------------------- #

def configure_github() -> str:
    """GitHub token sozlash."""
    print_info("GitHub token is optional for repository operations.")
    print_info("Get one at: https://github.com/settings/tokens")
    
    token = ask_question("GitHub token (leave empty to skip)", "")
    return token


def configure_database() -> dict:
    """Database sozlash."""
    config = {}
    
    print_info("Database configuration (PostgreSQL or MySQL)")
    
    db_type = ask_question("Database type (postgres/mysql/none)", "postgres")
    
    if db_type.lower() in ("postgres", "postgresql"):
        host = ask_question("PostgreSQL host", "localhost")
        port = ask_question("PostgreSQL port", "5432")
        user = ask_question("PostgreSQL user", "postgres")
        password = ask_question("PostgreSQL password", "")
        database = ask_question("Database name", "igris")
        
        config["DATABASE_URL"] = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    elif db_type.lower() in ("mysql", "mariadb"):
        host = ask_question("MySQL host", "localhost")
        port = ask_question("MySQL port", "3306")
        user = ask_question("MySQL user", "root")
        password = ask_question("MySQL password", "")
        database = ask_question("Database name", "igris")
        
        config["DATABASE_URL"] = f"mysql://{user}:{password}@{host}:{port}/{database}"
    
    return config


def configure_mongodb() -> dict:
    """MongoDB sozlash."""
    config = {}
    
    if ask_yes_no("Configure MongoDB?", default=False):
        host = ask_question("MongoDB host", "localhost")
        port = ask_question("MongoDB port", "27017")
        database = ask_question("Database name", "igris")
        
        config["MONGODB_URL"] = f"mongodb://{host}:{port}/{database}"
    
    return config


def configure_redis() -> dict:
    """Redis sozlash."""
    config = {}
    
    if ask_yes_no("Configure Redis?", default=False):
        host = ask_question("Redis host", "localhost")
        port = ask_question("Redis port", "6379")
        password = ask_question("Redis password (leave empty if none)", "")
        db = ask_question("Redis database number", "0")
        
        if password:
            config["REDIS_URL"] = f"redis://:{password}@{host}:{port}/{db}"
        else:
            config["REDIS_URL"] = f"redis://{host}:{port}/{db}"
    
    return config


def configure_browser() -> dict:
    """Browser (Web AI Bridge) sozlash."""
    config = {}
    
    print_info("Browser automation allows IGRIS to browse websites")
    
    if ask_yes_no("Enable browser automation?", default=True):
        config["WAB_HEADLESS"] = "false"
        config["WAB_BROWSER_CHANNEL"] = "chrome"
        config["WAB_CDP_ENABLED"] = "true"
        
        # Windows Chrome path
        if sys.platform == "win32":
            default_path = os.path.expanduser(
                "~/AppData/Local/Google/Chrome/User Data"
            )
        else:
            default_path = "~/.config/google-chrome"
        
        chrome_path = ask_question("Chrome user data path", default_path)
        config["WAB_CHROME_USER_DATA"] = chrome_path
        
        profile = ask_question("Chrome profile name", "Default")
        config["WAB_CHROME_PROFILE"] = profile
    
    return config


def configure_agent() -> dict:
    """Agent sozlash."""
    config = {}
    
    print_info("IGRIS Agent configuration")
    
    model = ask_question("Ollama model", "qwen3:8b")
    config["IGRIS_MODEL"] = model
    
    llm_url = ask_question("Ollama URL", "http://localhost:11434")
    config["IGRIS_LLM_URL"] = llm_url
    
    return config


# ---------------------------------------------------------------- #
# Write .env
# ---------------------------------------------------------------- #

def write_env_file(config: dict):
    """ .env faylini yozish."""
    # Load existing .env if present
    existing = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    existing[key.strip()] = value.strip()
    
    # Merge with new config (new values override existing)
    merged = {**existing, **{k: v for k, v in config.items() if v}}
    
    # Write .env file
    with open(ENV_FILE, "w") as f:
        f.write("# IGRIS BRAIN — MCP Server Configuration\n")
        f.write("# Generated by setup wizard\n\n")
        
        sections = {
            "GitHub": ["GITHUB_TOKEN"],
            "Database": ["DATABASE_URL"],
            "MongoDB": ["MONGODB_URL"],
            "Redis": ["REDIS_URL"],
            "WebSocket": ["WS_SECRET", "WS_MAX_CONNECTIONS", "WS_MAX_MESSAGE_SIZE", "WS_RATE_LIMIT"],
            "Browser": ["WAB_HEADLESS", "WAB_BROWSER_CHANNEL", "WAB_CDP_ENABLED", "WAB_CDP_URL", "WAB_CDP_PORT", "WAB_CHROME_USER_DATA", "WAB_CHROME_PROFILE"],
            "Agent": ["IGRIS_MODEL", "IGRIS_LLM_URL", "IGRIS_TEMPERATURE", "IGRIS_MAX_TOKENS", "IGRIS_MEMORY_ENABLED", "IGRIS_MEMORY_PATH"],
        }
        
        written_keys = set()
        for section, keys in sections.items():
            section_keys = [k for k in keys if k in merged]
            if section_keys:
                f.write(f"# ── {section} {'─' * (50 - len(section))}\n")
                for key in section_keys:
                    value = merged[key]
                    f.write(f"{key}={value}\n")
                    written_keys.add(key)
                f.write("\n")
        
        # Write any remaining keys
        remaining = {k: v for k, v in merged.items() if k not in written_keys}
        if remaining:
            f.write("# ── Other ──────────────────────────────────────────────\n")
            for key, value in remaining.items():
                f.write(f"{key}={value}\n")
    
    print_success(f".env file created at {ENV_FILE}")


# ---------------------------------------------------------------- #
# Validation
# ---------------------------------------------------------------- #

def validate_connections(config: dict):
    """Ulanishlarni tekshirish."""
    print_step(6, "Validating connections")
    
    # Redis
    if "REDIS_URL" in config:
        print_info("Testing Redis connection...")
        try:
            import redis
            r = redis.from_url(config["REDIS_URL"], socket_connect_timeout=3)
            r.ping()
            print_success("Redis connected")
        except Exception as exc:
            print_warning(f"Redis connection failed: {exc}")
    
    # PostgreSQL
    if "DATABASE_URL" in config and config["DATABASE_URL"].startswith("postgresql"):
        print_info("Testing PostgreSQL connection...")
        try:
            import psycopg2
            conn = psycopg2.connect(config["DATABASE_URL"])
            conn.close()
            print_success("PostgreSQL connected")
        except Exception as exc:
            print_warning(f"PostgreSQL connection failed: {exc}")
    
    # MongoDB
    if "MONGODB_URL" in config:
        print_info("Testing MongoDB connection...")
        try:
            from pymongo import MongoClient
            client = MongoClient(config["MONGODB_URL"], serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            client.close()
            print_success("MongoDB connected")
        except Exception as exc:
            print_warning(f"MongoDB connection failed: {exc}")


# ---------------------------------------------------------------- #
# Main Wizard
# ---------------------------------------------------------------- #

def run_wizard():
    """Asosiy sehrli illyuziya."""
    print_header("IGRIS BRAIN — First-Time Setup Wizard")
    
    print("Welcome to IGRIS! This wizard will help you configure everything.\n")
    
    # Step 1: Check prerequisites
    print_step(1, "Checking prerequisites")
    
    checks = [
        ("Python", check_python()),
        ("Node.js", check_node()),
        ("npm", check_npm()),
        ("Git", check_git()),
        ("Ollama", check_ollama()),
    ]
    
    all_ok = True
    for name, (ok, version) in checks:
        if ok:
            print_success(f"{name}: {version}")
        else:
            print_error(f"{name}: {version}")
            all_ok = False
    
    if not all_ok:
        print_warning("\nSome prerequisites are missing.")
        print_info("Please install missing components and run this wizard again.")
        print_info("Installation guide: https://github.com/your-repo/igris#installation")
        
        if not ask_yes_no("\nContinue anyway?", default=False):
            return
    
    # Step 2: Install dependencies
    print_step(2, "Installing dependencies")
    
    if ask_yes_no("Install Python dependencies?", default=True):
        install_python_deps()
    
    if ask_yes_no("Install optional database dependencies?", default=False):
        install_optional_deps()
    
    # Step 3: Configure Ollama
    print_step(3, "Ollama configuration")
    
    if "Ollama" in [c[0] for c in checks if c[1][0]]:
        if ask_yes_no("Pull Ollama model (qwen3:8b)?", default=True):
            install_ollama_model("qwen3:8b")
    else:
        print_warning("Ollama not found. You can install it later.")
        print_info("Download: https://ollama.ai/download")
    
    # Step 4: Configure services
    print_step(4, "Service configuration")
    
    config = {}
    
    # GitHub
    github_token = configure_github()
    if github_token:
        config["GITHUB_TOKEN"] = github_token
    
    # Database
    db_config = configure_database()
    config.update(db_config)
    
    # MongoDB
    mongo_config = configure_mongodb()
    config.update(mongo_config)
    
    # Redis
    redis_config = configure_redis()
    config.update(redis_config)
    
    # Browser
    browser_config = configure_browser()
    config.update(browser_config)
    
    # Agent
    agent_config = configure_agent()
    config.update(agent_config)
    
    # Step 5: Write configuration
    print_step(5, "Saving configuration")
    write_env_file(config)
    
    # Step 6: Validate
    validate_connections(config)
    
    # Summary
    print_header("Setup Complete!")
    
    print(f"""
{Colors.GREEN}{Colors.BOLD}IGRIS is now configured!{Colors.END}

{Colors.CYAN}Quick Start:{Colors.END}
  1. Start Ollama:     {Colors.BOLD}ollama serve{Colors.END}
  2. Start IGRIS:      {Colors.BOLD}cd Igris_brain && python igris_agent.py{Colors.END}
  3. Start server:     {Colors.BOLD}python server.py{Colors.END}

{Colors.CYAN}MCP Servers:{Colors.END}
  All MCP servers are configured in {Colors.BOLD}.env{Colors.END}
  They auto-load when IGRIS starts.

{Colors.CYAN}Documentation:{Colors.END}
  - README.md: Main documentation
  - .env.example: Configuration reference
  - mcp_servers/: MCP server implementations

{Colors.CYAN}Need help?{Colors.END}
  - Check the README.md
  - Open an issue on GitHub
  - Run: python setup_wizard.py (to reconfigure)

{Colors.GREEN}Happy coding with IGRIS! 🚀{Colors.END}
""")


if __name__ == "__main__":
    try:
        run_wizard()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Setup cancelled.{Colors.END}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n{Colors.RED}Error: {exc}{Colors.END}")
        sys.exit(1)
