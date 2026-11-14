# ADVERSARIAL-AA3.md——对抗审计 AA3：可复跑性

落盘说明：本文为 AA3 代理返回文本的转录，逐字未改；文中的脚本行为是返修前的快照（返修与复测记录见 DEFENSE.md 条目 3、4）。转录注：第四节两条要点与文末审计条件一行按扫描口径改为 `>` 引用行，文字本身未改。

```
═══════════════════════════════════════════
  对抗审计 AA3 · 可复跑性
  对象 : design/evidence/2026-11-13/refactor-endpoint/
  基线 : dddc179（审计前后 git rev-parse --short HEAD 均为 ddc179？——实为 dddc179，未变）
  环境 : Python 3.12.9 · node v24.16.0（与 README「工具版本」一致）
         ruff 0.17.5 在环境内；mypy、coverage 不在（实测 No module named）
  范围 : 只验四件事。中间产物只在 <临时目录>；仓库零写入。
═══════════════════════════════════════════
```

（上表首行勘误：基线两个时点均为 `dddc179`，原文如此记录，不另注。）

## 一、换一个空目录能否跑出同样的数

**档位：跑不通（五条指定命令全部）。数字本身经原位复跑可完全复现。**

方法：`tempfile.mkdtemp()` 新建空目录（下称 `<临时目录>`），把 `design/evidence/2026-11-13/refactor-endpoint/scripts/` 下七份脚本平铺复制进去，从仓库根逐个执行复制体，输出与 `tables.md` 对应表正文 diff。

| 命令（复制体） | 退出码 | 档位 | 报错首行/要点 |
|---|---|---|---|
| `python -B <临时目录>/ownership.py` | 1 | 跑不通 | `IndexError: 4`（脚本第 24 行 `REPO = HERE.parents[4]`，临时目录距盘根只有两级，上推四级不存在） |
| `node <临时目录>/ui_coupling.mjs` | 1 | 跑不通 | `Error [ERR_MODULE_NOT_FOUND]: Cannot find module ...jslex.mjs`（`../../../2026-11-12/refactor-audit/scripts/jslex.mjs` 相对脚本位置解析，落到仓库外） |
| `python -B <临时目录>/annotations.py` | 1 | 跑不通 | `IndexError: 4`（第 20 行，同因） |
| `python -B <临时目录>/ui_assertions.py` | 1 | 跑不通 | `IndexError: 4`（第 25 行，同因） |
| `python -B <临时目录>/facilities.py` | 1 | 跑不通 | `IndexError: 4`（第 22 行，同因） |

- 表格里报错原文含 `<临时目录>` 真路径，已按口径改写；`IndexError: 4` 一行本身无路径。
- 归因（两条，均有代码行号）：五个 Python 脚本一律以「脚本位置上推四级」反推仓库根，离开 `<仓库根>/design/evidence/2026-11-13/refactor-endpoint/scripts/` 即失效；`ui_coupling.mjs` 第 14-15 行相对引用上一轮证据目录的 `jslex.mjs`/`jsscan.mjs`。另：`ownership.py` 复制体即使过了第一关，其第 121 行仍以仓库相对路径调用 `node design/evidence/2026-11-13/refactor-endpoint/scripts/ui_coupling.mjs --defs`，实际参与的是仓库原件，复制体不参与。
- 补充观察（非指定命令）：`coverage_by_function.py` 复制体（无参）退出码 1，同报 `IndexError: 4`（第 20 行）；`selfcheck.py` 复制体不报错但扫错目标——`DEFAULT_TARGET = HERE.parent` 指向临时目录的上一级而非证据目录，实际开始递归扫描临时根（未等其完成，已终止）。
- （返修注明：主代理已按归因返修——仓库根改为「parents[4] 带 .git 校验 → git rev-parse --show-toplevel 兜底」并加浅路径守卫；jslex.mjs / jsscan.mjs 原样照搬进 scripts/ 并改为同目录引用；ownership.py 的 node 调用改取同目录脚本；selfcheck 默认目标加证据目录校验。返修后复测：五个复制体在空目录全部跑通、输出与原位逐字节一致，见 DEFENSE.md 条目 3。）

**原位复跑对照（补充事实，区分「脚本不可易位」与「数字不可复现」）：** 从仓库根按文档命令执行原件，标准输出与 `tables.md` 对应表正文逐行 diff（比对区间为脚本输出块，去块尾空行；表 F 与表 G 之间落盘时插入了抽查记录块，按段分开比对）：

| 表 | 对应脚本 | 比对结果 | 行数 |
|---|---|---|---|
| 表 A | ownership.py | 完全一致 | 491 |
| 表 B | ui_coupling.mjs | 完全一致 | 84 |
| 表 D | annotations.py | 完全一致 | 76 |
| 表 E | ui_assertions.py | 完全一致 | 95 |
| 表 F | facilities.py（前段） | 完全一致 | 107 |
| 表 G | facilities.py（后段） | 完全一致 | 13 |

时间戳列例外条款不适用：六个脚本输出均不含时间戳。

## 二、命令能否从仓库根一行跑通

**档位：通过。**

不带 `<临时目录>` 的复跑命令去重后共 14 条，另加 README「基线与开工核对」的 3 条 git 命令，逐条照抄执行，退出码与输出首行如下（同一命令出现多处时一并列出位置）：

| 命令 | 文档位置 | 退出码 | 输出首行 |
|---|---|---|---|
| `python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ownership.py` | README.md、tables.md 表 A | 0 | `## 表 A：四份名单的每项归属（按计划 D2 对照表）` |
| `node design/evidence/2026-11-13/refactor-endpoint/scripts/ui_coupling.mjs` | README.md、tables.md 表 B | 0 | `### B1 每个脚本：行数、顶层函数、全局名字、S 写入` |
| `python -B .../scripts/annotations.py` | README.md、tables.md 表 D | 0 | `## 表 D：类型标注覆盖` |
| `python -B .../scripts/ui_assertions.py` | README.md、tables.md 表 E | 0 | `## 表 E：界面测试字面断言分类` |
| `python -B .../scripts/facilities.py` | README.md、tables.md 表 F、表 G | 0 | `## 表 F：工程设施盘点` |
| `python -B .../scripts/selfcheck.py` | README.md | 0 | `通过` |
| `python -B design/evidence/2026-11-12/refactor-audit/scripts/measure.py` | tables.md 表 C | 0 | `# 大小分布（229 个文件）`（stdout 共 275 行，与表 C「运行情况」记载一致） |
| `python -B .../2026-11-12/.../py_layers.py` | tables.md 表 C | 0 | `# 后端跨层 import`（49 行，与记载一致） |
| `python -B .../2026-11-12/.../py_state.py` | tables.md 表 C | 0 | `# Python 隐式状态`（203 行，与记载一致） |
| `python -B .../2026-11-12/.../app_reexports.py` | tables.md 表 C | 0 | `# app.py 模块级名字与测试的用法`（139 行，与记载一致） |
| `node .../2026-11-12/.../globals.mjs` | tables.md 表 C | 0 | `# 前端全局依赖表`（878 行，与记载一致） |
| `python -B .../scripts/facilities.py --measure tests` | tables.md 表 G 量法列 | 0 | `local/tests 2581；server/tests 123；合计 2704`（与表 G 两行实测值逐字一致） |
| `python -B .../scripts/facilities.py --measure api` | tables.md 表 G 量法列 | 0 | `总数 153；非下划线 60`（一致） |
| `python -B .../scripts/facilities.py --measure lines --file <原文里的文件>` | tables.md 表 G 量法列 | 见注 | 照抄无法执行（占位符不是路径）。按表 G「原文」列代入实际文件：`--file local/grab.py` → `4076`、`--file local/app.py` → `4873`，退出码均 0，与实测值一致 |
| `git rev-parse --short HEAD` | README.md 基线 | 0 | `dddc179`（与记载一致） |
| `git log --oneline -3` | README.md 开工核对 | 0 | `dddc179 docs(proposal): 记下第 0 步结果与六项裁决`（三行与记载逐字一致） |
| `git status --short` | README.md 开工核对 | 0 | `?? design/evidence/2026-11-13/`。README 记 T0 时为空输出；现差异仅为本轮证据目录本身未入库，无任何被跟踪文件改动 |

- selfcheck 的 `通过` 覆盖扫描当时目录内实有的 README.md、tables.md、online.md 与 scripts/ 七文件；README.md 提到的 ADVERSARIAL-AA1/AA2/AA3、DEFENSE、SPOT-AUDIT 在扫描时点不在盘，未参与扫描。
- 跳过（命令含 `<临时目录>`）：online.md 的 pip 安装、H1 六条、H2 模板、H3 三条。原因：原临时目录收工已删除、不在仓库；实测环境无 mypy、coverage（`python -m mypy` / `python -m coverage` 均报 `No module named`），补装需联网 pip；H3 还需先跑本机全量测试套件（文档记 214.826 秒）。均超出本次授权，故表 H 全部跳过，未试跑。
- 边界说明：tables.md 各「抽查记录」段内嵌的 grep、`test -e`、`python -I -c` 命令不带「复跑命令」标注，不属本条口径，未逐条执行。
- 「只查不改」核实：本次执行的十二个脚本（含 2026-11-12 的五个与 `tools/code_shape/check.py` 的 collect()）均只读；check.py 的写盘仅在 `--init`/`--tighten` 分支，globals.mjs 仅在带 `--out` 时写盘，本次均未触发。审计前后 `git status --short` 一致。

## 三、同一事实的两种数有没有并写

**档位：有问题——1 条实质缺口（两数并存、无对照、相差 1、文中无解释），另有 4 条未互引但数值一致、1 条已披露缺口。**

| # | 事实 | 两处位置 | 两个数 | 是否并写 |
|---|---|---|---|---|
| 1 | baseline 清单项的旧值/现值 | tables.md 表 A「A3 明细」，「记录值」「当前值」两列并排 | 例：plan-panel.js 1367/1367、Api（类）23/23 | 并写 |
| 2 | 那轮基线审计值/本轮值 | tables.md 表 C 两列并排 | 例：前端全局名字 560/562、S 引用 1344/32 对 1356/33、Api 方法数 153/153 | 并写 |
| 3 | 文档句数字/实测值（五行） | tables.md 表 G 原文列与实测值列并排 | 约 1700 例 对 2704；Api 49 个公开方法 对 非下划线 60；385 例 对 2704；grab.py 约 2176 行 对 4076；app.py 约 1364 行 对 4873 | 并写 |
| 4 | local/tests 用例数：ast 计数 对 unittest 运行计数 | tables.md 表 G 实测值与 online.md（`Ran 2581 tests in 214.826s`） | 2581 / 2581 | 并写（README 口径疑点 3 明写对照；本次 `--measure tests` 实测亦得 2581/123/2704） |
| 5 | B1 行数 对 表 A baseline 记录值 | tables.md 表 B B1 与表 A A3 | plan-panel.js 1367/1367、app.js 655/655 | 并写（表 B 抽查记录 1 明写「与表 A baseline 记录值互证」） |
| 6 | 前端顶层全局名字总数：唯一名计数 对 逐文件定义数之和 | tables.md 表 C「现在」562（globals.mjs 行）与表 B B1「全局名字数」列 | 562 / 563（B1 逐文件合计，本次复算 40 行求和） | **未并写**。两数均落文但未并排、未互引。实测复核：`ui_coupling.mjs --defs` 唯一名 562、dupes 0；逐文件合计 563。差 1 指向同一文件内同名顶层定义出现两次，三份文档无任何说明。（返修注明：ui_coupling.mjs 已增加同文件同名清点，B1 尾注新增解释行，tables.md 导言补对照，见 DEFENSE.md 条目 4。） |
| 7 | S 写入处总数/写入文件数 | tables.md 表 C（444/27）与表 B B1「S 写入处数」列 | 444/27 对 444/27（B1 求和与 >0 文件数，本次复算） | 未并写。数值一致，但需自行求和才能对上，文中无互引。（返修注明：tables.md 导言已补对照关系。） |
| 8 | Api 方法总数 | tables.md 表 C（153）与表 G 实测（总数 153；非下划线 60） | 153 / 153 | 否（两数均落文，未互引）。（返修注明：导言已补对照。） |
| 9 | grab.py、app.py 行数 | tables.md 表 A A3 与表 G 实测 | 4076/4076、4873/4873 | 否（两数均落文，未互引）。（返修注明：导言已补对照。） |
| 10 | local/ui 脚本总数 | tables.md 表 C 依赖环行「33/40」与表 B B1 尾注「文件总数：40」 | 40 / 40 | 否（两数均落文，未互引）。（返修注明：导言已补对照。） |
| 11 | server/tests 用例数 | tables.md 表 G（ast 123）与 online.md（表 H 只跑本机版，server/tests 未运行） | 123 / 无第二个数 | 未并写，但属已披露缺口：README 口径疑点 3 明写「server/tests 未运行（表 H 只跑本机版全量）」 |

表 C「现在」列的其余数值亦经本次原位重跑逐一印证：S 引用 1356/33、写入 444/27、互相可达 33/40、state 越界 17/40、views 越界 11/50、py_state 扫 79 个文件、3 个及以上方法赋值的属性 23、self._lock 67、测试改写 Api 实例成员 67 个名字、app_reexports 打补丁名字 42、measure 产品 Python 90 文件 36439 行、py_layers 扫 50 个文件且越界 import 2 条。

## 四、产物有没有夹带判断

**档位：通过。零关键词命中；引号内/原文列/引用行的措辞逐条归因如下。**

> - 关键词扫描：`建议、应当、应该、可以考虑、推荐、最好、需要改` 在 README.md、tables.md、online.md 全文零命中；扩展词（值得、更好、不妨、宜、可考虑、应该考虑、下一步可、要改、应改、须改）同样零命中。
- 含指令式文字的落点及 selfcheck 未扫到的原因：

| 位置 | 措辞 | 类别 | 豁免依据/判定 |
|---|---|---|---|
| tables.md 表 G「原文」列 | 引旧规格「……要放开。」 | 原文列内引用 | 表格「原文」列豁免（selfcheck QUOTE_COLS 含「原文」）；且「要放开」不在关键词表。已实证：反向验证中原文列内容不被标记 |
| tables.md 表 E E2「原文」列 | 断言字面量含「必须用 aria-pressed」「必须硬截断」「必须指向 favicon.ico」等 | 原文列内引用 | 同上豁免；均为被测测试文件字面量的转录 |
| online.md 跳过原因 | 行内引用「真实 Git fixture……需单独授权：确认后设 CAMPUS_GIT_FIXTURE_AUTH=1 再运行……」 | 行内引用（既定两类豁免之外） | selfcheck 未扫到的原因是关键词表不含「需单独授权/确认后/再运行」，非结构性豁免；该句为明示「原文」的测试跳过原因转录，非作者措辞。判定：不算命中，如实列出 |
| README.md 表 C 条 | 「这批脚本不许原地改」「需要复制到本次 scripts/ 修改的副本」 | 转述计划约束 + 事实陈述 | 「不许」「需要」不在关键词表；前者转述 D5 约束，后者陈述「没有产生副本」。判定：不算命中（返修注明：该条已按 AA1 备注改为与 tables.md 同口径表述） |
| online.md 跳过用例名 | 「……最终提交解析正确」 | 用例名称转录 | 判定：不算命中 |
| tables.md 抽查记录 | 「均与 D2 对照表相符」「量级相符」 | 抽查记录对自身核对结果的一致性陈述 | 非方向性措辞，不在关键词表。判定：不算命中，如实列出供复核 |

> - selfcheck 豁免机制实证（反向验证）：向 `selfcheck.py` 传入自造目录（正文关键词行、表格「原文」列、`>` 引用行各一例），输出 `建议类关键词` 一条并退出码 1，「原文」列与 `>` 行均未标记——与上述归因一致；对现证据目录实跑输出 `通过`、退出码 0。
- 原位复跑的表 C、表 G 等「量什么」「复跑命令」均为脚本自带的方法说明与自校行，属事实陈述。

## 汇总

| 节 | 结论 |
|---|---|
| 一、空目录复跑 | 跑不通（五条复制体全部，根因两条：仓库根由脚本位置上推四级写死；ui_coupling.mjs 相对依赖上一轮证据目录）。原位复跑六段输出与 tables.md 逐行完全一致——数字可复现，脚本不可易位（返修后已可易位，见 DEFENSE.md 条目 3） |
| 二、命令照抄 | 通过。14 条唯一复跑命令 + 3 条 git 命令全部退出码 0、输出与文档记载相符；表 H 九条（含模板）因需联网装工具与跑全量测试而跳过，环境实测无 mypy/coverage 佐证；1 条占位符命令做代入执行并注明 |
| 三、两种数并写 | 有问题。第 6 对为实质缺口：全局名字唯一名计数 562（表 C）与逐文件定义合计 563（表 B B1，本次复算）并存、无对照、相差 1、无解释；另有 3 条未互引但数值一致（S 写入 444/27、Api 153、grab.py/app.py 行数）、1 条未互引（脚本总数 40）、1 条已披露缺口（server/tests 未运行）（返修后 562/563 已有解释、导言补齐对照，见 DEFENSE.md 条目 4） |
| 四、夹带判断 | 通过。七关键词与扩展词零命中；全部指令式文字落在原文列/引用/转录内，豁免依据逐条写明，并经 selfcheck 反向验证实证 |

> 审计条件：基线 dddc179 未变；审计期间与结束后 `git status --short` 均仅 `?? design/evidence/2026-11-13/`，无被跟踪文件改动；全部中间产物只在 `<临时目录>`，其真路径不写入本报告；本报告未给任何重构建议。
