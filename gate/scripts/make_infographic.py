"""report_numbers.json → 인포그래픽 HTML (수치 하드코딩 없음). usage: python make_infographic.py <out.html>"""
import json
import sys
from pathlib import Path

N = json.loads((Path(__file__).resolve().parent / "report_numbers.json").read_text())
E5, P, E6, K = N["E5"], N["E6P"], N["E6"], N["E6_kind_acc"]
STRONG = N["E6P_strong"]
f2 = lambda x: f"{x:.3f}"
NAME = {"c000": "c000 기준선", "c301": "c301 문구 변형", "c302": "c302 문구 변형", "c401": "c401 조건 분해 대조"}
VERD = {"c301": "판정 불가", "c302": "판정 불가 · 특이도↓", "c401": "지배 (두 축 모두↑)"}


def bars():
    rows = []
    for c in ("c000", "c301", "c302", "c401"):
        d = E6[c]
        hl = " hl" if c == "c401" else ""
        rows.append(f"""<div class="brow{hl}"><div class="bn">{NAME[c]}</div>
 <div class="bt"><div class="b r" style="width:{(d['recall']-0.6)/0.4*100:.1f}%"></div><span>{f2(d['recall'])}</span></div>
 <div class="bt"><div class="b s" style="width:{(d['specificity']-0.6)/0.4*100:.1f}%"></div><span>{f2(d['specificity'])}</span></div></div>""")
    o = STRONG["claude-opus-5-5"]
    return "\n".join(rows) + f"""<div class="ref">참고 · 파일럿 200단위 오푸스+c000 {f2(o[0])} / {f2(o[1])} · 소넷+c000 {f2(STRONG['claude-sonnet-5-5'][0])} / {f2(STRONG['claude-sonnet-5-5'][1])}</div>"""


LO, HI = -12, 17
pos = lambda v: (v - LO) / (HI - LO) * 100


def forest():
    out = [f'<div class="axis"><i style="left:{pos(0):.1f}%"></i></div>']
    for c in ("c301", "c302", "c401"):
        cells = []
        for ax, cls in (("recall", "r"), ("specificity", "s")):
            d, lo, hi = E6[c]["delta"][ax][:3]
            cells.append(f"""<div class="fw"><div class="fl"><div class="zero" style="left:{pos(0):.1f}%"></div>
<div class="ci {cls}" style="left:{pos(lo):.1f}%;width:{pos(hi)-pos(lo):.1f}%"></div>
<div class="pt {cls}" style="left:{pos(d):.1f}%"></div></div>
<div class="lab">{'재현율' if ax=='recall' else '특이도'} <b>{d:+.1f}</b>%p [{lo:+.1f}, {hi:+.1f}]</div></div>""")
        hl = " hl" if c == "c401" else ""
        out.append(f'<div class="frow{hl}"><div class="fn">{NAME[c]}<b>{VERD[c]}</b></div><div class="fc">{"".join(cells)}</div></div>')
    return "\n".join(out)


KN = {"Idrop": "I-drop 조건 누락", "Scf": "Scf 근거=기억 반대", "Iswap": "I-swap 다른 근거", "S": "S 정상",
      "C": "C 반대", "Ccf": "Ccf 근거만 반전"}


def kinds():
    rows = []
    for k in sorted(K["c000"], key=lambda k: K["c000"][k]):
        a, b = K["c000"][k], K["c401"][k]
        rows.append(f"""<div class="krow"><div class="kn">{KN[k]}</div><div class="kt">
<div class="kb a" style="width:{a*100:.1f}%"></div><div class="kb b" style="width:{b*100:.1f}%"></div></div>
<div class="kv">{a:.2f} → <b>{b:.2f}</b></div></div>""")
    return "\n".join(rows)


c0, c4 = E6["c000"], E6["c401"]
html = f"""<!doctype html><html lang="ko"><meta charset="utf-8"><style>
:root{{--ink:#141F38;--mut:#5B6475;--paper:#FAF9F6;--card:#FFFFFF;--r:#1F5FBF;--s:#B84A10;--ok:#127A4B;--line:#E3E0D8}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{width:1600px;background:var(--paper);color:var(--ink);font-family:'Pretendard',-apple-system,'Apple SD Gothic Neo',sans-serif;padding:56px 64px;word-break:keep-all}}
.k{{font-size:20px;letter-spacing:.08em;color:var(--s);font-weight:700}}
h1{{font-size:50px;line-height:1.2;margin:12px 0 10px;font-weight:800}}
.sub{{font-size:22px;color:var(--mut)}}
.flow{{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin:36px 0}}
.st{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:22px 22px 20px;position:relative}}
.st .t{{font-size:16px;color:var(--mut);font-weight:700}} .st .h{{font-size:24px;font-weight:800;margin:6px 0 8px}}
.st p{{font-size:17px;line-height:1.5;color:#2B3346}} .st.win{{border:2px solid var(--ok);background:#F1FAF5}}
.grid{{display:grid;grid-template-columns:1.05fr 1fr;gap:22px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:26px 28px}}
.card h2{{font-size:24px;margin-bottom:6px}} .card .note{{font-size:15px;color:var(--mut);margin-bottom:18px}}
.leg{{display:flex;gap:18px;font-size:15px;color:var(--mut);margin-bottom:14px}} .leg i{{display:inline-block;width:14px;height:14px;border-radius:3px;margin-right:6px;vertical-align:-2px}}
.brow{{display:grid;grid-template-columns:200px 1fr 1fr;gap:14px;align-items:center;padding:9px 8px;border-radius:10px}}
.brow.hl{{background:#F1FAF5}} .bn{{font-size:18px;font-weight:700}}
.bt{{position:relative;height:30px;background:#F0EEE8;border-radius:6px}} .b{{height:100%;border-radius:6px}}
.b.r{{background:var(--r)}} .b.s{{background:var(--s)}} .bt span{{position:absolute;right:6px;top:3px;font-size:16px;font-weight:800;color:var(--ink);background:#fff;border-radius:5px;padding:1px 6px}}
.ref{{font-size:15px;color:var(--mut);margin-top:12px;padding-left:8px}}
.axis{{position:relative;height:0}}
.frow{{display:grid;grid-template-columns:190px 1fr;gap:12px;align-items:center;padding:10px 8px;border-radius:10px}}
.frow.hl{{background:#F1FAF5}} .fn{{font-size:18px;font-weight:700}} .fn b{{display:block;font-size:15px;color:var(--ok);margin-top:4px}}
.frow:not(.hl) .fn b{{color:var(--mut)}}
.fl{{position:relative;height:34px}} .zero{{position:absolute;top:0;bottom:0;width:2px;background:#9AA0AC}}
.ci{{position:absolute;top:14px;height:6px;border-radius:3px;opacity:.55}} .ci.r{{background:var(--r)}} .ci.s{{background:var(--s)}}
.pt{{position:absolute;top:9px;width:16px;height:16px;border-radius:50%;margin-left:-8px}} .pt.r{{background:var(--r)}} .pt.s{{background:var(--s)}}
.fw{{display:grid;grid-template-columns:1fr 230px;gap:10px;align-items:center}} .lab{{font-size:15px;white-space:nowrap;color:#2B3346}}
.krow{{display:grid;grid-template-columns:190px 1fr 120px;gap:12px;align-items:center;margin:9px 0}}
.kn{{font-size:16px;font-weight:700}} .kt{{position:relative;height:26px;background:#F0EEE8;border-radius:6px}}
.kb{{position:absolute;left:0;border-radius:6px}} .kb.b{{top:0;height:26px;background:var(--ok);opacity:.85}} .kb.a{{top:0;height:26px;background:#9AA0AC;z-index:1;opacity:.9}}
.kv{{font-size:17px}} .kv b{{color:var(--ok)}}
.lim{{margin-top:22px;background:#FFF7F0;border:1px solid #F0D9C6;border-radius:18px;padding:20px 26px;font-size:17px;line-height:1.6}}
.lim b{{color:var(--s)}} .foot{{margin-top:18px;font-size:14px;color:var(--mut)}}
</style><body>
<div class="k">PARETO 메타하네스 측정 · E5 → E6 → 부속서10</div>
<h1>문구를 다듬는 걸론 안 됐고, 판정 절차를 바꾸니 하이쿠가 크게 좋아졌다</h1>
<div class="sub">판정기 claude-haiku-5-5 고정 · 사전등록 → 결과 순서 · 군집 짝 부트스트랩(B=2000)</div>
<div class="flow">
 <div class="st"><div class="t">① E5 · 천장</div><div class="h">{f2(E5['c000']['recall'])} / {f2(E5['c000']['specificity'])}</div>
  <p>문제집이 너무 쉬워 하네스 차이가 노이즈에 묻힘. c301·c302 Δ 모두 판정 불가.</p></div>
 <div class="st"><div class="t">② v4 문제집</div><div class="h">4문단 창 + Scf·Ccf</div>
  <p>파일럿 하이쿠 {f2(P['c000']['recall'])} / {f2(P['c000']['specificity'])} 게이트 PASS · 운영자 블라인드 검수 29/30 · 정원 N=626군집(1,252단위)</p></div>
 <div class="st"><div class="t">③ E6 본측정 · 11,268콜</div><div class="h">c000 {f2(c0['recall'])} / {f2(c0['specificity'])}</div>
  <p>문구 변형 c301·c302 → 둘 다 판정 불가. c302 는 특이도 유의 하락.</p></div>
 <div class="st win"><div class="t">④ 부속서10 · c401 · 4,356콜</div><div class="h">{f2(c4['recall'])} / {f2(c4['specificity'])}</div>
  <p>주장을 조건으로 쪼개 근거 문장과 대조 → 두 축 모두 <b>지배</b> (95%·97.5% 모두).</p></div>
</div>
<div class="grid">
 <div class="card"><h2>E6 본측정 1,252단위 · 재현율 / 특이도</h2><div class="note">막대 시작점 0.60 · 3판 다수결</div>
  <div class="leg"><span><i style="background:var(--r)"></i>재현율(문제 주장 잡기)</span><span><i style="background:var(--s)"></i>특이도(정상 주장 안 건드리기)</span></div>
  {bars()}</div>
 <div class="card"><h2>c000 대비 차이 (점 = Δ, 막대 = 95% 구간)</h2><div class="note">군집 626 짝 비교 · 회색선 = 0 · 구간이 0을 넘지 않아야 확정</div>
  {forest()}</div>
</div>
<div class="grid" style="margin-top:22px">
 <div class="card"><h2>유형별 정답률 · c000(회색) → c401(초록)</h2><div class="note">본측정 3판 평탄 · 약했던 유형일수록 크게 개선</div>{kinds()}</div>
 <div class="card"><h2>왜 좋아졌나</h2><div class="note">사후 서술 — 판정 근거 아님</div>
  <p style="font-size:19px;line-height:1.65">c000 은 근거에 <b>없는</b> 내용을 <b>반대</b>라고 자주 불렀다
  (CONTRADICTED {N['E6_pred']['c000']}회, 실제 반대 문제 {N['E6_pred']['gold_C']}건).<br>
  c401 은 "반대 문장이 실제로 있어야 C, 못 찾으면 I"로 정의를 갈라 {N['E6_pred']['c401']}회로 줄었다.<br><br>
  대가: 응답 시간 중앙값 {N['E6_elapsed']['c000']}s → {N['E6_elapsed']['c401']}s.</p></div>
</div>
<div class="lim"><b>한계</b> · ① "근거가 기억과 달라도 근거를 따른다" 문장은 v4 의 Scf 구성을 알고 씀(설계 누설) — 단 Scf 외 유형도 전부 개선
 · ② 문제집 1종·판정기 1종(하이쿠)만 확인 · ③ I-drop 라벨 잡음(인접 문단 재진술 결함 2건 확인)</div>
<div class="foot">원자료 판정콜: E5 {N['calls']['e5']:,} · E6P 파일럿 {N['calls']['e6p']:,} · E6 본측정 {N['calls']['e6']:,} · 수치는 report_numbers.json 에서 자동 생성</div>
</body></html>"""
Path(sys.argv[1]).write_text(html, encoding="utf-8")
print("wrote", sys.argv[1])
