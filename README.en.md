# pareto-measurement-gates — Gates that decide whether to adopt a self-improvement, and the measurement discipline behind them

**English** | [한국어](README.md) | [中文](README.zh-CN.md)

> 📌 **Renamed 2026-08** — formerly `reflection-probe-gate` / `probe-graph`.
> Old URLs remain alive via GitHub's 301 redirect. The reflection-probe
> experiment (Phases 1–3) is this repo's **starting point and one chapter**;
> the current subject is the **adoption gate and measurement discipline** it produced.

This repository contains a **verification subgraph** skill that plugs into a
citation-grounded QA pipeline (a RAG bot), together with the complete **A/B
measurement harness** used to judge whether it actually helps.

The headline result first: **the main probe of this repository (P1) was
rejected by its own measurement gate.** The value here is not a "universal
verification prompt" but (1) three probes designed from the literature and
(2) the reproducible end-to-end **judgment procedure that filtered them out
before adoption** (preregistration → blind grading → McNemar test).

And in the four stages that followed (Phase 1–3 + the instrument check), the
gate caught **its own failures** as well. The numbers with the highest reuse
value are on the gate side, not the probe side:

| Gate metric | Measured | Meaning |
|---|---|---|
| Instrument check detection recall | **81.8%** (9/11) | Confirms the measuring tool catches signal **before** the main run |
| Instrument check 3-run reproducibility | **0 SPLIT** / 55 | Verdicts do not wobble |
| Side-room validation (English·biomedical / Korean·non-accounting) | **2/2 PASS**, recall 100% | The procedure works even when domain, language, and labeler all change |
| Diagnostic cost | **1,650 calls → 165 calls** | Root-causing a failure at one tenth the cost |
| Probe 3-vote consensus (Phase 1) | Recall held at 90%, review burden 38.9%→35.2%, **0 automated false positives** | An outward Pareto move obtained by **removing**, not adding |

![A/B measurement verdict chart](docs/ab_verdict_chart.png)

> 📖 The full record of the single day this repo was built — design rationale, four
> consecutive failures, and the gate catching the author's own misdiagnosis — is kept
> in order in the [case study](docs/CASE_STUDY.en.md).
>
> 🧭 A one-week **field report** of running this gate on production data (three
> instrument failures, gap metrology, four meta-harness rounds, 8 diagrams, Korean):
> [`docs/field-report/FIELD_REPORT.md`](docs/field-report/FIELD_REPORT.md)

## Why this exists (motivation)

The starting point was a paper from Anthropic's interpretability team:

> **"Verbalizable Representations Form a Global Workspace in Language Models"**
> (Anthropic, 2026, transformer-circuits.pub/2026/workspace)

The paper shows that LLMs contain a privileged set of representations that can
be put into words, and that **counterfactual reflection** — training a model so
that when you interrupt it and ask "what are you thinking right now?" it states
its principles — also improves actual behavior in the uninterrupted case. It
further reports a **BUT-gap** (88%): cases where the model internally registers
an objection but does not reflect it in its output.

The paper's core technique (J-lens) requires residual stream access, so API
users cannot apply it. This skill therefore translates only the causal finding —
"**what the model would say if asked is what it is silently reasoning**" — to
the prompt level: a design that inserts a **reflection probe** as a pipeline
node, asking after answer generation, "point out the parts of this answer you
cannot support with evidence."

> **Scope note**: this repository is **not an implementation of the paper.**
> The paper's counterfactual reflection is a training (fine-tuning) technique;
> this repository is an inference-time prompt verifier. The paper is the design
> motivation only and does not validate the effect of P1/P2/P3 here — that
> judgment rests entirely on the repository's own A/B gate below.

## A naive implementation is harmful (design process)

Before implementing, the author reviewed 8 papers on self-correction, and the
counter-evidence was consistent: **naive probes actually degrade performance.**

| Paper | What it contributed to this design |
|---|---|
| Huang et al., *Large Language Models Cannot Self-Correct Reasoning Yet* (arXiv:2310.01798) | "Assume the answer is wrong" prompts cost up to −9.5pp (CSQA). Correct→incorrect flips always outnumber incorrect→correct → anchors A1 ("presume the answer is likely already correct") and A5 ("confirm agreement, do not hunt for problems") |
| Dhuliawala et al., *Chain-of-Verification (CoVe)* (arXiv:2309.11495) | Factored verification (not showing the draft prose to the verifier) raised FACTSCORE 55.9→71.4. Yes/no verification questions induce sycophancy bias → P1 takes only the claim list as input, plus A6 (mandatory verbatim source excerpt) |
| FBC/EIR line of work (verify-first ablation) | Anchoring on "independent re-verification before editing + fix only concrete errors" moved EIR (correct→incorrect flips) from 2% to 0%, McNemar p<10⁻⁴. Under the same budget, 3-iteration refine (86.6) < Self-Consistency (93.4) → **revise loop cap = 1**, plus A2 and A3 |
| Madaan et al., *Self-Refine* (arXiv:2303.17651) | Failure analysis: 61% were "inappropriate edits" → A4 ("if unsupported, flag it only; do not replace it with different content") |
| Shinn et al., *Reflexion* (arXiv:2303.11366) | The limiting conditions of reflection driven by external signals |
| Manakul et al., *SelfCheckGPT* (arXiv:2303.08896) | The place of sampling-based self-checking — the basis for not adopting it here |
| Tian et al. (arXiv:2305.14975) · Xiong et al. (arXiv:2306.13063) | A single verbalized confidence number clusters in overconfidence (80–100%); top-2 verbalized confidence calibrates better → A7 (high/medium/low + two alternative candidates) |
| Obfuscation Atlas (FAR.AI, ICML 2026) | Making the count of probe flags a KPI does not produce honesty; it optimizes for evading the probe → the "do not optimize for flag count" rule |
| Morris et al., *How Much Do Language Models Memorize?* (ICML 2026) | A memorization limit of ~3.6 bits per parameter → pulling standard/article numbers from memory yields errors → no parametric citation; citations must go through verbatim RAG excerpts |

These grounds are baked into the probe prompts as **anchors A1–A7**
(`skill/references/probe-prompts.md` — includes a per-anchor table of source
figures).

### The three probes

| Probe | Edit authority | Over-correction risk | Use |
|---|---|---|---|
| P1 citation cross-check | Indirect (triggers revise, cap = 1) | Low (suppressed by anchors) | Batch answer verification |
| P2 verify-first | Itself | Empirically 0 (FBC) | System prompt for the real-time path |
| P3 risk enumeration | **None** | **Structurally 0** | Nightly audit, routing to humans |

## Measurement ① — synthetic stress test (QA of the probe itself)

The first check was that the probe "catches planted errors and does not force
spurious flags onto correct answers" (`harness/`). 5 correct answers + 5 answers
with planted errors (misquoted article numbers, altered figures, claims outside
the evidence).

- run1: 9.5/10 — **found 1 needs_revision logic inconsistency**: the model
  correctly assigned verdict='근거없음' ("unsupported") yet emitted needs_revision=false.
  → Lesson: **do not trust the model for verdict fields; derive them in code via
  `any(verdict != "일치")`** ("match") — the Korean literals are the actual
  runtime schema and must be kept verbatim (reflected in the skill)
- run2 (after the fix): 5/5 errors localized, 0 spurious flags, 0 failures on
  verbatim quote existence, JSON 10/10 — pass

## Measurement ② — the A/B gate: and P1 failed it

**Preregistration** (`ab/ab_questions_FROZEN.json`, frozen and not to be
modified): 119 questions built on 12 publicly available K-IFRS standards =
84 normal + 17 no_answer (hallucination bait) + 18 distractor (similar-paragraph
traps). The grading rules were fixed before the experiment as well.

**Execution**: same model, same day, arm A (no probe) vs arm B (P1 + revise).
Grading used (1) mechanical cross-checking of citation errors (the grader itself
validated against 6 negative controls) and (2) a **blind LLM judge** with the arm
labels hidden (presentation order shuffled too).

**Results** (full text: [`ab/AB_VERDICT.md`](ab/AB_VERDICT.md)):

| Gate | arm A | arm B | Verdict |
|---|---|---|---|
| Primary metric: citation error rate | 0/119 (0%) | 0/119 (0%) | p=1.0 — no room for improvement ❌ |
| Guardrail 1: answer accuracy | 99.2% | 99.2% | no degradation ✅ |
| Guardrail 2: over-correction rate | — | **0.84% > threshold 0.5%** | ❌ |

What the "0%" primary metric precisely means (added after external review, to
prevent over-reading):

- The mechanical grader checks citation **structure, address, and quote
  existence** — 0/238 errors at this layer.
- Claim↔evidence **semantic agreement** was verified separately: all 238 answers
  were regraded claim-by-claim with an LLM judge (`claude-sonnet-4-6`,
  fail-closed, full judge transcripts published). Result: **0 semantic
  contradictions, 3/238 (1.3%) beyond-evidence claims** — perfectly symmetric
  across A/B, so the verdict is unchanged. Full report:
  [`gate/SEMANTIC_REGRADE.md`](gate/SEMANTIC_REGRADE.md)
- The 95% CI upper bound for 0/238 semantic contradictions is ~1.3% (rule of
  three). "0% error rate" is a point estimate and should be read with this
  interval.
- The 17 no_answer questions (14.3%) were correctly abstained in both arms —
  0 successful hallucination baits.

**Verdict: P1 rejected.** The single degradation case (Q092) is a live
reproduction of the EIR mechanism described in the literature — the probe, per
its rules, judged an "inference beyond the evidence" to be unsupported, and
revise, per its rules, hedged only that item; the result was an answer that
contradicted its own first sentence. It is an instance of **components that are
each individually correct combining to damage a correct answer**, exactly as in
the Self-Refine failure analysis (61% inappropriate edits).

### Lessons

1. **With a strong generation model and an evidence-attached structure, citation
   errors do not occur in the first place.** Even in the distractor traps, 0
   misattributions. If a verification layer has nothing to catch, the upside is 0
   and only the downside (over-correction) remains — not insurance, but pure cost.
2. Conditions under which adopting P1 is justified: environments where the
   generation model actually produces citation errors (weaker models, no attached
   evidence, reliance on parametric citation). **Measure your baseline error rate
   first; if it is 0%, do not attach P1.**
3. P3 (no edit authority) and P2 (verify-first anchors) are unaffected by this
   verdict — their over-correction is structurally 0 or empirically 0.
4. Without a judgment gate, a pure-cost layer would have shipped to production on
   the reasoning that "we added verification, so it must be safer." **The most
   reusable part of this repository is not the probe but the gate.**

## A Pareto reading — clamping down on the harness is not optimal

Restated in one sentence, this experiment becomes an economics Pareto argument:
**verification strength is not a free dial but a movement between two competing
metrics (error detection ↔ over-correction).**

- arm A was already at (citation errors 0%, accuracy 99.2%) — a corner point on
  the frontier, with no axis left to improve.
- Adding a verification layer on top of that, arm B was a **Pareto-inferior
  move**: no metric went up (upside 0) and one metric went down
  (over-correction −0.84%).
- Q092 is a live instance of the deadweight loss of over-regulation — both the
  regulation (the probe) and the enforcement (revise) followed their own rules,
  yet the combined result was a net welfare loss.
- From this angle the identity of the McNemar gate is clear: **a device that
  detects a Pareto-inferior move before it is adopted.** The intuition "more
  verification is safer" is true only inside the frontier and false on it.

The limits of the claim are stated as well: this measurement compares two points
on the verification-strength dial (no verification vs P1 + revise); it is not a
map of the whole frontier. The claim the data supports is not "we found the
optimum" but "**an inferior move was empirically identified**." Drawing the
frontier itself would require several levels of verification strength (e.g.,
P2 only / tuning P1 anchor strength / changing the revise threshold) and
measuring each point with the same gate.

## Measurement ③ — the four stages after: the gate catching its own failures

After the A/B verdict, four more stages were run to answer "then why did the
probe flag those false positives?" **Three consecutive stages returned
inconclusive**, and the fourth localized the cause. This section is the most
reusable part of the repository — because the kind of failure was different
every time.

| Stage | What it asked | Result | What it did not measure |
|---|---|---|---|
| Phase 1 | Does the probe catch problems? | Inconclusive | **Reproducibility** of the probe's verdicts |
| Phase 2 | Does more sample make it decidable? | Inconclusive | Human-label **base rate** (3.3%) |
| Phase 3 | Does the grading unit distort the verdict? | Inconclusive | Judge-verdict **base rate** (0%) |
| Instrument check | **Is the measuring tool itself sound?** | **PASS** | — |

### Phase 1 — discovering there is no reproducibility

Running the judge 3 times with an identical prompt and identical model, 5 of 54
items came out different every time. In other words, **reporting a single-run
number as performance is misreporting.** All grading from then on was fixed to a
3-run majority vote.

An outward Pareto move came out of that discipline. Switching the probe verdict
from 1 vote to a **3-vote consensus**:

- Recall 90.0% → 90.0% (**0 loss**)
- Human review burden 38.9% → **35.2%**
- 0 false positives in the automated band, held

The improvement came not from **adding** metrics but from **removing** the
unstable portion.

### Phase 2 — base rate beats sample size

The plan was to secure statistical power by adding human labels. An internal
pilot design labeled 30 items and read **only the base rate**: **3.3% (1/30)**.
Even labeling the full candidate pool of 201 items would yield an expected 6.7
problem cases, short of the 55 required.

→ **171 items were left unlabeled and the phase was terminated.** Completing the
original plan would have been Pareto-inferior. The pilot was not discarded but
nested inside the main sample, avoiding the optional stopping critique.

### Phase 3 — 1,650 calls burned, hypothesis untestable

The outcome variable was switched from human labels to **flips in the judge's
verdict**, driving the human cost to 0. A single-variable A/B toggling only the
presence of sibling-claim context, 3 runs per condition, 1,650 calls total.

Result: **0 of 271 problem verdicts in condition A (control).** With nothing to
flip, the hypothesis was never tested. The 6 observed disagreements all went the
opposite direction (becoming stricter) and were not significant at McNemar
p=0.125.

### Instrument check — localizing the cause in 165 calls

At this point two hypotheses diverged, with opposite prescriptions:

- **Hypothesis I (broken instrument)**: the judge is configured such that it
  cannot detect problems → fix the judge
- **Hypothesis C (corpus gap)**: the judge is fine and the sample had no problems
  → change the sample

Diffing the prompt code made Hypothesis I look likely. The Phase 3 judge was
**missing** the `[전체 답변]` ("full answer") block and the "distortion of the
rule" instruction that the validated Phase 1 judge had.

So before fixing anything, it was **measured**. The Phase 3 judge prompt was
applied to 55 human-labeled items without changing a single character
(importing the builder as-is). The verdict criteria and the scorer were
committed **before** looking at the results.

| Item | Value |
|---|---|
| Detected out of 11 human-judged problems | **9** |
| Detection recall | **81.8%** Wilson 95% [52.3%, 94.9%] |
| CONTRADICTED detections | 7 |
| 3-run SPLIT | **0** |

**PASS — Hypothesis I was rejected. The author's diagnosis was wrong.**
Even without the instruction, the judge caught problems well, and its 3-run
reproducibility was in fact better (0 wobbles) than the complex Phase 1 judge
(5 wobbles). Without the instrument check, the fix would have followed the
diagnosis and **a perfectly sound tool would have been "fixed" and that reported
as an improvement.**

### 🔴 The real cause — two disciplines in conflict

The cause was in the sample, and its source was the preregistration rule itself.

To avoid circular reasoning, Phase 3 adopted the rule "the sample that generated
the hypothesis is excluded from the confirmatory set." Measurement showed that
of the 28 questions where problems had been found, **0 were in the confirmatory
set and all 28 were in the excluded set.**

> **Excluding the hypothesis-generating sample to avoid circularity also
> excludes the signal.**
> Not excluding it is circular; excluding it removes what there was to test.

This was not carelessness but **the result of following the preregistration
discipline faithfully**. It is a case of two disciplines (blocking circularity ↔
testability) colliding with each other.

The remedy is not to abandon exclusion, but to **confirm before the main run
that a base rate of the outcome variable survives the exclusion**. That is the
instrument check, and it costs one tenth of the main run.

### Three rules to take from these four stages

1. **Compute statistical power against the base rate of the outcome variable,
   not the sample size.** "N=264 secured" is only the denominator. How many of
   those will be judged problems is the numerator, and if the numerator is 0, no
   N can test anything.
2. **Before fixing the measuring tool, measure whether the tool catches signal.**
   A code diff yields a plausible hypothesis, not a verdict. In this repository
   that hypothesis turned out to be wrong.
3. **Do not report a single-run number as performance.** Judge verdicts do not
   reproduce.

Full text: [`gate/PHASE1_VERDICT.md`](gate/PHASE1_VERDICT.md) ·
[`gate/PHASE2_VERDICT.md`](gate/PHASE2_VERDICT.md) ·
[`gate/PHASE3_VERDICT.md`](gate/PHASE3_VERDICT.md) ·
[`gate/INSTRUMENT_CHECK_RESULT.md`](gate/INSTRUMENT_CHECK_RESULT.md)

The pre-declaration documents for each stage (`*_PREREGISTRATION.md`,
`INSTRUMENT_CHECK_PREREG.md`) were all **committed before execution**, and the
commit order is verifiable from the git history.

## Domain portability — this is not K-IFRS-specific

The only thing in this repository tied to K-IFRS is the **measurement data (the
question set)**:

| Layer | Domain-dependent | Notes |
|---|---|---|
| Skill body (3 probes + anchors A1–A7 + graph structure) | No | A "claim ↔ verbatim evidence" cross-check structure — applicable to any citation QA with source documents (statutes, case law, internal policies, papers, contracts, medical guidelines) |
| Gate procedure (preregistration → blind → McNemar) | No | The statistical procedure itself has no domain |
| Measurement data (`ab/ab_questions_FROZEN.json`, 119 questions) | K-IFRS | The author's operating domain simply happened to be accounting QA. Other domains substitute their own question sets |

The source literature behind the anchors comes from math (GSM8K), commonsense
(CSQA), and biography-writing (FACTSCORE) benchmarks, none of which relate to
accounting.

### Measured: validated in two side-rooms (2026-07-28)

The previous version of this README marked this section **"unverified"**,
because it held only a design claim with no measurement behind it. That marking
is replaced by the measurement below.

**The instrument check procedure was applied as-is to two datasets differing in
domain, language, and labeler.** The judge prompt was not altered by a single
character (the builder was imported), and the threshold was kept identical to
the original room. The pre-declaration was committed before execution.

| Room | Language | Domain | Labeler | recall | SPLIT | Verdict |
|---|---|---|---|---|---|---|
| Original room (K-IFRS) | Korean | Accounting standards | The author | 81.8% (9/11) | 0 | **PASS** |
| Side-room 1 ([SciFact](https://arxiv.org/abs/2004.14500)) | **English** | **Biomedical** | **External** | 100% (22/22) | 0 | **PASS** |
| Side-room 2 ([KLUE-NLI](https://arxiv.org/abs/2105.09680)) | Korean | **Non-accounting** | **External** | 100% (22/22) | 0 | **PASS** |

What matters is that **PASS also came out of the two rooms whose labelers are
external**. In the original room the author labeled the data and instrument-checked
a judge the author had built, so the criteria could have been unconsciously
aligned; that explanation is not supported.

#### 🔴 And the axes split — recall is insensitive to language, precision is sensitive

Side-room 1 alone changed language, domain, and labeler simultaneously, making
causal attribution impossible. Side-room 2 separated them by **fixing the
language to Korean**.

| Metric | SciFact (en) | KLUE-NLI (ko) |
|---|---|---|
| Detection recall (gate metric) | 100% | 100% |
| 3-run unanimous agreement | 72.7% | **92.7%** |
| False positives (human S → problem verdict) | **36.4%** | **3.0%** |
| Precision (reference only, outside the gate) | 64.7% | 95.7% |

The failure of **missing** a problem was 0 in both languages, while the failure
of **calling a non-problem a problem** rose 12-fold in English. Under the
condition of a Korean prompt plus English evidence, the judge declared "outside
the scope of the evidence" more often.

**Which side is right is not something this experiment answers** — the judge may
be stricter, or its understanding of the evidence may be shallower under the
cross-language condition. Distinguishing them requires a condition with the
prompt translated into English, and that changes one more variable, so it is
left as a separate experiment.

#### What is still not claimed

- **This is not "it works in every domain."** What has been validated is 3 domains.
- **Cross-model portability is unverified**: the judge is still a single
  `claude-sonnet-4-6`.
- Side-room 2 (NLI) is an entailment task, different in character from citation
  verification.

Full text: [`gate/SIDECHECK_PREREG.md`](gate/SIDECHECK_PREREG.md) (pre-declaration) ·
[`gate/SIDECHECK_RESULT.md`](gate/SIDECHECK_RESULT.md) (result)

For the same reason, **the "P1 rejected" verdict is valid only within these
measurement conditions (K-IFRS + strong model + attached evidence)**. In other
domains, with weaker models, or without attached evidence, P1 may well be
effective — which is why the first step of the porting procedure is "measure the
baseline error rate in your own environment first," and this gate is the
automation of that judgment.

### Do existing harnesses really lack an adoption gate?

The claim "an adoption gate is needed" only holds if existing implementations can
be shown to lack one. This repo dissects one public reference implementation
(`PrimeIntellect-ai/prime-agent`, commit `a18809e`) at file:line granularity.

- **Form is enforced by code** — schema violations and concurrent-edit conflicts
  are reliably rejected.
- **The improvement judgment is delegated** — it is a single boolean
  `shouldRefine === true`, and the `expectedOutcome` each proposal stores is read
  in exactly **one place: the next prompt's rendering**. Self-improvement
  accumulates, but no code path measures whether it is improvement.
- Conversely, its **concurrency safeguards exceed anything in this repo**
  (generation-counter invalidation, baseline comparison right before apply,
  atomic writes). The two implementations guard different axes.

The same document also preserves **one absence-proof error of this project and
its correction** — a wrong file path was grepped and the tool's failure was read
as "0 hits"; a re-run broke it. An absence proof that does not reproduce is not
evidence.

Full text: [`gate/RELATED_HARNESSES.md`](gate/RELATED_HARNESSES.md)

### This is not a new problem — mapping to recursive estimation and pruning

Placing a **gain** on a repeatedly-updated estimator, and asking about
significance *before* growing, are both named prescriptions already.

- **The gain `K` in recursive least squares is where the adoption gate sits.**
  The reference implementation is effectively `K = 1` (apply whatever is
  proposed); this repo puts a Pareto verdict in that slot.
- **Autoregressive exposure bias reproduces exactly** — an agent re-reads the
  skills it wrote itself in the next session, so without ground-truth reinjection
  (periodic verification) drift is not blocked in principle.
- **Decision-tree pre-pruning** is structurally the same as instrument checking.
  In practice a 330-call check blocked a 1,650-call search before it started —
  along with pre-pruning's known weakness (the horizon effect).

🔴 However, **none of RLS's premises — linearity, convexity, convergence
guarantees — hold for a harness.** In particular RLS's gain is *computed* from a
covariance, and no such covariance exists here; it is replaced by a pre-registered
decision rule. The document records where the mapping breaks and which analogies
were deliberately not used.

Full text: [`gate/THEORY_MAPPING.md`](gate/THEORY_MAPPING.md)

### When the instrument is wrong, the verdict flips — five failure cases

![Measurement failures (cases 1–3)](docs/measurement_failures.png)

However well a gate is designed, **if the numbers it reads are wrong** the verdict
is meaningless. Five measurement failures from a production citation-QA pipeline
and its evaluation harness that actually flipped a verdict (or nearly did):

- **Counting-unit error** — `precision`'s denominator was slots, so duplicate
  correct documents were double-counted. The reported 0.672 was a performance that
  did not exist, and that inflation made a legitimate improvement read as
  **DOMINATED**. Recomputed on unique documents, the ratio axis moved −0.004
  (effectively zero) while the absolute-count axis moved 5.80 → 6.35 —
  **a ratio axis cannot see deduplication.**
- **Preprocessing circularity** — the build inserted newlines, and the scorer then
  counted "line-initial, therefore a paragraph number," letting its own false
  positives justify themselves. The scorer was **rewritten three times**, finally
  retreating to "count only unambiguous noise" as a lower-bound estimate to obtain
  a defensible figure (3.55%).
- **Adjudication circularity** — candidates were being validated by the same
  signal that grouped them. A context-blind independent adjudicator re-judged all
  66 pairs → **0 DIFFERENT** (the automatically extracted "conflicts" did not
  exist). Confirmed only after resolving all 7 initial UNCLEAR cases on full text.
- **Baseline fabrication** — the A/B baseline arm was not the production entry
  point but a reproduction borrowing a single helper function. Five experiment
  runs compared against a system that did not exist; the real entry point measured
  **3.1×** the reproduction, and the intervention being tested was already wired in.
- **Scoring-unit error** — gold answers keyed by file paths of one corpus while
  80% of system evidence came from other corpora, so correct answers scored zero
  (joining on content identifiers fixes it); the same answers read 0.244 vs
  **0.750** depending on scoring granularity. Several "improvements" were
  commissioned on top of this misdiagnosis — all rejected.

What the five share: **each was a situation where a wrong verdict was about to be
locked in first.** Doubting the instrument cost more than the improvements themselves —
and was justified all three times.

Full text: [`gate/MEASUREMENT_FAILURES.md`](gate/MEASUREMENT_FAILURES.md)

## Repository structure

```
skill/                  # Skill body (SKILL.md format for agent frameworks)
  SKILL.md              #   Graph structure, governing principles, measurement verdict record
  references/
    probe-prompts.md    #   Full text of the 3 probe prompts + per-anchor paper source figures
    evals.md            #   Binary quality gates (① self QA ② A/B gate)
skill-pareto/           # Pareto adoption-gate skill (the verdict procedure this experiment operationalizes)
  SKILL.md              #   Inferior-move / outward-move verdict rules + application map
harness/                # Measurement ①: synthetic stress test
  run_stress.py         #   Runner (separated from grading)
  cases.json            #   5 correct + 5 error-injected (based on synthetic evidence documents)
  evidence.md           #   Synthetic evidence document (not an actual standard)
  stress_results_run{1,2}.json
ab/                     # Measurement ②: A/B gate
  ab_questions_FROZEN.json  # 119 pre-registered questions (based on public K-IFRS standards)
  ab_results.json       #   Full raw output of both arms (for audit and regrading)
  ab_runner.py          #   Two-arm runner (incremental saves, resumable)
  grade_ab.py           #   Mechanical grading + blind judge + McNemar report
  merge_verify.py       #   Independent re-verifier used during question generation
  make_chart.py         #   Verdict chart generation
  ab_grades.json        #   Raw grading data
  AB_VERDICT.md         #   Full verdict text
gate/                   # Grading gate package + semantic-layer regrade + Phase 1–3 measurements
  src/reflection_gate/  #   Two-layer grader: deterministic (structure/address/excerpt) + semantic (LLM judge), fail-closed
  tests/                #   38 pytest cases (including 10 negative controls)
  SEMANTIC_REGRADE.md   #   Full 238-item regrade verdict (incl. human cross-check of 18 FLAGGED)
  LABELING_PROTOCOL.md  #   Human labeling protocol (committed before labeling started)
  PHASE1_VERDICT.md     #   Phase 1 verdict — no reproducibility found, 3-vote consensus adopted
  PHASE2_INTERNAL_PILOT.md  # Internal pilot design (base rate only, nested sample)
  PHASE2_PILOT_RESULT.md    # Pilot measurement — base rate 3.3%
  PHASE2_VERDICT.md     #   Phase 2 verdict — insufficient sample, terminated with 171 items unlabeled
  PHASE3_PREREGISTRATION.md # Phase 3 pre-declaration (committed before execution, McNemar threshold correction logged)
  PHASE3_VERDICT.md     #   Phase 3 verdict — untestable + cause (circularity blocking removed the signal)
  PHASE4_PREREGISTRATION.md # Phase 4 pre-declaration DRAFT (written before viewing Phase 3 results)
  INSTRUMENT_CHECK_PREREG.md   # Instrument check pre-declaration (committed before execution)
  INSTRUMENT_CHECK_RESULT.md   # Instrument check result — PASS, records that the author's diagnosis was wrong
  SIDECHECK_PREREG.md   #   Side-room validation pre-declaration (§8 committed before viewing side-room 1 results)
  SIDECHECK_RESULT.md   #   Results of both side-rooms — both PASS, recall↔precision axes split
  RELATED_HARNESSES.md  #   Reference-implementation dissection — measured absence of an adoption gate (incl. one absence-proof error of ours)
  THEORY_MAPPING.md     #   Mapping to RLS / autoregression / pruning + where the mapping breaks
  MEASUREMENT_FAILURES.md #  Five instrument failures — counting unit, preprocessing/adjudication circularity, baseline fabrication, scoring unit
  scripts/              #   Per-phase runners, scorers, raw data (scorers committed before viewing results)
docs/
  ab_verdict_chart.png
  pareto_chart.png      #   Pareto 3-panel (inferior move, outward move, axis split)
  failure_ladder.png    #   How the four phases each failed at a different layer
  gate_flow.png         #   The five stages of the pre-registration gate
  measurement_failures.png # Instrument-failure figure, cases 1-3 (figures parsed from the doc — no hardcoding)
  CASE_STUDY.md         #   Case study — the full day of development (ko/en/zh)
STATE.md                # Multi-session state digest (accumulated decisions, blockers, verification gates)
```

## Reproduction

```bash
# Prerequisite: claude CLI (or replace run_llm() with the LLM call of your choice)
cd ab
python3 ab_runner.py            # Run both arms (incremental per-question saves, resumable)
python3 grade_ab.py mech        # Mechanical citation grading
python3 grade_ab.py judge       # Blind judge (~250 calls)
python3 grade_ab.py report      # McNemar verdict table
python3 make_chart.py           # Chart (requires matplotlib)
```

### Reproducing the instrument check (recommended entry point)

The thing **most worth running first** in this repository is the instrument
check. It confirms in 165 calls whether the verifier in your own environment
catches signal.

```bash
cd gate
for r in run1 run2 run3; do
  .venv/bin/python scripts/instrument_check_run.py $r
done
.venv/bin/python scripts/instrument_check_score.py   # applies the pre-declared criteria automatically
```

The verdict is computed automatically from the threshold in
`INSTRUMENT_CHECK_PREREG.md` §4 (recall ≥ 30%).
**If it FAILs, do not start the main experiment** — a "no effect" obtained while
the tool cannot catch signal is a failure of measurement, not of the treatment.

To port this to another domain, only the label sheet read by `load_units()` in
`instrument_check_run.py` needs replacing (id / question / evidence /
claim_text / human labels S·C·I).

### Reproducing the side-room validation (domain portability)

This is the measurement that applied the same procedure to two public datasets.
The original data is not redistributed; the scripts fetch it directly from each
source.

```bash
cd gate
.venv/bin/python scripts/sidecheck_fetch.py          # SciFact (CC BY-NC 2.0)
.venv/bin/python scripts/sidecheck_build_units.py    # 55 stratified items, fixed seed
.venv/bin/python scripts/sidecheck2_build_units.py   # KLUE-NLI (CC BY-SA 4.0)
for r in run1 run2 run3; do
  .venv/bin/python scripts/sidecheck_run.py $r --room 1
  .venv/bin/python scripts/sidecheck_run.py $r --room 2
done
.venv/bin/python scripts/sidecheck_score.py --room 1
.venv/bin/python scripts/sidecheck_score.py --room 2
```

## References

- Anthropic (2026). *Verbalizable Representations Form a Global Workspace in Language Models.* transformer-circuits.pub/2026/workspace
- Huang, J. et al. (2023). *Large Language Models Cannot Self-Correct Reasoning Yet.* arXiv:2310.01798
- Dhuliawala, S. et al. (2023). *Chain-of-Verification Reduces Hallucination in Large Language Models.* arXiv:2309.11495
- Madaan, A. et al. (2023). *Self-Refine: Iterative Refinement with Self-Feedback.* arXiv:2303.17651
- Shinn, N. et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning.* arXiv:2303.11366
- Manakul, P. et al. (2023). *SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection.* arXiv:2303.08896
- Tian, K. et al. (2023). *Just Ask for Calibration.* arXiv:2305.14975
- Xiong, M. et al. (2023). *Can LLMs Express Their Uncertainty?* arXiv:2306.13063
- FAR.AI (2026). *Obfuscation Atlas.* ICML 2026 — probe gaming / policy obfuscation
- Morris, J. et al. (2026). *How Much Do Language Models Memorize?* ICML 2026
- Wadden, D. et al. (2020). *Fact or Fiction: Verifying Scientific Claims.* EMNLP 2020, arXiv:2004.14500 — side-room validation 1 (SciFact)
- Park, S. et al. (2021). *KLUE: Korean Language Understanding Evaluation.* NeurIPS 2021 D&B, arXiv:2105.09680 — side-room validation 2 (KLUE-NLI)

### Reference implementation (§"Do existing harnesses really lack an adoption gate?")

- PrimeIntellect-ai. *prime-agent.* github.com/PrimeIntellect-ai/prime-agent —
  the dissected target, pinned at commit `a18809e`. File:line citations and
  reproduction commands: [`gate/RELATED_HARNESSES.md`](gate/RELATED_HARNESSES.md)

### Theory mapping (§"This is not a new problem")

These are mappings of *structure*, not transplants of theorems. The premises each
one assumes — and where they fail to hold for a harness — are in
[`gate/THEORY_MAPPING.md`](gate/THEORY_MAPPING.md) §4.

- Åström, K. J. & Wittenmark, B. (1994). *Adaptive Control* (2nd ed.), Addison-Wesley —
  the RLS gain `K` and forgetting factor `λ`; the basis for placing the adoption
  gate at the gain
- Ljung, L. (1999). *System Identification: Theory for the User* (2nd ed.), Prentice Hall —
  the covariance `P` from which the gain is computed. **`P` is precisely what is
  missing here**
- Bengio, S. et al. (2015). *Scheduled Sampling for Sequence Prediction with
  Recurrent Neural Networks.* NeurIPS 2015, arXiv:1506.03099 — exposure bias and
  teacher forcing; maps to re-reading self-written skills
- Breiman, L. et al. (1984). *Classification and Regression Trees.* Wadsworth —
  pre-/post-pruning; instrument checking corresponds to pre-pruning
- Quinlan, J. R. (1987). *Simplifying Decision Trees.* Int. J. Man-Machine Studies 27(3) —
  the horizon effect of pre-pruning, inherited by the IC-1 FAIL interpretation

### Meta-harness literature survey (decision 15)

A six-source survey looking for front-as-parent-selection. The finding: absent in
the self-improvement layer, only partially present in other domains (equation
discovery, routing). Table in
[`gate/PARETO_META_HARNESS_DESIGN.md`](gate/PARETO_META_HARNESS_DESIGN.md) §2.
🔴 The warning TRACE-Router left behind — **claims of front occupancy require a
random-mixture control** ("random mixture also traces the line segment").

## License and data provenance

- **Code, skill, and documentation: MIT** — free to use, modify, and redistribute
  with no domain restrictions.
- The bundled question set (`ab/ab_questions_FROZEN.json`) was generated solely
  from **publicly available paragraphs of Korean International Financial
  Reporting Standards (K-IFRS)** and contains no private or internal data. This
  is a data provenance notice, not a restriction on the skill's scope of
  application — see the "Domain portability" section above.
