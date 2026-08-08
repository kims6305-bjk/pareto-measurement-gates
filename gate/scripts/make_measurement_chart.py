#!/usr/bin/env python3
"""계측 실패 3건 도식 — gate/MEASUREMENT_FAILURES.md README용.

수치 출처는 MEASUREMENT_FAILURES.md 본문(사설 커밋 6335bcd0/7edf8ba3/94b0cbd3+d4259f06의
익명화 요약). 원자료가 이 레포에 없으므로 문서에서 파싱해 그린다 —
문서와 그림이 어긋나면 즉시 죽도록 assert를 건다.
"""
import pathlib
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch

BASE = pathlib.Path(__file__).resolve().parents[1]
DOC = BASE / 'MEASUREMENT_FAILURES.md'
OUT = BASE.parent / 'docs' / 'measurement_failures.png'

for f in ("Pretendard", "Apple SD Gothic Neo", "AppleGothic"):
    if any(f.lower() in x.name.lower() for x in font_manager.fontManager.ttflist):
        plt.rcParams['font.family'] = f
        break
plt.rcParams['axes.unicode_minus'] = False

NAVY = '#141F38'; AMBER = '#B84A10'; PAPER = '#FAF9F6'
GRAY = '#8A8F98'; RED = '#C62828'; GREEN = '#2E7D32'

# ── 문서에서 수치 파싱 (하드코딩 금지 규율) ───────────────────────────
txt = DOC.read_text(encoding='utf-8')

def need(pattern, label):
    m = re.search(pattern, txt)
    if not m:
        raise SystemExit(f"🔴 문서에서 {label}을 못 찾음 — 그림과 문서가 어긋난다: {pattern}")
    return m

# 사례 1: 표에서 슬롯기준/고유문서 precision과 계수축
p_slot = float(need(r'슬롯 기준.*?\*\*(0\.\d+)\*\*', '슬롯기준 precision').group(1))
p_uniq_off, p_uniq_on = (float(x) for x in
    need(r'precision@10 \(고유문서 기준\) \| (0\.\d+) \| (0\.\d+)', '고유문서 precision').groups())
cnt_off, cnt_on = (float(x) for x in
    need(r'distinct_correct_docs\*\* \| (\d\.\d+) \| \*\*(\d\.\d+)\*\*', '계수축').groups())

# 사례 2: 오염률 (🔴 그룹 순서 주의 — 문서는 "전체 N refs 중 M건(P%)")
noise_tot, noise_n, noise_pct = need(
    r'전체 ([\d,]+) refs 중 ([\d,]+)건\((\d+\.\d+)%\) 오염', '오염률').groups()
noise_pct = float(noise_pct)
# 자릿수로 역전 검증 — 오염분이 전체보다 크면 즉시 죽는다
assert int(noise_n.replace(',', '')) < int(noise_tot.replace(',', '')), \
    f"🔴 오염 {noise_n} >= 전체 {noise_tot} — 파싱 그룹이 뒤집혔다"
rewrites = 3
assert '세 번' in txt, "🔴 재작성 횟수 문구가 바뀜"

# 사례 3: 판정 결과
pairs = int(need(r'(\d+)쌍 전수 판정', '쌍 수').group(1))
unclear = int(need(r'1차 UNCLEAR (\d+)건', 'UNCLEAR 수').group(1))

fig = plt.figure(figsize=(13.5, 5.4), facecolor=PAPER)
fig.suptitle('계측 실패 3건 — 계측기가 틀리면 판정이 뒤집힌다',
             fontsize=15.5, fontweight='bold', color=NAVY, y=0.975)
fig.text(0.5, 0.905,
         '수록 기준: 계측 오류가 판정을 실제로 뒤집었거나 뒤집을 뻔했던 것만 · '
         '세 건 모두 "개선했다"고 보고할 수 있었던 상황',
         ha='center', fontsize=9, color=GRAY)

# ── 패널 1: 계수 단위 오류 ──────────────────────────────────────────
ax1 = fig.add_axes([0.055, 0.14, 0.255, 0.60], facecolor=PAPER)
ax1.set_title('① 계수 단위 오류\n분모를 슬롯으로 잡아 중복을 보상',
              fontsize=10.5, color=NAVY, pad=8)
bars = ax1.bar([0, 1, 2], [p_slot, p_uniq_off, p_uniq_on],
               width=0.55, color=[RED, NAVY, AMBER])
for i, v in enumerate([p_slot, p_uniq_off, p_uniq_on]):
    ax1.text(i, v + 0.018, f'{v:.3f}', ha='center', fontsize=10,
             fontweight='bold', color=[RED, NAVY, AMBER][i])
ax1.text(0, p_slot / 2, '존재하지\n않는 성능', ha='center', va='center',
         fontsize=8.5, color=PAPER, fontweight='bold')
ax1.set_xticks([0, 1, 2])
ax1.set_xticklabels(['슬롯 분모\n(틀린 축)', '고유문서\nOFF', '고유문서\nON'],
                    fontsize=9, color=NAVY)
ax1.set_ylim(0, 0.82); ax1.set_ylabel('precision@10', color=NAVY, fontsize=9)
ax1.annotate('', xy=(1, 0.70), xytext=(0, 0.70),
             arrowprops=dict(arrowstyle='->', color=RED, lw=1.6))
ax1.text(0.5, 0.725, f'부풀림 −{p_slot - p_uniq_off:.3f}', ha='center',
         fontsize=8.5, color=RED, fontweight='bold')
for s in ('top', 'right'):
    ax1.spines[s].set_visible(False)
ax1.spines['left'].set_color(GRAY); ax1.spines['bottom'].set_color(GRAY)
ax1.tick_params(colors=GRAY, labelsize=8)

ax1b = ax1.twinx()
ax1b.plot([1, 2], [cnt_off, cnt_on], 'o-', color=GREEN, lw=2, ms=7)
ax1b.text(1.5, cnt_on + 0.62,
          f'계수축 +{cnt_on - cnt_off:.2f}\n(비율축은 −{p_uniq_off - p_uniq_on:.3f})',
          ha='center', fontsize=8.5, color=GREEN, fontweight='bold',
          bbox=dict(boxstyle='round,pad=0.28', fc=PAPER, ec='none', alpha=0.92))
ax1b.set_ylim(4.9, 7.9)
ax1b.set_ylabel('distinct_correct_docs', color=GREEN, fontsize=8.5)
ax1b.tick_params(colors=GREEN, labelsize=8)
for s in ('top', 'left'):
    ax1b.spines[s].set_visible(False)
ax1b.spines['right'].set_color(GREEN)

# ── 패널 2: 전처리 순환 ────────────────────────────────────────────
ax2 = fig.add_axes([0.385, 0.14, 0.245, 0.60], facecolor=PAPER)
ax2.set_title('② 전처리 순환\n파이프라인 산출물로 그 파이프라인을 채점',
              fontsize=10.5, color=NAVY, pad=8)
ax2.set_xlim(0, 10); ax2.set_ylim(0, 10); ax2.axis('off')

box = dict(boxstyle='round,pad=0.5', fc=PAPER, ec=NAVY, lw=1.3)
ax2.text(5, 8.6, '빌드가 문단번호 앞에\n개행을 삽입', ha='center', va='center',
         fontsize=9, color=NAVY, bbox=box)
ax2.text(5, 5.6, '계측기: "줄머리니까\n문단번호"로 카운트', ha='center', va='center',
         fontsize=9, color=RED,
         bbox=dict(boxstyle='round,pad=0.5', fc=PAPER, ec=RED, lw=1.3))
ax2.add_patch(FancyArrowPatch((5, 7.75), (5, 6.55), mutation_scale=15,
                              color=NAVY, lw=1.5, arrowstyle='->'))
ax2.add_patch(FancyArrowPatch((7.4, 6.0), (7.4, 8.2), mutation_scale=15,
                              color=RED, lw=1.5, arrowstyle='->',
                              connectionstyle='arc3,rad=-0.45'))
ax2.text(9.3, 7.1, '자기 오탐을\n자기가 정당화', ha='center', va='center',
         fontsize=8.5, color=RED, fontweight='bold')
ax2.text(5, 3.15, f'계측기 {rewrites}회 재작성 후\n'
                  '"명백한 노이즈만" 하한 추정으로 후퇴',
         ha='center', va='center', fontsize=9, color=NAVY,
         bbox=dict(boxstyle='round,pad=0.5', fc='#EFEDE8', ec=GRAY, lw=1))
ax2.text(5, 1.25, f'{noise_pct}%  ({noise_n} / {noise_tot} refs)',
         ha='center', fontsize=13, fontweight='bold', color=AMBER)
ax2.text(5, 0.45, '방어 가능한 하한 — 정밀도를 대가로 지불',
         ha='center', fontsize=8, color=GRAY)

# ── 패널 3: 판정 순환 ──────────────────────────────────────────────
ax3 = fig.add_axes([0.70, 0.14, 0.265, 0.60], facecolor=PAPER)
ax3.set_title('③ 자동 판정 순환\n묶은 신호로 묶인 것을 검증',
              fontsize=10.5, color=NAVY, pad=8)
ax3.set_xlim(0, 10); ax3.set_ylim(0, 10); ax3.axis('off')

ax3.text(2.6, 8.4, '유사도 신호', ha='center', va='center', fontsize=9,
         color=NAVY, bbox=box)
ax3.text(2.6, 5.7, f'후보 {pairs}쌍\n"견해 대립"', ha='center', va='center',
         fontsize=9, color=NAVY, bbox=box)
ax3.add_patch(FancyArrowPatch((2.6, 7.75), (2.6, 6.55), mutation_scale=14,
                              color=NAVY, lw=1.4, arrowstyle='->'))
ax3.add_patch(FancyArrowPatch((1.1, 6.2), (1.1, 8.0), mutation_scale=14,
                              color=RED, lw=1.4, arrowstyle='->',
                              connectionstyle='arc3,rad=0.5'))
ax3.text(0.55, 7.15, '순환', ha='center', va='center', fontsize=8.5,
         color=RED, fontweight='bold')

ax3.text(7.4, 8.4, '독립 판정자\n(맥락 미제공)', ha='center', va='center',
         fontsize=9, color=GREEN,
         bbox=dict(boxstyle='round,pad=0.5', fc=PAPER, ec=GREEN, lw=1.4))
ax3.add_patch(FancyArrowPatch((4.3, 5.9), (6.6, 7.6), mutation_scale=14,
                              color=GREEN, lw=1.5, arrowstyle='->'))
ax3.text(7.4, 5.5, 'DIFFERENT\n0건', ha='center', va='center',
         fontsize=12, fontweight='bold', color=GREEN)
ax3.text(5, 3.0, f'1차 UNCLEAR {unclear}건 → 전문 재판정으로 전건 해소',
         ha='center', fontsize=8.5, color=NAVY)
ax3.text(5, 1.9, '"대립 0건" ≠ "한쪽만 봐도 된다"', ha='center',
         fontsize=9, color=AMBER, fontweight='bold')
ax3.text(5, 1.0, '형식논리상 충돌이 아니어도 실무 위험은 남는다',
         ha='center', fontsize=8, color=GRAY)

fig.text(0.5, 0.045,
         '계측기를 의심하는 데 든 비용이 개선 자체보다 컸다 — 그리고 세 번 다 정당했다.',
         ha='center', fontsize=9.5, color=NAVY, style='italic')

OUT.parent.mkdir(exist_ok=True)
fig.savefig(OUT, dpi=170, facecolor=PAPER)
print(f"저장: {OUT}")
print(f"파싱 검증 — 슬롯 {p_slot} / 고유 {p_uniq_off}→{p_uniq_on} / "
      f"계수 {cnt_off}→{cnt_on} / 노이즈 {noise_pct}% / {pairs}쌍 / UNCLEAR {unclear}")
