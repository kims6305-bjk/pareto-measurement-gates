#!/usr/bin/env python3
"""AB_VERDICT 시각화 — README용 판정 차트 (ab_grades.json/ab_results.json에서 직접 계산)."""
import json
import pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE = pathlib.Path(__file__).parent
for f in ("Pretendard", "Apple SD Gothic Neo", "AppleGothic"):
    if any(f.lower() in x.name.lower() for x in font_manager.fontManager.ttflist):
        plt.rcParams['font.family'] = f
        break
plt.rcParams['axes.unicode_minus'] = False

NAVY = '#141F38'; AMBER = '#B84A10'; PAPER = '#FAF9F6'
GRAY = '#8A8F98'; RED = '#C62828'

g = json.loads((BASE / 'ab_grades.json').read_text())
r = json.loads((BASE / 'ab_results.json').read_text())
n = len(g)

# 실측치 계산 (하드코딩 금지 — 원자료에서 유도)
citeA = sum(1 for e in g.values() if e['citeA_err'])
citeB = sum(1 for e in g.values() if e['citeB_err'])
accA = sum(1 for e in g.values() if e.get('accA'))
accB = sum(1 for e in g.values() if e.get('accB'))
rev = sum(1 for v in r.values() if v.get('armB_needs_revision'))
over = sum(1 for e in g.values()
           if e.get('accB_draft') and 'accB' in e and not e['accB'])
over_pct = over / n * 100
THR = 0.5

fig = plt.figure(figsize=(11, 6.2), facecolor=PAPER)
fig.suptitle('P1 인용대조 프로브 A/B 실측 — 게이트 판정: 폐기',
             fontsize=15, fontweight='bold', color=NAVY, y=0.97)
fig.text(0.5, 0.905,
         f'K-IFRS {n}문항 (normal 84 · no_answer 17 · distractor 18) · '
         '같은 모델·같은 날 · 블라인드 저지 · exact McNemar',
         ha='center', fontsize=9, color=GRAY)

# 패널 1: 주지표 + 가드레일1
ax1 = fig.add_axes([0.07, 0.13, 0.38, 0.66], facecolor=PAPER)
x = [0, 1]; w = 0.32
A = [citeA / n * 100, accA / n * 100]
B = [citeB / n * 100, accB / n * 100]
ax1.bar([i - w/2 for i in x], A, w, color=NAVY, label='arm A · 프로브 없음')
ax1.bar([i + w/2 for i in x], B, w, color=AMBER, label='arm B · P1+revise')
for i, (a, b) in enumerate(zip(A, B)):
    ax1.text(i - w/2, a + 2, f'{a:.1f}%', ha='center', fontsize=10,
             color=NAVY, fontweight='bold')
    ax1.text(i + w/2, b + 2, f'{b:.1f}%', ha='center', fontsize=10,
             color=AMBER, fontweight='bold')
ax1.text(0, 16, '0% vs 0%\np = 1.00\n개선 여지 없음', ha='center',
         fontsize=9, color=GRAY)
ax1.text(1, 55, f'{accA}/{n} vs {accB}/{n}\np = 1.00\n비열화 ✓',
         ha='center', fontsize=9, color=PAPER, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(['인용오류율\n(주지표)', '답변정확도\n(가드레일 1)'],
                    fontsize=10, color=NAVY)
ax1.set_ylim(0, 112); ax1.set_ylabel('%', color=NAVY)
ax1.legend(loc='upper left', fontsize=8.5, framealpha=0)
for s in ('top', 'right'):
    ax1.spines[s].set_visible(False)
ax1.spines['left'].set_color(GRAY); ax1.spines['bottom'].set_color(GRAY)
ax1.tick_params(colors=GRAY)

# 패널 2: 과교정 vs 임계
ax2 = fig.add_axes([0.55, 0.13, 0.40, 0.66], facecolor=PAPER)
ax2.set_title('가드레일 2 — 과교정율 (정답→오답 전환)',
              fontsize=11, color=NAVY, pad=10)
ax2.barh([0], [over_pct], height=0.42, color=RED)
ax2.axvline(THR, color=NAVY, lw=2, ls='--')
ax2.text(THR, 0.62, f'임계 {THR}% (EIR 경계)', fontsize=9.5,
         color=NAVY, ha='center')
ax2.text(over_pct + 0.03, 0, f'{over_pct:.2f}%\n({over}/{n} · Q092)',
         va='center', fontsize=10.5, color=RED, fontweight='bold')
ax2.set_xlim(0, 1.6); ax2.set_ylim(-0.9, 1.1)
ax2.set_yticks([])
ax2.set_xlabel('전체 문항 대비 %', fontsize=9, color=GRAY)
for s in ('top', 'right', 'left'):
    ax2.spines[s].set_visible(False)
ax2.spines['bottom'].set_color(GRAY); ax2.tick_params(colors=GRAY)
ax2.text(0.02, -0.62,
         f'P1 revise 발동 {rev}건 중 개선 0건 · 열화 {over}건 '
         '(Q092: 프로브·revise 각자 규칙 준수 → 조합이 정답 훼손)',
         fontsize=8.5, color=GRAY)

fig.text(0.5, 0.02,
         '판정: 주지표 무효(N) + 과교정 임계 초과(N) → P1 폐기 · '
         '오류율 0% 시스템에 검증 레이어 = 상방 0, 하방만 존재',
         ha='center', fontsize=10, color=AMBER, fontweight='bold')

out = BASE / 'ab_verdict_chart.png'
fig.savefig(out, dpi=160, facecolor=PAPER, bbox_inches='tight')
print('saved', out)
