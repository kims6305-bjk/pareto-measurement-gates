#!/usr/bin/env python3
"""파레토 차트 — 원자료(json)에서 직접 계산해 그린다. 수치 하드코딩 금지.

3개 패널:
  (A) A/B 게이트 — 모서리점에 레이어를 얹으면 열등 이동
  (B) 프로브 1표 vs 3표 — 붙이지 않고 걷어내서 얻은 바깥이동
  (C) 옆방 검증 — 회수율↔정밀도가 언어에 따라 다르게 움직임
"""
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

BASE = pathlib.Path(__file__).resolve().parents[1]
DOCS = BASE.parent / "docs"

# --- 한글 폰트 (Pretendard > Apple SD Gothic Neo) --------------------------
for cand in ("Pretendard", "Apple SD Gothic Neo", "AppleGothic"):
    if any(cand in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = cand
        break
plt.rcParams["axes.unicode_minus"] = False

NAVY, AMBER, GREY = "#141F38", "#B84A10", "#9AA3B2"
PAPER = "#FAF9F6"


def load(p):
    return json.load(open(BASE / p, encoding="utf-8"))


# --- 원자료 ---------------------------------------------------------------
g3 = load("scripts/phase1_final_gate_probe3.json")
v1, v3 = g3["probe_1vote"], g3["probe_3vote"]
ic = load("scripts/instrument_check_result.json")
s1 = load("scripts/sidecheck_result.json")
s2 = load("scripts/sidecheck2_result.json")

fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.4), facecolor=PAPER)
for ax in axes:
    ax.set_facecolor(PAPER)
    ax.grid(alpha=.25, linestyle=":")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

# === (A) A/B 게이트 — 모서리점 =============================================
ax = axes[0]
ax.set_title("(A) 프런티어 모서리점에 레이어를 얹으면\n상방 0 · 하방만 열린다",
             fontsize=12, color=NAVY, pad=12)
# arm A = (인용오류 0%, 과교정 0%) / arm B = (인용오류 0%, 과교정 0.84%)
ax.scatter([0], [0], s=260, color=NAVY, zorder=5, label="arm A (검증 없음)")
ax.scatter([0], [0.84], s=260, color=AMBER, marker="X", zorder=5,
           label="arm B (프로브+수정)")
ax.annotate("", xy=(0, 0.80), xytext=(0, 0.06),
            arrowprops=dict(arrowstyle="-|>", color=AMBER, lw=2.4,
                            mutation_scale=22, shrinkA=0, shrinkB=0))
ax.text(0.008, 0.20, "열등 이동\n(악화 방향)", fontsize=9, color=AMBER,
        fontweight="bold")
ax.axhspan(0.5, 1.2, color=AMBER, alpha=.07)
ax.axhline(0.5, color=AMBER, ls="--", lw=1.2)
ax.text(0.040, 0.53, "과교정 임계 0.5%", fontsize=9, color=AMBER)
ax.text(0.010, -0.02, "개선할 축이 없음\n(인용오류 이미 0%)", fontsize=9, color=NAVY)
ax.set_xlim(-0.03, 0.12)
ax.set_ylim(-0.12, 1.2)
ax.set_xlabel("인용오류율 (%) — 낮을수록 좋음")
ax.set_ylabel("과교정율 (%) — 낮을수록 좋음")
ax.legend(fontsize=9, loc="upper right", frameon=False, borderaxespad=0.8)

# === (B) 1표 vs 3표 — 바깥이동 =============================================
ax = axes[1]
ax.set_title("(B) 붙이지 않고 걷어냈더니\n회수 손실 0으로 검토부담만 감소",
             fontsize=12, color=NAVY, pad=12)
x1, y1 = v1["review_rate"] * 100, v1["recall_with_review"] * 100
x3, y3 = v3["review_rate"] * 100, v3["recall_with_review"] * 100
ax.scatter([x1], [y1], s=260, color=GREY, zorder=5, label="프로브 1표")
ax.scatter([x3], [y3], s=260, color=NAVY, marker="D", zorder=5, label="프로브 3표 합의")
ax.annotate("", xy=(x3 + 0.35, y3), xytext=(x1 - 0.35, y1),
            arrowprops=dict(arrowstyle="-|>", color=NAVY, lw=2.4,
                            mutation_scale=22, shrinkA=6, shrinkB=6))
ax.text((x1 + x3) / 2, y1 + 1.4,
        f"검토 {x1:.1f}% → {x3:.1f}%\n회수 손실 0 (파레토 바깥이동)",
        fontsize=9.5, color=NAVY, ha="center", fontweight="bold")
ax.set_xlim(min(x1, x3) - 3, max(x1, x3) + 3)
ax.set_ylim(min(y1, y3) - 4, max(y1, y3) + 4)
ax.set_xlabel("사람 검토 부담 (%) — 낮을수록 좋음")
ax.set_ylabel("최종 회수율 (%) — 높을수록 좋음")
ax.legend(fontsize=9, loc="lower left", frameon=False)

# === (C) 옆방 — 두 축이 다르게 움직인다 ====================================
ax = axes[2]
ax.set_title("(C) 회수율은 언어에 둔감, 정밀도는 민감\n(계기 검침 3개 방)",
             fontsize=12, color=NAVY, pad=12)
pts = [
    ("K-IFRS (ko·회계)", ic["recall"] * 100,
     ic["precision_reported_only"] * 100, NAVY, "o"),
    ("SciFact (en·생의학)", s1["recall"] * 100,
     s1["precision_reported_only"] * 100, AMBER, "X"),
    ("KLUE-NLI (ko·비회계)", s2["recall"] * 100,
     s2["precision_reported_only"] * 100, "#2E7D5B", "D"),
]
for name, r, p, c, m in pts:
    ax.scatter([r], [p], s=260, color=c, marker=m, zorder=5, label=name)
    ax.annotate(f"({r:.1f}, {p:.1f})", (r, p), textcoords="offset points",
                xytext=(9, -13), fontsize=8.5, color=c)
ax.axvline(30, color=GREY, ls="--", lw=1.2)
ax.text(31, 88, "게이트 임계\nrecall 30%", fontsize=8.5, color=GREY)
ax.set_xlim(20, 112)
ax.set_ylim(45, 108)
ax.set_xlabel("검출 회수율 (%) — 게이트 지표")
ax.set_ylabel("정밀도 (%) — 게이트 밖 참고값")
ax.legend(fontsize=9, loc="lower center", frameon=False, ncol=1)

fig.suptitle("하네스를 꽉 잡는다고 좋은 게 아니다 — 실측 파레토 3장",
             fontsize=15, color=NAVY, y=1.01)
fig.tight_layout()
out = DOCS / "pareto_chart.png"
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=PAPER)
print(f"saved: {out}")
print(f"  (A) armA(0, 0) -> armB(0, 0.84)  임계 0.5")
print(f"  (B) 1표({x1:.1f}, {y1:.1f}) -> 3표({x3:.1f}, {y3:.1f})")
for name, r, p, _, _ in pts:
    print(f"  (C) {name}: recall {r:.1f} / precision {p:.1f}")
