"""Verification for the IGRIS brain.

Run: python test_brain.py
Exits non-zero if any assertion fails.
"""
import os
import sys

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from agent.igris_agent import IgrisAgent  # noqa: E402


def check(name: str, cond: bool):
    print(("PASS" if cond else "FAIL") + " | " + name)
    if not cond:
        sys.exit(1)


def main() -> int:
    a = IgrisAgent(use_llm=False)
    stats = a.status()
    print("STATUS:", stats)

    # 1. uz -> code (inverse of matrix)
    r = a.resolve("matritsani teskari top")
    check("uz SOV -> inverse of matrix", r["status"] == "ok" and "np.linalg.inv" in r["output"])

    # 2. uz -> sort list (suffix stripping)
    r = a.resolve("ro'yxatni sarala")
    check("uz suffix stripping -> sorted", r["status"] == "ok" and "sorted(" in r["output"])

    # 3. en -> sort list
    r = a.resolve("sort the list")
    check("en -> sorted", r["status"] == "ok" and "sorted(" in r["output"])

    # 4. en -> mean
    r = a.resolve("mean of the list")
    check("en -> mean", r["status"] == "ok" and "np.mean" in r["output"])

    # 5. determinism: same query twice -> same output
    r1 = a.resolve("matritsani teskari top")
    r2 = a.resolve("matritsani teskari top")
    check("deterministic output", r1["output"] == r2["output"])

    # 6. healing path (previously crashed): unknown query triggers heal + no LLM
    r = a.resolve("zzz unknown gibberish")
    check("unknown query does not crash", r is not None)

    # 7. healing report
    report = a.heal_report("chain_uz")
    check("heal_report returns dict", isinstance(report, dict))

    # 8. chains are present
    chains = set(a.chains.chains.keys())
    check("default chains", {"chain_math", "chain_code", "chain_analysis"}.issubset(chains))

    print()
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
