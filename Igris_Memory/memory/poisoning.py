"""
CODER AGENT MEMORY — Poisoning Protection
Memory xavfsizligi: adversarial injection, tamper detection.

Features:
- Content integrity checking
- Anomaly detection
- Audit logging
"""

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional


class PoisoningProtection:
    """
    Memory Poisoning Protection tizimi.
    
    Xavfsizlik choralari:
    - Content hash integrity check
    - Suspicious pattern detection
    - Audit logging
    - Anomaly scoring
    """

    # Suspicious patterns that might indicate poisoning
    SUSPICIOUS_PATTERNS = [
        r"ignore\s+(previous|all|above)\s+(instructions?|rules?|prompts?)",
        r"you\s+are\s+now\s+(a|an)\s+",
        r"forget\s+(everything|all|previous)",
        r"system\s*:\s*",
        r"<\s*(script|instruction)\s*>",
        r"override\s+(safety|rules?|instructions?)",
        r"jailbreak",
        r"DAN\s+mode",
        r"developer\s+mode",
        r"admin\s+access",
        r"bypass\s+(all|security|rules?)",
    ]

    def __init__(self, protection_dir: str = "memory/security"):
        self.protection_dir = protection_dir
        os.makedirs(protection_dir, exist_ok=True)
        self._integrity_hashes: dict[str, str] = {}
        self._audit_log: list[dict] = []
        self._load_integrity_db()

    def _load_integrity_db(self):
        """Load integrity hash database."""
        db_path = os.path.join(self.protection_dir, "integrity_db.json")
        if os.path.exists(db_path):
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    self._integrity_hashes = json.load(f)
            except Exception:
                self._integrity_hashes = {}

    def _save_integrity_db(self):
        """Save integrity hash database."""
        db_path = os.path.join(self.protection_dir, "integrity_db.json")
        try:
            with open(db_path, "w", encoding="utf-8") as f:
                json.dump(self._integrity_hashes, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _content_hash(self, content: str) -> str:
        """Generate content hash."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    # ============================================================
    # PUBLIC API
    # ============================================================

    def check_entry(self, entry: dict) -> dict:
        """
        Check a memory entry for potential poisoning.
        
        Args:
            entry: Memory entry to check
        
        Returns:
            Safety check result
        """
        result = {
            "safe": True,
            "score": 0,  # 0 = safe, 100 = definitely poisoned
            "warnings": [],
            "checks": {},
        }

        content = json.dumps(entry, ensure_ascii=False)
        summary = entry.get("summary", "")

        # 1. Check for suspicious patterns
        pattern_result = self._check_suspicious_patterns(content)
        result["checks"]["patterns"] = pattern_result
        if pattern_result["found"]:
            result["score"] += pattern_result["severity"] * 30
            result["warnings"].extend(pattern_result["matches"])

        # 2. Check content length anomalies
        length_result = self._check_content_anomaly(entry)
        result["checks"]["length"] = length_result
        if length_result["anomaly"]:
            result["score"] += 10
            result["warnings"].append(f"Content length anomaly: {length_result['reason']}")

        # 3. Check for encoding issues
        encoding_result = self._check_encoding(content)
        result["checks"]["encoding"] = encoding_result
        if encoding_result["issues"]:
            result["score"] += 5
            result["warnings"].extend(encoding_result["issues"])

        # 4. Check summary quality
        summary_result = self._check_summary_quality(summary)
        result["checks"]["summary"] = summary_result
        if summary_result["low_quality"]:
            result["score"] += 5
            result["warnings"].append("Summary quality is low")

        # Final verdict
        result["safe"] = result["score"] < 50
        result["verdict"] = "safe" if result["safe"] else "suspicious"

        # Audit log
        self._audit_log.append({
            "entry_id": entry.get("id", "unknown"),
            "entry_type": entry.get("type", "unknown"),
            "score": result["score"],
            "verdict": result["verdict"],
            "warnings_count": len(result["warnings"]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return result

    def register_integrity(self, entry_id: str, content: str):
        """Register content hash for integrity checking."""
        self._integrity_hashes[entry_id] = self._content_hash(content)
        self._save_integrity_db()

    def verify_integrity(self, entry_id: str, content: str) -> dict:
        """
        Verify content hasn't been tampered with.
        
        Args:
            entry_id: Entry ID
            content: Current content to verify
        
        Returns:
            Integrity check result
        """
        if entry_id not in self._integrity_hashes:
            return {"status": "unknown", "message": "Entry not registered"}

        stored_hash = self._integrity_hashes[entry_id]
        current_hash = self._content_hash(content)

        if stored_hash == current_hash:
            return {"status": "valid", "message": "Content integrity verified"}
        else:
            self._audit_log.append({
                "event": "integrity_violation",
                "entry_id": entry_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return {"status": "tampered", "message": "Content has been modified!"}

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        """Get recent audit log entries."""
        return self._audit_log[-limit:]

    def get_stats(self) -> dict:
        """Get protection statistics."""
        total_checks = len(self._audit_log)
        suspicious = len([l for l in self._audit_log if l.get("verdict") == "suspicious"])
        violations = len([l for l in self._audit_log if l.get("event") == "integrity_violation"])

        return {
            "total_checks": total_checks,
            "suspicious_entries": suspicious,
            "integrity_violations": violations,
            "registered_entries": len(self._integrity_hashes),
            "suspicious_rate": suspicious / total_checks if total_checks > 0 else 0,
        }

    # ============================================================
    # INTERNAL CHECKS
    # ============================================================

    def _check_suspicious_patterns(self, content: str) -> dict:
        """Check for suspicious patterns in content."""
        matches = []
        content_lower = content.lower()

        for pattern in self.SUSPICIOUS_PATTERNS:
            found = re.findall(pattern, content_lower, re.IGNORECASE)
            if found:
                matches.append(f"Pattern detected: {pattern[:50]}")

        return {
            "found": len(matches) > 0,
            "matches": matches,
            "severity": min(len(matches), 3),  # Cap at 3
        }

    def _check_content_anomaly(self, entry: dict) -> dict:
        """Check for content length anomalies."""
        content = json.dumps(entry, ensure_ascii=False)
        content_len = len(content)

        # Check if entry is suspiciously large
        if content_len > 10000:
            return {"anomaly": True, "reason": f"Entry too large ({content_len} chars)"}

        # Check if summary is suspiciously long
        summary = entry.get("summary", "")
        if len(summary) > 1000:
            return {"anomaly": True, "reason": f"Summary too long ({len(summary)} chars)"}

        return {"anomaly": False, "reason": ""}

    def _check_encoding(self, content: str) -> dict:
        """Check for encoding issues."""
        issues = []

        # Check for unusual Unicode characters
        unusual_chars = [c for c in content if ord(c) > 0xFFFF]
        if unusual_chars:
            issues.append(f"Unusual Unicode characters found: {len(unusual_chars)}")

        # Check for null bytes
        if "\x00" in content:
            issues.append("Null bytes detected")

        return {"issues": issues}

    def _check_summary_quality(self, summary: str) -> dict:
        """Check summary quality."""
        if not summary:
            return {"low_quality": True, "reason": "Empty summary"}

        # Check if summary is just numbers/symbols
        alpha_ratio = sum(c.isalpha() for c in summary) / max(len(summary), 1)
        if alpha_ratio < 0.3:
            return {"low_quality": True, "reason": "Summary has low alpha ratio"}

        return {"low_quality": False, "reason": ""}
