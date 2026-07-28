# Case Study — Pareto: Tightening the Harness Is Not Automatically Good

**English** | [한국어](CASE_STUDY.md) | [中文](CASE_STUDY.zh-CN.md)

> This is the development log of the single day on which this repo was built. It records the
> design rationale, the failures, and the adjudication process in order; for the summary of
> results, see the [README](../README.md).

**Repo**: the repo this document belongs to (MIT, README [KO](../README.md) / [EN](../README.en.md) / [ZH](../README.zh-CN.md))
**Scale**: 37 commits in one day, 2,145 LLM calls
**One line**: the author built a verification instrument, its own gate ruled that the instrument
should be discarded, four experiment stages then failed in a row, and at the end the gate caught
**the author's own misdiagnosis**.

---

## 0. Before the Write-Up — Terminology

This piece uses a handful of statistics and experimental-design terms. All of them are unpacked
first.

### What Pareto means

The word comes from the Italian economist Vilfredo Pareto. The core idea is **"a state in which
no one can be made better off without making someone else worse off."**

An everyday example: two people split eight slices of pizza. If the split is 4:4, then for me to
eat five slices the other person must drop to three. **A state in which raising one side
necessarily requires cutting the other** is the Pareto condition.

### What a Pareto frontier is

It is the **boundary line** connecting all those points where "no free gains remain."

- **Inside** the frontier = there is still waste. Both axes can still be improved.
- **On** the frontier = to gain on one axis you must give up on the other.
- **Outside** the frontier = unreachable with the current method.

### What Pareto optimal means

It means sitting on the frontier. One caution — **Pareto optimal is not "the single best point."**
Every point on the frontier is Pareto optimal. A point at recall 100% / precision 60% and a point
at recall 80% / precision 95% can **both** be Pareto optimal.
Which one to pick is decided not by statistics but **by the domain.**

### Pareto dominance — the criterion for an adoption decision

Candidate B **dominates** baseline A = B is at least as good as A on every metric and strictly
better on at least one.
If it dominates, adopting it is unconditionally safe. If it does not dominate, it is not an
improvement but a **trade.**

Two expressions that recur throughout this piece:
- **Pareto outward move**: the frontier itself was pushed out = a genuine improvement
- **Pareto-inferior move**: nothing got better and something got worse = a net loss

### What I mean by "Pareto engineering" in a meta-harness

This is the central perspective of this piece.

**Harness** = the apparatus that wraps an AI with checks, gates, and retries.
**Meta-harness** = the loop that evolves that harness itself automatically.

The publicly available meta-harness implementations today use a **single scalar** objective
function. Push "accuracy" up and you have won. But then **a mutation that burns unlimited
tokens, latency, and cost to raise accuracy always wins.** Degradation on the remaining axes
is never even measured.

The Pareto engineering I am describing is this:

> **The intuition that tightening the harness makes things better is true only inside the frontier.**
> On the frontier, whatever you tighten is paid for by cutting another axis.
> Therefore the objective must be a **vector** (performance, cost) rather than a scalar,
> and the adoption condition must be **"it achieved Pareto dominance"** rather than "the score went up."

And one more thing — **you must not force a mutation on every iteration.** If the baseline is
already at a corner of the frontier, the upside is 0 and only the downside is open, so the more
you force mutations the more negative the expected value becomes.
"There is nothing left to improve" must be a legitimate output.

### Reflection probe — what I meant by the term

An Anthropic interpretability team paper (*Verbalizable Representations Form a Global
Workspace in Language Models*, 2026) contains this finding:
**"what a model would say if asked" and "what the model silently reasons about" are causally linked.**
And the **BUT-gap** — where the model internally notices an objection yet does not reflect it in
the output — occurred 88% of the time.

The paper's main technique requires access to the model internals (residual stream), so API users
cannot apply it. So I **translated only that causal finding to the prompt level.**

> After the answer is fully produced, **insert a node that asks back: "tell me the parts of this
> answer for which you cannot cite evidence"** into the pipeline.

"Probe" originally denotes a diagnostic tool that pokes into the internals of a neural network;
I carried that over into **"a question asked back to the model itself."** In other words the word
means **a probe (diagnosis)**, not "a corrector." This distinction matters later — mistaking a
diagnostic tool for a performance-improvement tool produces a Pareto-inferior move.

### What an A/B gate is

**A/B**: running two versions that differ in exactly one thing under identical conditions and
comparing them. Here, arm A = no probe, arm B = probe attached.

**Gate**: the checkpoint that looks at that comparison and **mechanically decides adopt or discard.**
The important part is that the decision criteria are **fixed in advance, before seeing the results.**
If criteria are set after seeing results, a person will unconsciously pick criteria favorable to
their own outcome.

This experiment's gate had three layers:
1. **Primary metric** — this must improve for adoption to have a reason (citation error rate)
2. **Guardrail** — if this degrades, discard even if the primary metric improved (answer accuracy, over-correction rate)
3. **Statistical test** — is the difference chance or not (McNemar test)

### What a p-value is (what p=0.031 means)

**p-value = "the probability of seeing a difference this large purely by chance when there is no effect at all."**

Say you flip a coin 10 times and get 7 heads. Is it a rigged coin? Even a fair coin lands 7 heads
often enough → the p-value is large → you cannot say "it is rigged." But 70 heads out of 100 flips
is very unlikely for a fair coin → the p-value is small → "hard to attribute to chance."

By convention, **p < 0.05** is called "statistically significant." p=0.031 is a value that passes
that threshold.

The **McNemar test** used in this piece is the test for "the same subjects measured under two
conditions each." This experiment has exactly that structure — the same claims were scored with
and without the probe.

🔴 **I made a mistake here, and that too is on the record.** The pre-registration document said
"5 discordant pairs gives p=0.031," but that was **a calculation error that omitted the factor of
2 for a two-sided test.** The actual two-sided p-value for 5 pairs is 0.0625, which is not
significant, and the threshold is **6 pairs**. It was found while verifying the decision function
by independent recomputation, and **since it happened before results were seen, integrity was
unaffected.** Lesson: a decision formula must be recomputed once more by a different route before
it is used.

### What a baseline is

**The reference line against which improvement is measured.** The claim "our method is good"
always demands "compared to what?" That what is the baseline.

There is a reason the baseline is decisive in this piece. **If the baseline is already perfect,
there is no axis left to improve.** Then whatever verification layer you attach has zero upside
and only downside (side effects).
So the first practical rule this experiment produced is this:

> **Measure the baseline error rate before attaching a layer. If it is 0%, do not attach it.**

### What a label is — and why a human must assign it

**Label** = the answer key a human attaches to each case. It is what makes it possible to measure
"whether the machine's decision was right."

This experiment used three labels:

| Label | Meaning |
|---|---|
| **S (Supported)** | The claim is stated in, or directly derivable from, the provided evidence |
| **C (Contradicted)** | The evidence states something **opposite** to the claim |
| **I (Insufficient)** | Cannot be confirmed from the evidence alone. **Even if the statement is accounting-wise correct, if it lies outside the scope of the evidence it is I** |

🔴 The core rule of labeling: **do not ask "is this claim true." Ask only "does the provided
evidence support this claim."** The moment you begin adjudicating true/false with domain
knowledge, the labels are contaminated.

And labels are assigned **blind** — the column showing what the machine decided is hidden.
Labeling while looking at the machine's decision produces not an answer key but a copy of the
machine's decision.

---

## 1. Background — Why This Started

The starting point was the Anthropic paper mentioned above. I carried the causal finding — "what
would be said if asked = what is silently reasoned about" — to the prompt level and built the
**reflection probe**.

But before implementing, I read the self-correction literature first, and the counter-evidence was
consistent: **build it naively and performance gets cut instead.**

### The 8 papers reviewed and what each contributed to the design

| # | Paper | What it contributed to this design |
|---|---|---|
| 1 | Huang et al., *Large Language Models Cannot Self-Correct Reasoning Yet* (arXiv:2310.01798) | A prompt that presupposes "your answer may be wrong" costs up to **−9.5%p** (CSQA). Correct→incorrect flips **always** outnumbered incorrect→correct. → anchors A1 ("presume the answer is likely already accurate") · A5 ("not fault-finding, but consistency checking") |
| 2 | Dhuliawala et al., *Chain-of-Verification (CoVe)* (arXiv:2309.11495) | **Factored verification**, which withholds the draft prose from the verifier, moved FACTSCORE 55.9→71.4. Yes/no verification questions induce sycophancy bias. → feed the probe only the claim list + A6 (mandatory verbatim excerpt) |
| 3 | FBC/EIR line of work (verify-first ablation) | With the "independent re-check before edits + fix only concrete errors" anchor, EIR (correct→incorrect) went **2%→0%**, McNemar p<10⁻⁴. Under the same budget, 3 rounds of iterative revision (86.6) < simple majority vote (93.4). → **revision loop cap = 1 round** · A2 · A3 |
| 4 | Madaan et al., *Self-Refine* (arXiv:2303.17651) | Failure analysis: **61% were "inappropriate edits."** → A4 ("if there is no evidence, flag it only; do not swap in different content") |
| 5 | Shinn et al., *Reflexion* (arXiv:2303.11366) | The conditions under which external-signal-based reflection works, and its limits |
| 6 | Manakul et al., *SelfCheckGPT* (arXiv:2303.08896) | The standing of sampling-based self-checking — **the basis for not adopting it** in this design |
| 7 | Tian et al. (arXiv:2305.14975) · Xiong et al. (arXiv:2306.13063) | Single-number confidence clusters overconfidently at 80–100%; top-2 verbalized confidence calibrates better. → A7 (high/medium/low + 2 alternative candidates) |
| 8 | FAR.AI, *Obfuscation Atlas* (ICML 2026) · Morris et al., *How Much Do Language Models Memorize?* (ICML 2026) | The former: making the probe's flag count a KPI does not produce honesty but **optimization toward evading the probe** → the "no optimizing for flag count" rule. The latter: a memorization limit of ~3.6 bits per parameter → pulling paragraph numbers out of memory produces errors → parametric citation prohibited |

These grounds were fixed into the probe prompt as **anchors A1–A7**.
That is, the design started from the premise that "self-correction is dangerous."

---

## 2. Act 1 — Discarded Immediately After Being Built

An A/B gate was **pre-registered** on 119 items from the publicly available K-IFRS standards
(items and scoring rules frozen before execution) and then run. Scoring had two layers:
① mechanical citation matching ② a blind LLM judge with the arm labels hidden.

### Results

| Gate | arm A (no probe) | arm B (probe + revision) | Decision |
|---|---|---|---|
| Primary metric: citation error rate | 0/119 (0%) | 0/119 (0%) | No room to improve ❌ |
| Guardrail: answer accuracy | 99.2% | 99.2% | No degradation ✅ |
| Guardrail: over-correction rate | — | **0.84%** > threshold 0.5% | ❌ |

**Main probe P1 discarded.**

### Why it was discarded — "because it was too accurate" is correct; here it is spelled out

The author's question: *"Isn't the reason this came out that it's too accurate, so there's nothing
left to fix, making it Pareto-inferior? Check whether that's right and spell it out more"*
→ **Correct.** Confirmed by measurement, and precisely, it is this.

**① The baseline was already a corner point of the frontier.**
arm A was (citation errors 0%, answer accuracy 99.2%). Both axes are effectively at the ceiling.
Even on the trap items (18 distractors, similar paragraphs designed to induce miscitation), there
were 0 miscitations. **There is no axis left to improve.**

**② Then the expected value of a verification layer becomes structurally negative.**
- **Upside (what can be gained)**: citation errors cannot be reduced below 0 = **0**
- **Downside (what can be lost)**: the probe flags something as "outside the evidence" → the
  revision step edits that part → an originally correct answer can be damaged = **open**

That is, **a gamble with nothing to gain and only something to lose.** And it did in fact lose.

**③ A real case appeared (Q092).**
The probe, by the rules, ruled "inference outside the evidence scope" as unsupported. The revision
step, also by the rules, hedged only that item. **Both followed their own rules**, and the result
was an answer that contradicted the first sentence of the response. The "61% inappropriate edits"
reported in the Self-Refine paper was reproduced verbatim in this data.

**④ This fits the definition of a Pareto-inferior move exactly.**
- Metrics that improved: **none** (0 → 0)
- Metrics that worsened: **over-correction 0% → 0.84%**
- Therefore arm A **dominates** arm B → there is no reason to adopt

Put in economic terms, this is the **deadweight loss of excess regulation.** Both the regulation
(probe) and the enforcement (revision) are individually legitimate, yet the combined outcome cut
social welfare.

**⑤ So the first practical rule this experiment produced:**

> **The intuition that "more verification is safer" is true only inside the frontier.**
> Before attaching a layer, **measure the baseline error rate first. If it is 0%, do not attach it.**

To add one honest qualification, the validity of this ruling is limited to **these measured
conditions** (a strong generation model + evidence enclosed in the prompt + K-IFRS). With a weaker
model, or in an environment where evidence is not supplied, the baseline error rate would not be 0,
and then the probe could be effective.

![Panel (A) is the figure for this section](pareto_chart.png)

---

## 3. Act 2 — Phase 1: The Decision Does Not Reproduce

55 human labels were assigned blind (the labeling protocol was committed **before labeling began**).
Then judges v1/v2/v3 were measured.

- **v1 failed**: 9 false positives
- 🔴 **The most important finding**: running the same prompt with the same model 3 times,
  **5 out of 54 items changed every time.** LLM adjudication is not deterministic.
  → **Reporting a single-run number as performance is a false report.** From then on, all scoring
  was fixed to a 3-run majority vote.

### And this is where the only Pareto outward move appeared

Changing the probe decision from 1 vote to **3-vote consensus** (only items where all 3 runs said
YES enter review) gave:

| | 1 vote | 3-vote consensus |
|---|---|---|
| Final recall rate | 90.0% | **90.0%** (0 loss) |
| Human review load | 38.9% | **35.2%** |
| False positives in the automatic band | 0 | 0 |

**One of the two metrics unchanged, the other improved.** Pareto dominance holds.

The method matters here. This was not gained by **attaching** something, but by **removing an
unstable decision.** When people try to raise a metric they usually try to add something, but
**removing noise from existing hits pushes the frontier better.**

![Panel (B) is the figure for this section](pareto_chart.png)

**Phase 1 decision: probe effect = undeterminable.** However, it was pinpointed that the 12 false
positives were **100% the same failure mode** (a single rule split into several claims, then scored
with the claims isolated).

---

## 4. Act 3 — Phase 2: The Base Rate Beats the Sample Size

The plan was to add more human labels to secure statistical power. But **how many items to label**
was unknown. The required sample size is inversely proportional to the **base rate** (the rate at
which problem cases occur), and that base rate was unknown.

Here an **internal pilot** design was used. The core is this:

- Label only 30 items first and look at **the base rate only**. Do not open the performance metrics.
- Compute the required N **mechanically** from that base rate.
- Do not throw the 30 pilot items away — **overlap them as the first 30 of the main sample.**

The reason for going this far is that changing the sample size after seeing results invites the
**optional stopping** attack (collecting more data until the desired result appears). But
**adjusting N based on the base rate rather than the effect size** is a standard technique
recognized in statistics, so it is defensible.
That distinction is the whole design.

### Measured result: base rate 3.3% (1/30)

Labeling the **entire** candidate pool of 201 items would yield an expected 6.7 problem cases.
Far short of the target of 55.

**→ 171 items were left unlabeled and the phase was terminated.**

This too is a Pareto decision. If paying the full labeling cost (8–10 human hours) still fails to
buy statistical power, then finishing the run is **Pareto-inferior**. Honestly reporting
"undeterminable" is better.

---

## 5. Act 4 — Phase 3: 1,650 Calls Burned, and the Test Was Impossible

Since Phase 2 was blocked by human labeling cost, the outcome variable was changed.
Using **whether the judge's own decision flips** as the outcome variable instead of human labels
makes the human cost 0.

The design was made strict — **exactly one variable** was changed (presence or absence of sibling
claim context). Not a single character of the instructions was changed, and the prompt builder was
made to **verify in code, for every item, that the only difference between the two conditions was
the sibling block.**

Conditions A/B × 3 runs = **1,650 calls, about 2 hours.**

### Result: 0 problem decisions out of 271 in condition A

There was nothing to flip in the first place. The hypothesis was not **rejected**; **the test
itself was impossible.**

Here the author asked:

```
1-3실패면 아에 처음부터 다시하는게 맞지않나?
```

![The structure in which four stages each failed at a different layer](failure_ladder.png)

---

## 6. Act 5 — Instrument Check: 165 Calls Catch the Author's Misdiagnosis

Instead of a reset, **the cause was separated out first.** There were two hypotheses, and their
**prescriptions were exact opposites**:

- **Hypothesis I (instrument broken)**: the judge is configured such that it cannot detect problems → **the judge must be fixed**
- **Hypothesis C (corpus gap)**: the judge is fine and the sample had no problems → **the sample must be changed**

Comparing the prompt code, **Hypothesis I looked likely.** The Phase 3 judge genuinely **lacked**
two blocks (the full answer text, and the "distortion of the rule" guideline) that the validated
judge had.

### So it was measured before being fixed — this is the watershed of the project

**Instrument check**: without changing **a single character** of the judge (importing the prompt
builder as is), run it against the 55 labeled items whose answers are already known. The decision
criteria and the scorer were **committed before results were seen.**

| Item | Value |
|---|---|
| Detected out of 11 human-adjudicated problems | **9** |
| Detection recall | **81.8%** (Wilson 95% [52.3%, 94.9%]) |
| 3-run SPLIT (decision instability) | **0** |

**PASS — Hypothesis I was rejected. The author's diagnosis was wrong.**

Even without the guidelines, the judge caught them well, and its 3-run reproducibility was in fact
better (0 items) than Phase 1's complex judge (5 unstable items).

**Had the fix been made per the diagnosis without an instrument check, a perfectly good tool would
have been "fixed" and that change reported as an "improvement."** The cost was 1/10 of the main
run (1,650 calls → 165 calls).

### 🔴 And the real cause — two disciplines collided

The cause lay in the sample, and its origin was **the pre-registration rule itself.**

To avoid circular reasoning, Phase 3 had the rule "exclude the sample that generated the hypothesis
from the confirmation set." On measurement, **the 28 items where problems had been found were 0 in
the confirmation set and all 28 in the excluded set.**

> **Excluding the hypothesis-generating sample to avoid circular reasoning also excludes the signal.**
> Not excluding it is circular; excluding it makes the test target disappear.

This was not carelessness but **the result of faithfully following pre-registration discipline.**
Two disciplines (blocking circularity ↔ testability) collided with each other. The remedy is not to
abandon the exclusion, but to **verify, before the main run, that a base rate for the outcome
variable survives the exclusion** — that is the instrument check.

![The 5 stages of the pre-registration gate, and what happens if you skip ③](gate_flow.png)

---

## 7. Act 6 — Next-Room Validation: The Author Fixed the Design

This was the work of replacing the README's "generality unverified" note with measurements.

Here one remark from the author changed the design:

```
정안되면 옆방을 한국어꺼 찾아서 교체해서다시가자
```

That suggestion **changed the design.** Swapping the dataset after seeing results would be the
dataset version of optional stopping. But declaring it **as an "addition" before seeing results**
is defensible.

And there was something more important — the first next room (SciFact) changed language, domain,
and labeler **simultaneously**, so if results were bad, **attributing the cause would be
impossible**. Adding a Korean next room splits the axes.
This was not a contingency plan but **the design that should have been used from the start.**

| Room | Language | Domain | Labeler | recall | SPLIT | Decision |
|---|---|---|---|---|---|---|
| Original room (K-IFRS) | Korean | Accounting standards | the author | 81.8% | 0 | **PASS** |
| Next room 1 (SciFact) | **English** | **Biomedical** | **external** | **100%** | 0 | **PASS** |
| Next room 2 (KLUE-NLI) | Korean | **Non-accounting** | **external** | **100%** | 0 | **PASS** |

What matters is that **PASS also came out in rooms with external labelers.** For the original room
the objection was available that "the criteria were unconsciously aligned," since the author
labeled it and then instrument-checked a judge the author had built — and that objection was
rejected.

### 🔴 Axis separation — an unexpected gain

| Metric | SciFact (en) | KLUE-NLI (ko) |
|---|---|---|
| Detection recall (gate metric) | 100% | 100% |
| 3-label exact agreement | 72.7% | **92.7%** |
| False positives (human S → problem decision) | **36.4%** | **3.0%** |
| Precision | 64.7% | **95.7%** |

> **Recall is insensitive to language; precision is sensitive to language.**

The failure of **missing** a problem was 0 in both languages, while the failure of **calling
something a problem when it is not** rose 12-fold in English. Putting English evidence into a
Korean prompt made the judge declare "outside the evidence scope" more often.

**Which side is right is not something this experiment answers** — distinguishing whether the judge
is stricter or whether comprehension shallowed under a cross-lingual condition would require a
condition with the prompt translated into English, and since that changes one more variable, it was
left as a separate experiment.

![Panel (C) is the figure for this section](pareto_chart.png)

---

## 8. But Why Is the Author's 81.8% Better Than 100%

The two next rooms have recall 100% while only the original room has 81.8%. At a glance it looks
like a loss. **It is not.** It is in fact **the most valuable number in this project.** Here it is
unpacked in three layers.

### ① What were the 2 missed items — they are items the human also noted as ambiguous

| id | Human label | Note the human left at labeling time |
|---|---|---|
| Q068-A-c1 | C | **"Ambiguous: whether only the first date is the necessary condition, or the whole 'earlier of' rule…"** |
| Q068-A-c2 | C | **"Ambiguous: room for interpretation as to whether it enumerates candidate dates or asserts the actual recognition date"** |

**Both are boundary cases the labeler personally marked "ambiguous."** These are not easy items
that were missed; the machine split **at the very point where the human's judgment also split.**

### ② The difficulty differs to begin with — benchmark vs. field data

- **SciFact / KLUE-NLI**: benchmarks. The dataset creators design them to **split cleanly.**
  Ambiguous items get filtered out from the start because annotators cannot reach agreement.
- **The 55 K-IFRS items**: **raw** items taken from actual answers. Accounting-practice boundary
  lines such as "is this a necessary or a sufficient condition" are present as is.

**The layer the benchmarks filtered out is still here.** If the 100% is a 100% obtained on easy
problems, then the 81.8% is an 81.8% obtained on hard problems.

### ③ In Pareto terms it is beside, not below

| Room | recall | Precision |
|---|---|---|
| K-IFRS (author-labeled) | 81.8% | **69.2%** |
| SciFact | 100% | 64.7% |
| KLUE-NLI | 100% | 95.7% |

**SciFact has recall 100% but lower precision than the author's room.** Out of 33 items the human
called "fine," it insisted 12 were problems. That is, SciFact's 100% is not "it did everything
well" but **a 100% obtained by throwing a lot of suspicion.** The author's room produced 81.8%
while throwing less suspicion.

**There is no dominance relation between the two points.** In Pareto terms it sits at a different
point, not below.

### ④ From the RAG · ontology · LLM wiki perspective — why this matters

This is the crux.

**RAG (retrieval-augmented generation) is a fragment-memory method.** When a question arrives, it
pulls in a few similar fragments (chunks) and answers from those alone. The moment chunks are cut,
**the connections between documents are severed.** So RAG cannot see relations like "paragraph A
is an exception clause to paragraph B." It is a method that **shaves** fragments off and brings
them over.

**Ontologies and LLM wikis connect instead.** If documents are woven together with nodes (concepts)
and edges (relations), then reading A drags along the structure "this is an exception to B, and C is
a precondition."
It **links rather than shaves.**

And yet — **boundary cases arise at exactly those "connection" points.**

Q068 is the physical example. Look at the actual data as is.

**Evidence (K-IFRS 1019, paragraph 103, Korean-language standard)**
> Past service cost shall be recognized as an expense at **the earlier of the following dates**:
> - (1) when the plan amendment or curtailment occurs
> - (2) when the related restructuring costs or termination benefits are recognized

**Full answer text**
> Past service cost is recognized as an expense at the earlier of (1) or (2).
> **In the case of past service cost arising from an amendment to a retirement benefit plan, if
> there is no separate recognition of restructuring or termination benefits, it is recognized
> immediately as an expense at the point the plan amendment occurs.**

**One of the split claims (Q068-A-c1)**
> "Past service cost is recognized as an expense when the plan amendment or curtailment occurs."

The judge marked this **INSUFFICIENT**. Its reason: "the claim describes only the first condition
and omits the second, making it incomplete."

### 🔴 What the author pointed out here — the point that shows why this is a "deviation"

> **An accounting standard is a document that requires human judgment and whose answer is fixed
> only once the presupposed conditions are attached. Isn't that why deviations like this arise?**

Exactly right. And **the data proves it.** Three things are visible at once.

**First, the standard itself is written as a "conditional rule."**
Paragraph 103 does not give a single answer. **Which of (1) and (2) is earlier varies by
situation.** That is, the standard does not give the answer; it gives **the procedure for choosing
the answer.**
Accounting standards are written this way by nature — they set a principle and leave application to
the facts.

**Second, the answer did state that premise.**
Look at the second sentence of the answer — **"if there is no separate recognition of restructuring
or termination benefits."** That attaches a precondition. Since the question was "past service cost
arose from an amendment to a retirement benefit plan," in this situation (2) is absent and (1)
becomes the earlier date.
**Read as a whole, the answer is complete.** This is exactly the answer an accounting practitioner
wants.

**Third, and yet the scoring stripped that premise away and looked at one sentence only.**
The approach of "split into claims and score each" **cut the preconditions away along with them.**
Isolate the sentence and it becomes "(2) was omitted"; read it together with the whole answer and it
becomes "(1) was specified under a premise." **Same sentence, opposite verdict.**

That is, the identity of this "deviation" is not the judge's incompetence but **a structural mismatch
between the document type that is an accounting standard and per-claim scoring**:

| | Nature of an accounting standard | Assumption of per-claim scoring |
|---|---|---|
| Form of the answer | Fixed only with preconditions attached | One sentence is self-sufficiently true/false |
| Who judges | A human applies the facts | String comparison against the evidence paragraph |
| Paragraph relations | Principle ↔ exception, disjunction ↔ conjunction | Paragraphs are independent |

**Fourth — so this is evidence of why an ontology is needed.**

This problem is not solved by cutting chunks better or raising similarity. What is needed is
**explicit relations**:

- That paragraph 103 is a **disjunctive rule** (OR) — not a conjunction (AND)
- That in the context of a "plan amendment" question, (2) is an **inactive branch**
- That the answer's premise clause is the **grounds** for that branch selection

Weave this into nodes and edges and the verdict is settled. Pull in only the paragraph, as RAG does,
and it **looks like an "omission" forever.**

Therefore:

1. **The benchmarks' 100% is a 100% obtained on "problems decidable from a single chunk."**
   They are solvable even if you only fetch fragments with RAG. Put the other way, they are
   **problems where RAG's limits never surface.**
2. **The 2 items missed in the author's room are "problems solvable only by looking at relations and premises."**
   That these remain means this dataset **actually touches the ceiling of the RAG approach.**
3. And these 2 items are **evidence of why an ontology/wiki structure is needed.** Chunk similarity
   will never solve them; solving them requires making inter-paragraph relations (disjunction ↔
   conjunction, principle ↔ exception) and **preconditions** explicit.

One more thing — this diagnosis was in fact **confirmed by measurement.** In Phase 1 the 12 false
positives were **100% the same failure mode**, and when sibling claims were shown together, the 9
items that had siblings **flipped 9/9.** That is, the diagnosis "a problem created by cutting away
premises and context" is not a guess; the data supports it.

**In other words, 81.8% is an indicator not of "our tool is inadequate" but of "this data contains
real problems."** Had only the 100% benchmarks been run, it would have ended at "works fine," and
the reason to extend RAG into an ontology would never have been found.

**Drop the 2 missed items and it becomes 9/9 = 100%. That was not done.** Because dropping the
ambiguous ones to raise the number is exactly what this project set out not to do.
**81.8% with those 2 items attached is more honest than 100%, and it tells you what to do next.**

---

## 9. Things Caught Along the Way (the Gate's Work Log)

1. **A false positive from the anonymization checker itself** — the biomedical evidence's
   "**anterior** membrane" was flagged as a company name and blocked the push. It was narrowed with
   a context-restricted pattern and **verified with a negative control** (deliberately insert a real
   company name to confirm it is caught, and remove it to confirm it passes).
   → **Getting 0 hits from a newly built check proves nothing. It only becomes meaningful when you
   deliberately insert what ought to be blocked.**
2. **A child agent's self-report error** — an agent delegated a translation reported "23 headings"
   while the actual file had 22. → A comparison script that measures structure directly was built
   and turned into a gate.
3. **A file that was mid-run got swept into a commit** — partial results embedded in the repo can be
   misread as "something was done after seeing results," so it was reverted.
4. **A statistics error in the pre-registration document** — that is the error described in the
   p-value item in §0 above. It was found before results were seen and a correction record was left.

---

## 10. Final Deliverables

- **Public repo**: the repo this document belongs to (MIT, README KO/EN/ZH)
- 4 reusable gates: instrument check / exhaustive anonymization scan / README structure comparison / numeric preservation check
- 3 validated domains: Korean accounting / English biomedical / Korean everyday text
- All pre-registration documents are **committed before execution**, and the commit order is verifiable from the git history

## 11. Tech Stack

Python, claude CLI, 38 pytest tests, GitHub Actions (ubuntu/windows × py3.11/3.12),
McNemar exact test, Wilson confidence interval, matplotlib (charts computed from raw data — no
hard-coded numbers)

**Model configuration** (measurement-confirmed):
- **Judge (judge · probe) = fixed to `claude-sonnet-4-6`** — all 2,145 calls across all runs are
  recorded with this model (measured from the `model` field in the raw jsonl). Aliases prohibited;
  pinned in the manifest.
- **The agent that designed and operated this experiment = Opus 5** — the side that conversed with
  the human and produced the design, decisions, and documents.

🔴 **The two must not be confused.** The judge was deliberately pinned to a smaller model **not for
the cost axis but for reproducibility.** The judge must run thousands of calls, 3 runs each, and if
the model changes, comparison with past decisions becomes impossible. So it was pinned to an exact
version ID before execution and never changed to the end.

---

## 12. The 5 Rules This Experiment Produced (Reusable)

1. **Measure the baseline error rate before attaching a layer. If it is 0%, do not attach it.**
2. **Compute statistical power against the base rate of the outcome variable, not the sample size.**
   "N=264 items secured" is only the denominator. If the numerator is 0, no N can test it.
3. **Before fixing a measurement instrument, measure whether the instrument catches the signal.**
   A code comparison gives a plausible hypothesis but not a verdict. In this experiment that
   hypothesis was in fact wrong.
4. **Do not report a single-run number as performance.** LLM adjudication does not reproduce (5 out of 54).
5. **When raising a metric, remove before you attach.** Stripping the unstable portion out of
   existing hits pushes the frontier better.
6. **Match the scoring unit to the nature of the document.** Documents like accounting standards and
   statutes, **whose answers are fixed only with preconditions attached**, must not be scored by
   isolating a single sentence. The moment the premise is cut away, a perfectly good answer looks
   like an "omission" (measured: all 12 false positives were this failure mode; given sibling
   context, 9/9 flipped).

---

## Appendix — Data Sources

- SciFact (CC BY-NC 2.0, arXiv:2004.14500)
- KLUE-NLI (CC BY-SA 4.0, arXiv:2105.09680)
- K-IFRS publicly available standards

**The original datasets are not redistributed in this repo.** The reproduction scripts download them
from the source.
