# 手机页渲染组安全网补测第一批：`ui-sync.js` 19 条结论对照

- **范围**：针对 `design/evidence/2026-11-23/phone-render-net/before.md` 中 `local/ui/m/ui-sync.js` 全部 **19 条**无人守变异（`M146`、`M150`、`M158`、`M159`、`M160`、`M169`、`M177`、`M181`、`M182`、`M188`、`M189`、`M206`、`M208`、`M209`、`M213`、`M222`、`M223`、`M224`、`M225`），分布于 `ingest`（12 条）、`tickClock`（3 条）、`scheduleTick`（2 条）、`tickBoardLed`（1 条）、`tickRowLeft`（1 条）。
- **执行方式**：只读复用 `scripts/mutate_render.py`，在 `tempfile.gettempdir()` 下由 `git archive HEAD` 导出并叠加工作区 `local/tests/test_phone_ui.py` 的独立临时副本中先跑 19 条定向复跑，再跑全组 226 条回归复跑（`--workers 4`，配合 `scripts/equiv.json`）。产品代码零改动。

## 1. 本批 19 条逐条结论

| 编号 | 类 | 文件 | 函数 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例或等价说明 |
|---|---|---|---|---|---|---|---|
| M146 | 甲 | `ui-sync.js` | `scheduleTick` | `  if (model.tickTimer) clearTimeout(model.tickTimer); ↵   model.tickTimer = null;` | `  if (model.tickTimer) clearTimeout(model.tickTimer); ↵   void 0;` | 等价 | 见第 3 节 `M146` 调用方证明 |
| M150 | 甲 | `ui-sync.js` | `scheduleTick` | `  model.tickTimer = setTimeout(() => { ↵     model.tickTimer = null;` | `  model.tickTimer = setTimeout(() => { ↵     void 0;` | 等价 | 见第 3 节 `M150` 调用方证明 |
| M158 | 乙 | `ui-sync.js` | `tickClock` | `  const chipText = nowS !== null ↵     ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)).slice(0, 5) : ""; ↵   if (typeof document !== "undefined" && typeof document.querySelectorAll === "function") {` | `  const chipText = !(nowS !== null) ↵     ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)).slice(0, 5) : ""; ↵   if (typeof document !== "undefined" && typeof document.querySelectorAll === "function") {` | 行为守 | `PhoneTickTests.test_second_tick_updates_nowchip_only_when_calibrated` |
| M159 | 乙 | `ui-sync.js` | `tickClock` | `if (typeof document !== "undefined" && typeof document.querySelectorAll === "function")` | `if (!(typeof document !== "undefined" && typeof document.querySelectorAll === "function"))` | 行为守 | `PhoneTickTests.test_second_tick_updates_nowchip_only_when_calibrated` |
| M160 | 乙 | `ui-sync.js` | `tickClock` | `if (chipText && el.textContent !== chipText)` | `if (!(chipText && el.textContent !== chipText))` | 行为守 | `PhoneTickTests.test_second_tick_updates_nowchip_only_when_calibrated` |
| M169 | 乙 | `ui-sync.js` | `tickBoardLed` | `if (d.cls)` | `if (!(d.cls))` | 行为守 | `PhoneTickTests.test_tick_board_led_assigns_lit_dot_classes_when_countdown_changes` |
| M177 | 乙 | `ui-sync.js` | `tickRowLeft` | `if (String(small.className \|\| "") !== cls)` | `if (!(String(small.className \|\| "") !== cls))` | 行为守 | `PhoneTickSleepAndDrawerTests.test_tick_row_left_updates_urgent_class_name` |
| M181 | 甲 | `ui-sync.js` | `ingest` | `model.seq = 0;` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_reset_rewinds_poll_cursor_and_clears_old_logs` |
| M182 | 乙 | `ui-sync.js` | `ingest` | `if (logs)` | `if (!(logs))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_reset_rewinds_poll_cursor_and_clears_old_logs` |
| M188 | 乙 | `ui-sync.js` | `ingest` | `if (model.selected.length !== before.length)` | `if (!(model.selected.length !== before.length))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_notice_when_selection_intact_and_clears_when_pruned` |
| M189 | 甲 | `ui-sync.js` | `ingest` | `model.notice = "";` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_notice_when_selection_intact_and_clears_when_pruned` |
| M206 | 甲 | `ui-sync.js` | `ingest` | `model.retryHydrated = true;` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M208 | 甲 | `ui-sync.js` | `ingest` | `model.retryOptions = state.retry_options;` | `void 0;` | 等价 | 见第 3 节 `M208` 调用方证明 |
| M209 | 甲 | `ui-sync.js` | `ingest` | `model.seq = Math.max(model.seq, eventSeq);` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_reset_rewinds_poll_cursor_and_clears_old_logs` |
| M213 | 甲 | `ui-sync.js` | `ingest` | `model.seenEventSeq.delete(Math.min.apply(null, Array.from(model.seenEventSeq)));` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_deduplicates_event_seq_but_reset_accepts_new_round`（实际卡死在紧随其后的 `PhoneDomBehaviourTests.test_ingest_evicts_oldest_seen_event_after_400_events` `while (size > 400)` 死循环，90 秒超时退出码 124） |
| M222 | 乙 | `ui-sync.js` | `ingest` | `if (syncLine)` | `if (!(syncLine))` | 行为守 | `PhoneSyncPolicyTests.test_ingest_updates_last_sync_time_and_falls_back_when_uncalibrated` |
| M223 | 乙 | `ui-sync.js` | `ingest` | `syncNow !== null ↵       ?` | `!(syncNow !== null) ↵       ?` | 行为守 | `PhoneSyncPolicyTests.test_ingest_updates_last_sync_time_and_falls_back_when_uncalibrated` |
| M224 | 乙 | `ui-sync.js` | `ingest` | `if (model.sheetId === "review")` | `if (!(model.sheetId === "review"))` | 行为守 | `SheetsOpsDomTests.test_ingest_refreshes_open_review_drawer_and_closes_only_review_when_empty` |
| M225 | 乙 | `ui-sync.js` | `ingest` | `if (!model.selected.length)` | `if (!(!model.selected.length))` | 行为守 | `SheetsOpsDomTests.test_ingest_refreshes_open_review_drawer_and_closes_only_review_when_empty` |

### 本批 19 条分类合计

- 行为守：16（甲类 5、乙类 11、丙类 0）
- 等价：3（甲类 3：`M146`、`M150`、`M208`）
- 字面守：0
- 无人守：0
- 无效：0
- 总计：19

## 2. 新增行为用例清单

均写入 `local/tests/test_phone_ui.py` 对应主题测试类，仅断言用户可见 DOM（`textContent`、`hidden`、`className`、`value`、追加节点文本）与替身 `fetch` 请求：

| 测试类 / 用例名 | 守的用户可见结果 | 对应变异编号 |
|---|---|---|
| `PhoneDomBehaviourTests.test_ingest_reset_rewinds_poll_cursor_and_clears_old_logs` | 断线 `reset` 清空 `#logs` 旧日志文本并将游标回拨至本轮 `events[].seq`，后续轮询带回正确 `after=` | `M181`、`M182`、`M209` |
| `PhoneDomBehaviourTests.test_ingest_keeps_notice_when_selection_intact_and_clears_when_pruned` | 服务端快照未删减已选场次时保留冲突提示条，被剔除时自动收起（顺带覆盖 `ui-list.js` 的 `M087`、`M138`） | `M188`、`M189`（另顺带 `M087`、`M138`） |
| `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` | 用户修改并保存重试设置后，后续旧快照不覆盖 `#retry-for` 与 `start_plan` 载荷 | `M206` |
| `PhoneDomBehaviourTests.test_ingest_evicts_oldest_seen_event_after_400_events` | 超过 400 条事件后淘汰最早序号并可重新接收该序号，其余仍在窗内序号继续去重 | `M213` |
| `SheetsOpsDomTests.test_ingest_refreshes_open_review_drawer_and_closes_only_review_when_empty` | 核对抽屉打开期间刷新重画剩余批次、清空时收起，不影响「更多」等其他抽屉 | `M224`、`M225` |
| `PhoneSyncPolicyTests.test_ingest_updates_last_sync_time_and_falls_back_when_uncalibrated` | 快照摄入后把北京时间 `HH:MM` 写入 `#last-sync`，时钟不可用时落回 `--:--` | `M222`、`M223` |
| `PhoneTickTests.test_second_tick_updates_nowchip_only_when_calibrated` | 整秒刷新仅在时钟已校准时更新列表 `.nowchip b`，未校准时不覆盖现有文字 | `M158`、`M159`、`M160` |
| `PhoneTickTests.test_tick_board_led_assigns_lit_dot_classes_when_countdown_changes` | 整秒刷新重绘点阵屏时为亮暗点格保留 `on` 与空类名 | `M169` |
| `PhoneTickSleepAndDrawerTests.test_tick_row_left_updates_urgent_class_name` | 行内倒计时进入 10 分钟窗补充 `soon` 样式类，跨过开放时刻后清除 | `M177` |

## 3. 等价判定与全调用方证明

已写入 `design/evidence/2026-11-23/phone-render-net/scripts/equiv.json`：

- **`M146`**（`ui-sync.js:scheduleTick`）：`model.tickTimer` 的全部读写方只有 `scheduleTick`（`ui-sync.js:10,11,14,15`）、`onNeedPair`（`ui-session.js:275-276`）、`visibilitychange` 监听（`ui-shell.js:254-255`）与 `pagehide` 监听（`ui-shell.js:264-265`），所有读取方都只执行 `if (model.tickTimer) clearTimeout(model.tickTimer)`。`scheduleTick` 第 10 行已调用 `clearTimeout` 取消旧定时器：若第 12/13 行提前返回，保留已取消的单调 ID 仅使后续清理方再次对其调用空操作 `clearTimeout`；若继续到第 14 行则立即覆写新定时器 ID。浏览器与测试沙箱（`++timerSeq`）均不复用已分配的定时器 ID，任何 DOM、fetch 请求或活跃定时器都无法区分变异前后。
- **`M150`**（`ui-sync.js:scheduleTick`）：`model.tickTimer` 的全部读写方同上（`ui-sync.js:10,11,14,15`、`ui-session.js:275-276`、`ui-shell.js:254-255`、`ui-shell.js:264-265`）。本条位于 `scheduleTick` 的 `setTimeout` 回调内（第 15 行），此时定时器已触发并退出活跃队列：第 16 行 `tickClock()` 不读 `model.tickTimer`（内部若有 `poll(false)` 也在 `await fetch` 之后才调度），第 17 行立即调用 `scheduleTick()` 对该已触发单调 ID 调用空操作 `clearTimeout` 并由第 11 行置 `null` 或第 14 行覆写新 ID。任何 DOM、fetch 请求或活跃定时器均不变。
- **`M208`**（`ui-sync.js:ingest`）：在 `local/ui/m/` 全部 12 份脚本中检索 `retryOptions`，除 `ingest()` 第 174 行写入 `model.retryOptions = state.retry_options` 外无任何读取方，`ui-session.js` 中的 `model` 初值也未声明该字段；第 175 行直接将参数 `state.retry_options` 传给 `fillRetryOptions(state.retry_options)`。去掉这句未读取的属性写入不会影响任何 DOM、fetch 请求或定时器。

## 4. 全组 226 条回归复跑对照

| 统计维度 | 补测前（`before.md`） | 第一批补测后（本次 226 条复跑） | 变化 |
|---|---:|---:|---:|
| 行为守 | 142 | 160 | +18（本批 16 条 + 顺带覆盖 `ui-list.js` `M087`/`M138` 2 条） |
| 字面守 | 0 | 0 | 0 |
| 无人守 | 84 | 63 | -21（`ui-status.js` 29、`ui-list.js` 34、`ui-sync.js` **0**） |
| 无效 | 0 | 0 | 0 |
| 等价 | 0 | 3 | +3 |
| **总计** | **226** | **226** | **0** |

### 原有 142 条回归检查与按文件/口径分布

- **原有 142 条行为守**：零退化（142 条全部保持 `行为守`）。
- **按文件分布（本次 226 条）**：
  - `ui-sync.js`（82 条）：行为守 79、等价 3、**无人守 0**、字面守 0、无效 0
  - `ui-status.js`（83 条）：行为守 54、等价 0、**无人守 29**、字面守 0、无效 0
  - `ui-list.js`（61 条）：行为守 27、等价 0、**无人守 34**、字面守 0、无效 0
- **按变异口径单列统计（本次 226 条）**：
  - 甲类（`model.字段` 写换 `void 0`，40 条）：行为守 28、无人守 9、等价 3
  - 乙类（条件 `C` 换 `!(C)`，141 条）：行为守 110、无人守 31
  - 丙类（`.hidden = X` 显隐写换 `void 0`，45 条）：行为守 22、无人守 23

## 5. 复现命令

```bash
python -m unittest discover -s local/tests -p "test_phone_ui.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_code_shape.py"
python design/evidence/2026-11-23/phone-render-net/scripts/mutate_render.py \
  --ids M146,M150,M158,M159,M160,M169,M177,M181,M182,M188,M189,M206,M208,M209,M213,M222,M223,M224,M225 \
  --workers 4 --phase 补测之后 \
  --equiv-json design/evidence/2026-11-23/phone-render-net/scripts/equiv.json
python design/evidence/2026-11-23/phone-render-net/scripts/mutate_render.py \
  --workers 4 --phase 补测之后 \
  --equiv-json design/evidence/2026-11-23/phone-render-net/scripts/equiv.json
```
