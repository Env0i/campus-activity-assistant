# SPOT-AUDIT.md——抽检复核（现实检验者）

落盘说明：本文为抽检代理返回文本的转录，逐字未改；仅标题中与时间口径不符的日期标注按口径去除。

## 抽样规则与选取理由

**抽样规则**：只看证据文件本身可独立检验的陈述，不采纳任何解释性论证；能复跑的从仓库根复跑，能对源码的逐字核对；带 `<临时目录>` 占位的命令按任务规则跳过并注明；全程只读，中间产物只放 `<临时目录>`。开工核对：`git rev-parse --short HEAD` = dddc179，与证据 README「基线与开工核对」一致；`git status --short` 仅证据目录本身未跟踪，与 README 所记 T0 空输出的差异即本轮证据落盘。

**选取理由（各一句）**：

1. 复核点 1 取自 `design/evidence/2026-11-13/refactor-endpoint/online.md` 的表 H——任务必选项，核 H1/H2/H3 的数字引用链与可独立重算的测试数。
2. 复核点 2 取自 `tables.md` 表 E E2 抽样——它是唯一带 文件:行号+原文 列的材料，可逐字对源码，并覆盖 DEFENSE.md 条目 1 的返修落点行。
3. 复核点 3 取自 `tables.md` 表 B B1 与尾注——563/562 与 PhonePanel 两处行号可用我自己的列求和与源码核对独立重算，兼覆盖 DEFENSE.md 条目 4。
4. 复核点 4 取自 `tables.md` 表 C——「现在」列 11 个值全部声称可由五个旧脚本重跑得出，是唯一能整列当场复现的表，且复跑命令无占位符。
5. 复核点 5 取自 `ADVERSARIAL-AA2.md` 的 ruff.toml 行号引用——它引用的四处 ruff.toml 行号可用源码逐字核验，兼核 DEFENSE.md 条目 2 的返修落点（tables.md 表 A 抽查记录第 2 条）。

---

## 复核点 1｜表 H 数字引用一致性（online.md）与测试数独立重算

**方法**：(a) 对 H1/H2/H3 各表做独立算术求和；(b) 用我自己的 ast 脚本（`python -I`，遍历 FunctionDef/AsyncFunctionDef 且名字以 test_ 开头）独立计数 local/tests 与 server/tests；(c) 复跑 `python -B design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py --measure tests`（无占位符）；(d) 核对 tables.md 导言、README 口径疑点 3、表 G 实测值的交叉引用。online.md 的 pip 安装、六条 mypy、ruff 模板、三条 coverage 命令均带 `<临时目录>` 占位，跳过。

**实测**：
- H1-A 错误总数 61；「目录×错误码」表 14 行求和 = 61，「文件」表 15 行求和 = 61，两表各自恰等于总数。
- H1-B 总数 1270；两张「前 20」表分别求和 1242 与 1210，均不超过总数，与截断口径相符（1270 本身因跳过命令未能当场重现）。
- H2 九组的前五规则码求和均 ≤ 组总数；I 组 100=100、C90 组 92=92 精确相等，E 剩 1、B 剩 1、SIM 剩 3、UP 剩 14、PL 剩 187、RUF 剩 71。
- H3 2576 + 5 = 2581，与同行引用的「Ran 2581 tests」一致；跳过清单恰 5 条。
- 我的独立 ast 计数：local/tests 2581（78 个 .py）、server/tests 123（8 个）、合计 2704；`facilities.py --measure tests` 输出 `local/tests 2581；server/tests 123；合计 2704`，两者与表 G 实测值及 README 口径疑点 3、tables.md 导言的引用完全一致。

**判定**：站得住（可检验范围内；注明 H3 原始「Ran 2581 tests」行因占位命令未复跑，该侧一致性仅由 2576+5 与跳过清单数、独立 ast 计数间接支持）。

---

## 复核点 2｜表 E E2 抽样的 文件:行号 原文比对（tables.md）

**方法**：sed 逐行打印 E2 引用的 12 处 文件:行号，与 tables.md「原文」列逐字比对；多行调用按 README 口径疑点 12 核对「差 1」；用 Python unicodedata 核验 DEFENSE.md 条目 1 涉及的 test_ui_contract_settings.py:936 的 × 字符。

**实测**（全部与源码逐字一致）：
- tables.md ↔ test_ui_contract_plan.py:35：`self.assertIn("工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。", ask,`。
- tables.md ↔ test_phone_ui.py:5318：`self.assertEqual(r["locked"]["alertTitle"], "电脑上还没有同意使用条款")`。
- tables.md ↔ test_phone_ui.py:4246：调用行 4246，原文 `汇总行集与计数同一口径（不过段钮过滤，R-P3-7）` 在续行 4247，差 1，与口径相符。
- tables.md ↔ test_ui_contract_terms.py:1114：原文在续行 1115，差 1，与口径相符。
- tables.md 两条同指 test_ui_contract_list.py:888：该调用两个直接实参字面量分别在 888 与续行 889（`aria-selected="false">可报名`、`button 上的 aria-selected 非法，必须用 aria-pressed`），均归调用行。
- tables.md ↔ test_ui_contract_list.py:891/904/903：`chip.setAttribute("aria-selected"`、`aria-expanded="false"`、`role="button"` 三行实测原文一致。
- tables.md ↔ test_ui_conflict_cancel.py:226：实测 `self.assertEqual(out["mid"], "", "还不到 140ms，不开")`，该行确含空串直接实参，与「原文」列为空相符。
- tables.md ↔ test_ui_contract_components.py:32、test_ui_contract_terms.py:385、test_ui_contract_update.py:128、test_phone_ui.py:1927，原文一致。
- test_ui_contract_settings.py:936 实测为 `self.assertNotIn("dlg-x", block, "帮助弹窗不得有 × 关闭按钮")`，× 实测 U+00D7、Unicode 类别 Sm（半角符号），与 DEFENSE.md 条目 1 返修落点描述的字符事实相符。

**判定**：站得住。

---

## 复核点 3｜表 B B1 独立重算与尾注（tables.md，DEFENSE 条目 4）

**方法**：awk 对 tables.md 表体逐行切列求和；wc -l 与 sed 核对尾注所引 phone.js 两行与行数；从仓库根复跑 `node design/evidence/2026-11-13/refactor-endpoint/scripts/ui_coupling.mjs` 并核 `--defs` 输出。

**实测**：
- awk 对 40 个数据行求和：「全局名字数」列合计 563（尾注声称 563）；「S 写入处数」列合计 444，与 tables.md 导言及表 C 的 444 构成求和对照；行数 40 与「文件总数：40」一致。
- `wc -l local/ui/views/phone.js` = 1252，与 B1 序 27 行「行数」列一致；:154 为 `const PhonePanel = {`，:1252 为 `if (typeof window !== "undefined") window.PhonePanel = PhonePanel;`（顶层 if 语句内含 window.X 赋值，与赋值同处一行），与尾注所写两处位置相符。
- 复跑退出码 0、stderr 0 字节；B1 40 行、B2 26 行与三条尾注逐行同 tables.md 一致；`--defs` 返回唯一名 562 个，与表 C「前端全局名字总数 562」一致。

**判定**：站得住。

---

## 复核点 4｜表 C「现在」列整列复跑（tables.md）

**方法**：按 tables.md 表 C 的复跑命令从仓库根重跑五个旧脚本（design/evidence/2026-11-12/refactor-audit/scripts/ 下 measure.py、py_layers.py、py_state.py、app_reexports.py、globals.mjs；运行前确认脚本只打印不写盘，app_reexports.py 仅在传 `--out` 时写文件，本次未传），stdout/stderr 存 `<临时目录>`，逐行核对表 C 的 11 个「现在」值与运行情况及伴随事实。

**实测**：
- 五条命令退出码全 0，stderr 全空（0 字节），stdout 行数 275 / 49 / 203 / 139 / 878，与表 C「运行情况」逐项一致。
- globals.mjs：「读了 40 个脚本，顶层定义了 562 个全局名字」；高扇入表 S 行「33 | 1356」；「S 的写入：444 处，分布在 27 个文件」；「33 个文件互相可达」；state 段「去重后 17 个名字……共 40 处引用」；views 段「去重后 11 个名字……共 50 处引用」——对应 562、1356/33、444/27、33/40、17/40、11/50，全部相符。
- py_state.py：「Api 实例属性（local/app.py，153 个方法，74 个属性）」；「共 23 个」；`self._lock | 67`；「测试改写 Api 实例成员的位置（67 个名字）」——对应 153、23、67、67，全部相符。
- app_reexports.py：「被测试打补丁的模块级名字，共 42 个」，对应 42 相符；「18 个文件用到了 app 模块」与伴随事实一致。
- measure.py：「产品 Python | 90 | 36439」；行数表中 local/app.py 4873、local/grab.py 4076——与伴随事实一致，并与表 G 实测值、表 A「当前值」列交叉相符。
- py_layers.py：「扫了 50 个文件」、「越界的 import，共 2 条」；py_state.py「扫了 79 个文件」——与伴随事实一致。

**判定**：站得住。

---

## 复核点 5｜ADVERSARIAL-AA2.md 的 ruff.toml 行号引用与 tables.md 表 A 抽查记录第 2 条

**方法**：sed 逐字核对 ruff.toml 四个行位；用我自己的 Python 脚本独立统计 `[lint.per-file-ignores]` 节的条目结构（文件条目数、双规则码条目、按「文件×规则码」展开数）；与 tables.md 表 A 抽查记录第 2 条（返修后引用）、「ruff 42」来源分解、A2 ruff 段与 A3 ruff 段交叉。

**实测**：
- ruff.toml:25 = `"local/app.py" = ["F401"]`，ruff.toml:53 = `"local/tests/test_updater.py" = ["F811"]`——与 tables.md 表 A 抽查记录第 2 条返修后的两处引用一致。
- ruff.toml:31 = `"local/infrastructure/credential_store.py" = ["F841"]`，ruff.toml:3 = 注释行——与 ADVERSARIAL-AA2.md 引用的另两处行位相符。
- `[lint.per-file-ignores]` 起于 ruff.toml:23；实测 41 个文件条目，其中 3 个双规则码条目恰为 test_phone_http.py（F401+F841）、test_phone_service.py（F401+F841）、test_session_persistence.py（F401+F823），展开 44 项——与 ADVERSARIAL-AA2.md 的结构计数一致。
- 交叉：A3 ruff 段 44 行中 2 行有归属（app.py×F401→步骤 2、grab.py×F401→步骤 3），A2 ruff 段 42 行全为未排进，44 − 42 = 2，与表 A 自校（89 + 165 = 254）方向一致。

**判定**：站得住。

---

## 跳过的命令

- H1 的 6 条 mypy、H2 的 1 条模板 ruff、H3 的 3 条 coverage 及 online.md 的一次性 pip 安装命令均含 `<临时目录>` 占位，按任务规则跳过；H1/H2 的字面数值与 H3 的「Ran 2581 tests」原行未当场重现，复核点 1 的判定仅覆盖数字引用链与可独立重算部分。

## 判定分布

复核点 1 站得住｜复核点 2 站得住｜复核点 3 站得住｜复核点 4 站得住｜复核点 5 站得住 —— 5 站得住 / 0 站不住。
