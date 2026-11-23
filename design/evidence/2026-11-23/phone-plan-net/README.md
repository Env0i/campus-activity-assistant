# 手机页第三组（「计划操作」）安全网

- **执行日期**：2026-11-23
- **分支与基线**：`refactor/phone-page`（只增改 `local/tests/test_phone_ui.py` 与本目录证据文件；`local/ui/m/` 全部产品代码零改动）。
- **核心结论**：针对 `local/ui/m/ui-plan.js` 的 13 个顶层函数（含内部箭头回调）生成五类共 **97 条**单点变异；补测前行为守 53、无人守 44；补入 11 条纯行为用例并给出 1 条带全调用方证明的等价判定后，补测结论为 **行为守 96、等价 1、无人守 0、字面守 0、无效 0**。

## 1. 范围与五类变异口径

- **目标范围**：按 `design/evidence/2026-11-22/phone-net/move-facts.md` 归入「计划操作」组的 `local/ui/m/ui-plan.js` 全部 **13 个**顶层函数（`fillRetryOptions` 不含五类语法节点，其余 12 个函数共产生 97 条变异）。
- **五类单点变异口径**：
  - **甲类（28 条）**：函数体内每一处 `model.字段` 或局部别名 `pending`（即 `model.pending`）的字段写操作整条替换为 `void 0`。
  - **乙类（31 条）**：函数体内每一个 `if`、`else if` 与三元表达式条件 `C` 替换为 `!(C)`。
  - **丙类（1 条）**：函数体内每一处 `.hidden = X` 显隐写入整条替换为 `void 0`。
  - **丁类（28 条）**：函数体内每一处 `postAction` 调用的对象字面量里（含嵌套 `args` 与 `retry_policy`），每个属性的值替换为 `undefined`（简写属性 `items` 先展开为 `items: undefined`）。
  - **戊类（9 条）**：函数体内每一处 `return true` 与 `return false` 互换。
- **执行环境与方法**：在 `%TEMP%`（`tempfile.gettempdir()`）下由 `git archive HEAD` 导出、再叠加工作区 `local/tests/test_phone_ui.py` 的独立临时副本中运行 `scripts/mutate_plan.py`，每条变异先过 `node --check`，再跑 `local/tests/test_phone_ui.py` 全量用例；跑完删除临时副本。单条测试超时（90 秒）按失败计并在报告里标注「超时」（本组 `M008` 即 `start_plan` 的 `action` 置 `undefined` 时触发首个用例超时，记入行为守并标注「超时」）。

## 2. 13 个函数对照

| 函数 | 变异数 | 口径（甲 / 乙 / 丙 / 丁 / 戊） | 补测前（行为守 / 无人守） | 补测后（行为守 / 等价 / 无人守） |
|---|---:|---|---|---|
| `startPlan` | 20 | 5 / 7 / 0 / 8 / 0 | 14 / 6 | 19 / 1 / 0 |
| `reconcile` | 15 | 4 / 8 / 0 / 3 / 0 | 11 / 4 | 15 / 0 / 0 |
| `cancelPendingStart` | 15 | 6 / 3 / 0 / 3 / 3 | 7 / 8 | 15 / 0 / 0 |
| `stopPlan` | 8 | 0 / 2 / 0 / 3 / 3 | 5 / 3 | 8 / 0 / 0 |
| `showComputerWindow` | 3 | 0 / 1 / 0 / 2 / 0 | 0 / 3 | 3 / 0 / 0 |
| `cancelTask` | 9 | 0 / 2 / 0 / 4 / 3 | 5 / 4 | 9 / 0 / 0 |
| `reselectFailed` | 8 | 5 / 3 / 0 / 0 / 0 | 5 / 3 | 8 / 0 / 0 |
| `finishPlanView` | 5 | 5 / 0 / 0 / 0 / 0 | 2 / 3 | 5 / 0 / 0 |
| `saveRetry` | 7 | 1 / 1 / 0 / 5 / 0 | 0 / 7 | 7 / 0 / 0 |
| `fillRetryOptions` | 0 | 0 / 0 / 0 / 0 / 0 | 0 / 0 | 0 / 0 / 0 |
| `renderReview` | 3 | 0 / 2 / 1 / 0 / 0 | 1 / 2 | 3 / 0 / 0 |
| `removeFromReview` | 3 | 2 / 1 / 0 / 0 / 0 | 2 / 1 | 3 / 0 / 0 |
| `openReview` | 1 | 0 / 1 / 0 / 0 / 0 | 1 / 0 | 1 / 0 / 0 |
| **合计（13 个函数）** | **97** | **28 / 31 / 1 / 28 / 9** | **53 / 44** | **96 / 1 / 0** |

## 3. 补测前后统计对照

| 结论分类 | 补测前（`before.md`） | 补测后（`after.md`） | 变化 |
|---|---:|---:|---:|
| 行为守 | 53 | **96** | +43 |
| 字面守 | 0 | 0 | 0 |
| 无人守 | 44 | **0** | -44 |
| 无效 | 0 | 0 | 0 |
| 等价 | 0 | **1** | +1 |
| **总计** | **97** | **97** | **0** |

按口径分布（补测后最终态）：
- 甲类（28 条）：行为守 27、等价 1、无人守 0
- 乙类（31 条）：行为守 31、等价 0、无人守 0
- 丙类（1 条）：行为守 1、等价 0、无人守 0
- 丁类（28 条）：行为守 28、等价 0、无人守 0
- 戊类（9 条）：行为守 9、等价 0、无人守 0

## 4. 新增行为用例清单（共 11 条）

全部写入 `local/tests/test_phone_ui.py` 对应主题既有测试类，仅断言用户可见 DOM、定时器或替身 `fetch` 请求路径与载荷（丙类显隐用例开场先设为与预期相反的 `hidden`），测试文件总数保持 39 个：

| 测试类 / 用例名 | 守的用户可见结果或请求载荷 | 对应无人守变异编号 |
|---|---|---|
| `MobileWriteResilienceTests.test_start_plan_payload_and_sync_accept_clears_notice` | 发送 `items` 与 `headed: false`，清 `#list-notice`，同步受理后隐藏 `#btn-cancel-start` 且窗口内不误报未核对 | `M006`、`M010`、`M011`、`M018` |
| `MobileWriteResilienceTests.test_start_plan_collapses_expanded_list_for_running_plan` | 上轮展开列表后开始新计划，运行态折叠 `#today-items` 并置 `aria-expanded="false"` | `M007` |
| `MobileWriteResilienceTests.test_reconcile_single_flight_payload_and_canceled_banner_kind` | 对账在途单飞不重发、携带 `args.request_id`，取消终态写 `#banner.dataset.kind="info"` | `M023`、`M025`、`M026`、`M033` |
| `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` | 取消等待在途防重发并屏蔽迟到对账，重试成功后关抽屉并触发 `/api/state` 轮询 | `M038`、`M039`、`M048`、`M049`、`M050` |
| `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` | 取消失败留抽屉并放行后续对账，已决后点确认不发请求且保持抽屉打开与按钮可点 | `M037`、`M046`、`M047` |
| `MobileWriteResilienceTests.test_save_retry_payload_failure_log_and_clears_dirty_before_hydration` | 修改重试发送完整 `save_retry_policy` 载荷，失败记 `#logs`，成功后解除首轮快照覆盖门禁 | `M084`–`M090` |
| `SheetsOpsDomTests.test_stop_plan_payload_and_missing_plan_keeps_confirm_open` | 停止计划带 `args.plan_id`，无计划时点确认保留抽屉并放开按钮 | `M052`、`M054`、`M055` |
| `SheetsOpsDomTests.test_show_computer_window_payload_and_logs` | 显示电脑窗口发送 `action="show_window"` 与空 `args`，成功与失败分别记 `#logs` | `M059`、`M060`、`M061` |
| `SheetsOpsDomTests.test_cancel_task_failure_success_and_missing_task_keeps_confirm_open` | 取消单场失败留抽屉提示 `#sheet-err`、成功收起抽屉，任务消失时保留抽屉并放开按钮 | `M063`、`M068`、`M069`、`M070` |
| `SheetsOpsDomTests.test_review_render_act_line_warns_visibility_and_remove_clears_notice` | 核对项仅有时段时绘 `<small>`，双向显隐 `#review-warns`，移除条目同步清 `#list-notice` | `M091`、`M092`、`M095` |
| `ResultTermsDomTests.test_reselect_and_finish_dismiss_plan_collapse_list_and_clear_notice` | 重新选择与完成回草稿均记住已收起 `plan_id`、收起列表展开态并清除 `#list-notice` | `M071`、`M076`、`M077`、`M079`、`M082`、`M083` |

## 5. 等价判定摘要（1 条）

完整理由与全目录扫描证明见 `design/evidence/2026-11-23/phone-plan-net/scripts/equiv.json` 与 `after.md` 末尾：

- **`M019`**（`ui-plan.js:startPlan`）：`model.pending.outcome = "accepted";` 改 `void 0;`。第 21 行新建的 `model.pending` 上 `outcome` 初值为 `undefined`；全目录 12 份手机页脚本仅有 `model.js:250-251`（`PhoneModel.startPending`）读取 `pending.outcome`，且只判断 `=== "canceled" || === "rejected"`，`"accepted"` 与 `undefined` 在所有正常分支返回值完全相同，其余 9 份脚本与 DOM/请求/定时器零读取。

## 6. 未覆盖项

- 手机真机与打包后的电脑端 WebView2 冻结窗口未实测，所有行为用例均在受控 Node `vm` 沙箱与本机离线单元测试运行。
- 本组安全网仅覆盖 `local/ui/m/ui-plan.js` 的 13 个顶层函数；「外壳与接线」「重新登录」两组未纳入本批变异。

## 7. 复现命令

在仓库根执行（Python 3.12；运行前清空 `http_proxy` / `HTTP_PROXY` / `https_proxy` / `HTTPS_PROXY` / `all_proxy`，并设 `PYTHONIOENCODING=utf-8`）：

```bash
python -m unittest discover -s local/tests -p "test_phone_ui.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_code_shape.py"
python design/evidence/2026-11-23/phone-plan-net/scripts/mutate_plan.py --list
python design/evidence/2026-11-23/phone-plan-net/scripts/mutate_plan.py --baseline
python design/evidence/2026-11-23/phone-plan-net/scripts/mutate_plan.py \
  --workers 4 --phase 补测之后 \
  --equiv-json design/evidence/2026-11-23/phone-plan-net/scripts/equiv.json \
  --out design/evidence/2026-11-23/phone-plan-net/after.md
```
