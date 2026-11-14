# ADVERSARIAL-AA1——对抗审计（事实核对）报告

审计对象：`design/evidence/2026-11-13/refactor-endpoint/tables.md`（表 A–G 全部数据行与自校行）、同目录 `online.md` 的 H3 两个数字（仅做引用一致性检查，不改判）。
审计角色：AA1（证据收集者 / 事实核对），目标是找出证据里站不住的数字与 文件:行号，不是复述执行方报告。
落盘说明：本文为 AA1 代理返回文本的转录；返修后 tables.md 行号有整体位移，文中的行号是审计时点的快照。

## 0. 基线、抽样规则、核对方法

### 基线
- 仓库根经 `git rev-parse --show-toplevel` 确认；`git log --oneline -1` = `dddc179 docs(proposal): 记下第 0 步结果与六项裁决`，与 tables.md 头部「基线提交 dddc179」及该目录 README「基线与开工核对」一致。
- 开工时 `git status --short` 仅 `?? design/evidence/2026-11-13/`（被审目录本身，尚未入库）；收工时相同。本次审计未改动仓库内任何文件；复跑输出与核对脚本只放在 `tempfile.mkdtemp()` 新建目录（下文写作 `<临时目录>`）。

### 抽样规则（任务原文照录）
- 抽样单位 = 该表的数据行（表 E = E1 的每文件行 + E2 的抽样行，两部分都算）。
- 每表抽 30%（向上取整）且不少于 20 条；数据行不足 20 的表全量核对并写明。
- 表 F 全量核；表 A 自校行、表 E 自校行必须复核（重算等式）。

实际执行说明：本次对表 A–G 的全部数据行做了程序化核对（超出抽样下限）。各表数据行数与应抽数：

| 表 | 数据行数 | 应抽（30% 向上取整，≥20） | 实际核对 |
|---|---|---|---|
| A | A3 明细 254 行 + A2 未排进清单 165 行（两视图覆盖同一批 254 个名单项） | 126 | 全量 419 行 |
| B | B1 40 行 + B2 26 行 | 20 | 全量 66 行 |
| C | 11 行 | 不足 20，全量 | 全量 11 行 |
| D | D1 7 行 + D2 52 行 | 20 | 全量 59 行 |
| E | E1 17 行 + 合计行 + E2 60 行 | 24 | 全量 78 行 |
| F | F1 28 行 + F2 5 行 + F3 2 行 + F4 清单 | 全量（任务指定） | 全量 |
| G | 5 行 | 不足 20，全量 | 全量 5 行 |

### 核对方法（每条标注）
- **M1 复跑命令**：按各表「复跑命令」原样重跑，stdout/stderr 存 `<临时目录>`，与 tables.md 正文逐行比对。复跑结果：五个本轮脚本（ownership.py、ui_coupling.mjs、annotations.py、ui_assertions.py、facilities.py）与五个旧脚本（measure.py、py_layers.py、py_state.py、app_reexports.py、globals.mjs）全部退出码 0、stderr 全空；tables.md 表 A/B/D/E/F/G 六段正文与对应脚本 stdout **逐字节一致**（含「量什么」与自校行；仅末尾空行归一）。
- **M2 独立复算**：自写代码（ast、自写 JS 清洗器/花括号配对扫描器、独立计数器）重算数字，不复用被审脚本的实现。JS 函数行数一类：命名 function 声明用自写扫描器；对象字面量方法简写与 `#anonN` 编号项按任务口径「当前值（对当前文件或 check 量法）」用 `design/evidence/2026-11-12/refactor-audit/scripts/jsfuncs.mjs` 直接取值，两类结果与表中数字全部一致。
- **M3 文件:行号 与原文核对**：打开被引文件该行逐字比对（表 G 的管道符转义与行首空白差异按其抽查记录披露口径处理）。
- **M4 引用一致性**（仅 H3）：跨文件检查两数字的引用是否一致，不重跑全量测试。

## 1. 表 A：四份名单的每项归属（D2、D3）

核对内容每行三件事：记录值（对 `tools/code_shape/baseline.json` / `tools/code_shape/ui_layer_allow.json` / `ruff.toml` / `local/tests/test_layer_boundaries.py` 原文）、当前值（独立复算）、归属（对 `design/evidence/2026-11-13/refactor-endpoint/scripts/ownership.py` 顶部常量 D2_STEPS，一个文件一个归属）。

| 条目组 | 行数 | 核对方法 | 判定 |
|---|---|---|---|
| A3·baseline 文件名单（over800） | 12 | M1+M2+M3 | 站得住（12/12） |
| A3·baseline 文件名单（over500） | 13 | 同上 | 站得住（13/13） |
| A3·baseline 函数名单（over100） | 33 | 同上 | 站得住（33/33） |
| A3·baseline 函数名单（over60） | 86 | 同上 | 站得住（86/86） |
| A3·baseline 测试函数名单 | 19 | 同上 | 站得住（19/19） |
| A3·baseline 类名单 | 4 | 同上 | 站得住（4/4） |
| A3·前端分层白名单 ui_layer_allow.json | 41 | 每行核 5 项：引用方归属、当前行数、定义文件（自写 local/ui 顶层定义扫描）、定义文件归属、名字确在 json 内 | 站得住（41/41） |
| A3·分层测试存量例外 LEGACY_DIRECTION_VIOLATIONS | 2 | M2（自写 ast 解析）+M1 | 站得住（2/2） |
| A3·ruff.toml per-file-ignores | 44 | M2（自写 toml 解析，共 44 项）+M1 | 站得住（44/44） |
| A2·未排进任何一步清单（按源分组 7+9+17+51+19+3+15+2+42） | 165 | 每行核当前行数/规则码/归属必为未排进 | 站得住（165/165） |

定位样例（每行均按同法核对，无一例外）：

| 条目 | 核对方法 | 判定 |
|---|---|---|
| `local/ui/views/plan-panel.js` 记录值 1367（baseline.json files.over800 原文核对）、当前值 1367（自写行数器）、归属 步骤 1C 计划栏（D2_STEPS） | M2+M3 | 站得住 |
| `local/ui/views/phone.js::paintRelogin` 记录值 88、当前值 88（jsfuncs.mjs 量法：phone.js:321-408）、归属 步骤 1A | M2+M3 | 站得住 |
| `local/ui/led.js::#anon1` 记录值 108、当前值 108（jsfuncs.mjs）、归属 未排进任何一步 | M1+M2 | 站得住 |
| `tools/qa_runtime_reliability.py::_#22` 记录值 130、当前值 130（自写 ast 复算 + check.py 同名限定名编号规则）、归属 未排进 | M2 | 站得住 |
| `local/ui/state/clock.js × paintClockPopFeedback`：引用方归属 未排进、当前行数 314、定义文件 `local/ui/views/clock-pop.js`、定义归属 未排进 | M2 | 站得住 |
| `local/ui/views/plan-panel.js × refresh`：定义文件 `local/ui/controllers/refresh.js`（步骤 1 共用） | M2 | 站得住 |
| `("infrastructure/component_packages.py", "runtime_paths")` 在 test_layer_boundaries.py 的 LEGACY 字典内，补前缀后与表一致 | M3 | 站得住 |
| `ruff.toml` `"local/tests/test_updater.py" = ["F811"]` 在表记 未排进；`"local/app.py" = ["F401"]` 记 步骤 2 | M3 | 站得住 |

## 2. 表 B：前端文件耦合（D4）

| 条目 | 核对方法 | 判定 |
|---|---|---|
| B1 全部 40 行的「序/文件/层/归属」四列（index.html 加载顺序独立解析、层按目录前缀、归属按 D2 对照） | M2 | 站得住（40/40） |
| B1 全部 40 行「行数」（自写计数器：\r\n 归一、去末尾换行） | M2 | 站得住（40/40） |
| B1 全部 40 行「顶层函数数/全局名字数」（自写顶层定义扫描：brace/paren 深度 0 处的 function/const/let/var/class/window.X=） | M2 | 站得住（40/40） |
| B1 全部 40 行「S 写入处数」（自写检测器按 collectWrites 语义重写：赋值运算符、++/--、delete、容器变异方法调用、Object.assign 首参，含函数局部遮蔽排除；首轮简化版曾偏差，精细版 40/40 一致） | M2 | 站得住（40/40） |
| 尾注「文件总数：40（index.html 顺序 40 个，另外发现 0 个）」与「同一名字在两个文件里都有顶层定义：0 处」 | M2 | 站得住 |
| B2 全部 26 行：引用步骤 1 定义的名字数与清单、被步骤 1 引用的名字数与清单（自写 refs/defs 实现，含属性访问、对象字面量键、函数关键字后名字、局部遮蔽排除） | M2 | 站得住（26/26，4 字段全对） |

定位样例：`local/ui/views/list.js`（B1 序 7：行数 449、顶层函数 18、全局名字 18、S 写入 7）；`local/ui/controllers/terms.js`（序 23：S 写入 85）；B2 行 `local/ui/state/terms.js`（引用 1：S；被引用 2：termsAccepted、termsLocked）；B2 行 `local/ui/controllers/tick.js`（引用 20 个名字清单逐字一致、被引用 7 个名字清单逐字一致）。判定均为站得住。

## 3. 表 C：审计数字对照（D5）

11 行数据行 < 20，全量核对。「审计时」列不改判，只核其确实写在那轮 `design/evidence/2026-11-12/refactor-audit/inventory.md`（旧基线 7e2d31c，inventory.md:3 确认）里；「现在」列用 M1 复跑定位到对应行。

| 指标（审计时｜现在） | 审计时出处（M3） | 现在复跑定位（M1） | 判定 |
|---|---|---|---|
| 前端全局名字总数 560｜562 | inventory.md:695「读了 39 个脚本，顶层定义了 560 个全局名字」 | C_globals 输出行 5「读了 40 个脚本，顶层定义了 562 个全局名字」 | 站得住 |
| S 引用 1344/32｜1356/33 | inventory.md:750（S 行 32/1344） | 输出行 61（33/1356） | 站得住 |
| S 写入 441/27｜444/27 | inventory.md:917 | 输出行 214 | 站得住 |
| 依赖环 33/39｜33/40 | inventory.md:780 与 :695 | 输出行 92 与 :5 | 站得住 |
| state 引用上层 25/62｜17/40 | inventory.md:856 | 输出行 168 | 站得住 |
| views 引用 controllers 15/80｜11/50 | inventory.md:895 | 输出行 196 | 站得住 |
| Api 方法数 153｜153 | inventory.md:374 | py_state 输出行 31 | 站得住 |
| 3 个及以上方法赋值的标志位 23｜23 | inventory.md:378 | py_state 输出行 35 | 站得住 |
| self._lock 方法数 67｜67 | inventory.md:442 | py_state 输出行 99 | 站得住 |
| app.X 补丁名字数 42｜42 | inventory.md:554 | app_reexports 输出行 6 | 站得住 |
| 测试改写 Api 实例成员数 66｜67 | inventory.md:474「66 个名字」 | py_state 输出行 131「67 个名字」 | 站得住 |

「表 C 运行情况与出处」段的事实核对（全部成立）：五个脚本 stdout 行数 275/49/203/139/878 与段内数字一致；「取行位置」各条均在复跑输出中找到；伴随事实 py_layers「扫了 50 个文件」（旧 inventory.md:294 为 51）、py_state「扫了 79 个文件」（旧 :346 为 80）、app_reexports「18 个文件」（旧 :552 为 15）、measure 产品 Python 90 个文件 36439 行（旧 :28 为 90/37070）、「越界的 import，共 2 条」（旧 inventory.md:305 同为 2 条）均属实。

备注（非数字项，不计入判定分布）：该目录 README「表 C（D5）」条写「表 C 里写明了这一点（没有产生需要复制到本次 scripts/ 修改的副本）」，tables.md 表 C 段的实际表述是「退出码全 0，stderr 全空，全部产出完整 stdout，无一行『输出里没有该行』」，未逐字出现「副本」一句；两处语义相容，措辞有差。（返修注明：主代理已把 README 表 C 条改为与 tables.md 同口径的表述。）

## 4. 表 D：类型标注覆盖（D6）

| 条目 | 核对方法 | 判定 |
|---|---|---|
| D1 全部 7 行（文件数/函数数/三类计数） | M2（自写 ast 分类器：self/cls 不算参数、*args/**kwargs 计位、零参无返回注算未标、五组+build+其他分组） | 站得住（7/7） |
| D2 全部 52 行（每组函数最多的十个文件） | M2 | 站得住（52/52） |
| 总计行「全部函数合计：1307；都标了 579、一部分 242、完全没标 486」 | M2 重算 | 站得住 |

定位样例：`local/domain/phone_rules.py` 28/0/18/10；`local/app.py` 218/184/22/12；`local/infrastructure/component_packages.py` 70/0/8/62；`server/deploy/grab_signup.py` 41/0/0/41——四行独立复算全部与表一致。D1 七行函数数相加 83+96+208+614+261+45+0=1307、三类相加 579+242+486=1307，独立重算成立。

## 5. 表 E：界面测试字面断言分类（D7）

（返修注明：本节判定针对返修前的表 E；分类口径按 AA2 的挑战返修后，表 E 已重出，三类合计为 36/1631/1471/3138，总量与无障碍名称数、node 数不变。）

| 条目 | 核对方法 | 判定 |
|---|---|---|
| E1 全部 17 个文件行（三类计数、合计、node 沙箱测试函数数） | M2（自写 ast 收集器 + 自写分类器：含 aria-/role=/alt=/title= 为无障碍；去空白与标点后全为汉字/数字为文案；其余源码形状） | 站得住（17/17，每行 5 列全对） |
| 合计行（36/1658/1444/3138/335） | M2 | 站得住 |
| 自校行「三类之和 3138 = 脚本找到的字面量断言总数 3138 -> 成立」 | M2 重算等式：36+1658+1444=3138，且等于收集总数 3138 | 成立，站得住 |
| E2 全部 60 条抽样行 | M2（以同种子 20261113、同排序键独立复现抽样，60 条顺序与内容完全一致）+ M3（每条 文件:行号 打开源码，字面量确为该行断言调用的直接实参）+ M2（每条类别独立复判） | 站得住（60/60：定位、原文、类别三项全对） |

定位样例（60 条中抽列，全部同法核对）：`local/tests/test_ui_contract_terms.py:385` 原文 `aria-label="关闭条款"` 类别 无障碍名称；`local/tests/test_ui_contract_list.py:793` 原文 `刷新` 类别 文案；`local/tests/test_phone_ui.py:1124` 原文 `下载没有完成：GitHub 暂时无法响应，请稍后重试，可以重试。` 类别 源码形状；`local/tests/test_ui_conflict_cancel.py:255` 原文为空串类别 源码形状。四条均站得住。

## 6. 表 F：工程设施盘点（D8）——全量核

| 条目 | 核对方法 | 判定 |
|---|---|---|
| F1 全部 28 行（25 个配置文件名 + mypy/coverage 配置节 2 行 + 节标记） | M2/M3（test -e 逐个检测，全部不存在；pyproject.toml/setup.cfg 不存在故配置节「无」） | 站得住（28/28） |
| F2 全部 5 行（requirements 文件 14/7/2、3/3/3、2/2/2、3/1/0、15/2/2 及未锁行清单） | M2（独立 grep/解析） | 站得住（5/5，未锁行逐字一致） |
| F3 两行（.githooks、.github/workflows 均「无」） | M2（目录不存在） | 站得住 |
| F4·unittest/pytest/compileall「无」 | M2（grep 计数 0） | 站得住 |
| F4·--prepare 行清单 22 行（tools/release.py:8,17,27,660,803,809,933,941,946,948,951,957,961,968,988,993,1000,1046,1059,1269,1292,1302） | M2（grep -n -- "--prepare" 恰 22 行，行号一致） | 站得住 |
| F4·tools/code_shape/check.py 存在「是」 | M3 | 站得住 |
| F4·ruff 字符串查找 21 行清单 | M2（按同扩展名过滤 git ls-files 独立复跑，21 行逐条一致） | 站得住 |

定位样例：AGENTS.md:112/115/224/227 四行均含 ruff（M3 核实）；requirements-dev.txt:3 内容 `ruff==0.17.5`（M3 核实）。

## 7. 表 G：文档数字对账（D9）——5 行 < 20，全量核对

| 文件:行号 | 核对方法 | 判定 |
|---|---|---|
| AGENTS.md:91（测试用例个数） | M3 逐字比对（`# 本机版全量，约 1700 例；仓库在共享盘上，要跑几分钟`）+ M2（自写 ast 数 test_ 函数：local/tests 2581、server/tests 123、合计 2704）+ M1（--measure tests 复跑同值） | 站得住 |
| docs/ARCHITECTURE.md:179（Api 方法个数） | M3（`|` 在表中写作 `\|` 的转义还原后逐字一致）+ M2（Api 类方法总数 153、非下划线 60）+ M1 | 站得住 |
| docs/UI_SPEC.md:884（测试用例个数） | M3 逐字一致 + M2/M1 同上 | 站得住 |
| docs/superpowers/specs/2026-11-03-architecture-revision-design.md:39（源文件行数） | M3 逐字一致 + M2（自写行数器 local/grab.py = 4076） | 站得住 |
| docs/superpowers/specs/2026-11-03-architecture-revision-design.md:121（源文件行数） | M3（行首两个空格被脚本 strip，表 G 抽查记录第 2 条已披露，还原后逐字一致）+ M2（local/app.py = 4873） | 站得住 |

完备性复核（M2）：按脚本顶部四类正则对 AGENTS.md、README.md、local/README.md、docs/ 下全部 md 独立复推候选行，恰得同样 5 行，无遗漏、无多余。

## 8. 自校复核（任务指定重算等式）

| 自校行 | 独立重算 | 结论 |
|---|---|---|
| 表 A「各步项数 89 + 未排进项数 165 = 四份名单总项数 254 -> 成立」 | 各步独立重数：1A 10 + 1B 16 + 1C 18 + 1共用 6 + 步骤 2 17 + 步骤 3 13 + 手机页 9 = 89；未排进 165；总项数 254（baseline 四名单 167 + 前端白名单 41 + 分层例外 2 + ruff 44 = 254） | 等式成立 |
| 表 E「三类之和 3138 = 脚本找到的字面量断言总数 3138 -> 成立」 | 独立重算：36 + 1658 + 1444 = 3138，等于独立收集总数 3138 | 等式成立 |

## 9. H3 引用一致性（仅两个数字，不改判）

- `online.md:167`：`` `Ran 2581 tests in 214.826s`；`OK (skipped=5)` ``；同句「失败 0、错误 0、通过 2576、跳过 5」，2576+5=2581 算术自洽。
- `README.md` 口径疑点 3：「local/tests 2581、server/tests 123、合计 2704……local/tests 的计数与 H3 全量运行的『Ran 2581 tests』一致」——与 online.md 一致。
- `tables.md` 表 G 两行实测值 `local/tests 2581` 及表 G 抽查记录第 4 条——与 online.md、README 一致。
- 结论：三个文件对这两个数字的引用一致，未发现矛盾（按任务口径不做实测改判）。

## 10. 判定分布汇总

判定单位 = 数据行（表 F 的 F4 清单行与各表尾注、运行情况事实不计入行数，单独以「全部成立」记述）。

| 表 | 数据行数 | 站得住 | 部分站不住 | 推翻 |
|---|---|---|---|---|
| A | 419（A2 165 + A3 254） | 419 | 0 | 0 |
| B | 66（B1 40 + B2 26） | 66 | 0 | 0 |
| C | 11 | 11 | 0 | 0 |
| D | 59（D1 7 + D2 52） | 59 | 0 | 0 |
| E | 78（E1 17 + 合计行 + E2 60） | 78 | 0 | 0 |
| F | 35（F1 28 + F2 5 + F3 2）+ F4 清单全部成立 | 35 | 0 | 0 |
| G | 5 | 5 | 0 | 0 |
| 合计 | 673 | 673 | 0 | 0 |

- 自校行：表 A、表 E 两处等式重算均成立。
- H3 引用一致性：一致（3 处引用 + 1 处算术自洽）。
- 与执行方结论的差异：无。本次未发现任何对不上的数字、归属或 文件:行号；唯一记录在案的非数字观察是第 3 节备注（README 与 tables.md 对「表 C 是否写明无副本」的措辞差异）。
- 留存：复跑输出与核对脚本均在 `<临时目录>`（tempfile.mkdtemp()），收工后即弃，不在仓库留任何产物。
