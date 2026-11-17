# 要改的旧用例（动手前先列）

开工 HEAD `c3eb9d0`。按照计划要求，先 grep 这一批要动的函数名与条件原文，列出断言或读法可能跟着改的旧用例；这里记录「原来是什么、打算改成什么、依据哪一条」。表外的旧用例若变红，按计划停下，不改断言凑绿。

预计总时长 40 分钟：不变区对照约 1 分钟、变异约 2 分钟、本机版全量约 10 分钟，其余用于改写与验证。

## 先 grep 到的锚点

| 锚点原文 | 出现在 |
|---|---|
| `function doStopPlan()` | `local/tests/test_ui_contract_plan.py::test_stop_only_after_confirmation`（从函数头切到下一个 `function`） |
| `document.addEventListener("visibilitychange"` | `local/tests/test_ui_reliability.py::test_app_js_starts_the_loop_and_ticks_when_the_window_returns`（从监听器切到 `setInterval(tick, 1000)`） |
| `function paintEmpty(` / `function paintCount(` | `local/tests/test_ui_contract_feedback.py` 的空态切片；本批不动这两段 |
| `paintRunPanel`、`#run-warn` | `local/tests/test_ui_plan_board.py`、`local/tests/test_ui_contract_plan.py` 的整页沙箱用例；按文字切源码的没有 |
| `stop_plan` 回 `ok: false` | `local/tests/test_ui_plan_flow.py::test_stop_rejection_clears_stopping_and_editing`、`local/tests/test_prerefactor_fixes.py` 两条停止被拒用例 |

## 表内：断言正是这一批改掉的样子，才改断言

| 文件与用例 | 原来的输入与断言 | 改后的断言 | 依据 |
|---|---|---|---|
| 无 | 暂无：按画板改掉的三处现状原本都没有期望测试，新样子由 `test_plan_transitions.py` 守；下面这几条照旧用例应当保持绿 | 不动 | T6 |

## 表内：只改测试桩的输入，断言一个字不动

| 文件与用例 | 原来的输入与断言 | 改后的输入与断言 | 依据 |
|---|---|---|---|
| `local/tests/test_prerefactor_fixes.py::test_stop_refused_while_editing_returns_to_the_running_plan` | 停止桩回 `{ ok: false, text: "当前没有这个计划" }`，`bootstrap` 桩固定回 `{ busy: false }`；断言 `busy` 为真、「计划继续运行」在、「计划已暂停」不在 | 停止桩不变；在 `__stopImpl` 之后加一行 `window.pywebview.api.bootstrap = () => Promise.resolve({ busy: true });`，快照桩改成 `busy` 为真；断言一字不改，文档字符串末尾补「（后端拿到的是旧计划号，快照仍说在跑）」 | 后端回「当前没有这个计划」时前端按快照对账；快照仍在跑就仍在跑。真实后端回这句，可能是前端拿的是旧计划号、后端在跑另一个计划，此时快照 `busy` 为真 |

## 表内：只改从哪一段取，断言一个字不动

| 文件与用例 | 原来的读法 | 改后的读法 | 依据 |
|---|---|---|---|
| `local/tests/test_ui_contract_plan.py::test_stop_only_after_confirmation` | `js.index("function doStopPlan()")` 切到下一个 `function ` | 不变：`doStopPlan` 的函数头与它内部的 `"stop_plan"` 都保留；新增的 `resyncPlanFromBootstrap` 放在它后面，切片仍到下一个 `function` 为止，断言不变 | T4 |
| `local/tests/test_ui_reliability.py::test_app_js_starts_the_loop_and_ticks_when_the_window_returns` | 从 `document.addEventListener("visibilitychange"` 切到 `setInterval(tick, 1000)` | 不变：新增的一行和一句注释都在这个切片里，断言 `autoRefreshTick()` 仍在即可 | T5 |
| `local/tests/test_ui_contract_feedback.py::test_board_and_empty_no_longer_repeat_full_component_hint` | 从 `paintEmpty` 里的组件分支与状态机/样子表两处取 | 不变：本批不动空态与大屏标题区状态机，锚点不改 | T7 不变区 |

## 表外风险（变红就停下，不改）

`local/tests/test_prerefactor_fixes.py` 的 `test_stop_refused_while_editing_returns_to_the_running_plan` 与 `test_plain_stop_refusal_do_not_invent_the_editing_sentence`：桩里的 `bootstrap` 固定回 `{ busy: false }`，而 `stop_plan` 回 `ok: false`。按 T4 要对账，快照说没有计划时 `setBusy(false)`，于是「仍在运行」的旧断言会失效。这个文件不在计划的 `allowed_paths` 里，不能改；若实测变红，按停下条件处理，写进结果，不把断言改绿。

## 复核办法

- 开工 HEAD 副本：`git archive c3eb9d0` 到临时目录，跑新测试，确认新转移红、照旧用例绿。
- 实现后：跑 `test_plan_transitions.py`、`test_ui_plan_flow.py`、`test_ui_plan_board.py`、`test_ui_contract_plan.py`、`test_ui_contract_feedback.py`、`test_ui_reliability.py`、`test_plan_machine.py`、`test_ui_modules.py` 与代码结构检查；任何表外红都停下。
