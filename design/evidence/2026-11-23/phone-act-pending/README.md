# 手机页开始前举办时间检查证据

日期：2026-11-23

## 一、范围

- **原型与画板**：`design/prototype/workbench-2026-11/Phone.dc.html`、`PhoneActPending.dc.html`、`PhoneSignedActPending.dc.html`、`canvas.json`、`README.md`。
- **手机页纯规则与底栏**：`local/ui/m/model-conflict.js`、`local/ui/m/model.js`、`local/ui/m/model-list.js`、`local/ui/m/ui-status.js`。
- **规格与文档**：`design/specs/copywriting.md`、`docs/UI_SPEC.md`。
- **测试与反证**：`local/tests/test_phone_ui.py`、[changed-tests.md](changed-tests.md)、[mutations.md](mutations.md)。
- 未改动后端、`local/ui/m/` 快照字段、桌面前端与勾选规则。

## 二、与桌面及后端的对应关系

- 决策 004 与电脑后端 `local/signup_plan.py`（`validate_plan`）规定：缺少完整举办时段（`act_start` / `act_end` 缺失、非法或结束不晚于开始）的活动不能加入可执行计划；当存在选择时，若已报名活动缺少完整举办时段，也因无法确认是否冲突而保守阻止计划。
- 桌面端在勾选时不拦举办时间缺失的活动，只在开始前通过 `local/ui/state/filters.js`（`validateSelection`）与 `local/ui/features/plan/view-draft.js`（`startBlocker`）提示「活动时间待确认」「已报名活动时间待确认」并禁用开始按钮。
- 手机页沿用相同原则：列表行照旧允许勾选（不改 `PhoneModel.actionable`），在开始前拦截并由底栏直接说明还差哪一类场次。

## 三、新规则与文案

- `PhoneModel.actBlock(items, selectedIds)`（`local/ui/m/model-conflict.js`）：空选择返回 `null`；先查已选场次中 `actRange(i) === null` 的场次，命中返回 `{ kind: "selected", names: [...] }`；否则再查全部活动里 `signed` 且 `actRange(i) === null` 的场次，命中返回 `{ kind: "signed", names: [...] }`；都齐全返回 `null`（名称取 `PhoneModel.itemTitle`）。
- `PhoneModel.canStart(model)`（`local/ui/m/model.js`）：在既有过时、忙态、时钟、空选检查之后接入 `PhoneModel.actBlock(model.items, model.selected) === null`。
- `PhoneModel.actBlockText(block)`（`local/ui/m/model-conflict.js`）：首场名称超过 12 个字截成前 12 字加「…」；`selected` 单场写「还差一步：已选的「名称」举办时间待公布，先取消勾选」，多场写「还差一步：已选的 N 场举办时间待公布，先取消勾选」；`signed` 单场写「还差一步：已报名的「名称」缺少举办时间，暂时开始不了」，多场写「还差一步：已报名的 N 场缺少举办时间，暂时开始不了」；`null` 返回空串。
- `renderBar`（`local/ui/m/ui-status.js`，55 行）：在非运行态副题链中排在条款、自动登录中、登录失效、时钟待校准、离线分支之后，默认 `planSummary` 之前取 `actBlockText`；`btn-start` 仍随 `canStart` 禁用。
- `PhoneModel.rowView`（`local/ui/m/model-list.js`，54 行）：`actSpan` 为空且行状态为 `pre` 或 `open` 时，举办时间格写「举办时间待公布」；`closed` 与 `unknown` 现有写法不变。

## 四、旧用例夹具改动与测试结果

- **旧用例夹具调整**：仅给 7 条原本与举办时间无关但被勾选活动缺 `act_start` / `act_end` 的既有 `test_phone_ui.py` 用例补上不重叠的合法举办时间，期望断言一字未改；逐条明细见 [changed-tests.md](changed-tests.md)。
- **测试结果（清除代理环境变量，Python 3.12.9）**：
  - 动手前（产品代码落地后、改测试前）：`test_phone_ui.py` 258 条中 251 通过、7 失败（全部为上述 7 条缺举办时间夹具的旧用例），`test_ui_contracts.py` 374 通过 / 0 失败 / 0 跳过。
  - 动手后：`test_phone_ui.py` 262 通过 / 0 失败 / 0 跳过（新增 4 条，全过）；`test_ui_contracts.py` 374 通过 / 0 失败 / 0 跳过；`test_code_shape.py` 15 通过 / 0 失败 / 0 跳过；`python tools/code_shape/check.py` 通过（exit 0，`baseline.json` 未改）。
  - 本机全量（`local/tests`）：`Ran 2813 tests in 198.299s`，`OK (skipped=2)`。
- **变异反证**：在 `%TEMP%` 独立副本先验证 `ActPendingBlockTests` 基线全绿，随后五条单点变异全部变红（exit 1），明细见 [mutations.md](mutations.md)。

## 五、未验证项与复现命令

- **未验证项**：
  - 原型查看器在真实浏览器下的 `PhoneActPending.dc.html` / `PhoneSignedActPending.dc.html` 视觉渲染截图及真机手机浏览器与电脑联调未在本次执行。
  - 本机全量测试中既有的 2 条环境条件跳过用例（`skipped=2`）未在本机覆盖。
- **复现命令**（先清除 `http_proxy` / `HTTP_PROXY` / `https_proxy` / `HTTPS_PROXY` / `all_proxy`）：

```bash
node --check local/ui/m/model.js
node --check local/ui/m/model-conflict.js
node --check local/ui/m/model-list.js
node --check local/ui/m/ui-status.js
python tools/code_shape/check.py
python -m unittest discover -s local/tests -p "test_phone_ui.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_code_shape.py"
python -m unittest discover -s local/tests -p "test_*.py"
```
