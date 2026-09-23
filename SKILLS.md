# Skill index / 스킬 색인 / 技能索引

This repository is a collection of complementary agent skills. Choose the skill by the decision you need; the skills are not tied to a particular model or agent runtime.

이 저장소는 서로 보완하는 에이전트 스킬 모음입니다. 필요한 판단에 따라 스킬을 고르며, 특정 모델이나 에이전트 런타임에 종속되지 않습니다.

本仓库收录一组互补的智能体技能。请按所需决策选择技能；这些技能不依赖特定模型或智能体运行时。

- [한국어](#한국어)
- [English](#english)
- [中文](#中文)

## 한국어

| 스킬 | 언제 쓰는지 | 쓰지 않는지 | 핵심 산출물 | 경로 |
|---|---|---|---|---|
| Reflection probe | 인용과 답변을 원문 근거에 대조하는 검증 프로브가 필요할 때 | 하네스의 채택·제거를 비교하거나 artifact 계보를 증명할 때 | P1/P2/P3 프로브 설계, 앵커, 수정·통과·사람 검토 라우팅 | [`skill/SKILL.md`](skill/SKILL.md) |
| Pareto / harness diet | 같은 고정 코호트의 OFF/ON 실측으로 하네스를 더할지, 유지할지, 덜어낼지 판정할 때 | 개별 답변의 인용을 검증하거나 증거 원장의 무결성만 확인할 때 | `KEEP` / `TEST_THIN` / `REMOVE` / `NOT_MEASURED` 판정과 비교 계약 | [`skill-pareto/SKILL.md`](skill-pareto/SKILL.md) |
| Chain of custody | 원천 → 판정 → 결정 → 적용 → 검증 계보와 위변조 탐지가 필요할 때 | artifact 본문 저장소, 전자서명·공증, 접근제어 시스템이 필요할 때 | portable locator, SHA-256 artifact 색인, append-only event ledger와 verifier | [`skill-custody/SKILL.md`](skill-custody/SKILL.md) |

권장 경계: 판단기는 판단하고, custody는 그 증거 계보를 검증하며, Pareto는 검증된 동일 코호트의 채택 여부를 결정합니다.

## English

| Skill | Use when | Do not use when | Core output | Path |
|---|---|---|---|---|
| Reflection probe | You need a probe that checks citations and answers against source evidence | You need to decide whether to adopt/remove a harness, or prove artifact lineage | P1/P2/P3 probe designs, anchors, and revise/pass/human-review routing | [`skill/SKILL.md`](skill/SKILL.md) |
| Pareto / harness diet | You must decide whether to add, keep, thin, or remove a harness from OFF/ON measurements on the same fixed cohort | You need to verify a single answer's citations or only validate an evidence ledger | `KEEP` / `TEST_THIN` / `REMOVE` / `NOT_MEASURED` verdict and comparison contract | [`skill-pareto/SKILL.md`](skill-pareto/SKILL.md) |
| Chain of custody | You need source → judgment → decision → application → verification lineage and tamper detection | You need artifact content storage, digital signatures/notarization, or access control | Portable locators, SHA-256 artifact index, append-only event ledger, and verifier | [`skill-custody/SKILL.md`](skill-custody/SKILL.md) |

Recommended boundary: a judge evaluates, custody verifies the evidence lineage, and Pareto decides adoption only for verified measurements from the same cohort.

## 中文

| 技能 | 何时使用 | 不应使用 | 核心产物 | 路径 |
|---|---|---|---|---|
| Reflection probe | 需要把引用与回答同原始依据逐项核对时 | 需要判定测试台的采纳或移除，或证明产物谱系时 | P1/P2/P3 探针设计、锚点，以及修改／通过／人工复核路由 | [`skill/SKILL.md`](skill/SKILL.md) |
| Pareto / harness diet | 需要基于同一固定队列的 OFF/ON 实测，判定测试台应增加、保留、精简还是移除时 | 需要核验单条回答的引用，或只验证证据账本时 | `KEEP` / `TEST_THIN` / `REMOVE` / `NOT_MEASURED` 判定与比较契约 | [`skill-pareto/SKILL.md`](skill-pareto/SKILL.md) |
| Chain of custody | 需要“来源 → 判断 → 决策 → 应用 → 验证”的谱系与防篡改检测时 | 需要存储产物正文、数字签名／公证或访问控制时 | 可移植定位符、SHA-256 产物索引、只追加事件账本与验证器 | [`skill-custody/SKILL.md`](skill-custody/SKILL.md) |

建议边界：判断器负责评估，custody 验证证据谱系，Pareto 仅对已验证且来自同一队列的测量作采纳决策。

## Release-reference synchronization

This index intentionally links only repository paths that exist in the current tree. After a tag or release is actually published, add its immutable tag and commit reference here and in all three README files in one change; do not predeclare release URLs.
