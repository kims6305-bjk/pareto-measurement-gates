# pareto-measurement-gates — 判定是否采纳自我改进的门禁，及其背后的测量规律

[English](README.en.md) | [한국어](README.md) | **中文**

> 📌 **2026-08 更名** —— 原 `reflection-probe-gate` / `probe-graph`。
> 旧 URL 通过 GitHub 的 301 重定向依然有效。反思探针实验（Phase 1~3）是
> 本仓库的**起点与其中一章**；当前主题是由该实验催生的
> **采纳门禁与测量规律**。

本仓库包含一个可插入引用基础型 QA 流水线（RAG 机器人）的**验证子图 (verification subgraph)** 技能，
以及用于判定其效果的**完整 A/B 实测测试台 (harness)**。

先亮出核心结论：**本仓库的主探针（P1）在自建的实测门禁中被判定为废弃。**
本仓库的价值不在于某个"万能验证提示词"，而在于
①依据文献设计的三种探针，以及②在采纳它们**之前**就将其筛除的判定流程
（预注册 (preregistration) → 盲评 (blind judging) → McNemar 检验 (McNemar test)）的可复现全过程。

并且在此之后的 4 个阶段（Phase 1~3 + 仪器校验 (instrument check)）里，门禁**连自己的失败也一并抓了出来。**
复用价值最高的数值不在探针那一侧，而在门禁这一侧：

| 门禁指标 | 实测值 | 含义 |
|---|---|---|
| 仪器校验检出召回率 | **81.8%**（9/11） | 在正式运行**之前**确认测量工具能否抓到信号 |
| 仪器校验 3 轮再现性 | **SPLIT 0 例** / 55 | 判定不会摇摆 |
| 隔壁房间 (side-room) 验证（英语·生物医学 / 韩语·非会计） | **2/2 PASS**，召回率 100% | 即使更换领域、语言与标注者，流程依然有效 |
| 诊断成本 | **1,650 次调用 → 165 次调用** | 以十分之一的成本查明失败原因 |
| 探针 3 票共识（Phase 1） | 召回率维持 90%，复核负担 38.9%→35.2%，**自动区间误报 0** | 不是靠加装、而是靠**剔除**得到的帕累托外移 |

![A/B 实测判定图表](docs/ab_verdict_chart.png)

> 📖 本仓库诞生这一天的完整过程（设计依据、连续四次失败、以及门控查出作者本人的误诊）
> 按顺序记录在[案例研究](docs/CASE_STUDY.zh-CN.md)中。
>
> 🇰🇷 在生产数据上运行此闸门的两篇韩文实战记录（GPTers 社区）：
> [① 宣告 Pareto 工程 + 仪表检定 FAIL 实验记](https://www.gpters.org/nocode/post/now-youve-built-up-8Oqvvpr4EtdFBfA) ·
> [② 一周实战运营记 — 尺子坏了三次](https://www.gpters.org/nocode/post/pareto-enjinieoring-eul-seoneonhan-daeum-jue-siljero-beoleojin-il----ja-chi-2nT8LYb8nCv89pV)
> （② 是 `gate/MEASUREMENT_FAILURES.md` 案例 1~3 的叙事版本）

## 为什么要做（动机）

出发点是 Anthropic 可解释性团队的一篇论文：

> **"Verbalizable Representations Form a Global Workspace in Language Models"**
> (Anthropic, 2026, transformer-circuits.pub/2026/workspace)

该论文指出，LLM 内部存在一个"可以用语言说出来的表征特权集合"；并且表明，若通过**反事实反思 (counterfactual reflection)**
——即"在中途打断并追问'你现在在想什么？'，训练模型说出其所遵循的原则"——进行训练，
那么在不被打断的情况下模型的实际行为也会随之改善。论文还报告了模型在内部已经意识到异议、
却未将其反映到输出中的 **BUT-gap**（88%）。

论文的主体技术（J-lens）需要访问残差流 (residual stream)，API 用户无法使用。
因此，本技能只把其中的因果发现——"**被问到时会说出来的内容，就是它在静默推理时所想的内容**"——
翻译到提示词层面：在生成答案之后追问"说出这个答案中你拿不出依据的部分"，
将这一**反思探针 (reflection probe)** 作为流水线节点插入。

> **范围说明**：本仓库**不是该论文的实现。** 原论文的 counterfactual reflection
> 是一种训练（fine-tuning）技术，而本仓库是推理时的提示词验证器。论文只是设计动机，
> 并不能证明本仓库 P1/P2/P3 的效果——效果判定完全由下文的自建 A/B 门禁承担。

## 天真地实现反而有害（设计过程）

在实现之前，作者审阅了 8 篇自我纠正 (self-correction) 文献，得到的反面证据高度一致：
**天真的探针反而会削低性能。**

| 论文 | 对本设计的贡献 |
|---|---|
| Huang et al., *Large Language Models Cannot Self-Correct Reasoning Yet* (arXiv:2310.01798) | "假定答错"式提示最多带来 −9.5pp（CSQA）。正确→错误的翻转始终多于错误→正确 → 锚点 A1（"预设答案很可能已经正确"）· A5（"不是找错，而是确认一致"） |
| Dhuliawala et al., *Chain-of-Verification (CoVe)* (arXiv:2309.11495) | 因子化验证（不把初稿散文交给验证者）使 FACTSCORE 从 55.9 提升到 71.4。yes/no 式验证问题会引发附和偏差 → P1 仅输入主张列表 + A6（强制原文摘录） |
| FBC/EIR 系列（verify-first 消融实验） | 采用"修改前先独立复核 + 只修具体错误"的锚点，使 EIR（正确→错误）从 2% 降至 0%，McNemar p<10⁻⁴。在同等预算下，3 轮迭代 refine（86.6）< Self-Consistency（93.4） → **revise 循环上限 = 1** · A2·A3 |
| Madaan et al., *Self-Refine* (arXiv:2303.17651) | 失败分析：61% 属于"不当修改" → A4（"没有依据就只做标注，不要改成别的内容"） |
| Shinn et al., *Reflexion* (arXiv:2303.11366) | 基于外部信号的反思的适用边界条件 |
| Manakul et al., *SelfCheckGPT* (arXiv:2303.08896) | 基于采样的自检的定位——本设计中未采纳的依据 |
| Tian et al. (arXiv:2305.14975) · Xiong et al. (arXiv:2306.13063) | 单一数值置信度会集中在过度自信区间（80~100%），top-2 verbalized 的校准更优 → A7（高/中/低 + 2 个备选候选） |
| Obfuscation Atlas (FAR.AI, ICML 2026) | 若把探针指出的问题数量当作 KPI，模型不会变诚实，而会朝着规避探针的方向优化 → "禁止优化指出条数"规则 |
| Morris et al., *How Much Do Language Models Memorize?* (ICML 2026) | 每参数约 3.6 比特的记忆上限 → 从记忆中取条文编号必然出错 → 禁止参数化引用，引用必须经由 RAG 原文摘录 |

这些依据以探针提示词的**锚点 A1~A7** 的形式被固化下来
（`skill/references/probe-prompts.md` — 含各锚点的出处数值表）。

### 三种探针

| 探针 | 修改权限 | 过度校正风险 | 用途 |
|---|---|---|---|
| P1 引用对照 | 间接（触发 revise，上限 = 1） | 低（由锚点抑制） | 批量答案验证 |
| P2 verify-first | 自身 | 实证为 0（FBC） | 实时路径的系统提示词 |
| P3 风险枚举 | **无** | **结构性为 0** | 夜间审计、人工路由 |

## 实测 ① — 合成压力测试（探针自身的 QA）

首先验证探针是否"能抓住植入的错误，且不对正常答案做牵强的指摘"
（`harness/`）。正常答案 5 条 + 植入错误的答案 5 条（条文误写、数值篡改、超出依据的主张）。

- run1：9.5/10 — **发现 1 处 needs_revision 逻辑不一致**：模型准确判定 verdict='근거없음'（"无依据"），
  却输出 needs_revision=false。→ 教训：**判定字段不要信任模型，应在代码中用
  `any(verdict != "일치")`（"一致"）推导** — 韩文字面量是运行时 schema 的实际取值，请勿翻译（已反映到技能中）
- run2（修正后）：错误定位 5/5、牵强指摘 0、quote 原文实存 0 失败、JSON 10/10 — 通过

## 实测 ② — A/B 门禁：结果 P1 落选

**预注册** (`ab/ab_questions_FROZEN.json`，冻结后禁止修改)：
基于 12 种 K-IFRS（韩国采用国际财务报告准则）公开准则书的 119 道题 = normal 84 + no_answer 17（诱发幻觉）
+ distractor 18（相似段落陷阱）。评分规则同样在实验前冻结。

**执行**：同一模型、同一天，arm A（无探针）vs arm B（P1+revise）。
评分采用 ①引用错误的机器对照（评分器本身用 6 种负对照进行验证）+
②隐藏 arm 标签的**盲评 LLM 裁判**（呈现顺序亦做打乱）。

**结果**（全文：[`ab/AB_VERDICT.md`](ab/AB_VERDICT.md)）：

| 门禁 | arm A | arm B | 判定 |
|---|---|---|---|
| 主指标：引用错误率 | 0/119 (0%) | 0/119 (0%) | p=1.0 — 无改进空间 ❌ |
| 护栏 1：答案准确率 | 99.2% | 99.2% | 未劣化 ✅ |
| 护栏 2：过度纠正率 (over-correction rate) | — | **0.84% > 阈值 0.5%** | ❌ |

主指标"0%"的准确含义（外部评审后补充，防止过度解读）：

- 机械评分器检查引用的**结构、地址与摘录实存**——该层错误 0/238。
- "主张↔依据语义一致性"另行验证：238 条全部按 claim 粒度用 LLM 评审
  （`claude-sonnet-4-6`，fail-closed，评审原文与理由全文公开）重新评分，
  结果为**语义相悖 0 条，超出依据范围 3/238（1.3%）**——A/B 完全对称，判定不变。
  全文：[`gate/SEMANTIC_REGRADE.md`](gate/SEMANTIC_REGRADE.md)
- 语义相悖 0/238 的 95% CI 上界约为 1.3%（rule of three）。
  "错误率 0%"是点估计，应连同该置信区间一并解读。
- no_answer 层 17 题（14.3%）在两个 arm 中均正常弃答——幻觉诱导成功 0 例。

**判定：P1 废弃。** 唯一的劣化案例（Q092）正是文献中 EIR 机制的原样复现——
探针按规则将"超出 evidence 的推断"判为无依据，revise 也按规则只把该条目改成了 hedging，
但结果却是与首句自相矛盾的答案。
这正是 Self-Refine 失败分析（不当修改 61%）所指出的
**即便各组件各自正确，其组合仍可能损害正确答案**的实例。

### 教训

1. **在强生成模型 + 依据随附的结构下，引用错误本来就不会发生。**
   即便在 distractor 陷阱中也是误引 0 例。若验证层无物可抓，
   上行空间为 0，只剩下行空间（过度校正）——这不是保险，而是净成本。
2. 引入 P1 得以正当化的条件：生成模型确实会产生引用错误的环境
   （更弱的模型、依据未随附、依赖参数化引用）。**请先测量 baseline 错误率，
   若为 0% 就不要加装 P1。**
3. P3（无修改权限）与 P2（verify-first 锚点）不受此判定影响——
   因为其过度校正在结构上为 0 或在实证上为 0。
4. 如果没有这道判定门禁，就会以"加了验证应该更安全吧"为由，
   把一个净成本层推上生产环境。**本仓库中复用价值最高的部分不是探针，
   而是门禁。**

## 帕累托视角 — 把测试台拧到最紧并非最优

把这个实验浓缩为一句话，就成了经济学中的帕累托概念：
**验证强度不是一个免费的旋钮，而是在两个相互冲突的指标（错误检出 ↔ 过度校正）之间的移动。**

- arm A 已经处于（引用错误 0%、准确率 99.2%），不存在可改进的维度，
  它位于前沿面 (frontier) 的角点上。
- 在其之上叠加验证层的 arm B 是一次**帕累托劣化移动 (Pareto-inferior move)**：
  没有任何指标上升（上行为 0），只有一个指标下降（过度校正 −0.84%）。
- Q092 是过度监管所致**无谓损失 (deadweight loss)** 的实物样本——
  监管方（探针）与执行方（revise）各自都遵守了规则，组合的结果却是福利净减少。
- 从这一视角看，McNemar 门禁的本质十分清晰：**一个在采纳帕累托劣化移动之前将其探测出来的装置。**
  "加更多验证就更安全"的直觉只在前沿面内侧为真，在前沿面上则为假。

主张的适用边界同样明示：本次实测比较的是验证强度旋钮上的两个点（无验证 vs
P1+revise），而不是整个前沿面的地图。本数据所支持的主张不是"找到了最优点"，
而只到"**用实测判别出了一次劣化移动**"为止。
若要描绘前沿面本身，需要把验证强度设置为多个档位（例如：仅 P2 / 调节 P1 锚点强度 /
变更 revise 阈值），并用同一道门禁逐点测量。

## 实测 ③ — 此后的 4 个阶段：门禁抓住自身失败的记录

A/B 判定之后，为了查明"那么探针抓到的误报究竟是怎么来的"，又多跑了 4 个阶段。
**连续三次判定不能**，第四次才锁定原因。本节是本仓库中复用价值最高的部分——
因为每一次失败的种类都不一样。

| 阶段 | 问的是什么 | 结果 | 没测到的东西 |
|---|---|---|---|
| Phase 1 | 探针能否抓住问题 | 判定不能 | 探针判定的**再现性** |
| Phase 2 | 增大样本能否判定 | 判定不能 | 人工标注的**基础发生率 (base rate)**（3.3%） |
| Phase 3 | 评分粒度是否扭曲判定 | 判定不能 | 裁判判定的**基础发生率**（0%） |
| 仪器校验 | **测量工具本身是否完好** | **PASS** | — |

### Phase 1 — 发现"没有再现性"

用同一提示词、同一模型把裁判跑了 3 次，54 条中有 5 条每次都不一样。
也就是说，**把单次运行的数值当作性能来报告就是虚假报告**。此后所有评分都固定为 3 轮多数决。

正是这条规律带来了一次帕累托外移。把探针判定从 1 票改为 **3 票共识**后：

- 召回率 90.0% → 90.0%（**损失为 0**）
- 人工复核负担 38.9% → **35.2%**
- 自动区间误报维持 0 例

这不是靠**加装**指标，而是靠**剔除**不稳定成分得到的改进。

### Phase 2 — 基础发生率胜过样本量

原打算通过增加人工标注来确保检验效能。以内部试点 (internal pilot) 设计标注 30 条、
**只读基础发生率**，结果是 **3.3%（1/30）**。即便把 201 条候选池全部标注，
期望的问题案例也只有 6.7 条，远达不到目标的 55 条。

→ 于是**在没有标注 171 条的情况下结案**。因为按原案走完全程本身就是帕累托劣化。
试点没有作废，而是嵌套 (nested) 进正式样本中，以规避 optional stopping 的批评。

### Phase 3 — 烧掉 1,650 次调用却无法检验

把结果变量从人工标注改为**裁判判定的翻转**，从而把人工成本降到 0。
只改变兄弟主张上下文有无的单变量 A/B，每个条件 3 轮，总计 1,650 次调用。

结果：**条件 A（对照）的问题判定在 271 条中为 0 条。** 没有可供翻转的对象，假设未被检验。
观测到的 6 条不一致全部是相反方向（变得更严格），McNemar p=0.125，不显著。

### 仪器校验 — 用 165 次调用锁定原因

在这里两个假设分道扬镳，而且处方完全相反：

- **假设 I（仪器故障）**：裁判的配置检不出问题 → 应当修裁判
- **假设 C（语料空白）**：裁判正常，是样本里本来就没有问题 → 应当换样本

对照提示词代码后，假设 I 看上去更有说服力。Phase 3 的裁判**缺少** Phase 1 那个
已验证裁判中的 `[전체 답변]` 区块与"规则的扭曲"指引。

所以在动手修之前**先测量。** 一个字都不改 Phase 3 的裁判提示词
（直接 import 原构建器），把它应用到 55 条人工标注上。判定基准与评分器
都在看到结果**之前**就已提交。

| 项目 | 值 |
|---|---|
| 人工判定的 11 条问题中被检出 | **9 条** |
| 检出召回率 | **81.8%** 威尔逊区间 (Wilson interval) 95% [52.3%, 94.9%] |
| CONTRADICTED 检出 | 7 条 |
| 3 轮 SPLIT | **0 例** |

**PASS — 假设 I 被否定。作者的诊断是错的。**
即便没有那条指引，裁判也抓得很好；而且 3 轮再现性反而优于 Phase 1 那个复杂裁判
（后者摇摆 5 条）——为 0 例。若没做校验就照诊断去修，**就会把一个完好的工具改一通，
并把这件事当作改进来报告。**

### 🔴 真正的原因 — 两条规律相互冲突

原因在样本上，而其源头正是预注册规则本身。

Phase 3 为了避免循环论证，设了"生成假设所用的样本要从验证集 (confirmatory set) 中排除"的规则。
实测下来发现，**被发现有问题的 28 道题在验证集中为 0 道，在排除集中则是全部 28 道。**

> **为避免循环论证而排除假设生成样本时，信号也会被一并排除。**
> 不排除就是循环，排除了检验对象就消失。

这不是疏忽，而是**忠实遵守预注册规律所导致的结果**。是两条规律
（阻断循环 ↔ 可检验性）彼此冲突的案例。

解法不是放弃排除，而是**在正式运行之前先确认：排除之后结果变量的基础发生率是否还留得下来。**
那就是仪器校验，成本只有正式运行的十分之一。

### 从这 4 个阶段带走的 3 条规则

1. **检验效能不是对样本量、而是对结果变量的基础发生率来计算的。**
   "确保 N=264 条"只是分母。其中有几条会被判定为问题才是分子，
   分子为 0 时，任何 N 都无法检验。
2. **在修理测量工具之前，先测这个工具能不能抓到信号。**
   代码对照能给出貌似合理的假设，但那不是判定。在本仓库中，那个假设实际上是错的。
3. **不要把单次运行的数值当作性能来报告。** 裁判判定并不可再现。

全文：[`gate/PHASE1_VERDICT.md`](gate/PHASE1_VERDICT.md) ·
[`gate/PHASE2_VERDICT.md`](gate/PHASE2_VERDICT.md) ·
[`gate/PHASE3_VERDICT.md`](gate/PHASE3_VERDICT.md) ·
[`gate/INSTRUMENT_CHECK_RESULT.md`](gate/INSTRUMENT_CHECK_RESULT.md)

各阶段的事前声明文档（`*_PREREGISTRATION.md`、`INSTRUMENT_CHECK_PREREG.md`）
全部**在执行前提交**，提交顺序可通过 git 历史验证。

## 领域可移植性 — 并非 K-IFRS 专用

本仓库中依赖 K-IFRS 的只有**实测数据（题目集）**：

| 层 | 领域依赖 | 备注 |
|---|---|---|
| 技能本体（3 种探针 + 锚点 A1~A7 + 图结构） | 无 | "主张 ↔ 依据原文对照"的结构——只要是有依据文档的引用型 QA 皆可（法令、判例、公司内部规程、论文、合同、医疗指南） |
| 门禁流程（预注册 → 盲评 → McNemar） | 无 | 统计流程本身不含领域属性 |
| 实测数据（`ab/ab_questions_FROZEN.json` 119 题） | K-IFRS | 只是因为作者的业务领域恰好是会计 QA。其他领域替换为自己的题目集即可 |

锚点所依据的文献本身来自数学（GSM8K）、常识（CSQA）、传记写作（FACTSCORE）等基准，
与会计无关。

### 实测：在两个"隔壁房间"中完成验证 (2026-07-28)

上一版 README 把本节标注为**"未验证 (unverified)"**，因为当时只有设计主张而没有实测。
现将该标注替换为下述实测结果。

**把仪器校验流程原封不动地应用到领域、语言与标注者都不同的两个数据集上**（跨领域验证
cross-domain validation）。判定器提示词一个字都没改（直接 import 原构建器），
阈值也与原来的房间保持一致。事前声明在执行前提交。

| 房间 | 语言 | 领域 | 标注者 | recall（召回率） | SPLIT | 判定 |
|---|---|---|---|---|---|---|
| 原来的房间（K-IFRS） | 韩语 | 会计准则 | 作者 | 81.8%（9/11） | 0 | **PASS** |
| 隔壁房间 1（[SciFact](https://arxiv.org/abs/2004.14500)） | **英语** | **生物医学** | **外部** | 100%（22/22） | 0 | **PASS** |
| 隔壁房间 2（[KLUE-NLI](https://arxiv.org/abs/2105.09680)） | 韩语 | **非会计** | **外部** | 100%（22/22） | 0 | **PASS** |

重要的是，**在标注者为外部人员的两个房间里同样得到 PASS**。原来的房间是由作者标注、
再去校验作者自己做的判定器，因此存在基准被无意识对齐的可能性；而该解释未获支持。

#### 🔴 而且两个轴分开了 — 召回率对语言不敏感，精确率则敏感

仅凭隔壁房间 1，语言、领域与标注者是同时改变的，无法做原因归属。
隔壁房间 2 **把语言固定为韩语**，从而实现了分离。

| 指标 | SciFact (en) | KLUE-NLI (ko) |
|---|---|---|
| 检出召回率（门禁指标） | 100% | 100% |
| 3 轮标注完全一致 | 72.7% | **92.7%** |
| 误报（人工判 S → 判定为问题） | **36.4%** | **3.0%** |
| 精确率 (precision)（门禁之外的参考值） | 64.7% | 95.7% |

**漏掉**问题的失败在两种语言中都是 0；而把**不是问题的东西判为问题**的失败，
在英语条件下增加到了 12 倍。即在韩语提示词 + 英文依据的条件下，
判定器更频繁地宣告"超出依据范围"。

**哪一侧才是对的，本实验回答不了**——可能是判定器变得更严格，
也可能是在跨语言条件下对依据的理解变浅了。要区分这两者需要一个把提示词
翻译成英语的条件，而那会再多改变一个变量，因此留作独立实验。

#### 仍然不主张的东西

- **不是"在所有领域都行得通"。** 已验证的是 3 个领域。
- **模型间的可移植性尚未验证**。判定器依然只有 `claude-sonnet-4-6` 一个。
- 隔壁房间 2（NLI）是蕴含判定任务，与引用验证的任务性质不同。

全文：[`gate/SIDECHECK_PREREG.md`](gate/SIDECHECK_PREREG.md)（事前声明）·
[`gate/SIDECHECK_RESULT.md`](gate/SIDECHECK_RESULT.md)（结果）

同理，**"P1 废弃"判定的有效范围也仅限于本次实测条件（K-IFRS + 强模型 + 依据随附）**。
在其他领域、更弱的模型、依据未随附的环境中，P1 仍可能有效——
所以移植流程的第一步是"先测量你自己环境的 baseline 错误率"，
而将这一判定自动化的，正是这道门禁。

### 既有的 harness 里真的没有采纳门禁吗

"需要采纳门禁"这一主张，必须以"既有实现中确实没有"的实测为前提。
我们对一个公开的参考实现（`PrimeIntellect-ai/prime-agent`，提交 `a18809e`）
做了文件:行级别的解剖。

- **形式由代码强制** —— schema 违规、并发修改冲突都会被可靠地拒绝。
- **是否为改进的判定被委托出去了** —— 只是 `shouldRefine === true` 一个布尔值；
  每个提案一并保存的 `expectedOutcome`，其读取处**只有一个：下一轮提示词的渲染**。
  自我改进在累积，却没有任何代码路径去衡量它是否真的是改进。
- 反过来，它的**并发安全机制超出本仓库的水平**（世代号失效、应用前的 baseline 比对、
  原子写入）。两个实现守的是不同的轴。

同一份文档里也原样保留了**我们自己的一处"不存在证明"错误及其纠正过程** ——
我们用错误的文件路径 grep，把工具的失败读成了"0 条"，重跑时被推翻。
无法复现的不存在证明，不构成证据。

全文：[`gate/RELATED_HARNESSES.md`](gate/RELATED_HARNESSES.md)

### 这并不是新问题 —— 与递推估计、剪枝的对应

给反复更新的估计器加上**增益（gain）**，以及在生长之前先问显著性，
都是早已有名字的处方。

- **递推最小二乘（RLS）中的增益 `K`，正是采纳门禁所在的位置。** 参考实现实际上是
  `K = 1` 固定（提案即应用），本仓库在这个位置放入帕累托判定。
- **自回归模型的曝光偏差原样重现** —— 智能体在下一轮会重新读取自己写下的技能，
  因此若没有 ground truth 的再注入（定期验证），漂移在原理上无法被阻止。
- **决策树的预剪枝**与仪器校验是同一结构。实测中 330 次调用的校验，
  在开始之前就拦下了 1,650 次调用的搜索 —— 同时也一并继承了预剪枝的已知弱点
  （horizon effect）。

🔴 但是，**RLS 所预设的线性、凸性、收敛保证，在 harness 上一条都不成立。**
尤其 RLS 的增益是从协方差*计算*出来的，而我们没有那个协方差，
只能以事前登记的判定规则替代。对应断裂的位置，以及我们决定不采用的类比，
都写在同一份文档里。

全文：[`gate/THEORY_MAPPING.md`](gate/THEORY_MAPPING.md)

### 仪器错了，判定就会翻转 —— 三个失败案例

![三个测量失败](docs/measurement_failures.png)

无论门禁设计得多好，**只要它读到的数字是错的**，判定就没有意义。
这里收录了在运行中的引用 QA 流水线上，真正翻转过（或差点翻转）判定的三个测量失败。

- **计数单位错误** —— `precision` 的分母取成了槽位，导致重复的正确文档被重复计数。
  上报的 0.672 是并不存在的性能，而这份虚高把一项正当的改进误判为 **DOMINATED**。
  改用唯一文档为基准后，比率轴只动了 −0.004（实际为零），
  而绝对计数轴从 5.80 动到 6.35 —— **比率轴看不见去重。**
- **预处理循环** —— 构建过程插入了换行，评分器随即按"位于行首，所以是段落号"来计数，
  让自己的误报为自己背书。评分器**重写了三次**，最终退到"只统计明确噪声"的下界估计，
  才得到可辩护的数字（3.55%）。
- **判定循环** —— 候选是被"把它们聚在一起的那个信号"验证的。改由不提供上下文的
  独立判定者对 66 对全量重判 → **DIFFERENT 0 条**（自动抽取出的"对立"并不存在）。
  直到把首轮 7 条 UNCLEAR 全部以全文重判解决之后才确定。

三者的共同点是：**每一次都可以直接上报"改进了"。**
怀疑仪器的成本高于改进本身，但三次都是值得的。

全文：[`gate/MEASUREMENT_FAILURES.md`](gate/MEASUREMENT_FAILURES.md)

## 仓库结构

```
skill/                  # 技能正文（面向 agent 框架的 SKILL.md 格式）
  SKILL.md              #   图结构·总原则·实测判定记录
  references/
    probe-prompts.md    #   3 种探针提示词全文 + 各锚点的论文出处数值
    evals.md            #   二元质量门禁（①自身 QA ②A/B 门禁）
skill-pareto/           # 帕累托采纳门禁技能（本实验所运营化的判定流程）
  SKILL.md              #   劣势移动/外移判定规则 + 应用地图
harness/                # 实测 ① 合成压力测试
  run_stress.py         #   运行器（与评分分离）
  cases.json            #   正常 5 + 注入错误 5（基于合成依据文档）
  evidence.md           #   合成依据文档（非真实准则书）
  stress_results_run{1,2}.json
ab/                     # 实测 ② A/B 门禁
  ab_questions_FROZEN.json  # 预注册题目 119（基于 K-IFRS 公开准则书）
  ab_results.json       #   两个 arm 的原始输出全文（供审计·重评分）
  ab_runner.py          #   两个 arm 的运行器（增量保存·可续跑）
  grade_ab.py           #   机器评分 + 盲评裁判 + McNemar 报告
  merge_verify.py       #   题目生成时的独立复核器
  make_chart.py         #   判定图表生成
  ab_grades.json        #   评分原始数据
  AB_VERDICT.md         #   判定全文
gate/                   # 评分门禁包 + 语义层重评分 + Phase 1~3 实测
  src/reflection_gate/  #   确定性（结构·地址·摘录）+ 语义（LLM 裁判）双层评分器，fail-closed
  tests/                #   pytest 38 项（含 10 种负对照）
  SEMANTIC_REGRADE.md   #   238 条全量重评分判定（含 FLAGGED 18 条的人工对照）
  LABELING_PROTOCOL.md  #   人工标注协议（标注开始前提交）
  PHASE1_VERDICT.md     #   Phase 1 判定 — 发现没有再现性，采纳 3 票共识
  PHASE2_INTERNAL_PILOT.md  # 内部试点设计（只查阅基础发生率，嵌套样本）
  PHASE2_PILOT_RESULT.md    # 试点实测 — 基础发生率 3.3%
  PHASE2_VERDICT.md     #   Phase 2 判定 — 样本不足，未标注 171 条即结案
  PHASE3_PREREGISTRATION.md # Phase 3 事前声明（执行前提交，含 McNemar 阈值订正记录）
  PHASE3_VERDICT.md     #   Phase 3 判定 — 无法检验 + 原因（阻断循环把信号一并移除）
  PHASE4_PREREGISTRATION.md # Phase 4 事前声明 DRAFT（在查阅 Phase 3 结果前撰写）
  INSTRUMENT_CHECK_PREREG.md   # 仪器校验事前声明（执行前提交）
  INSTRUMENT_CHECK_RESULT.md   # 仪器校验结果 — PASS，记录作者的诊断是错的
  SIDECHECK_PREREG.md   #   隔壁房间验证事前声明（§8 在查阅隔壁房间 1 结果前提交）
  SIDECHECK_RESULT.md   #   两个隔壁房间的结果 — 均为 PASS，召回率↔精确率两轴分离
  RELATED_HARNESSES.md  #   参考实现解剖 — 采纳门禁缺失的实测（含我们自己的一处不存在证明错误）
  THEORY_MAPPING.md     #   与 RLS／自回归／剪枝的对应 + 对应断裂的位置
  MEASUREMENT_FAILURES.md #  三个测量失败 —— 计数单位·预处理循环·判定循环
  scripts/              #   各 Phase 的运行器·评分器·原始数据（判定器在查阅结果前提交）
docs/
  ab_verdict_chart.png
  pareto_chart.png      #   帕累托三面板（劣化移动·外移·轴分离）
  failure_ladder.png    #   四个阶段各自在不同层失败的结构
  gate_flow.png         #   预注册门控的五个阶段
  measurement_failures.png # 三个测量失败的图示（数值从文档解析 —— 无硬编码）
  CASE_STUDY.md         #   案例研究 — 开发当天的完整过程（韩/英/中）
STATE.md                # 多会话状态摘要（决策累积·卡点·验证门禁）
```

## 复现

```bash
# 前提：claude CLI（或将 run_llm() 替换为你想用的 LLM 调用）
cd ab
python3 ab_runner.py            # 运行两个 arm（按题目增量保存，中断后可续跑）
python3 grade_ab.py mech        # 机器引用评分
python3 grade_ab.py judge       # 盲评裁判（约 250 次调用）
python3 grade_ab.py report      # McNemar 判定表
python3 make_chart.py           # 图表（需要 matplotlib）
```

### 仪器校验的复现（推荐入口）

本仓库中**最值得第一个跑起来的**是仪器校验。
用 165 次调用确认你自己环境中的验证器能否抓到信号。

```bash
cd gate
for r in run1 run2 run3; do
  .venv/bin/python scripts/instrument_check_run.py $r
done
.venv/bin/python scripts/instrument_check_score.py   # 自动套用事前声明的基准
```

判定由 `INSTRUMENT_CHECK_PREREG.md` §4 的阈值（recall ≥ 30%）自动算出。
**若为 FAIL，请不要开始正式实验**——在工具抓不到信号的状态下得到的
"没有效果"，不是处置的失败，而是测量的失败。

若要移植到其他领域，只需替换 `instrument_check_run.py` 中 `load_units()` 所读取的
标注表（id / question / evidence / claim_text / 人工标注 S·C·I）即可。

### 隔壁房间验证的复现（领域可移植性）

这是把同一套流程应用到两个公开数据集上的实测。原始数据不做再分发，
由脚本直接从各自出处获取。

```bash
cd gate
.venv/bin/python scripts/sidecheck_fetch.py          # SciFact (CC BY-NC 2.0)
.venv/bin/python scripts/sidecheck_build_units.py    # 分层抽样 55 条，seed 固定
.venv/bin/python scripts/sidecheck2_build_units.py   # KLUE-NLI (CC BY-SA 4.0)
for r in run1 run2 run3; do
  .venv/bin/python scripts/sidecheck_run.py $r --room 1
  .venv/bin/python scripts/sidecheck_run.py $r --room 2
done
.venv/bin/python scripts/sidecheck_score.py --room 1
.venv/bin/python scripts/sidecheck_score.py --room 2
```

## 参考文献

- Anthropic (2026). *Verbalizable Representations Form a Global Workspace in Language Models.* transformer-circuits.pub/2026/workspace
- Huang, J. et al. (2023). *Large Language Models Cannot Self-Correct Reasoning Yet.* arXiv:2310.01798
- Dhuliawala, S. et al. (2023). *Chain-of-Verification Reduces Hallucination in Large Language Models.* arXiv:2309.11495
- Madaan, A. et al. (2023). *Self-Refine: Iterative Refinement with Self-Feedback.* arXiv:2303.17651
- Shinn, N. et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning.* arXiv:2303.11366
- Manakul, P. et al. (2023). *SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection.* arXiv:2303.08896
- Tian, K. et al. (2023). *Just Ask for Calibration.* arXiv:2305.14975
- Xiong, M. et al. (2023). *Can LLMs Express Their Uncertainty?* arXiv:2306.13063
- FAR.AI (2026). *Obfuscation Atlas.* ICML 2026 — 探针博弈 / 策略混淆
- Morris, J. et al. (2026). *How Much Do Language Models Memorize?* ICML 2026
- Wadden, D. et al. (2020). *Fact or Fiction: Verifying Scientific Claims.* EMNLP 2020, arXiv:2004.14500 — 隔壁房间验证 1（SciFact）
- Park, S. et al. (2021). *KLUE: Korean Language Understanding Evaluation.* NeurIPS 2021 D&B, arXiv:2105.09680 — 隔壁房间验证 2（KLUE-NLI）

### 参考实现（§"既有的 harness 里真的没有采纳门禁吗"）

- PrimeIntellect-ai. *prime-agent.* github.com/PrimeIntellect-ai/prime-agent —
  解剖对象，固定于提交 `a18809e`。文件:行引用与复现命令见
  [`gate/RELATED_HARNESSES.md`](gate/RELATED_HARNESSES.md)

### 理论对应（§"这并不是新问题"）

这些是*结构*的对应，而非定理的移植。各项所预设的条件，
以及它们在 harness 上不成立的位置，见
[`gate/THEORY_MAPPING.md`](gate/THEORY_MAPPING.md) §4。

- Åström, K. J. & Wittenmark, B. (1994). *Adaptive Control* (2nd ed.), Addison-Wesley —
  RLS 的增益 `K` 与遗忘因子 `λ`；把采纳门禁放在增益位置的依据
- Ljung, L. (1999). *System Identification: Theory for the User* (2nd ed.), Prentice Hall —
  用于计算增益的协方差 `P`。**我们所缺的正是这个 `P`**
- Bengio, S. et al. (2015). *Scheduled Sampling for Sequence Prediction with
  Recurrent Neural Networks.* NeurIPS 2015, arXiv:1506.03099 —
  曝光偏差与 teacher forcing；对应"重新读取自己写下的技能"
- Breiman, L. et al. (1984). *Classification and Regression Trees.* Wadsworth —
  预剪枝／后剪枝；仪器校验对应预剪枝
- Quinlan, J. R. (1987). *Simplifying Decision Trees.* Int. J. Man-Machine Studies 27(3) —
  预剪枝的 horizon effect，被 IC-1 FAIL 的解释一并继承

### 元 harness 文献对照（决定 15）

为寻找"以 front 作为父代选择规则"的六源对照。结论是：
自我改进层中不存在，仅在其他领域（公式发现、路由）部分存在。表见
[`gate/PARETO_META_HARNESS_DESIGN.md`](gate/PARETO_META_HARNESS_DESIGN.md) §2。
🔴 其中 TRACE-Router 留下的警告 —— **关于 front 占据的主张需要随机混合对照组**
（"random mixture also traces the line segment"）。

## 许可证与数据来源

- **代码、技能、文档：MIT** — 可不受领域限制地自由使用、修改与再分发。
- **随附的题目集**（`ab/ab_questions_FROZEN.json`）仅基于韩国采用国际财务报告准则（K-IFRS）
  的**公开准则书段落**生成，不包含任何私有/内部数据。这只是数据来源的告知，
  并不构成对本技能适用范围的限制——参见上文"领域可移植性"一节。
