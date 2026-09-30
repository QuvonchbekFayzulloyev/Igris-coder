# -*- coding: utf-8 -*-
"""IGRIS_FULL_AUDIT V4 infografika rasmlarini qayta yaratish.

Eski PNG'lar hozirgi baholar bilan almashtiriladi:
  image1.png  Header (4.5x4.36 in)  — umumiy baho 84/100, 211 test
  image2.png  4 texnik kategoriya (6.5x3.07 in)
  image3.png  UI/UX donut 78
  image4.png  UI/UX detallar (donut kichik)
  image5.png  Memory bar 76
  image6.png  Brain donut 87
  image7.png  Brain detallar
  image8.png  web-ai-bridge donut 86
  image9.png  web-ai-bridge detallar
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

BG = "#0d0d10"
TXT = "#e8e8ef"
MUT = "#9a9aa8"
TEAL = "#2bcab6"
AMBER = "#f1b723"
RED = "#e5484d"
BLUE = "#4d9de0"
GREEN = "#3ddc84"
GRID = "#22222a"

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG,
    "savefig.facecolor": BG, "text.color": TXT,
    "axes.edgecolor": GRID, "axes.labelcolor": TXT,
    "xtick.color": MUT, "ytick.color": MUT,
    "font.family": "DejaVu Sans",
})

OUT = "_audit_media_new"
import os
os.makedirs(OUT, exist_ok=True)


def score_color(s):
    if s >= 85:
        return GREEN
    if s >= 75:
        return TEAL
    if s >= 65:
        return BLUE
    return RED


def save(fig, name, dpi=100):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=dpi, transparent=False)
    plt.close(fig)
    print("saved", path)


# ---------------------------------------------------------------- header
def header():
    fig, ax = plt.subplots(figsize=(4.5, 4.36))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.text(50, 94, "IGRIS CODER", ha="center", va="center",
            fontsize=26, fontweight="bold", color=TXT)
    ax.text(50, 86.5, "TO'LIQ AUDIT  \u2022  SIFAT O'LCHAMLARI  \u2022  TUZATISH REJASI",
            ha="center", va="center", fontsize=9, color=MUT)

    # big gauge ring
    theta = np.linspace(0, 2 * np.pi, 200)
    ax.plot(50 + 30 * np.cos(theta), 50 + 30 * np.sin(theta),
            color=GRID, lw=14, solid_capstyle="round", zorder=1)
    ax.plot(50 + 30 * np.cos(theta), 50 + 30 * np.sin(theta),
            color=TEAL, lw=14, solid_capstyle="round", zorder=2,
            alpha=0.9)
    # segment marks
    for k in range(8):
        a = np.pi / 2 + k * np.pi / 4
        ax.plot([50 + 27 * np.cos(a), 50 + 33 * np.cos(a)],
                [50 + 27 * np.sin(a), 50 + 33 * np.sin(a)],
                color=BG, lw=3, zorder=3)
    ax.text(50, 62, "84", ha="center", va="center", fontsize=52,
            fontweight="bold", color=TXT, zorder=4)
    ax.text(50, 49, "/ 100", ha="center", va="center", fontsize=15,
            color=MUT, zorder=4)
    ax.text(50, 40, "UMUMIY BAHO", ha="center", va="center", fontsize=11,
            color=AMBER, fontweight="bold", zorder=4)

    # stat chips
    chips = [("211", "doimiy test"), ("A2 \u2713", "confidence kalibratsiyasi"),
             ("RAG \u2713", "fail himoyasi")]
    y = 24
    for val, lab in chips:
        ax.add_patch(FancyBboxPatch((16, y - 2.5), 22, 6.5,
                     boxstyle="round,pad=0.4,rounding_size=1.2",
                     fc="#15151c", ec=score_color(84), lw=1.2))
        ax.text(27, y + 1.2, val, ha="center", va="center", fontsize=11,
                fontweight="bold", color=TXT)
        ax.text(27, y - 3.2, lab, ha="center", va="center", fontsize=6.2,
                color=MUT)
        y -= 11
    fig.tight_layout(pad=0.2)
    save(fig, "image1.png")


# ------------------------------------------------- 4 texnik kategoriya
def tech_categories():
    cats = [("UI / UX", 78, "Yaxshi"), ("Memory", 76, "Yaxshi"),
            ("Brain", 87, "Kuchli"), ("web-ai-bridge", 86, "Kuchli")]
    fig, ax = plt.subplots(figsize=(6.5, 3.07))
    x = np.arange(len(cats))
    vals = [c[1] for c in cats]
    bars = ax.bar(x, vals, width=0.55, color=[score_color(v) for v in vals],
                  alpha=0.95, zorder=3)
    ax.set_ylim(0, 100)
    ax.set_xticks(x)
    ax.set_xticklabels([c[0] for c in cats], fontsize=10)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for b, (c, v, st) in zip(bars, cats):
        ax.text(b.get_x() + b.get_width() / 2, v + 2.5, f"{v}",
                ha="center", va="bottom", fontsize=15, fontweight="bold",
                color=TXT)
        ax.text(b.get_x() + b.get_width() / 2, 6, st, ha="center", va="bottom",
                fontsize=7.5, color=score_color(v))
    ax.set_title("4 TEXNIK KATEGORIYA \u2014 BAHO  (V4: 2026-08-12)",
                 fontsize=11, fontweight="bold", color=TXT, pad=8)
    ax.set_ylabel("Baho / 100", fontsize=8.5, color=MUT)
    fig.tight_layout(pad=0.5)
    save(fig, "image2.png")


# ------------------------------------------------- donut helper
def donut(score, title, subtitle, name, inner="", status=""):
    fig, ax = plt.subplots(figsize=(2.6, 1.71))
    frac = score / 100.0
    ax.pie([frac, 1 - frac], colors=[score_color(score), GRID],
           startangle=90, counterclock=False,
           wedgeprops=dict(width=0.24, edgecolor=BG, linewidth=2))
    ax.text(0, 0.12, str(score), ha="center", va="center", fontsize=20,
            fontweight="bold", color=TXT)
    ax.text(0, -0.18, "/100", ha="center", va="center", fontsize=8, color=MUT)
    if inner:
        ax.text(0, -0.52, inner, ha="center", va="center", fontsize=6.5,
                color=score_color(score))
    ax.text(0, -1.25, title, ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=TXT)
    ax.text(0, -1.55, subtitle, ha="center", va="center", fontsize=6.5,
            color=MUT)
    if status:
        ax.text(0, -1.95, status, ha="center", va="center", fontsize=7,
                fontweight="bold", color=score_color(score))
    ax.set(aspect="equal")
    fig.tight_layout(pad=0.1)
    save(fig, name)


# ------------------------------------------------- horizontal bar (memory)
def hbar(cats, title, name, note=""):
    fig, ax = plt.subplots(figsize=(6.5, 3.07))
    y = np.arange(len(cats))[::-1]
    vals = [c[1] for c in cats]
    ax.barh(y, vals, height=0.55, color=[score_color(v) for v in vals],
            alpha=0.95, zorder=3)
    ax.set_xlim(0, 100)
    ax.set_yticks(y)
    ax.set_yticklabels([c[0] for c in cats], fontsize=9)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for yi, (c, v) in zip(y, cats):
        ax.text(v + 2, yi, f"{v}", va="center", fontsize=12,
                fontweight="bold", color=TXT)
    ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
    if note:
        ax.text(0.5, -0.62, note, transform=ax.transAxes, fontsize=7,
                color=MUT, ha="center")
    fig.tight_layout(pad=0.5)
    save(fig, name)


# ================================================================ render
header()
tech_categories()

# UI/UX (image3 donut, image4 detail donut)
donut(78, "UI / UX", "Igris_Interface", "image3.png", "Yaxshi")
donut(76, "UI / UX", "Tauri \u2013 zaif backend", "image4.png", "a11y \u2716")

# Memory (image5 bar, image6 donut)
hbar([("Sxema to'liq", 88), ("Persistent", 80), ("RAG/MAG", 74),
      ("Sync", 60), ("Poisoning", 40)],
     "MEMORY AUDIT \u2014 modullar bo'yicha", "image5.png",
     note="Memory 76/100 \u2013 MultiAgentSync o'lik, poisoning ulanmagan")
donut(76, "Memory", "Igris_Memory", "image6.png", "Yaxshi")

# Brain (image7 bar, image8 donut)
hbar([("CAG kesh", 92), ("MAG xotira", 88), ("Intellekt (12)", 90),
      ("A2 confidence", 86), ("RAG himoyasi", 84)],
     "BRAIN AUDIT \u2014 modullar bo'yicha", "image7.png",
     note="Brain 87/100 \u2013 A2 kalibratsiya + verified='fail' RAG himoyasi, 211 test")
donut(87, "Brain", "Igris_brain", "image8.png", "Kuchli")

# web-ai-bridge (image9)
donut(86, "web-ai-bridge", "24 tool", "image9.png", "Kuchli")

print("done")
