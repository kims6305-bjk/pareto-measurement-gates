#!/usr/bin/env python3
"""인포그래픽 2장 — 사례글용. 수치는 원자료(json)에서 읽는다(하드코딩 금지).

  (1) failure_ladder.png  — 4단계가 매번 다른 층에서 실패한 구조
  (2) gate_flow.png       — 사전등록 게이트 순서 (실행 전 커밋이 왜 방어인가)
"""
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

BASE = pathlib.Path(__file__).resolve().parents[1]
DOCS = BASE.parent / "docs"

for cand in ("Pretendard", "Apple SD Gothic Neo", "AppleGothic"):
    if any(cand in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = cand
        break
plt.rcParams["axes.unicode_minus"] = False

NAVY, AMBER, GREEN, GREY = "#141F38", "#B84A10", "#2E7D5B", "#9AA3B2"
PAPER = "#FAF9F6"

ic = json.load(open(BASE / "scripts/instrument_check_result.json", encoding="utf-8"))


def box(ax, x, y, w, h, text, fc, tc="white", fs=10.5, weight="normal"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                facecolor=fc, edgecolor="none"))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            color=tc, fontsize=fs, fontweight=weight, linespacing=1.5)


def arrow(ax, x1, y1, x2, y2, color=GREY, lw=2.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=18, color=color, lw=lw,
                                 shrinkA=2, shrinkB=2))


# ═══ (1) 실패 사다리 ═══════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12.5, 7.4), facecolor=PAPER)
ax.set_facecolor(PAPER)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

ax.text(.5, .955, "같은 실수를 네 번 — 매번 다른 층에서", ha="center",
        fontsize=17, color=NAVY, fontweight="bold")
ax.text(.5, .905, "표본 크기는 셌지만, 측정 도구가 신호를 잡는지는 안 쟀다",
        ha="center", fontsize=11.5, color=GREY)

rows = [
    ("Phase 1", "프로브가 문제를 잡는가", "판정 불가", "프로브 판정의 재현성", AMBER),
    ("Phase 2", "표본을 늘리면 판정되는가", "판정 불가", "사람 라벨 기저율 (3.3%)", AMBER),
    ("Phase 3", "채점 단위가 판정을 왜곡하는가", "판정 불가", "저지 판정 기저율 (0%)", AMBER),
    ("계기 검침", "측정 도구는 멀쩡한가", "PASS", "— (드디어 이걸 쟀다)", GREEN),
]
y0, h, gap = .70, .105, .035
ax.text(.075, y0 + h + .035, "단계", fontsize=10, color=GREY, fontweight="bold")
ax.text(.315, y0 + h + .035, "무엇을 물었나", fontsize=10, color=GREY, fontweight="bold")
ax.text(.585, y0 + h + .035, "결과", fontsize=10, color=GREY, fontweight="bold")
ax.text(.795, y0 + h + .035, "안 잰 것", fontsize=10, color=GREY, fontweight="bold")

for i, (stage, q, res, missed, c) in enumerate(rows):
    y = y0 - i * (h + gap)
    box(ax, .04, y, .13, h, stage, NAVY, fs=11, weight="bold")
    ax.text(.315, y + h / 2, q, ha="center", va="center", fontsize=10.5, color=NAVY)
    box(ax, .525, y, .12, h, res, c, fs=10.5, weight="bold")
    ax.text(.795, y + h / 2, missed, ha="center", va="center",
            fontsize=10.5, color=c, fontweight="bold")
    if i < 3:
        arrow(ax, .10, y - .004, .10, y - gap + .004, GREY, 1.6)

ax.add_patch(FancyBboxPatch((.04, .045), .92, .105,
                            boxstyle="round,pad=0.012,rounding_size=0.02",
                            facecolor="#EFF3F0", edgecolor=GREEN, lw=1.6))
ax.text(.5, .098,
        f"계기 검침 = 라벨된 소표본에 판정기를 그대로 물려 recall을 잰다  →  "
        f"실측 {ic['recall']*100:.1f}% ({ic['n_detected']}/{ic['n_problem']}), "
        f"3판 SPLIT {ic['n_split']}건",
        ha="center", va="center", fontsize=11.5, color=NAVY, fontweight="bold")
fig.tight_layout()
out1 = DOCS / "failure_ladder.png"
fig.savefig(out1, dpi=150, bbox_inches="tight", facecolor=PAPER)
print(f"saved: {out1}")

# ═══ (2) 게이트 흐름 ═══════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(12.5, 6.6), facecolor=PAPER)
ax.set_facecolor(PAPER)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

ax.text(.5, .945, "결과를 보기 전에 커밋한다 — 그것이 유일한 방어",
        ha="center", fontsize=17, color=NAVY, fontweight="bold")
ax.text(.5, .893, "커밋 타임스탬프가 “결과 보고 기준을 고치지 않았다”의 증거가 된다",
        ha="center", fontsize=11.5, color=GREY)

steps = [
    ("①  가설·판정기준·N 선언", "무엇을 보면 채택/기각인지\n숫자로 미리 고정", NAVY),
    ("②  채점기 작성 + 커밋", "판정 로직을 결과 보기 전에\n박아 둔다", NAVY),
    ("③  계기 검침 (본 실행의 1/10)", "도구가 신호를 잡는가?\nFAIL이면 본 실행 금지", GREEN),
    ("④  본 실행 → 채점기 그대로 실행", "수정 없이 돌린다.\n여기서 고치면 전부 무효", NAVY),
    ("⑤  결과가 나쁘면 그대로 보고", "표본·기준을 바꾸지 않는다\n(= optional stopping 회피)", AMBER),
]
w, h = .158, .30
gap = (1 - .05 * 2 - w * 5) / 4
for i, (title, desc, c) in enumerate(steps):
    x = .05 + i * (w + gap)
    box(ax, x, .40, w, h, "", c)
    ax.text(x + w / 2, .40 + h - .075, title, ha="center", va="center",
            color="white", fontsize=9.4, fontweight="bold")
    ax.text(x + w / 2, .40 + h / 2 - .055, desc, ha="center", va="center",
            color="white", fontsize=8.9, linespacing=1.6)
    if i < 4:
        arrow(ax, x + w + .004, .55, x + w + gap - .004, .55, GREY, 2.0)

ax.add_patch(FancyBboxPatch((.06, .10), .88, .21,
                            boxstyle="round,pad=0.014,rounding_size=0.02",
                            facecolor="#FDF2E3", edgecolor=AMBER, lw=1.6))
ax.text(.5, .245, "이 실험에서 실제로 일어난 일",
        ha="center", fontsize=11.5, color=AMBER, fontweight="bold")
ax.text(.5, .162,
        "③을 건너뛰고 ④로 갔다  →  1,650콜을 태우고 “검정 불가”\n"
        "뒤늦게 ③을 165콜로 돌리자, 도구는 멀쩡했고 틀린 건 저자의 진단이었다",
        ha="center", va="center", fontsize=11, color=NAVY, linespacing=1.7)
fig.tight_layout()
out2 = DOCS / "gate_flow.png"
fig.savefig(out2, dpi=150, bbox_inches="tight", facecolor=PAPER)
print(f"saved: {out2}")
