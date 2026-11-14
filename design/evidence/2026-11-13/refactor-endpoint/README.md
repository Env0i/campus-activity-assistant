# 重构终点的证据收集（refactor-endpoint）——口径与复跑

本目录是计划 `plan-20261113-refactor-endpoint-evidence`（D1–D10）的产物：只收集事实，不下判断、不给方向性措辞。七个离线表在 `tables.md`（表 A–G），联网试跑在 `online.md`（表 H）；四道防线的审计与攻防在同目录的 `ADVERSARIAL-AA1.md`、`ADVERSARIAL-AA2.md`、`ADVERSARIAL-AA3.md`、`DEFENSE.md`、`SPOT-AUDIT.md`。

## 时间口径

- 设备本地时区偏移为 +8 小时；T0 = 2026-11-13 22:30 (UTC+6)。此后全篇只用 UTC+6 这一种表示，跨阶段用 T0+n 分钟。
- 计划创建：2026-11-13 20:30 (UTC+6)（原值 2026-11-13T22:30:00+08:00，仅此处保留原始偏移，用于复核换算）。
- 证据目录名固定 2026-11-13，跨零点不改；执行区间自 T0 起至收工（各阶段落盘时刻见结果文件）。
- 与那轮基线（design/evidence/2026-11-12/refactor-audit/）的旧时间戳不做换算；对照时只写「那轮基线 / 本轮（T0+n）」。

## 基线与开工核对

开工（T0）时执行的三条命令与原文（收工比对基准）：

```text
$ git rev-parse --short HEAD
dddc179
$ git log --oneline -3
dddc179 docs(proposal): 记下第 0 步结果与六项裁决
3c19727 docs(agents): 写入代码结构规则
512dddd chore(lint): 引入 ruff，存量告警只减不增
$ git status --short
（空输出）
```

全部数字以 `dddc179` 为准。

## 工具版本

Python 3.12.9；node v24.16.0。表 H 另装 mypy 2.4.1、coverage 7.17.3、ruff 0.17.5（只装进临时目录，收工删除，未进任何 Python 环境）。

## 各表口径与复跑命令

每张表的详细口径在对应脚本顶部与 `tables.md`、`online.md` 的「量什么」行里，此处只列要点与命令。

- **D2 归属对照表**：严格照计划 decisions D2 的固定对照表执行，一个文件的归属只有一个；对照表没有的文件一律记「未排进任何一步」，不看 baseline.json 的 reason 字段。对照表原文写在 `scripts/ownership.py` 顶部常量（出处注释指向本计划）。
- **表 A（D3）**：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ownership.py` —— 四份名单（baseline.json 文件两档、函数两档、测试函数、类；ui_layer_allow.json；LEGACY_DIRECTION_VIOLATIONS；ruff.toml per-file-ignores）逐项标归属，自校行输出「各步项数 + 未排进项数 = 四份名单总项数」。
- **表 B（D4）**：`node design/evidence/2026-11-13/refactor-endpoint/scripts/ui_coupling.mjs` —— local/ui 下不含 m/ 的每个脚本量行数、顶层函数数、全局名字数、S 写入处数；未排进脚本另量与步骤 1 文件的相互引用。定义与引用的识别照搬那轮基线的 jslex.mjs / jsscan.mjs（两文件逐字未改，副本在本目录 scripts/，便于脚本被复制到别处时仍能复跑），load/topDefs/scanUses 照搬自那轮的 globals.mjs，局限照抄如下：
  > 按名字匹配，不做作用域分析。函数的参数或局部变量如果和别的文件的全局同名，会被多数成一次引用；脚本把「本文件内有同名局部声明」的引用单独标出来，清单里只用没有同名局部声明的。经 window["名字"] 这类字符串访问的数不到。
- **表 C（D5）**：重跑那轮基线的五个清点脚本（命令在 tables.md 表 C 段）。这批脚本不许原地改；本轮五个脚本全部跑通、stderr 全空、无一行「输出里没有该行」，没有产生复制到本次 scripts/ 的修改副本。
- **表 D（D6）**：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/annotations.py` —— ast 数函数标注，分三类；五组照 D6，local/build 与 local 其他子目录单列（口径疑点 1）。
- **表 E（D7）**：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ui_assertions.py` —— 五种断言调用的直接实参字符串按固定规则分三类（先命中先算）；抽样种子 20261113，三类各 20 条，每条带 文件:行号 与原文。
- **表 F（D8）、表 G（D9）**：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py` —— 设施盘点只查「有没有」；文档数字对账的四类正则写在脚本顶部，原文含主机路径时替换为 `<主机路径>` 并在该行标注，其余字符不动。
- **表 H（D10）**：联网试跑（mypy、ruff、覆盖率全量），命令与结果见 `online.md`；本表经用户明确授权执行。
- **表 E2（本计划 decisions D7）**：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ui_test_kinds.py` —— 表 E 同一批 17 个文件里每个 test_ 函数按「是否跑 node」分两类（ast 找运行函数并沿调用传播，含类方法与嵌套）；表 E 原文不动，表在 tables.md 表 E 后面。
- **零执行清单加列（本计划 decisions D6）**：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/zero_exec_in_tests.py` —— 把 online.md 两份「一行都没执行到的函数」清单的每个函数取限定名第一个点号前的部分，数它在 local/tests 下全部 .py 文本里作为完整单词出现的次数；表在 online.md 的 H3 末尾。

## 多智能体派发台账（摘要）

- 可用子代理清单核对：计划点名的 8 个角色名（代码库入职引导工程师、后端架构师、测试自动化工程师、技术文档工程师、证据收集者、遗留系统工程师、策略对决推演师、现实检验者）全部在可用清单里，未改名、未换用只读专家替代。
- 派发 8 次成功、1 次未启动（技术文档工程师首轮因并发上限未启动，按补充规则 2.3 记一次重派）：表 A、B 由代码库入职引导工程师产出；表 C 由后端架构师产出；表 D、E 由测试自动化工程师产出；表 F、G 由技术文档工程师产出；AA1 由证据收集者产出；AA2 由遗留系统工程师产出；AA3 由策略对决推演师产出；抽检由现实检验者产出。逐条台账（subagent_type、目的、产出文件、是否重派）见 `.claude/results/20261113-refactor-endpoint-evidence-result.yaml`。
- 分工方式：子代理只回文本（并行只读），统一由主代理落盘；每次派发的 brief 自带仓库相对路径、D 编号口径原文、输出格式与「只写事实、不下判断」约束。

## 口径疑点

1. D6 的五组不涵盖 local/build（4 个文件 45 个函数）；脚本把它与「local 其他子目录」（本轮 0 个文件）单列，未自行并组。
2. D7 的「断言调用里的字符串字面量参数」取直接实参（含关键字实参），嵌套调用（如 `read("ui/app.js")`）里的字面量不算；文件合计与三类之和自校一致（3138）。
3. D9 测试用例个数的实测以 ast 数 test_ 函数（local/tests 2581、server/tests 123、合计 2704）；local/tests 的计数与 H3 全量运行的「Ran 2581 tests」一致；server/tests 未运行（表 H 只跑本机版全量）。
4. D3 归属不看 baseline 的 reason 字段，因此 reason 写着步骤 2 的项（如 local/infrastructure/component_packages.py、local/application/plan_service.py::run_plan_task）按 D2 记「未排进任何一步」。
5. 磁盘上没有 .githooks/ 目录，git config core.hooksPath 未设置（只读查询，退出码 1）；计划 git_rules 写的 .githooks/commit-msg 门禁在本工作区不可见。表 F 照实记「无」。
6. 表 C「审计时」值取自那轮基线的 README.md 与 inventory.md；其中「S 的引用文件数 32」取高扇入表 S 行，「写入文件数 27」取写入小节标题行。
7. D4「顶层函数数」只数 function 声明（const 箭头函数计入「全局名字数」、不计入本列），与那轮 C2 表「函数」列同口径。
8. 表 G 行数类排除了「第 N 行」「文件:行号」式引用（正则 RE_LINE_REF 在 facilities.py 顶部）；AGENTS.md 里「超过 800 行的文件与超过 100 行的函数」一句因句内没有具体 .py/.js/.mjs 文件名而不入表。
9. mypy 计数只数带 [错误码] 的 error 行；--no-error-summary 下每条错误一行，note 行不计。
10. coverage JSON 的文件键在本机是反斜杠路径；coverage_by_function.py 先归一成正斜杠再取数。
11. 表 E 抽样先按（文件、行号、字面量）排序再 random.Random(20261113).sample，保证复跑同序同样本；「源码形状」类里混有中文注释性字面量（如「已报名组：注空、cls signed」），它们不含规则一、二的特征，按 D7 规则三如实归入。「文案」与「源码形状」的边界按 D7 字面口径执行：去「空白与标点」（Unicode P* 类）后，剩余字符须全是汉字、数字或全角符号——「全角符号」指 FF 段（U+FF00–FFEF）的符号类字符（＝、＋、＜、＞），放行；半角符号（= < > | × → ≤）不放行，归「源码形状」。对抗审计 AA2 据此指出 27 条边界错并（最初实现把符号类全部去除），已按此口径返修脚本并重出表 E。
12. 表 E 的 文件:行号 取断言调用所在行；多行调用时与字符串字面量所在行可能差 1（AA2 记录过 1 例）。
13. 表 C 的「前端全局名字总数 562」按唯一名计（globals.mjs 口径）；表 B B1「全局名字数」列逐文件合计 563，差 1 是 local/ui/views/phone.js 顶层同名定义 PhonePanel 两处（:154 的 const 与 :1252 的 window.X 赋值），表 B 尾注与 tables.md 导言写明对照。
14. 表 G 的三行「约 N 行」（docs/superpowers/specs/2026-11-03-architecture-revision-design.md 第 39、121、194 行）是位置引用（指函数或常量在文件中的位置），不是「这个文件有多少行」；按本计划 decisions D2，第 39、121 行移出正表，三行的原文与理由都在表 G 下的「已排除：位置引用」一节；第 194 行「约 61 行」低于三位数下限，本就未进正表；行数正则与三位数下限未改，grab.py 4076 行、app.py 4873 行两行实测值不变。
15. 表 H 两轮对照（本计划 decisions D3 与 D4）：H1 的 mypy 错误总数 61、1270 两轮相同，「目录×错误码」分布两轮不同，第二轮分布已并排列在 online.md 的 H1 小节开头；H2 的 E 组总数，第一轮产物与第二轮实测都是 3783，review2 对账行写「3784（第一轮）vs 3783（第二轮）」且本计划 D4 沿用了它，但「3784」在第一轮产物与两份结果文件里检索不到出处，已按「对不上写明差在哪」在 online.md 的 H2 段如实记录，第一轮实测值未改。
16. 表 H 的零执行清单（本计划 decisions D5）：有的测试用 ast 把 Api 的方法抽出来单独求值、不 import local/app.py（local/tests/test_terms_consent.py 文件头写明这种做法），coverage 记不到 local/app.py 头上，两份零执行清单只是「可能没测到」的上限；原计划 D10 要的「每个文件的行覆盖率」未产出（见跳过的任务）。
17. 表 E2（本计划 decisions D7）的口径与表 E 的「node 沙箱测试函数数」列不同：E2 用 ast 找运行函数（函数体调用了 run_js，或函数源码段同时含 subprocess 与 node）并沿调用传播，把每个 test_ 函数分为跑 node 与不跑 node；表 E 那一列只数函数子树里直接出现 run_js 调用的 test_ 函数，两列不可互比。E2 合计与参照数逐项一致（748、552、196；test_phone_ui.py 210、195、15；test_ui_contract_components.py 15、0、15）；D6 零执行清单 64 个函数里 37 个名字在测试里出现过，与参照数一致。

## 跳过的任务

- 无。D1–D10 全部执行；表 H 按用户授权执行。服务器版全量测试不在本计划范围（H3 只跑本机版全量），不算跳过。
- 本计划追加：每个文件的行覆盖率：未产出（原计划 D10 要的这张表没有产出；覆盖率数据已随临时目录删除，本计划不重跑）。

## selfcheck

```bash
python -B design/evidence/2026-11-13/refactor-endpoint/scripts/selfcheck.py
```

扫描范围与类别见脚本顶部说明；反向验证三例的输出记录在结果文件。

本计划（2026-11-14 返修）改完后从仓库根直接跑上面这条命令：输出「通过」，返回码 0。返修前的实况：收工后直跑返回 1，报出 review2/VERDICT.md 第 39、47 行命中了自查的关键词表；按本计划 decisions D1 把两行改写成陈述事实的句子后通过，未移走任何目录、未加豁免。
