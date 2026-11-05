# v3（插件专家可用版）：发给 ZCode 的 `/goal`

> 与 v2 的唯一区别：派发时点名**插件里的真实专家**（`代码审查员`、`后端架构师`…），v2 只用 general-purpose/Explore。
> 已验证：332 位都在插件里、`@名字` 不触发派发，必须**显式要求用 Agent 工具**并指定 `subagent_type`。

## 1. 整段粘这个

/goal 你是本仓库今晚的审计负责人。工作区：<审计副本>（已含 .git 与 27 项未提交改动）。

【开工三数核对，不符就停手报告】pwd = 上述路径；`git status --porcelain | wc -l` = 27；`git log --oneline -1` = 4ec0b3d。三项全对才继续。

【派发纪律（最重要）】你有 332 位插件专家可派：代码审查员、后端架构师、前端开发者、测试自动化工程师、UI 视觉验收设计师、技术文档工程师、密钥与凭据治理工程师、代码执行者（唯一可写）。规则：
1. 必须**真的调用 Agent 工具**（subagent_type 填上面中文名）。只写"某某说…"而没有 Agent 调用 = 造假，立刻自纠。
2. 并行 ≤3；同一时刻只允许 `代码执行者` 一个写者，其余只读。
3. 每次派发后，在正文说明「派了谁 / 审什么 / 拿到什么」。

【五层审计，逐层出结论】
L1 代码：近 7 天 68 笔提交 / 423 文件 + 27 项未提交。按缺陷（做错事）、风险（可能做错）、漂移（与文档/原型不一致）三档记。
L2 原型：`design/prototype/workbench-2026-11/` 是硬基准。`prototype-gap.md` 的 99 处逐条核：原型有的必须 1:1 实现，未实现即**阻断**；原型没覆盖的不计入；13 处「演示：」控件本就不实现，不算缺口。
L3 契约文档：`docs/UI_SPEC.md` §9 的 63 条逐条标 已验/blocked/未覆盖；`design/specs/` 与实际行为是否一致。
L4 决策记录：`design/evidence/2026-11-04/decision-agenda.md` 的 D1–D9（已作决定的不要重开）、`.claude/handoff/2026-11-04-receipt.md` 的 B 组十条、两份 plan 的落地情况。
L5 发布口径：`VERSION` 1.2.0 + `CHANGELOG` + `design/specs/versioning-and-release.md` 三态；本机 git tag = 0，`v1.1.1` 不可追溯 → 这条只能记 blocked。

【修复】只修「已复现且根因已定位」的缺陷，由 `代码执行者` 串行改。每处修复必须给：改前红灯 / 改后绿灯 + **反向对照**（把实现改坏，对应用例必须变红）。界面类必须给机械判据数值（getBoundingClientRect、scrollWidth、disabled、hidden），不许用"看起来"。

【产出】全部写副本内 `reports/`（已被 .gitignore，正常）：AUDIT.md（总账）、FINDINGS.md（逐条：现象/证据/根因文件:行号/严重度/修没修）、PROTOTYPE-GAP.md（99 处逐条）、DECISION-CHECK.md（D1–D9 + B 组）、RELEASE-STATE.md（L5）、EVIDENCE-INDEX.md（命令 + 输出摘要）、RISK.md（未验证项）、PATCHES/（改动补丁）。

【禁止】push、commit 主树、合并分支、打 tag、装依赖、访问学校真实接口、读 `.env` 或 `local/data`/`server/data`/`server/config.json`、切模型渠道、关机、问我要不要继续。

【卡住怎么办】同一问题最多试 2 轮；第 3 轮写进 `reports/BACKLOG.md`（现象/试过什么/需要什么）标 blocked，立刻进下一层。任何"只能人定"的问题：先做最小可逆选择并记进 `reports/DEFERRED.md`，不停下。

【时间纪律】07:45 后不再开新的长修复，07:55 前收尾并输出四行汇报：L1–L5 各一句结论 / 缺陷数 / blocked 数 / 报告路径。

【终止条件只有三条】五层都有结论且报告写完；额度不可用；连续三轮无有效进展（先写 BACKLOG）。

【三态标记】每条结论必须标：已复现 / 静态推断 / 无法验证。

## 2. 附加在目标的第二段（可选，写进 goal 之后单发一条）

先用一轮做**派发连通性自检**：派 `代码审查员` 审 `local/ui/controllers/tick.js` 最近 3 笔改动，要求只读、给文件:行号。拿到结果再进 L1，避免整晚空转。

## 3. 发之前的三条提醒

- 工作区必须选 **副本**（`<审计副本>`），不是主树。
- 主树那 27 项是别人在途的改动，副本已冻结，不要回头改主树。
- 巡检由我每 60 分钟做一次，只看 `git`/`reports/` 时间戳，不看截图。
