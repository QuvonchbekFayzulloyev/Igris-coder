"""Universal Composition zanjiri tekshiruvi (yaxlitlangan).

UCE (composition.py) + UCC (ui_compose.py) + planner + executor — barchasi
bitta test faylida. (Ilgari test_composition.py va test_ui_compose.py ikkita
bir maqsadli fayl edi — birlashtirildi.)

Run: python test_composition.py
Exits non-zero if any assertion fails.
"""
import os
import shutil
import sys
import tempfile

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from task.composition import (  # noqa: E402
    CardRegistry, CompositionEngine, CompositionError,
    build_code_registry, build_ttk_registry, fnum, to_frac,
)
from ui.ui_compose import (  # noqa: E402
    UI_STANDARDS,
    brick_stats,
    check_bounds,
    check_overlaps,
    compose_app,
    compose_ui,
    spec_to_cards,
)


def check(name: str, cond: bool):
    print(("PASS" if cond else "FAIL") + " | " + name)
    if not cond:
        sys.exit(1)


# ---------------------------------------------------------------------- #
# UCE — Universal Composition Engine
# ---------------------------------------------------------------------- #

def test_engine():
    # ---- 1. TTK: validation toza bo'lishi kerak ----
    eng = CompositionEngine(build_ttk_registry())
    check("ttk validation clean", eng.validate() == [])

    # ---- 2. Explosion (top-down talab, loss bilan) ----
    ex = eng.explode("shashlik", 1)
    # 1 porsiya shashlik -> 1 kg marinad -> gosht brutto = 0.45 / (1-0.30) = 9/14 kg
    check("gosht brutto = 9/14 kg (loss 30%)", ex["qoy-goshti"] == to_frac("9/14"))
    # brutto * (1-loss) == netto (45/100)
    check("brutto->netto to'g'ri",
          ex["qoy-goshti"] * (1 - to_frac("30/100")) == to_frac("45/100"))
    # piyoz brutto = 0.10 / (1-0.10) = 1/9 kg
    check("piyoz brutto = 1/9 kg (loss 10%)", ex["piyoz"] == to_frac("1/9"))
    check("zira brutto = 2/100 kg", ex["zira"] == to_frac("2/100"))

    # ---- 3. Aniqlik: float xatosi yo'q ----
    check("0.1 + 0.2 == 0.3 (Fraction)", to_frac("0.1") + to_frac("0.2") == to_frac("0.3"))
    check("fnum chiroyli chiqish", fnum(to_frac("9/14"), 4) == "0.6429")

    # ---- 4. Where-used (teskari bog'lanish) ----
    check("where_used gosht -> marinad", eng.where_used("qoy-goshti") == ["marinad-gosht"])
    check("where_used marinad -> shashlik", eng.where_used("marinad-gosht") == ["shashlik"])

    # ---- 5. Qatlamlar (bottom-up qurish tartibi) ----
    layers = eng.build_layers("shashlik")
    check("layer0 = barglar (xomashyo)",
          set(layers[0]) == {"qoy-goshti", "piyoz", "zira", "tuz", "sirka"})
    check("layer1 = marinad (yarimfabrikat)", layers[1] == ["marinad-gosht"])
    check("layer2 = shashlik (ildiz)", layers[2] == ["shashlik"])

    # ---- 6. Implosion (bottom-up tannarx / kalkulyatsiya) ----
    # marinad narxi = 9/14*80000 + 1/9*8000 + 2/100*60000 + 3/100*3000 + 5/100*10000
    cost = eng.implode("marinad-gosht", 1)
    expected = (to_frac("9/14") * 80000 + to_frac("1/9") * 8000
                + to_frac("2/100") * 60000 + to_frac("3/100") * 3000
                + to_frac("5/100") * 10000)
    check("marinad tannarxi aniq", cost == expected)

    # ---- 7. Cycle detection ----
    bad = CardRegistry()
    bad.add_dict({"id": "a", "kind": "composite", "components": [{"ref": "b", "qty": 1}]})
    bad.add_dict({"id": "b", "kind": "composite", "components": [{"ref": "a", "qty": 1}]})
    check("cycle topiladi", any("cycle" in e for e in CompositionEngine(bad).validate()))
    try:
        CompositionEngine(bad).explode("a", 1)
        check("explode cycle'da xato beradi", False)
    except CompositionError:
        check("explode cycle'da xato beradi", True)
    # implode ham RecursionError emas, CompositionError berishi kerak
    try:
        CompositionEngine(bad).implode("a", 1)
        check("implode sikl'da CompositionError beradi", False)
    except CompositionError:
        check("implode sikl'da CompositionError beradi", True)

    # ---- 8. Noma'lum ref ----
    bad2 = CardRegistry()
    bad2.add_dict({"id": "a", "kind": "composite", "components": [{"ref": "nope", "qty": 1}]})
    check("noma'lum ref aniqlanadi",
          any("unknown reference" in e for e in CompositionEngine(bad2).validate()))

    # ---- 9. Son bo'lmagan qty/loss_pct aniqlanadi (to_frac jimgina 0 qaytarmaydi) ----
    bad3 = CardRegistry()
    bad3.add_dict({"id": "a", "kind": "composite",
                   "components": [{"ref": "x", "qty": "abc", "loss_pct": "30%"}]})
    bad3.add_dict({"id": "x", "kind": "atomic", "cost": 5})
    errs = CompositionEngine(bad3).validate()
    check("son bo'lmagan qty/loss aniqlanadi",
          any("not a number" in e for e in errs))

    # ---- 10. build_plan ----
    plan = eng.build_plan("shashlik", 10)
    check("build_plan layers", len(plan["layers"]) == 3)
    check("exec_order bottom-up",
          plan["exec_order"][0] in {"qoy-goshti", "piyoz", "zira", "tuz", "sirka"}
          and plan["exec_order"][-1] == "shashlik")
    check("cost mavjud", plan["cost"] is not None)
    # total = per_unit * demand (yagona implode hisobidan). fnum 6 xonagacha
    # yaxlitlaydi — taqqoslash mikron tolerantlik bilan (display darajasida).
    pu = to_frac(plan["cost"]["per_unit"])
    check("cost total = per_unit * demand",
          abs(float(to_frac(plan["cost"]["total"])) - float(pu * 10)) <= 1e-4)
    # chiziqlilik (linearity) darajada ham aniq: implode(q*10) == implode(q)*10
    check("cost linearity aniq (implode)",
          eng.implode("shashlik", 10) == eng.implode("shashlik", 1) * 10)
    check("materials = xomashyo",
          set(plan["materials"]) == {"qoy-goshti", "piyoz", "zira", "tuz", "sirka"})

    # ---- 11. JSON round-trip ----
    tmp2 = tempfile.mkdtemp(prefix="uce_json_")
    try:
        path = os.path.join(tmp2, "cards.json")
        eng.registry.save_json(path)
        eng2 = CompositionEngine(CardRegistry().load_json(path))
        check("JSON round-trip explosion bir xil",
              eng2.explode("shashlik", 1) == eng.explode("shashlik", 1))
    finally:
        shutil.rmtree(tmp2, ignore_errors=True)


# ---------------------------------------------------------------------- #
# Executor: run_composition (bottom-up qatlamlab bajarish)
# ---------------------------------------------------------------------- #

def test_executor():
    from executor.executor import AgentExecutor  # noqa: E402
    reg = build_code_registry()
    tmp = tempfile.mkdtemp(prefix="uce_")
    try:
        exe = AgentExecutor(workspace_root=tmp, llm=None)
        res = exe.run_composition("app", registry=reg)
        check("executor status ok", res["status"] == "ok")
        check("executor 3 qatlam", res["stats"]["layers"] == 3)
        check("atomic node bajarildi",
              res["nodes"].get("api-routes", {}).get("status") == "ok")
        check("fayllar yozildi",
              os.path.isfile(os.path.join(tmp, "api.py"))
              and os.path.isfile(os.path.join(tmp, "ui.jsx")))

        # pastki qatlam xatosi -> yuqori qatlamlar to'xtaydi
        bad_reg = build_code_registry()
        bad_reg.add_dict({"id": "api-routes", "kind": "atomic",
                          "attrs": {"tool": "nonexistent_tool_xyz"}})
        res2 = exe.run_composition("app", registry=bad_reg)
        check("xato pastki qatlam status partial", res2["status"] == "partial")
        check("xato qatlam report", any(
            l["status"] == "error" for l in res2["layers"]))

        # noma'lum goal -> error, exception emas
        res3 = exe.run_composition("nope_goal", registry=reg)
        check("noma'lum goal error", res3["status"] == "error"
              and any("unknown goal" in e for e in res3["errors"]))

        # composite faqat bolalari ok bo'lsa ok (max_layer_errors=99 bilan)
        res4 = exe.run_composition("app", registry=bad_reg, max_layer_errors=99)
        check("composite bolasi xato bo'lsa error",
              res4["nodes"].get("backend", {}).get("status") == "error")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------- #
# UCC — Universal UI Composition (ui_compose)
# ---------------------------------------------------------------------- #

def test_ui():
    # ---- 12. Dashboard uchun to'liq kompozitsiya ----
    plan = compose_app("dashboard")
    check("dashboard ok", plan["ok"] is True)
    check("layers topildi (barg->ildiz)", len(plan["layers"]) >= 3)
    check("exec_order to'liq", len(plan["exec_order"]) >= 50)

    # ---- 13. Overlap — qavatlar va bosh menyu xalaqit qilmasligi ----
    check("dashboard overlap yo'q", plan["overlaps"] == [])
    check("bounds toza", plan["bounds"] == [])

    # ---- 14. Boshqa app'lar ham toza ----
    for app in ("login", "chat", "settings", "profile", "mobile_app"):
        p = compose_app(app)
        check(f"{app} ok + no overlap",
              p["ok"] and p["overlaps"] == [])

    # ---- 15. G'isht (brick) tahlili — takroriy elementlar aniqlanadi ----
    bricks = brick_stats(compose_app("dashboard")["spec"])
    check("brick reuse hisoblanadi", bricks["reuse_ratio"] >= 0)
    check("takroriy brick bor", bricks["reusable_bricks"] > 0)

    # ---- 16. Ataylab qoplangan element -> aniqlanadi ----
    spec = compose_app("dashboard")["spec"]
    # nav qavatiga kontentga tegib turuvchi element qo'shamiz (xuddi dashboard
    # kontent 244,90 da — sidebar bilan kesishmasligi kerak)
    for st in spec["stages"]:
        if st["id"] == "layout":
            st["elements"].append(
                {"type": "rect", "x": 150, "y": 300, "w": 120, "h": 60,
                 "fill": "#ff0000"})
    overlaps = check_overlaps(spec)
    check("ataylab qoplangan element topiladi", len(overlaps) > 0)

    # ---- 17. Chegara tekshiruvi — canvas'dan chiqqan element ----
    spec2 = compose_app("dashboard")["spec"]
    for st in spec2["stages"]:
        if st["id"] == "bg":
            st["elements"][0]["x"] = -50  # canvas tashqarisiga chiqaramiz
    check("canvas'dan chiqqan element aniqlanadi",
          any("chegarasidan" in w for w in check_bounds(spec2)))

    # ---- 18. Reparent qilingan element MUTLAQ koordinatada tekshiriladi ----
    # sidebar (200,0) ichidagi elementning absolyut x = 200+150=350 > 300
    spec3 = {
        "canvas": {"w": 300, "h": 300},
        "stages": [
            {"id": "layout", "elements": [
                {"type": "rect", "id": "sb", "x": 200, "y": 0, "w": 100, "h": 300}]},
            {"id": "nav", "elements": [
                {"type": "text", "id": "t1", "parent": "sb", "x": 150, "y": 10,
                 "w": 80, "h": 12}]},
        ],
    }
    check("reparent element absolute chegarada tekshiriladi",
          any("chegarasidan" in w for w in check_bounds(spec3)))
    # ... lekin canvas ichida qolgan reparent element xato bermaydi
    spec4 = {
        "canvas": {"w": 600, "h": 400},
        "stages": [
            {"id": "layout", "elements": [
                {"type": "rect", "id": "sb", "x": 0, "y": 64, "w": 220, "h": 336}]},
            {"id": "nav", "elements": [
                {"type": "text", "id": "t1", "parent": "sb", "x": 20, "y": 30,
                 "w": 150, "h": 16}]},
        ],
    }
    check("ichkaridagi reparent element toza", check_bounds(spec4) == [])

    # ---- 19. spec -> cards -> composition engine ----
    reg = spec_to_cards(compose_app("dashboard")["spec"])
    engine = CompositionEngine(reg)
    check("spec cards valid", engine.validate() == [])
    check("explode ishlaydi", engine.explode("app", 1).get("app") == 1)

    # ---- 20. Standartlar mavjud ----
    check("standartlar bor", UI_STANDARDS["min_el_w"] == 8
          and UI_STANDARDS["overlap_tolerance"] >= 0)

    # ---- 21. compose_ui (spec to'g'ridan-to'g'ri, build_plan'ga delegatsiya) ----
    direct = compose_ui(compose_app("dashboard")["spec"])
    check("compose_ui ok + exec_order", direct["ok"] and len(direct["exec_order"]) > 0)
    check("compose_ui explosion build_plan'dan", "app" in direct["explosion"])


def main():
    test_engine()
    test_executor()
    test_ui()
    print()
    print("ALL COMPOSITION + UI TESTS PASSED")


if __name__ == "__main__":
    raise SystemExit(main())
