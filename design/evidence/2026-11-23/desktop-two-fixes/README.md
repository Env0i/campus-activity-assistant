# 桌面两处小缺陷修复证据

日期：2026-11-23

## 一、两处缺陷的现象与例子

1. **截止那一刻列表仍判「开放中」**
   - 现象：业务时钟恰好走到 `sign_end` 那一秒时，列表行仍显示「开放中」、复选框仍可勾选；点击「开始报名计划」时却因 `modeOf` 判为 `closed` 被 `validateSelection` 拦下并报「报名已截止」。
   - 例子：活动 `sign_start = "2026-11-06 10:00:00"`、`sign_end = "2026-11-06 14:00:00"`，当业务时钟恰好为 `2026-11-06 14:00:00`（UTC+8）时，改前 `stateOf` 返回 `"open"` 而 `modeOf` 返回 `"closed"`。

2. **转人工后用户输错验证码仍重复并误报电脑原因**
   - 现象：自动识别结果不合规（`attempts = 1`）就转人工后，用户每次输错验证码换新图，后端中继的 `handoff` 仍保持真且 `attempts` 继续累加；用户再输错两次到 `attempts = 3` 时，重登对话框不仅每张图都重复弹转人工原因，还会改说「自动识别 3 次没认对，请输入验证码。」，把用户输错算到电脑头上，违背验证码错只换图的文案规则。
   - 例子：`flow_id = "f1"` 在 `attempts = 1` 时因识别不合规转人工，随后用户连错两次收到 `attempts = 2`、`attempts = 3` 的新验证码时，改前对话框在 `attempts = 2` 重复显示「电脑没认出这张验证码，请输入验证码。」，在 `attempts = 3` 改为显示「自动识别 3 次没认对，请输入验证码。」。

## 二、根因

1. `local/ui/state/labels.js` 的 `stateOf` 用 `end !== null && end < bn` 判断已截止，而同文件 `modeOf`、后端 `signup_plan.classify_signup_mode` 与手机页 `stOf` 均使用 `end <= now`（截止时刻已到即截止），边界少算了等于 `sign_end` 的那一秒。
2. `local/ui/features/login/view-relogin.js` 的 `reloginShowChallenge` 每次收到新验证码时，只要 `payload.handoff` 为真就直接按当时的 `payload.attempts` 选句并调用 `reloginError`；而编排层 `local/ui/features/login/actions-relogin.js` 虽然在 `receiveReloginState` 用 `reloginHandoffSeen` 把运行记录限制为只写一次，但未记住转人工那一刻的尝试次数，也没有限制对话框只在转人工那一张验证码上展示原因。

## 三、修法

1. **列表截止边界对齐**：将 `local/ui/state/labels.js` 中 `stateOf` 的 `end !== null && end < bn` 改为 `end !== null && end <= bn`，其余分支不变。
2. **转人工原因只说一次并锁定当时次数**：
   - 在 `local/ui/features/login/actions-relogin.js` 新增 `reloginHandoffFlow` 与 `reloginHandoffAttempts`，由 `trackReloginHandoff` 在同一 `flow_id` 首次看到 `handoff` 为真时记下当时的 `attempts`（当 `handoff` 变回假或换了 `flow_id` 时清掉）；`openRelogin` 与 `receiveReloginState` 调用 `reloginShowChallenge` 时经 `challengeWithHandoff` 传入附带 `handoff_attempts` 的浅拷贝（不改后端载荷，对话框在早已转人工后打开也沿用已记下的次数）。
   - 在 `local/ui/features/login/view-relogin.js` 的 `reloginShowChallenge` 中，只在 `payload.handoff` 为真、`handoff_attempts` 存在且 `Number(payload.attempts || 0) === Number(payload.handoff_attempts)` 时显示转人工原因，并按 `handoff_attempts` 选句（`>= 3` 显示「自动识别 3 次没认对，请输入验证码。」，否则显示「电脑没认出这张验证码，请输入验证码。」）；后续换图时只保留 `#rl-cap-tries`（「已经试过 N 次，换了一张新图。」），两句原文与文案规格及决策 006 保持一致，视图层不引用编排层。

## 四、测试与变异结果

- 语法与结构检查：
  - `node --check` 覆盖 `local/ui/state/labels.js`、`local/ui/features/login/actions-relogin.js`、`local/ui/features/login/view-relogin.js` 全部通过（exit 0）。
  - `python tools/code_shape/check.py` 通过（exit 0，未改动 `baseline.json`）。
  - `node tools/code_shape/ui_modules.mjs` 通过（exit 0，模块图与层规则无违规）。
- 五份相关 UI 测试文件（清除代理环境变量、Python 3.12.9）：
  - `local/tests/test_ui_main_window.py`：101 通过 / 0 失败 / 0 跳过（含新增 `test_state_of_closes_at_exact_sign_end_second`，既有断言未改）。
  - `local/tests/test_ui_reliability.py`：动手前 109 通过 / 0 失败 / 0 跳过 → 动手后 111 通过 / 0 失败 / 0 跳过（新增 2 条用例，见 [changed-tests.md](changed-tests.md)）。
  - `local/tests/test_ui_contracts.py`：374 通过 / 0 失败 / 0 跳过。
  - `local/tests/test_ui_plan.py`：70 通过 / 0 失败 / 0 跳过。
  - `local/tests/test_ui_layers.py`：31 通过 / 0 失败 / 0 跳过。
- 本机全量测试（`local/tests`）：`Ran 2809 tests in 197.798s`，`OK (skipped=2)`。
- 变异反证：在 `%TEMP%` 独立副本先验证基线全绿，随后逐条注入三处单点变异，对应新用例均变红（exit 1），详情见 [mutations.md](mutations.md)。

## 五、未验证项与复现命令

- 未验证项：
  - 真实学校站点与真机 WebView2 窗口下，等待业务时钟跨过 `sign_end` 的端到端界面截图与自动重登转人工真机交互联调未在本次执行。
  - 本机全量测试中既有的 2 条环境条件跳过用例（`skipped=2`）未在本机覆盖。
- 复现命令（先清除 `http_proxy` / `HTTP_PROXY` / `https_proxy` / `HTTPS_PROXY` / `all_proxy`）：

```bash
node --check local/ui/state/labels.js
node --check local/ui/features/login/actions-relogin.js
node --check local/ui/features/login/view-relogin.js
python tools/code_shape/check.py
node tools/code_shape/ui_modules.mjs
python -m unittest discover -s local/tests -p "test_ui_main_window.py"
python -m unittest discover -s local/tests -p "test_ui_reliability.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_ui_plan.py"
python -m unittest discover -s local/tests -p "test_ui_layers.py"
python -m unittest discover -s local/tests -p "test_*.py"
```
