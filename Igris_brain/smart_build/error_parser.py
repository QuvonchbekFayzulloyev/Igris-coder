"""Smart Error Parser — raw error → structured context.

LLMga raw error bermaslik, structured evidence berish.
Error → Root location → Classification → Relevant frames → Changed code → LLM
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ErrorType(str, Enum):
    """Error turlari."""
    SYNTAX = "syntax"
    IMPORT = "import"
    RUNTIME = "runtime"
    TYPE = "type"
    LOGIC = "logic"
    DEPENDENCY = "dependency"
    TEST = "test"
    BUILD = "build"
    UNKNOWN = "unknown"


class ErrorSeverity(str, Enum):
    """Error og'irligi."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ErrorLocation:
    """Error joylashuvi."""
    file_path: str = ""
    line_number: int = 0
    column: int = 0
    function_name: str = ""

    def to_dict(self) -> dict:
        return {
            "file": self.file_path,
            "line": self.line_number,
            "column": self.column,
            "function": self.function_name,
        }


@dataclass
class ErrorCandidate:
    """Xato sababi candidate."""
    cause: str
    confidence: float = 0.0
    suggestion: str = ""
    evidence: str = ""


@dataclass
class ParsedError:
    """Tuzilgan error."""
    raw_error: str
    error_type: ErrorType = ErrorType.UNKNOWN
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    message: str = ""
    location: ErrorLocation = field(default_factory=ErrorLocation)
    relevant_frames: list[dict] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    candidates: list[ErrorCandidate] = field(default_factory=list)
    suggestion: str = ""
    to_llm_prompt: str = ""

    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type.value,
            "severity": self.severity.value,
            "message": self.message[:200],
            "location": self.location.to_dict(),
            "candidate_count": len(self.candidates),
            "changed_files": self.changed_files,
        }


class SmartErrorParser:
    """Raw error'larni tuzilgan evidence ga aylantirish."""

    # Error patterns
    ERROR_PATTERNS = {
        ErrorType.SYNTAX: [
            r"SyntaxError",
            r"IndentationError",
            r"TabError",
            r"invalid syntax",
        ],
        ErrorType.IMPORT: [
            r"ModuleNotFoundError",
            r"ImportError",
            r"cannot import",
        ],
        ErrorType.RUNTIME: [
            r"RuntimeError",
            r"ValueError",
            r"KeyError",
            r"IndexError",
            r"AttributeError",
            r"TypeError",
            r"NameError",
        ],
        ErrorType.DEPENDENCY: [
            r"No module named",
            r"Package not found",
            r"version mismatch",
        ],
        ErrorType.TEST: [
            r"AssertionError",
            r"FAILED",
            r"assert .*==",
        ],
        ErrorType.BUILD: [
            r"BuildError",
            r"CompilationError",
            r"cannot compile",
        ],
    }

    def __init__(self, project_root: str = ""):
        self.project_root = project_root

    def parse(self, raw_error: str, changed_files: list[str] = None,
              dependencies: list[str] = None) -> ParsedError:
        """Raw error'ni tuzilgan evidence ga aylantirish."""
        parsed = ParsedError(raw_error=raw_error)

        # 1. Error type aniqlash
        parsed.error_type = self._classify_error(raw_error)

        # 2. Severity aniqlash
        parsed.severity = self._assess_severity(parsed.error_type)

        # 3. Message extraction
        parsed.message = self._extract_message(raw_error)

        # 4. Location extraction
        parsed.location = self._extract_location(raw_error)

        # 5. Relevant frames
        parsed.relevant_frames = self._extract_frames(raw_error)

        # 6. Changed files
        parsed.changed_files = changed_files or []

        # 7. Dependencies
        parsed.dependencies = dependencies or []

        # 8. Candidates
        parsed.candidates = self._generate_candidates(parsed)

        # 9. Suggestion
        parsed.suggestion = self._generate_suggestion(parsed)

        # 10. LLM prompt
        parsed.to_llm_prompt = self._build_llm_prompt(parsed)

        return parsed

    def _classify_error(self, raw: str) -> ErrorType:
        """Error turini aniqlash."""
        for error_type, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, raw, re.IGNORECASE):
                    return error_type
        return ErrorType.UNKNOWN

    def _assess_severity(self, error_type: ErrorType) -> ErrorSeverity:
        """Error og'irligini baholash."""
        severity_map = {
            ErrorType.SYNTAX: ErrorSeverity.CRITICAL,
            ErrorType.IMPORT: ErrorSeverity.HIGH,
            ErrorType.DEPENDENCY: ErrorSeverity.HIGH,
            ErrorType.BUILD: ErrorSeverity.CRITICAL,
            ErrorType.RUNTIME: ErrorSeverity.MEDIUM,
            ErrorType.TEST: ErrorSeverity.MEDIUM,
            ErrorType.LOGIC: ErrorSeverity.LOW,
            ErrorType.UNKNOWN: ErrorSeverity.MEDIUM,
        }
        return severity_map.get(error_type, ErrorSeverity.MEDIUM)

    def _extract_message(self, raw: str) -> str:
        """Error xabarini ajratib olish."""
        lines = raw.strip().split("\n")
        for line in lines[:3]:
            line = line.strip()
            if line and not line.startswith("Traceback"):
                return line[:200]
        return lines[0][:200] if lines else "Unknown error"

    def _extract_location(self, raw: str) -> ErrorLocation:
        """Error joylashuvini aniqlash."""
        location = ErrorLocation()
        # Pattern: File "path", line N
        match = re.search(r'File "([^"]+)", line (\d+)', raw)
        if match:
            file_path = match.group(1)
            location.file_path = file_path
            location.line_number = int(match.group(2))
        return location

    def _extract_frames(self, raw: str) -> list[dict]:
        """Stack frame'larni ajratib olish."""
        frames = []
        pattern = r'File "([^"]+)", line (\d+), in (.+)'
        for match in re.finditer(pattern, raw):
            frames.append({
                "file": match.group(1),
                "line": int(match.group(2)),
                "function": match.group(3),
            })
        return frames

    def _generate_candidates(self, parsed: ParsedError) -> list[ErrorCandidate]:
        """Xato sababi candidate'larni generatsiya qilish."""
        candidates = []

        if parsed.error_type == ErrorType.IMPORT:
            candidates.append(ErrorCandidate(
                cause="wrong import path",
                confidence=0.7,
                suggestion="Check import path and module name",
            ))
            candidates.append(ErrorCandidate(
                cause="package not installed",
                confidence=0.5,
                suggestion=f"Install with: pip install <package>",
            ))

        elif parsed.error_type == ErrorType.SYNTAX:
            candidates.append(ErrorCandidate(
                cause="syntax error in code",
                confidence=0.9,
                suggestion="Check indentation and syntax",
            ))

        elif parsed.error_type == ErrorType.RUNTIME:
            candidates.append(ErrorCandidate(
                cause="null/undefined reference",
                confidence=0.6,
                suggestion="Check variable initialization",
            ))
            candidates.append(ErrorCandidate(
                cause="type mismatch",
                confidence=0.4,
                suggestion="Check argument types",
            ))

        return candidates

    def _generate_suggestion(self, parsed: ParsedError) -> str:
        """Tuzatish bo'yicha taklif."""
        suggestions = {
            ErrorType.SYNTAX: "Check syntax and indentation",
            ErrorType.IMPORT: "Verify import path and package installation",
            ErrorType.DEPENDENCY: "Install missing dependencies",
            ErrorType.BUILD: "Check build configuration",
            ErrorType.RUNTIME: "Check variable types and initialization",
            ErrorType.TEST: "Review test assertions and expected values",
            ErrorType.LOGIC: "Review algorithm and conditions",
        }
        return suggestions.get(parsed.error_type, "Investigate error details")

    def _build_llm_prompt(self, parsed: ParsedError) -> str:
        """LLM uchun tuzilgan prompt."""
        lines = [
            "ERROR ANALYSIS:",
            f"Type: {parsed.error_type.value}",
            f"Severity: {parsed.severity.value}",
            f"Message: {parsed.message}",
            "",
        ]

        if parsed.location.file_path:
            lines.append(f"Location: {parsed.location.file_path}:{parsed.location.line_number}")

        if parsed.changed_files:
            lines.append(f"\nChanged recently: {', '.join(parsed.changed_files[:3])}")

        if parsed.dependencies:
            lines.append(f"Dependencies: {', '.join(parsed.dependencies[:3])}")

        if parsed.candidates:
            lines.append("\nCANDIDATE CAUSES:")
            for c in parsed.candidates:
                lines.append(f"  {c.confidence:.0%} - {c.cause}")
                lines.append(f"    → {c.suggestion}")

        lines.append(f"\nSUGGESTION: {parsed.suggestion}")
        return "\n".join(lines)

    def get_status(self) -> dict:
        return {
            "project_root": self.project_root,
            "parser_type": "smart_error_parser",
            "error_types": [e.value for e in ErrorType],
        }
