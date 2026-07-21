"""
Regression tests for CLI argument parsing -- specifically the
--project flag working consistently across subcommands. A real bug was
found while adding `igris seed-knowledge`: argparse subparsers silently
clobber an already-parsed top-level --project value back to None if the
subparser also defines --project with a default of None (not
SUPPRESS), even when the subcommand invocation didn't include --project
at all. `igris --project X seed-knowledge` would silently seed the
wrong (auto-resolved) project instead of X, with no error.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.cli import _build_parser


def test_project_after_subcommand():
    parser = _build_parser()
    args = parser.parse_args(["seed-knowledge", "--project", "myapp"])
    assert args.command == "seed-knowledge"
    assert getattr(args, "project", None) == "myapp"


def test_project_before_subcommand_is_not_clobbered():
    """The exact regression: this used to silently reset project to None."""
    parser = _build_parser()
    args = parser.parse_args(["--project", "myapp", "seed-knowledge"])
    assert args.command == "seed-knowledge"
    assert getattr(args, "project", None) == "myapp"


def test_project_omitted_entirely_falls_back_to_none():
    parser = _build_parser()
    args = parser.parse_args(["seed-knowledge"])
    assert args.command == "seed-knowledge"
    assert getattr(args, "project", None) is None


def test_project_before_subcommand_for_default_run_still_works():
    """Sanity check the existing (non-subcommand) --project flow wasn't broken by the fix."""
    parser = _build_parser()
    args = parser.parse_args(["--project", "myapp", "-p", "do something"])
    assert args.project == "myapp"
    assert args.prompt == "do something"
