# 手机页外壳与接线组安全网

- **执行日期**：2026-11-23
- **分支与基线**：`refactor/phone-page`（只增改 `local/tests/test_phone_ui.py` 与本目录证据文件；`local/ui/m/` 全部产品代码零改动）。
- **核心结论**：针对 `local/ui/m/ui-shell.js` 的 7 个顶层函数生成六类共 **141 条**单点变异；补测前行为守 83、无人守 58；按功能区合并补入 **10 条**纯行为用例并给出 **6 条**带全调用方证明的等价判定后，补测结论为 **行为守 135、等价 6、无人守 0、字面守 0、无效 0**。

## 1. 范围与六类变异口径

- **目标范围**：按 `design/evidence/2026-11-22/phone-net/move-facts.md` 归入「外壳与接线」组的 `local/ui/m/ui-shell.js` 全部 **7 个**顶层函数（`sheetBusy`、`openSheet`、`closeSheet`、`showSheetError`、`askConfirm`、`onConfirmYes`、`wire`，含内部箭头回调与事件处理函数），函数边界通过 `tools/code_shape/jsscan.mjs` 求得，共产生 141 条单点变异。文件末尾 `PhoneUI` 导出与 `DOMContentLoaded` 启动不在任何函数内，不纳入变异。
- **六类单点变异口径**：
  - **甲类（25 条）**：函数体内每一处 `model.字段` 与 `model.字段.子字段` 写操作整条替换为 `void 0`。
  - **乙类（38 条）**：函数体内每一个 `if`、`else if` 与三元表达式条件 `C` 替换为 `!(C)`。
  - **丙类（19 条）**：函数体内每一处 `.hidden = X` 显隐写入整条替换为 `void 0`。
  - **戊类（0 条）**：函数体内每一处 `return true` 与 `return false` 互换（本文件无此类字面返回）。
  - **己类（17 条）**：函数体内每一处 `.textContent`、`.value`、`.disabled` 的赋值整条替换为 `void 0`。
  - **庚类（42 条）**：`wire` 内每一处 `addEventListener` 调用整条语句（含其处理函数）替换为 `void 0`。
- **执行环境与方法**：在 `%TEMP%`（`tempfile.gettempdir()`）下由 `git archive HEAD` 导出、再叠加工作区 `local/tests/test_phone_ui.py` 的独立临时副本中运行 `scripts/mutate_shell.py`，每条变异先过 `node --check`，再跑 `local/tests/test_phone_ui.py` 全量用例；跑完删除临时副本。单条测试超时（90 秒）按失败计并在报告里标注「超时」。

## 2. 7 个函数对照

| 函数 | 变异数 | 口径（甲 / 乙 / 丙 / 戊 / 己 / 庚） | 补测前（行为守 / 无人守） | 补测后（行为守 / 等价 / 无人守） |
|---|---:|---|---|---|
| `sheetBusy` | 1 | 0 / 1 / 0 / 0 / 0 / 0 | 1 / 0 | 1 / 0 / 0 |
| `openSheet` | 17 | 2 / 4 / 9 / 0 / 2 / 0 | 8 / 9 | 17 / 0 / 0 |
| `closeSheet` | 18 | 4 / 4 / 9 / 0 / 1 / 0 | 11 / 7 | 17 / 1 / 0 |
| `showSheetError` | 3 | 0 / 1 / 1 / 0 / 1 / 0 | 3 / 0 | 3 / 0 / 0 |
| `askConfirm` | 8 | 1 / 1 / 0 / 0 / 6 / 0 | 6 / 2 | 8 / 0 / 0 |
| `onConfirmYes` | 9 | 0 / 5 / 0 / 0 / 4 / 0 | 6 / 3 | 9 / 0 / 0 |
| `wire` | 85 | 18 / 22 / 0 / 0 / 3 / 42 | 48 / 37 | 80 / 5 / 0 |
| **合计（7 个函数）** | **141** | **25 / 38 / 19 / 0 / 17 / 42** | **83 / 58** | **135 / 6 / 0** |

## 3. 补测前后统计对照

| 结论分类 | 补测前（`before.md`） | 补测后（`after.md`） | 变化 |
|---|---:|---:|---:|
| 行为守 | 83 | **135** | +52 |
| 字面守 | 0 | 0 | 0 |
| 无人守 | 58 | **0** | -58 |
| 无效 | 0 | 0 | 0 |
| 等价 | 0 | **6** | +6 |
| **总计** | **141** | **141** | **0** |

按口径分布（补测后最终态）：
- 甲类（25 条）：行为守 19、等价 6、无人守 0
- 乙类（38 条）：行为守 38、等价 0、无人守 0
- 丙类（19 条）：行为守 19、等价 0、无人守 0
- 戊类（0 条）：行为守 0、等价 0、无人守 0
- 己类（17 条）：行为守 17、等价 0、无人守 0
- 庚类（42 条）：行为守 42、等价 0、无人守 0

## 4. 新增行为用例清单（共 10 条）

全部按功能区合并写入 `local/tests/test_phone_ui.py` 对应既有测试类（测试文件总数保持 39 个），仅断言用户可见 DOM、焦点替身、替身 `fetch` 请求路径与载荷或 `__timerDelays()` 定时器排程（丙类显隐与己类文字/禁用用例开场先设为与预期相反的值；账号、密码、验证码均使用一眼可辨的假值）：

| 功能区 / 测试类与用例名 | 守的用户可见结果或请求载荷 | 对应无人守变异编号 |
|---|---|---|
| 配对 · `PairStatesDomTests.test_pair_code_input_normalizes_clears_error_and_enter_submits` | 输入配对码过滤非数字截断 6 位并清 `#pair-error`，仅回车发 `/pair` 请求 | `M058`、`M059`、`M060`、`M061`、`M062`、`M063` |
| 筛选与搜索 · `ListDetailModelTests.test_more_query_and_status_and_time_chips_filter_dom_and_sync_inputs` | 更多面板 `#q` 同步 `#search-q` 并过滤，状态与时间筛选片双向切 `aria-pressed` 并筛行 | `M102`、`M103`、`M104`、`M105`、`M115`、`M116`、`M117`、`M119`、`M120` |
| 刷新同步 · `PhoneSyncPolicyTests.test_refresh_button_click_forces_poll_from_seq_zero` | 点击 `#btn-refresh` 发起 `/api/state?after=0` 全量拉取 | `M064` |
| 底栏与核对/计划 · `RunWaitDomTests.test_review_start_button_closes_sheet_and_posts_and_stop_opens_confirm` | `#btn-review-start` 收起抽屉并发 `start_plan`；`#btn-stop` 弹确认槽并发 `stop_plan` | `M008`、`M077`、`M082` |
| 重试设置 · `MobileWriteResilienceTests.test_retry_dirty_protects_unsaved_inputs_from_snapshot_overwrite` | 修改 `#retry-for` 与 `#max-attempts` 尚未保存成功前，首轮快照不覆盖未保存值 | `M123`、`M126` |
| 重新登录 · `ReloginSheetTests.test_relogin_buttons_and_input_listeners_drive_begin_submit_and_refresh` | 重登输入监听实时更新主钮可用态，登录/提交/换图钮依次发对应动作 | `M093`、`M095`、`M099`、`M101` |
| 重新登录 · `ReloginSheetTests.test_relogin_cancel_failure_clears_confirm_layer` | 取消重登被拒而留抽屉时仍清掉确认层回到表单态 | `M097` |
| 抽屉 · `SheetShellTests.test_open_and_close_sheet_restore_focus_toggle_all_panels_and_clear_confirm` | `openSheet` 记焦点并双向切全部面板/页脚/关闭钮/入口文案，`closeSheet` 全部复位、清确认层并还焦点 | `M003`、`M005`、`M006`、`M008`、`M010`、`M014`、`M015`、`M016`、`M017`、`M026`、`M027`、`M028`、`M029`、`M030`、`M034` |
| 抽屉与确认 · `SheetShellTests.test_sheet_backdrop_escape_and_confirm_button_disable_lifecycle` | 点遮罩与按 `Esc` 收抽屉（误点内层与他键不关），确认在途禁双钮、打开/失败均放开 | `M046`、`M047`、`M052`、`M053`、`M056`、`M070`、`M071`、`M072`、`M073` |
| 前后台切换 · `PhoneTickSleepAndDrawerTests.test_pagehide_clears_active_poll_and_tick_timers` | `pagehide` 事件同时清掉轮询与整秒计时器 | `M135`、`M136`、`M138` |

## 5. 等价判定摘要（6 条）

完整理由与全目录扫描证明见 `design/evidence/2026-11-23/phone-shell-net/scripts/equiv.json` 与 `after.md` 末尾：

- **`M035`**（`ui-shell.js:closeSheet`）：`model.sheetOpener = null;` 改 `void 0;`。第 48 行已置 `model.sheetId = ""` 阻止重入 `closeSheet`，第 65 行已取入局部常量 `opener`；后续任何 `openSheet` 在读取前第 21 行必无条件覆写 `model.sheetOpener`。
- **`M114`**（`ui-shell.js:wire`）：`model.notice = res.notice;` 改 `void 0;`。`#btn-pick-next` 仅在 `model.selected` 有效项为空时显示；所有使 `selected` 归零的入口及 `buildRow` 取消路径均已清 `model.notice = ""`，且空选择下 `PhoneModel.pickItem` 恒返回 `notice: ""`。
- **`M130`、`M137`**（`ui-shell.js:wire`）：`visibilitychange` 与 `pagehide` 中清理后的 `model.pollTimer = null;` 改 `void 0;`。全目录所有读取方仅在 `clearTimeout` 前判真，前一语句已取消该单调递增句柄，后续空操作 `clearTimeout` 与 `schedule` 覆写均不影响任何外部可观结果。
- **`M132`、`M139`**（`ui-shell.js:wire`）：`visibilitychange` 与 `pagehide` 中清理后的 `model.tickTimer = null;` 改 `void 0;`。全目录所有读取方仅在 `clearTimeout` 前判真，前一语句已取消该单调递增句柄，后续空操作 `clearTimeout` 与 `scheduleTick` 覆写均不影响任何外部可观结果。

## 6. 未覆盖项

- 手机真机（如 iOS Safari）与打包后的电脑端 WebView2 冻结窗口未实测，所有行为用例均在受控 Node `vm` 沙箱与本机离线单元测试运行。

## 7. 复现命令

在仓库根执行（Python 3.12；运行前清空 `http_proxy` / `HTTP_PROXY` / `https_proxy` / `HTTPS_PROXY` / `all_proxy`，并设 `PYTHONIOENCODING=utf-8`）：

```bash
python -m unittest discover -s local/tests -p "test_phone_ui.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_code_shape.py"
python design/evidence/2026-11-23/phone-shell-net/scripts/mutate_shell.py --list
python design/evidence/2026-11-23/phone-shell-net/scripts/mutate_shell.py --baseline
python design/evidence/2026-11-23/phone-shell-net/scripts/mutate_shell.py \
  --workers 4 --phase 补测之后 \
  --equiv-json design/evidence/2026-11-23/phone-shell-net/scripts/equiv.json \
  --out design/evidence/2026-11-23/phone-shell-net/after.md
```

## 8. 手机页四组安全网总览

按 `design/evidence/2026-11-22/phone-net/move-facts.md` 划分的手机页 DOM 层全部 67 个顶层函数（含拆批收尾共 5 个证据目录）已全部收口，全组无人守均为 **0**：

| 分组 | 目标文件（函数数） | 证据目录 | 变异总数 | 补测前（行为守 / 无人守 / 等价） | 补测后结论 |
|---|---|---|---:|---|---|
| 请求与配对会话 | `ui-session.js`（16） | `design/evidence/2026-11-22/phone-net/` | 72 | 48 / 18 / 6 | **行为守 66、等价 6、无人守 0** |
| 摄入与渲染 | `ui-sync.js`、`ui-status.js`、`ui-list.js`（23） | `design/evidence/2026-11-23/phone-render-net/` | 226 | 142 / 84 / 0 | **行为守 220、等价 6、无人守 0** |
| 计划操作 | `ui-plan.js`（13） | `design/evidence/2026-11-23/phone-plan-net/` | 97 | 53 / 44 / 0 | **行为守 96、等价 1、无人守 0** |
| 重新登录 | `ui-relogin.js`（8） | `design/evidence/2026-11-23/phone-relogin-net/` | 129 | 79 / 50 / 0 | **行为守 128、等价 1、无人守 0** |
| 外壳与接线 | `ui-shell.js`（7） | `design/evidence/2026-11-23/phone-shell-net/` | 141 | 83 / 58 / 0 | **行为守 135、等价 6、无人守 0** |
| **全页合计** | **67 个 DOM 函数** | — | **665** | **405 / 254 / 6** | **行为守 645、等价 20、无人守 0** |
