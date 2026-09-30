"""Verification for the Refactor Machine (assessment layer).

Run: python test_assessment.py
Exits non-zero if any assertion fails.
"""
import os
import sys

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from assessor.assessor import KnowledgeAssessor, KnowledgeItem, QueryAssessor
from assessor.classifier import BrickExperienceClassifier
from assessor.linker import RelationshipLinker, KnowledgeItem as KI
from assessor.telemetry import ProcessAnalyzer, ResolutionEvent
from assessor.standards import standard_summary, quality_band
from setup.refactor_machine import RefactorMachine
from agent.igris_agent import IgrisAgent


def check(name: str, cond: bool):
    print(("PASS" if cond else "FAIL") + " | " + name)
    if not cond:
        sys.exit(1)


def main() -> int:
    # ---- 1. Assessor: 4 dimensions + quality ------------------ #
    ass = KnowledgeAssessor()

    brick = KnowledgeItem(
        id="concept_inverse", kind="concept",
        content="np.linalg.inv", code_template="np.linalg.inv({arg})",
        surface_forms={"uz": ["teskari"], "en": ["inverse"], "code": ["np.linalg.inv"]},
        domains=["mathematics"],
    )
    a = ass.assess(brick)
    check("brick has 4 dimension scores", set(a.scores) == {"situation", "information", "volume", "semantics"})
    check("brick low situation", a.scores["situation"] <= 0.3)
    check("brick high volume (atomic)", a.scores["volume"] >= 0.7)
    check("brick quality in [0,1]", 0.0 <= a.quality <= 1.0)

    exp = KnowledgeItem(
        id="exp-abc", kind="experience",
        content="Debugged auth outage on Tuesday night. Root cause was a revoked JWT.",
        sessions=["s1"], timestamps=["2026-08-01T10:00:00"],
        summary="auth outage debug session",
    )
    ea = ass.assess(exp)
    check("experience high situation", ea.scores["situation"] >= 0.5)

    # ---- 2. Classifier ----------------------------------------- #
    clf = BrickExperienceClassifier(ass)
    cb = clf.classify(brick)
    check("inverse concept classified brick", cb.category == "brick")

    ce = clf.classify(exp)
    check("experience classified as experience", ce.category == "experience")

    # ---- 3. QueryAssessor -------------------------------------- #
    qa = QueryAssessor()
    q1 = qa.assess("matritsani teskari top", lang="uz")
    q2 = qa.assess("what maybe something", lang="en")
    check("clear query low ambiguity", q1["ambiguity"] <= 0.3)
    check("vague query higher ambiguity", q2["ambiguity"] > q1["ambiguity"])

    # ---- 4. Linker --------------------------------------------- #
    ln = RelationshipLinker()
    items = [
        KI(id="a", kind="concept", surface_forms={"en": ["inverse"]}, domains=["math"]),
        KI(id="b", kind="concept", surface_forms={"en": ["inverse", "invert"]}, domains=["math"]),
        KI(id="c", kind="experience", content="x", sessions=["s9"]),
        KI(id="d", kind="observation", content="y", sessions=["s9"]),
    ]
    links = ln.link_all(items)
    check("semantic link created", any(l.link_type == "semantic" for l in links))
    check("sequence link created", any(l.link_type == "sequence" for l in links))
    check("no self links", all(l.source != l.target for l in links))

    # ---- 5. Telemetry ------------------------------------------ #
    te = ProcessAnalyzer(window_size=5)
    for i in range(6):
        te.record(ResolutionEvent(query=f"q{i}", status="ok", confidence=0.9,
                                  engine="deterministic", chains=["chain_math"]))
    snap = te.snapshot()
    check("telemetry ok_rate ~1.0", snap.ok_rate >= 0.9)
    check("telemetry top chains", "chain_math" in snap.top_chains)

    # declining-confidence detection
    te2 = ProcessAnalyzer(window_size=3)
    for c in [0.9, 0.85, 0.8, 0.5, 0.4, 0.3]:
        te2.record(ResolutionEvent(query="q", status="ok", confidence=c))
    check("confidence decline detected", te2.snapshot().confidence_declining)

    # ---- 6. RefactorMachine end-to-end -------------------------- #
    agent = IgrisAgent(use_llm=False)
    rm = RefactorMachine(agent)
    report = rm.refactor_report()
    check("refactor report has inventory", "inventory" in report)
    check("refactor report links", report["links"]["total_links"] >= 0)
    check("refactor report telemetry", "telemetry" in report)

    ev = rm.evaluate_query("matritsani teskari top", lang="uz")
    check("evaluate_query returns semantics", "query_semantics" in ev)
    check("evaluate_query resolves", "resolution" in ev and ev["resolution"]["status"] == "ok")
    check("telemetry recorded after resolve", agent.refactor.telemetry.stats()["total_events"] >= 1)

    # agent CLI-integrated observe: resolving already records
    agent.resolve("sort the list")
    check("agent.resolve feeds telemetry", agent.refactor.telemetry.stats()["total_events"] >= 2)

    # no double-counting: each resolve = exactly 1 telemetry event
    before = agent.refactor.telemetry.stats()["total_events"]
    rm.evaluate_query("ro'yxatni sarala", lang="uz")
    after = agent.refactor.telemetry.stats()["total_events"]
    check("evaluate_query does not double-count", after - before == 1)

    # composition links: brick -> rule now resolvable from real ids
    links2 = rm.link_agent()
    check("composition links exist", any(l.link_type == "composition" for l in links2))

    # ---- 7. Standards ------------------------------------------- #
    s = standard_summary()
    check("standards mention 4 dimensions", all(k in s for k in ("situation", "information", "volume", "semantics")))
    band, _ = quality_band(0.9)
    check("quality band wisdom at 0.9", band == "wisdom")

    print()
    print("ALL ASSESSMENT TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
