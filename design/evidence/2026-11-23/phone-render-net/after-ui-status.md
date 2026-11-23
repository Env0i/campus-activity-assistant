# 手机页渲染组安全网补测第二批：`ui-status.js` 29 条结论对照

- **范围**：针对 `design/evidence/2026-11-23/phone-render-net/before.md` 中 `local/ui/m/ui-status.js` 全部 **29 条**无人守变异（`M020`、`M022`、`M023`、`M025`、`M026`、`M027`、`M028`、`M030`、`M031`、`M035`、`M036`、`M038`、`M039`、`M043`、`M046`、`M053`、`M055`、`M056`、`M062`、`M066`、`M070`、`M072`、`M073`、`M074`、`M075`、`M076`、`M077`、`M078`、`M082`），分布于 `refreshControls`（8 条）、`renderBoard`（8 条）、`renderBar`（7 条）、`renderRail`（2 条）、`canWrite`（1 条）、`renderStats`（1 条）、`renderPlan`（1 条）、`renderTasks`（1 条）。
- **执行方式**：只读复用 `scripts/mutate_render.py`，在 `tempfile.gettempdir()` 下由 `git archive HEAD` 导出并叠加工作区 `local/tests/test_phone_ui.py` 的独立临时副本中先跑 29 条定向复跑，再跑全组 226 条回归复跑（`--workers 4`，配合追加后的 `scripts/equiv.json`）。所有显隐用例均先将被断言元素的 `hidden` 设为与预期相反值。产品代码零改动。

## 1. 本批 29 条逐条结论

| 编号 | 类 | 文件 | 函数 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例或等价说明 |
|---|---|---|---|---|---|---|---|
| M020 | 甲 | `ui-status.js` | `canWrite` | `model.nowMs = Date.now();` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_can_write_reads_fresh_clock_after_idle_gap_before_start` |
| M022 | 丙 | `ui-status.js` | `refreshControls` | `$("stale-note").hidden = !stale;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_stale_note_and_stop_and_cancel_start_visibility_follow_state` |
| M023 | 丙 | `ui-status.js` | `refreshControls` | `$("btn-stop").hidden = !model.busy;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_stale_note_and_stop_and_cancel_start_visibility_follow_state` |
| M025 | 乙 | `ui-status.js` | `refreshControls` | `if (account)` | `if (!(account))` | 等价 | 见第 3 节 `M025` 调用方证明 |
| M026 | 丙 | `ui-status.js` | `refreshControls` | `account.hidden = setup ? !PhoneModel.relNeedAcct(model.flow, setup) : true;` | `void 0;` | 等价 | 见第 3 节 `M026` 调用方证明 |
| M027 | 乙 | `ui-status.js` | `refreshControls` | `setup ?` | `!(setup) ?` | 等价 | 见第 3 节 `M027` 调用方证明 |
| M028 | 丙 | `ui-status.js` | `refreshControls` | `$("btn-cancel-start").hidden = !(model.pending && !model.pending.done);` | `void 0;` | 行为守 | `ExceptionStatesTests.test_stale_note_and_stop_and_cancel_start_visibility_follow_state` |
| M030 | 乙 | `ui-status.js` | `refreshControls` | `if (model.sheetId)` | `if (!(model.sheetId))` | 行为守 | `SheetShellTests.test_sheet_close_button_hides_only_when_open_sheet_is_busy` |
| M031 | 丙 | `ui-status.js` | `refreshControls` | `$("btn-sheet-close").hidden = sheetBusy();` | `void 0;` | 行为守 | `SheetShellTests.test_sheet_close_button_hides_only_when_open_sheet_is_busy` |
| M035 | 丙 | `ui-status.js` | `renderBar` | `$("btn-reselect").hidden = !result \|\| !result.canRetry;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` |
| M036 | 丙 | `ui-status.js` | `renderBar` | `$("btn-finish").hidden = !result;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` |
| M038 | 丙 | `ui-status.js` | `renderBar` | `$("btn-start").hidden = true;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` |
| M039 | 丙 | `ui-status.js` | `renderBar` | `$("btn-cancel-start").hidden = true;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` |
| M043 | 乙 | `ui-status.js` | `renderBar` | `PhoneModel.pendingLong(model.pending, Date.now()) ↵       ?` | `!(PhoneModel.pendingLong(model.pending, Date.now())) ↵       ?` | 行为守 | `RunWaitDomTests.test_pending_bar_title_switches_after_window_and_start_hides_when_busy` |
| M046 | 丙 | `ui-status.js` | `renderBar` | `$("btn-start").hidden = false;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_pc_list_error_bar_readies_start_button_and_run_tip_toggles_with_busy` |
| M053 | 丙 | `ui-status.js` | `renderBar` | `$("btn-start").hidden = model.busy;` | `void 0;` | 行为守 | `RunWaitDomTests.test_pending_bar_title_switches_after_window_and_start_hides_when_busy` |
| M055 | 丙 | `ui-status.js` | `renderRail` | `box.hidden = !steps.length;` | `void 0;` | 行为守 | `RunWaitDomTests.test_board_rail_visibility_and_step_classes_and_task_card_tone` |
| M056 | 乙 | `ui-status.js` | `renderRail` | `if (step.state)` | `if (!(step.state))` | 行为守 | `RunWaitDomTests.test_board_rail_visibility_and_step_classes_and_task_card_tone` |
| M062 | 丙 | `ui-status.js` | `renderBoard` | `section.hidden = !board;` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M066 | 丙 | `ui-status.js` | `renderBoard` | `nowLine.hidden = false;` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M070 | 丙 | `ui-status.js` | `renderBoard` | `$("board-stats").hidden = !result;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` |
| M072 | 甲 | `ui-status.js` | `renderBoard` | `model.pickId = "";` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_hides_pick_next_and_clears_pick_target` |
| M073 | 丙 | `ui-status.js` | `renderBoard` | `$("btn-pick-next").hidden = true;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_hides_pick_next_and_clears_pick_target` |
| M074 | 乙 | `ui-status.js` | `renderBoard` | `if (d.cls)` | `if (!(d.cls))` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M075 | 甲 | `ui-status.js` | `renderBoard` | `model.pickId = board.pickId \|\| "";` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M076 | 丙 | `ui-status.js` | `renderBoard` | `$("btn-pick-next").hidden = !board.pickId;` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M077 | 乙 | `ui-status.js` | `renderStats` | `if (n.tone)` | `if (!(n.tone))` | 行为守 | `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` |
| M078 | 丙 | `ui-status.js` | `renderPlan` | `tip.hidden = !model.busy;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_pc_list_error_bar_readies_start_button_and_run_tip_toggles_with_busy` |
| M082 | 乙 | `ui-status.js` | `renderTasks` | `card.tone ?` | `!(card.tone) ?` | 行为守 | `RunWaitDomTests.test_board_rail_visibility_and_step_classes_and_task_card_tone` |

### 本批 29 条分类合计

- 行为守：26（甲类 3、乙类 6、丙类 17）
- 等价：3（乙类 2：`M025`、`M027`；丙类 1：`M026`）
- 字面守：0
- 无人守：0
- 无效：0
- 总计：29

## 2. 新增行为用例清单

均写入 `local/tests/test_phone_ui.py` 对应主题测试类，仅断言用户可见结果（`hidden`、`textContent`、`className`、`checked`、替身 `fetch` 请求），且显隐断言前均先预设相反的 `hidden` 初值：

| 测试类 / 用例名 | 守的用户可见结果 | 对应变异编号 |
|---|---|---|
| `MobileWriteResilienceTests.test_can_write_reads_fresh_clock_after_idle_gap_before_start` | 上次刷新后静置超过 30 秒再点开始时按当下时间拦下，弹出过时提示且不发提交请求 | `M020` |
| `SheetShellTests.test_sheet_close_button_hides_only_when_open_sheet_is_busy` | 无抽屉打开时不改动关闭钮显隐；抽屉打开且提交忙态时隐藏关闭钮 | `M030`、`M031` |
| `RunWaitDomTests.test_pending_bar_title_switches_after_window_and_start_hides_when_busy` | 核对中超过 15 秒底栏标题切换提示，运行中隐藏开始钮且非运行态恢复 | `M043`、`M053` |
| `RunWaitDomTests.test_board_rail_visibility_and_step_classes_and_task_card_tone` | 四站进度条按步骤数显隐并写入阶段类名，任务卡状态徽章按任务状态写入色调类名 | `M055`、`M056`、`M082` |
| `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` | 详情板与北京时间行显式显示，点阵保留亮暗类名，「选这一场」可加选并在无候选时隐藏 | `M062`、`M066`、`M074`、`M075`、`M076` |
| `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` | 结果态显隐底栏结果钮、收起开始与取消等待钮、显示统计区并写色调类，切回草稿后重收起 | `M035`、`M036`、`M038`、`M039`、`M070`、`M077` |
| `ResultTermsDomTests.test_result_hides_pick_next_and_clears_pick_target` | 结果态隐藏「选这一场」并清空待选目标，不再将旧候选写入已选列表 | `M072`、`M073` |
| `ExceptionStatesTests.test_stale_note_and_stop_and_cancel_start_visibility_follow_state` | `#stale-note`、`#btn-stop`、`#btn-cancel-start` 双向随状态显隐 | `M022`、`M023`、`M028` |
| `ExceptionStatesTests.test_pc_list_error_bar_readies_start_button_and_run_tip_toggles_with_busy` | 列表失败隐藏底栏后开始钮恢复未隐藏，且 `#run-tip` 双向随 `busy` 显隐 | `M046`、`M078` |

## 3. 等价判定与全调用方证明

已追加至 `design/evidence/2026-11-23/phone-render-net/scripts/equiv.json`（保留第一批 `M146`、`M150`、`M208` 原文不改）：

- **`M025`**（`ui-status.js:refreshControls`）：在 `index.html:254` 与测试 DOM 桩中 `#relogin-account` 恒存在；且同一 `refreshControls()` 函数第 133 行无条件调用 `renderRelogin()`（`ui-relogin.js:32` 无条件写入 `$("relogin-account").hidden = !view.needAcct`），第 118–132 行（`renderAlerts`、`renderBar` 等）均不读取 `#relogin-account`。将第 117 行的 `if (account)` 反转后仅跳过第 117 行，随后第 133 行仍会写入完全相同的显隐值，任何 DOM、fetch 请求或定时器均不变。
- **`M026`**（`ui-status.js:refreshControls`）：在 `refreshControls()`（`ui-status.js:117`）后，第 118–132 行（`renderAlerts`、`renderBar` 等）均不读取 `#relogin-account`；第 133 行无条件调用 `renderRelogin()`（`ui-relogin.js:32`），且 `model-relogin.js:107` 在 `reloginView()` 所有 `return` 分支前已将 `view.needAcct` 置为 `s ? PhoneModel.relNeedAcct(f, s) : false`，即 `!view.needAcct` 与第 117 行的 `setup ? !PhoneModel.relNeedAcct(model.flow, setup) : true` 完全同义。删掉第 117 行赋值后第 133 行仍立即写回同值（`beginRelogin` 也先调 `refreshControls()` 再读 `account.hidden`），外部结果完全等价。
- **`M027`**（`ui-status.js:refreshControls`）：在 `refreshControls()`（`ui-status.js:117`）紧接着的第 118–132 行没有任何代码读取 `#relogin-account.hidden`；同一同步调用末尾第 133 行无条件调用 `renderRelogin()`（`ui-relogin.js:32`），将 `$("relogin-account").hidden` 覆写为 `!view.needAcct`（`model-relogin.js:107` 保证其恒等于 `setup ? !PhoneModel.relNeedAcct(model.flow, setup) : true`）。反转第 117 行三元条件只改变被同一同步函数末尾立即覆写的中间 DOM 属性，任何外部可见结果均不变。

## 4. 全组 226 条回归复跑对照

| 统计维度 | 补测前（`before.md`） | 第一批后（`after-ui-sync.md`） | 第二批后（本次 226 条复跑） | 本批变化 |
|---|---:|---:|---:|---:|
| 行为守 | 142 | 160 | 186 | +26 |
| 字面守 | 0 | 0 | 0 | 0 |
| 无人守 | 84 | 63 | 34 | -29（`ui-status.js` **0**、`ui-sync.js` **0**、`ui-list.js` 34） |
| 无效 | 0 | 0 | 0 | 0 |
| 等价 | 0 | 3 | 6 | +3 |
| **总计** | **226** | **226** | **226** | **0** |

### 第一批后结论核对与按文件/口径分布

- **第一批后结论核对**：原有 160 条行为守与 3 条等价判定（`M146`、`M150`、`M208`）全部保持一致，零退化。
- **按文件分布（本次 226 条）**：
  - `ui-sync.js`（82 条）：行为守 79、等价 3、**无人守 0**、字面守 0、无效 0
  - `ui-status.js`（83 条）：行为守 80、等价 3、**无人守 0**、字面守 0、无效 0
  - `ui-list.js`（61 条）：行为守 27、等价 0、**无人守 34**、字面守 0、无效 0
- **按变异口径单列统计（本次 226 条）**：
  - 甲类（`model.字段` 写换 `void 0`，40 条）：行为守 31、无人守 6、等价 3
  - 乙类（条件 `C` 换 `!(C)`，141 条）：行为守 116、无人守 23、等价 2
  - 丙类（`.hidden = X` 显隐写换 `void 0`，45 条）：行为守 39、无人守 5、等价 1

## 5. 复现命令

```bash
python -m unittest discover -s local/tests -p "test_phone_ui.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_code_shape.py"
python design/evidence/2026-11-23/phone-render-net/scripts/mutate_render.py \
  --ids M020,M022,M023,M025,M026,M027,M028,M030,M031,M035,M036,M038,M039,M043,M046,M053,M055,M056,M062,M066,M070,M072,M073,M074,M075,M076,M077,M078,M082 \
  --workers 4 --phase 补测之后 \
  --equiv-json design/evidence/2026-11-23/phone-render-net/scripts/equiv.json
python design/evidence/2026-11-23/phone-render-net/scripts/mutate_render.py \
  --workers 4 --phase 补测之后 \
  --equiv-json design/evidence/2026-11-23/phone-render-net/scripts/equiv.json
```
