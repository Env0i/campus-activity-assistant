# 手机页第二组（「摄入与渲染」）安全网与主界面显示守卫

- **执行日期**：2026-11-23
- **分支与基线**：`refactor/phone-page`（只增改 `local/tests/test_phone_ui.py` 与本目录证据文件；`local/ui/m/` 全部产品代码零改动）。
- **核心结论**：补全主界面显示守卫用例后，针对「摄入与渲染」组 3 个文件 23 个函数的 **226 条**单点变异，分三批补入 25 条纯行为用例并给出 6 条带全调用方证明的等价判定；补测后全组 **行为守 220、等价 6、无人守 0、字面守 0、无效 0**。

## 1. 范围与三类变异口径

- **目标范围**：按 `design/evidence/2026-11-22/phone-net/move-facts.md` 归入「摄入与渲染」组的 **23 个**顶层函数（`addLog` 函数体不含三类语法节点，故产生变异的函数为 22 个，总计 226 条变异）。
- **三类单点变异口径**：
  - **甲类（40 条）**：函数体内每一处 `model.字段` 写操作（赋值、复合赋值、自增自减、原地修改）整条替换为 `void 0`。
  - **乙类（141 条）**：函数体内每一个 `if`、`else if` 与三元表达式条件 `C` 替换为 `!(C)`。
  - **丙类（45 条）**：函数体内每一处 `.hidden = X` 显隐写入整条替换为 `void 0`。
- **执行环境与方法**：只读复用 `scripts/mutate_render.py`，在 `%TEMP%`（`tempfile.gettempdir()`）下由 `git archive HEAD` 导出、再叠加工作区 `local/tests/test_phone_ui.py` 的独立临时副本中，先过 `node --check`，再跑 `local/tests/test_phone_ui.py` 全量用例；跑完删除临时副本。所有显隐类新用例均先将被断言元素的 `hidden` 设为与预期相反的初值。

## 2. 23 个函数与三个文件的对照

| 文件 | 函数 | 变异数 | 口径（甲 / 乙 / 丙） | 补测后（行为守 / 等价 / 无人守） |
|---|---|---:|---|---|
| `ui-status.js` | `setBanner` | 3 | 1 / 1 / 1 | 3 / 0 / 0 |
| `ui-status.js` | `clearStaleBanner` | 1 | 0 / 1 / 0 | 1 / 0 / 0 |
| `ui-status.js` | `syncOffline` | 8 | 1 / 4 / 3 | 8 / 0 / 0 |
| `ui-status.js` | `renderAlerts` | 7 | 0 / 2 / 5 | 7 / 0 / 0 |
| `ui-status.js` | `canWrite` | 1 | 1 / 0 / 0 | 1 / 0 / 0 |
| `ui-status.js` | `refreshControls` | 11 | 1 / 4 / 6 | 8 / 3 / 0 |
| `ui-status.js` | `renderBar` | 22 | 0 / 13 / 9 | 22 / 0 / 0 |
| `ui-status.js` | `renderRail` | 3 | 0 / 2 / 1 | 3 / 0 / 0 |
| `ui-status.js` | `renderBoard` | 20 | 2 / 11 / 7 | 20 / 0 / 0 |
| `ui-status.js` | `renderStats` | 1 | 0 / 1 / 0 | 1 / 0 / 0 |
| `ui-status.js` | `renderPlan` | 1 | 0 / 0 / 1 | 1 / 0 / 0 |
| `ui-status.js` | `renderTasks` | 5 | 0 / 4 / 1 | 5 / 0 / 0 |
| `ui-status.js` | `addLog` | 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| `ui-list.js` | `buildRow` | 19 | 2 / 17 / 0 | 19 / 0 / 0 |
| `ui-list.js` | `buildWhy` | 2 | 0 / 2 / 0 | 2 / 0 / 0 |
| `ui-list.js` | `goSigned` | 12 | 4 / 8 / 0 | 12 / 0 / 0 |
| `ui-list.js` | `renderItems` | 22 | 1 / 11 / 10 | 22 / 0 / 0 |
| `ui-list.js` | `toggleSearch` | 6 | 2 / 3 / 1 | 6 / 0 / 0 |
| `ui-sync.js` | `scheduleTick` | 6 | 3 / 3 / 0 | 4 / 2 / 0 |
| `ui-sync.js` | `tickClock` | 10 | 2 / 8 / 0 | 10 / 0 / 0 |
| `ui-sync.js` | `tickBoardLed` | 9 | 0 / 9 / 0 | 9 / 0 / 0 |
| `ui-sync.js` | `tickRowLeft` | 9 | 0 / 9 / 0 | 9 / 0 / 0 |
| `ui-sync.js` | `ingest` | 48 | 20 / 28 / 0 | 47 / 1 / 0 |
| **合计** | **23 个函数（3 文件）** | **226** | **40 / 141 / 45** | **220 / 6 / 0** |

## 3. 补测前后四档统计对照

| 结论分类 | 补测前（`before.md`） | 第一批后（`after-ui-sync.md`） | 第二批后（`after-ui-status.md`） | 第三批后（`after.md`） | 总变化 |
|---|---:|---:|---:|---:|---:|
| 行为守 | 142 | 160 | 186 | **220** | +78 |
| 字面守 | 0 | 0 | 0 | 0 | 0 |
| 无人守 | 84 | 63 | 34 | **0** | -84 |
| 无效 | 0 | 0 | 0 | 0 | 0 |
| 等价 | 0 | 3 | 6 | **6** | +6 |
| **总计** | **226** | **226** | **226** | **226** | **0** |

按文件分布（补测后最终态）：
- `ui-sync.js`（82 条）：行为守 79、等价 3、无人守 0
- `ui-status.js`（83 条）：行为守 80、等价 3、无人守 0
- `ui-list.js`（61 条）：行为守 61、等价 0、无人守 0

## 4. 主界面显示用例与两条显隐变异结论

- **新增守卫用例**：`PairStatesDomTests.test_pair_and_session_restore_show_app_view`（开场显式设 `#app.hidden = true`、`#pair.hidden = false`，依次走配对成功与首屏带 cookie 会话恢复两条路，均断言 `#app` 显示且 `#pair` 隐藏）。
- **两条显隐变异复跑结论**（在独立临时副本删除 `local/ui/m/ui-session.js` 对应语句后跑 `test_phone_ui.py`）：
  1. 删 `showAppView` 中 `$("app").hidden = false;` → 退出码 1（1 条失败），首个失败用例：`PairStatesDomTests.test_pair_and_session_restore_show_app_view`。
  2. 删 `showPairView` 中 `$("pair").hidden = false;` → 退出码 1（2 条失败），首个失败用例：`MobileWriteResilienceTests.test_action_401_clears_active_poll_and_tick_timers`（同批还失败 `MobileWriteResilienceTests.test_need_pair_still_sends_the_user_back_to_pairing`）。

## 5. 三批新增行为用例清单（共 25 条）

全部写入 `local/tests/test_phone_ui.py` 对应主题测试类，仅断言用户可见结果，测试文件总数保持 39 个：

### 第一批：`ui-sync.js`（9 条）

| 测试类 / 用例名 | 守的用户可见结果 | 对应变异编号 |
|---|---|---|
| `PhoneDomBehaviourTests.test_ingest_reset_rewinds_poll_cursor_and_clears_old_logs` | 断线 `reset` 清空 `#logs` 旧日志并回拨游标至本轮 `events[].seq` | `M181`、`M182`、`M209` |
| `PhoneDomBehaviourTests.test_ingest_keeps_notice_when_selection_intact_and_clears_when_pruned` | 快照保留已选时留冲突提示条，剔除时收起（顺带守 `ui-list.js` `M087`、`M138`） | `M188`、`M189`（顺带 `M087`、`M138`） |
| `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` | 保存重试设置后旧快照不覆盖 `#retry-for` 与 `start_plan` 载荷 | `M206` |
| `PhoneDomBehaviourTests.test_ingest_evicts_oldest_seen_event_after_400_events` | 超 400 条事件淘汰最早序号并允许重收，窗内其余序号继续去重 | `M213` |
| `SheetsOpsDomTests.test_ingest_refreshes_open_review_drawer_and_closes_only_review_when_empty` | 核对抽屉刷新重画剩余批次并在选空时收起，不影响其他抽屉 | `M224`、`M225` |
| `PhoneSyncPolicyTests.test_ingest_updates_last_sync_time_and_falls_back_when_uncalibrated` | 同步后将北京时间 `HH:MM` 写入 `#last-sync`，未校准落回 `--:--` | `M222`、`M223` |
| `PhoneTickTests.test_second_tick_updates_nowchip_only_when_calibrated` | 整秒刷新仅在校准后更新 `.nowchip b`，未校准不覆盖文字 | `M158`、`M159`、`M160` |
| `PhoneTickTests.test_tick_board_led_assigns_lit_dot_classes_when_countdown_changes` | 整秒重绘点阵屏时保留亮暗格类名 `on` 与空串 | `M169` |
| `PhoneTickSleepAndDrawerTests.test_tick_row_left_updates_urgent_class_name` | 行内倒计时进 10 分钟窗补 `soon` 类，越过开放时刻清除 | `M177` |

### 第二批：`ui-status.js`（9 条）

| 测试类 / 用例名 | 守的用户可见结果 | 对应变异编号 |
|---|---|---|
| `MobileWriteResilienceTests.test_can_write_reads_fresh_clock_after_idle_gap_before_start` | 静置超 30 秒再点开始按当下时间拦下并弹过时提示，不发写请求 | `M020` |
| `SheetShellTests.test_sheet_close_button_hides_only_when_open_sheet_is_busy` | 无抽屉打开时不改动关闭钮显隐；抽屉打开且提交忙态时隐藏 | `M030`、`M031` |
| `RunWaitDomTests.test_pending_bar_title_switches_after_window_and_start_hides_when_busy` | 核对超 15 秒切底栏标题，运行中隐藏开始钮且非运行态恢复 | `M043`、`M053` |
| `RunWaitDomTests.test_board_rail_visibility_and_step_classes_and_task_card_tone` | 四站进度条按步数显隐并写阶段类名，任务卡徽章写色调类名 | `M055`、`M056`、`M082` |
| `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` | 详情板与北京时间行显式显示，点阵保留亮暗类名，「选这一场」可加选并随选空隐藏 | `M062`、`M066`、`M074`、`M075`、`M076` |
| `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` | 结果态显隐底栏结果钮、收起开始/取消钮、显统计区写色调类，回草稿重收起 | `M035`、`M036`、`M038`、`M039`、`M070`、`M077` |
| `ResultTermsDomTests.test_result_hides_pick_next_and_clears_pick_target` | 结果态隐藏「选这一场」并清空待选目标，不再将旧候选写入已选列表 | `M072`、`M073` |
| `ExceptionStatesTests.test_stale_note_and_stop_and_cancel_start_visibility_follow_state` | `#stale-note`、`#btn-stop`、`#btn-cancel-start` 双向随状态显隐 | `M022`、`M023`、`M028` |
| `ExceptionStatesTests.test_pc_list_error_bar_readies_start_button_and_run_tip_toggles_with_busy` | 列表失败藏底栏后恢复开始钮不隐藏，`#run-tip` 双向随 `busy` 显隐 | `M046`、`M078` |

### 第三批：`ui-list.js`（7 条）

| 测试类 / 用例名 | 守的用户可见结果 | 对应变异编号 |
|---|---|---|
| `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` | 待公布行 `txt` 类、临近倒计时 `soon` 类、`flag` 类、未截止才显地点、奖励与重叠行警 | `M088`、`M089`、`M090`、`M091`、`M096`、`M097`、`M098` |
| `PhoneRowDomTests.test_clash_row_click_prevents_default_and_go_button_stops_bubbling` | 点重叠行拦默认动作且缺 `preventDefault` 不崩；点「去已报名那场」止冒泡不重开原因 | `M101`、`M104`（亦守 `M105`、`M114`） |
| `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` | 「去已报名那场」收原因、清隐藏筛选与片选、展开已报名汇总、滚动、高亮并在 2 秒后熄灭 | `M085`、`M105`、`M106`、`M107`、`M108`、`M109`、`M110`、`M111`、`M112`、`M113`、`M114`、`M115`、`M116` |
| `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` | 保留开放组样式，按匹配与忙闲收放 `#upcoming-zone`、`#filter-empty`、`#search-view` 与 `#btn-toggle-list` | `M121`、`M124`、`M125`、`M128`、`M130`、`M131` |
| `ListDetailModelTests.test_toggle_search_reveals_box_before_focus_and_clears_queries` | 展开搜索先显示容器再聚焦，清空 `#q`/`#search-q` 与筛选词，收起时不聚焦 | `M140`、`M142`、`M143`、`M144` |
| `ResultTermsDomTests.test_signed_summary_items_populate_only_in_result_state` | `#signed-items` 汇总行只在结果态填充，草稿态不重复填入 | `M134` |
| `RunWaitDomTests.test_render_items_refreshes_clock_before_offline_board_render` | 离线重绘列表先刷新 `nowMs`，使运行看板立即切换为离线过时提示与 dim 样式 | `M117` |

## 6. 等价判定摘要（6 条）

完整调用方排查与逐行证明见 `design/evidence/2026-11-23/phone-render-net/scripts/equiv.json` 与 `after.md` 末尾：

- **`M025`、`M026`、`M027`**（`ui-status.js:refreshControls`）：紧随其后的第 118–132 行均不读取 `#relogin-account`，同一同步调用第 133 行无条件调用 `renderRelogin()` 覆写为同语义的 `!view.needAcct`。
- **`M146`、`M150`**（`ui-sync.js:scheduleTick`）：全部读取方只在 `clearTimeout` 前判真，`scheduleTick` 先取消旧定时器并在后续分支立即覆写新 ID 或保持空操作清理，浏览器与沙箱均不复用单调定时器 ID。
- **`M208`**（`ui-sync.js:ingest`）：全目录 12 份脚本仅在 `ingest()` 写入 `model.retryOptions`，无任何读取方，参数 `state.retry_options` 直接传入 `fillRetryOptions`。

## 7. 未覆盖项

- 手机真机（如 iOS Safari）与打包后的电脑端 WebView2 冻结窗口未实测，所有行为用例均在受控 Node `vm` 沙箱与本机离线单元测试运行。
- 本组安全网仅覆盖「摄入与渲染」组的 23 个函数（与前置 `showAppView`/`showPairView` 显隐守卫）；「外壳与接线」「计划操作」「重新登录」三组未纳入本批变异。

## 8. 复现命令

在仓库根执行（Python 3.12；运行前清空 `http_proxy` / `HTTP_PROXY` / `https_proxy` / `HTTPS_PROXY` / `all_proxy`，并设 `PYTHONIOENCODING=utf-8`）：

```bash
python -m unittest discover -s local/tests -p "test_phone_ui.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_code_shape.py"
python design/evidence/2026-11-23/phone-render-net/scripts/mutate_render.py --list
python design/evidence/2026-11-23/phone-render-net/scripts/mutate_render.py --baseline
python design/evidence/2026-11-23/phone-render-net/scripts/mutate_render.py \
  --workers 4 --phase 补测之后 \
  --equiv-json design/evidence/2026-11-23/phone-render-net/scripts/equiv.json \
  --out design/evidence/2026-11-23/phone-render-net/after.md
```
