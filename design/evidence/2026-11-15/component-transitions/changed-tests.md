# 这一批改写的旧断言

计划要求「先列一张表、改完产品以实际红补全」。下表先按改动前的源码把会变红的断言逐条列出来，
产品改完跑全量后按实际结果回填：改名前后的用例名、实际变红的清单、表外为零的结论。

## 表一：改了用户能看到的结果，旧断言必须换口径

| 文件 | 用例（改后） | 原断言 | 新断言 | 依据 |
|---|---|---|---|---|
| local/tests/test_phone_ui.py | `test_cancel_leaves_no_trace_on_the_phone_row`（原 `test_cancelled_state_says_nothing_was_changed`） | `#phone-component-state` 的文字是「下载已取消，没有装任何东西。」且未 hidden | 主按钮可见且仍是「下载并安装」；取消按钮收起；没装块可见；`#phone-probe` 与「重试」都收起；导入行收起；手机面板模块组原文里那句取消句出现 0 次 | 画板第 4 条：取消下载后直接回到「没装」，不留「已取消」；元素连同文字一起删 |
| local/tests/test_phone_ui.py | `test_cancel_returns_to_not_installed_and_says_nothing_was_installed` | 取消后 `#ocr-note` 的文字是那句取消句 | 取消后 `#ocr-note` 为空（收起），其余（没装态、主按钮文字、桥接调用）不变 | 识别行的 `#ocr-note` 只写面板自己的 note，取消句不再由绘制派生 |
| local/tests/test_phone_ui.py | `test_missing_is_one_click_and_the_import_link_only_follows_a_failure` | 末尾断言取消后 `note` 是那句取消句 | 同上：取消后 `note` 为空 | 同上 |
| local/tests/test_phone_ui.py | `OcrAndLoginRecoveryTests.test_static_copy_follows_the_prototype` | 手机面板模块组原文里那句取消句出现 1 次 | 出现 0 次 | 两行都不再写这句 |
| local/tests/test_phone_ui.py | `PhoneAccessStateMachineTests.test_static_copy_follows_the_prototype` | 同上 | 同上 | 同上 |
| local/tests/test_phone_ui.py | `test_checking_component_is_not_missing_and_offers_no_install_or_enable` | 检查中：进度块可见、进度文字是「正在检查组件…」 | 检查中：进度块收起、`#phone-probe` 可见且是「正在确认组件状态…」（`dataset.probe` 为 `waiting`）、`#btn-phone-component-retry` 收起；主按钮、启用、取消、没装块仍收起 | 读状态没有结论时先说一句「正在确认组件状态…」，不再借进度块冒充下载 |
| local/tests/test_phone_ui.py | `test_checking_ocr_component_is_not_missing_in_settings_or_login_line` | 同上（识别行） | 同上：进度块收起、`#ocr-probe` 可见、`#btn-ocr-retry` 收起；登录那句由 status 派生，不变 | 同上 |
| local/tests/test_phone_ui.py | `test_import_disabled_and_failure_states_are_independent` | 坏了时 `#btn-ocr-feature-install` 的文字是「重新导入组件包」 | 观察点换成识别行主按钮，坏了时文字是「重新安装」；该元素已不在页面 | 坏了不再指望本地包，走同一条在线下载（画板第 7 节） |
| local/tests/test_phone_ui.py | `test_busy_disables_all_mutations_and_a_canceled_pick_is_quiet` | 面板忙时 `#btn-ocr-feature-install` 被禁用 | 换成 `#btn-ocr-retry`（忙时禁用） | 按钮换了，守的性质不变：有副作用的按钮在忙时都禁 |
| local/tests/test_phone_ui.py | `test_outdated_shows_update_button_instead_of_broken` | 观察点里有 `$("#btn-ocr-feature-install").hidden` | 去掉这个观察点，改成断言页面里没有 `id="btn-ocr-feature-install"` | 元素删了 |
| local/tests/test_phone_ui.py | `test_desktop_entry_keeps_existing_contracts` | 页面里有 `id="btn-ocr-feature-install"` | 页面里没有它；有 `id="phone-probe"`、`id="btn-phone-component-retry"`、`id="ocr-probe"`、`id="btn-ocr-retry"` | 元素删了，换成读状态那一句与「重试」 |
| local/tests/test_ui_component_rows.py | `test_checking_state_is_not_missing_on_both_rows` | 两行进度块可见、文字都是「正在检查组件…」 | 两行都没显示成没装、进度块都收起、两行读状态说明都是「正在确认组件状态…」（`dataset.probe` 为 `waiting`）、两个「重试」都收起 | 同上 |
| local/tests/test_ui_phone_access_rows.py | `test_phone_phase_broken_offers_reinstall`（原 `..._offers_reimport`） | 坏了时 `#btn-phone-feature-install` 是「重新导入组件包」 | 坏了时主按钮是「重新安装」、可见可点，点它发出 `download_advanced_feature`（手机控制）；红条是「组件文件不完整。重新安装不会动你的账号和设置。」；`#btn-phone-feature-install` 收起；chip 仍是「加载失败」 | 坏了不靠本地包，走在线下载；入口收成一个 |
| local/tests/test_ui_panel_wiring.py | `test_wire_ocr_reinstall_sends_the_ocr_download`（原 `test_wire_ocr_reimport_opens_the_ocr_dialog`） | 点 `#btn-ocr-feature-install` 打开导入弹窗 | 识别行坏了点主按钮发出 `download_advanced_feature`（验证码识别），弹窗不开 | 弹窗入口只剩下载失败后的句内链接 |
| local/tests/test_ui_contract_components.py | `test_component_download_elements_exist` | marker 列表里有 `id="phone-component-state"` | 没有它；有 `id="phone-probe"` 与 `id="btn-phone-component-retry"` | 元素删了，读状态那句是新的 |
| local/tests/test_ui_contract_components.py | `test_component_state_is_announced` | `id="phone-component-state" aria-live="polite"` | `#phone-probe` 带 `role="status"`；读屏断言仍在 `#phone-status` | 同上 |

## 表二：以为会红、实际没红

| 文件 | 用例 | 为什么没红 |
|---|---|---|
| local/tests/test_ui_contract_components.py | `test_the_install_buttons_only_open_the_dialog` | 手机模块组里 `PhonePanel.openComponents("phone_control")` 仍是 2 次（坏了档那处入口不在模块组原文里计），`settings.js` 里 `openComponents("relogin_ocr")` 仍是 1 次（删的是选择器数组里的一项，绑定的函数没变）。用例原样不动 |

## 实际变红清单（产品改完、测试未改时）

`test_component_rows`、`test_ui_phone_access_rows`、`test_ui_panel_wiring`、`test_ui_contract_components`、
`test_phone_ui.py` 共 6 个文件 17 条用例变红，逐条落在表一里，**表外为零**。
另 `test_component_machine.py` 当时全绿（它的断言不依赖这批界面结果）。

## 新加的行为由新用例守

- `local/tests/test_component_transitions.py`（新增，13 条）：画板转移表一行一条用例，两行都适用的两行都断言。
  读状态收起、检查中说明、超时与「重试」、点重试重新计时、读不到、恢复后收起并清起点、坏了的「重新安装」、
  坏了再下载失败、取消不留痕、下载中同时等锁仍能取消。
- `local/tests/test_component_machine.py`（补 3 条）：`probe` 四种取值与下载优先、超时从重试起点算、`ctx.running` 下的状态与 `loading`。
