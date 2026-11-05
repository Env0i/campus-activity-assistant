# AUDIT — 总账(2026-11-04 深夜开审,2026-11-05 收官)

工作区:<审计副本>。开工三数核对通过(pwd cygpath 确认、`git status --porcelain | wc -l`=27、`git log --oneline -1`=4ec0b3d)。审计期间按修复纪律改动工作区(见 §修复),未 commit、未 push。

## 一、五层结论(每层一句 + 分母/逐条对账)

### L1 代码 —— 结论:发现 6 类缺陷、5 类风险、4 类漂移;3 个"结构性必红"缺陷已修(红→绿→反向对照齐备),AGENTS.md 硬边界检查零违反
- 分母与覆盖:近 7 天提交深读 11 笔(高风险链全读)+55 笔 stat 核对(抽样依据与未抽清单见 FINDINGS);27 项未提交逐 hunk 审查;千行大文件(app.py 3757/grab.py 3683/gui.py 1116)函数级全审(145/110/37 个定义全清单);server/scripts 24 文件逐个结论;全量 469 文件规则扫描(7 规则族,逐文件判定入 COVERAGE.md)。
- 逐条:F-01 `<tmp>` 夹具(已修 Fix A)、F-02 时钟双读(已修 Fix B)、F-03 属性急切求值(已修 Fix C)、F-04/F-05 update.js 丢动态文案(已修 Fix D)、F-06 空 flow 去重(已修 Fix E)、F-08/F-10/F-11 server 独立实现漂移(留人定)、F-09/F-13/F-14 风险(记录)、F-12 gui.py 遗留壳漂移、F-15 间歇 flake(BACKLOG)。

### L2 原型 —— 结论:99/99 逐条核完(M=N=99,无漏);15 已实现 1:1 / 10 部分 / 72 未实现(阻断级,集中手机页+计划栏结果态+设置抽屉)/ 2 不计;台账本身 10 处记录错误 + 14 条已过时(演示控件数"13"不成立,实际 16 标注/19 控件)
- 逐条表见 PROTOTYPE-GAP.md(每条双侧证据:原型文件:行 + 实现文件:行或 grep 无匹配命令)。0 条无法静态判定。
- 72 条未实现按任务书口径=阻断;处置为记录+排期留人定(DEFERRED-1),未擅自开工(工程量数天且手机页服务层未深审)。

### L3 契约文档 —— 结论:§9 63/63 逐条标完:60 已验(7 条带漂移注记)/ 3 blocked(需实跑:五视口渲染、runtime-check 实包、680×480 真实指针)/ 0 未覆盖;五篇 specs 四篇有漂移点(共 8 处,全是"文档落后于实现"方向),41 红无一落在 §9 证据链上
- 逐条表见 FINDINGS F-19~F-24 与 EVIDENCE-INDEX §6。契约主测试 test_ui_contract 289 例全绿(修复后)。

### L4 决策记录 —— 结论:D1–D9 中 8 条已落地、D7 部分落地(截图验收无法在仓库验证);B 组 6 落地、B5/B7 回执标注与仓库现状矛盾(未落地)、B9 符合"待执行"语义、B6 无法验证;Plan-A 除 C1 规格残留一行外全落地;Plan-B M1-M9/S1-S6/L1/L3/L5 全落地
- 逐条表见 DECISION-CHECK.md(M=9+10+7+17+,逐条有判定)。已作决定无一重开。

### L5 发布口径 —— 结论:三态核完;VERSION=1.2.0 与 CHANGELOG「待发布」一致;v1.1.1「已发布」本机不可追溯(tag=0)记 blocked(任务书预告结论);versioning spec 规则本体与发布纪律一致;README:256 一处版本口径漂移
- 见 RELEASE-STATE.md。发布口径类文件今晚一律只记录不改动。

## 二、修复账(代码执行者串行,唯一写者;每处=改前红灯/改后绿灯/反向对照+patch)

| Fix | 内容 | 红 | 绿 | 反向对照 | patch |
|---|---|---|---|---|---|
| A | `<tmp>` 夹具映射(11 文件 16 处) | 本机 f=1,e=40;server 66 failed | 本机 e=2(另案);server 122 passed | test_https_only 红↔绿 | fix-A-tmp-fixtures.patch |
| B | plan_service 时钟单读(按 kind 门控) | 2!=1 | 单测+25+347 OK | 撤门控红↔绿 | fix-B-clock-single-read.patch |
| C | _component_service_for 惰性化 | AttributeError | 单测+7+343 OK | HEAD 态红↔绿 | fix-C-component-service-lazy.patch |
| D | update.js 恢复后端文案透传(launching/no_installer)+2 新契约用例 | 2 failures | 288 全量 OK | 固定文案红↔绿 | fix-D-update-dynamic-text.patch |
| E | relogin.js 空 flow_id 哨兵去重+1 新契约用例 | 调用序列翻倍红 | 289 全量 OK | 旧条件红↔绿 | fix-E-relogin-empty-flow.patch |

界面类修复的机械判据:textContent 精确等值(F-04/F-05)、API 调用序列全等(F-06)、getBoundingClientRect/scrollWidth 类视觉判据本批未涉及(今晚 UI 修复全部是文案与调用语义,均有 DOM 级断言)。

## 三、数字对账

| 指标 | 数 |
|---|---|
| 缺陷(三档:缺陷) | 8(F-01/F-02/F-03/F-04/F-05 计代码缺陷,F-25/F-26/F-27 计流程缺陷;代码缺陷 5 项已修,流程缺陷 3 项留人定) |
| 风险 | 7(F-01b/F-06 已修、F-09/F-13/F-14/F-15 未修、密钥常量提示) |
| 漂移 | F-07/F-08/F-10/F-11/F-12/F-17~F-24/F-29 + F-18(72 条原型缺口) |
| blocked | 5:§9#14、§9#30、§9#57(需实跑)、v1.1.1 追溯(BL-1)、B6(条件未到)——见 RISK/BACKLOG |
| 无法验证 | R-1/R-3/R-6/R-7/R-8/R-9 等(见 RISK.md) |
| 已修/总数 | 5 修复切片(Fix A–E),全部红→绿→反向对照;未 commit |
| 修复后终态 | 本机套件 1696 例 [终态数字见 §四]、server 122 passed、node 37+8、语法门槛 0 错 |

## 四、终态验证(修复全部落地后,主代理复跑)

- 本机:`python -m unittest discover -s local/tests -p "test_*.py"` → **Ran 1699 tests, OK (skipped=4),EXIT=0**(基线 1696 例 FAILED(failures=1, errors=40) → 41 红全部清零;1699=1696+新增 3 个契约用例;基线 4 个 skip 不变)
- 服务器:`python -m pytest server/tests -q` → **122 passed, 0 failed**(基线 66 failed,56 passed)
- node:test_bot_runtime **37/0**、test_handled_messages **8 passed**
- 语法:`python -m compileall -q local server` + `node --check local/ui/app.js` → OK
- 覆盖账:COVERAGE.tsv **469 行**(=git ls-files 行数)、COVERAGE.md 逐文件表 469 数据行、未审 72 条全部带理由(脚本核验 none missing)
- 硬边界终检:`git tag | wc -l`=0、`git for-each-ref refs/tags | wc -l`=0(测试输出中的 tag 字样经查来自 release.py 在临时沙盒仓的自建远端,本仓零污染);工作区改动 37 个文件=开工 27 项+修复 10 文件,全部未 commit

## 五、产出清单(reports/,均已被 .gitignore)

AUDIT.md(本文件)、FINDINGS.md(29 条逐条)、PROTOTYPE-GAP.md(99 处逐条)、DECISION-CHECK.md(D1–D9+B 组+两份 plan 逐条)、RELEASE-STATE.md(L5 三态)、COVERAGE.md + COVERAGE.tsv(469 文件逐行覆盖账)、EVIDENCE-INDEX.md(命令+输出摘要)、RISK.md(未验证项)、DEFERRED.md(8 项留人定)、BACKLOG.md(BL-1 blocked)、PATCHES/(fix-A~E 五个补丁)、_tools/(count.py/static_scan.py/coverage_gen.py + 扫描产物)。

## 六、派发记录(真调用 Agent 工具,并行 ≤3,写者唯一)

| 批次 | 派了谁 | 审什么 | 拿到什么 |
|---|---|---|---|
| 1 | 代码审查员 | 27 项未提交 diff+66 笔抽样 | 6 发现+3 观察+逐文件审计表+命令清单 |
| 1 | 后端架构师 | 千行大文件+server 全链+硬边界 | 9 发现+函数级审/未审清单+24 文件逐个结论 |
| 1 | UI 视觉验收设计师 | 99 处逐条独立重核 | 15/10/72/2 判定+台账 10 处纠错 |
| 2 | 代码审查员(续,L4) | D1–D9+B 组+两份 plan | 8+1 部分/6+3 矛盾/Plan 双全表 |
| 2 | 技术文档工程师 | §9 63 条+5 篇 specs | 60/3/0+8 漂移点 |
| 2 | 测试自动化工程师 | 正式测试基线+口径核实 | 基线总表+失败三分类+68/423 边界解释 |
| 2 | 密钥与凭据治理工程师 | 469 文件+68 笔历史凭据扫描 | 真密钥 0+治理 4 项正面结论 |
| 3–7 | 代码执行者(串行×5) | Fix A–E | 5 补丁+红绿灯+反向对照 |

## 七、留人定(摘,详见 DEFERRED.md)

72 条原型缺口排期 / B5·B7·C1 回执矛盾处理 / README 版本口径 / server 三漂移移植授权 / 协议常量搬移排期 / flake 夹具处理 / 提交级全覆盖是否需要 / 空 flow 协议层强制与否。
