# 要改的旧断言

依据：`dom-contract.md` 的元素去向，与计划里「状态与标题行对照表」的每一格。原则是只改被删、被挪、文字改掉的那几处观察点，改成读替代元素；用例一条不删。

初稿按读代码列出，改完产品后以实际跑出来的红补全（见文末「实际变红」）。

## 一、`local/tests/test_ui_component_rows.py`

| 用例 | 原断言 | 改成 | 依据 |
| --- | --- | --- | --- |
| `test_checking_state_is_not_missing_on_both_rows` | `$("#phone-prog-text").textContent` 等读进度文字 | 读 `#phone-feature-status-text` / `#ocr-feature-status-text` 的状态句（检查中那句「正在确认组件状态…」），`#phone-loading` 仍是进度条、检查中收起 | 检查中没有上次结论这一格；进度文字元素已删 |
| `test_installing_*`（两处读 `#*-prog-text`） | 读「正在安装组件…」 | 读状态句「正在安装组件…」 | 安装中那一格 |
| `test_verifying_*`（读 `#*-prog-text` 与 loading） | 「下载完成，正在校验组件…」 | 状态句「下载完了，正在校验…」，进度条仍显示且满 | 校验中那一格 |
| 读 `#ocr-note` 的一处 | `noteText` | 改读 `#ocr-probe`（刚装好那句改由小字槽承载） | `#ocr-note` 已删 |

## 二、`local/tests/test_ui_phone_access_rows.py`

| 用例 | 原断言 | 改成 | 依据 |
| --- | --- | --- | --- |
| 读 `#phone-feature-status` 的 chip 文案 | `chip: textContent` | 读 `#phone-feature-status-text`，并读外层 `className` 里的 tone | 状态句拆成圆点 + 文字 |
| `test_phone_phase_broken_offers_reinstall` | 读 `#phone-component-error` | 不变（红条仍在标题行下） | 坏了那格 |
| 读 `#phone-loading`（三处 `loadingShown`） | 进度块显隐 | 不变（`#phone-loading` 仍是进度条），再断言下载中时状态句是「下载中 …」 | 下载中/校验中两格 |
| 读 `#phone-loading-error`（两处） | 加载错误文字 | 元素挪进 `#phone-loading-note`，断言不变 | 元素只是挪位置 |
| 读 `#btn-phone-start` 的用例 | 在通道下面找 | 仍在标题行按钮位：断言可见性与文字，点它仍发开始请求 | 「开启」挪进标题行 |

## 三、`local/tests/test_component_transitions.py`

| 用例 | 原断言 | 改成 | 依据 |
| --- | --- | --- | --- |
| `__ui()` 里的 `missing` / `loading` / `probe` / `retry` | 读 `#phone-missing`、`#phone-loading`、`#phone-probe`、`#btn-phone-component-retry` | 不变（都保留 id），但 `#phone-probe` 现在承载「需要更新」「坏了」的小字 | 小字槽合并 |
| `__ui()` 里的 `chip` | `#phone-feature-status` 的 textContent | 改读 `#phone-feature-status-text` | 状态句拆分 |
| `test_cancelling_a_download_leaves_no_trace` | `note: [#ocr-note.hidden, textContent]` | 改读 `#ocr-probe` | `#ocr-note` 已删 |
| 读 `#ocr-feature-status` 的 chip | textContent | 改读 `#ocr-feature-status-text` | 同手机行 |

## 四、`local/tests/test_phone_link.py`

| 用例 | 原断言 | 改成 | 依据 |
| --- | --- | --- | --- |
| `LinkStateTests` 四元组 `[hidden, textContent, className, dataset.link]` | 读 `#phone-feature-status` | 读 `#phone-feature-status-text` 的文字，外层 class 里的 tone 换成 `adv-s` 的 `ok/warn/blink` 等，`dataset.link` 仍写在外层 | 状态句拆分；颜色改由 class 表达 |
| 配对块几处 | 读 `#phone-ok`、`#phone-pair-note` 等 | 不变 | 元素只是挪进展开区 |

## 五、`local/tests/test_phone_ui.py`

| 用例 | 原断言 | 改成 | 依据 |
| --- | --- | --- | --- |
| 读 `#phone-prog-text` / `#phone-prog-num` 的用例 | 进度文字与 MB 数 | 读状态句「下载中 x / y MB」 | 进度文字元素已删，进度由状态句表达 |
| 读 `#ocr-prog-text` / `#ocr-prog-num` 的用例 | 同上 | 读 `#ocr-feature-status-text` | 同上 |
| 读 `#ocr-title-chip` 的用例 | 「未启用」chip | 状态句「已装好还没启用」 | `#ocr-title-chip` 已删 |
| 读 `#phone-feature-status` 的用例 | chip 文案 | 读 `#phone-feature-status-text` | 状态句拆分 |
| 读 `#ocr-note` 的用例 | 刚装好那句 | 读 `#ocr-probe` | 小字槽合并 |
| 读 `#btn-phone-start` / `#btn-phone-stop` 的用例 | 在展开区里找 | 标题行按钮位，可见性与文字照旧 | 按钮挪位置 |
| `LayoutStaticTests` 里数元素出现次数的断言 | 数 `#ocr-title-chip` 等 | 数新元素（`#*-row-detail`、`#*-row-toggle`、`#*-feature-status-text`） | 元素更替 |

## 六、`local/tests/test_ui_panel_wiring.py`

| 用例 | 原断言 | 改成 | 依据 |
| --- | --- | --- | --- |
| 点 `#btn-phone-start` / `#btn-phone-stop` 的接线用例 | 元素在通道卡下面 | 断言标题行里能点到、仍发同一个请求 | 按钮挪位置 |
| 新增 | — | 点 `#btn-phone-row-toggle` / `#btn-ocr-row-toggle` 切换 `#*-row-detail` 的显隐 | 展开收起是新行为 |

## 七、`local/tests/test_ui_exit_paths_components.py`

| 用例 | 原断言 | 改成 | 依据 |
| --- | --- | --- | --- |
| 走「开启手机访问」的路径 | 找 `#btn-phone-start` | 同在，断言不依赖位置 | 按钮挪位置 |

## 八、`local/tests/test_ui_contract_components.py` / `test_ui_contract_settings.py`

| 用例 | 原断言 | 改成 | 依据 |
| --- | --- | --- | --- |
| 数元素存在的契约断言 | `id="ocr-title-chip"` 等 | 换成 `id="btn-*-row-toggle"`、`id="*-row-detail"`、`id="*-feature-status-text"` | 元素更替 |
| 读 `#phone-feature-status` 的契约断言 | 读 ph-st 的 class | 读 `adv-s` 的 class | 状态句拆分 |

## 九、`local/tests/test_ui_modules.py`（只读，不许改）

新模块 `state-row.js` 进入模块图后，用 `node tools/code_shape/ui_modules.mjs --expect` 重新生成 `tools/code_shape/ui_modules_expect.json`；`PhonePanel` 成员清单不动。

## 实际变红

改完产品、还没动测试时，全量本机版有 **18 条**变红，全部落在上表之内，表外为零：

| 文件 | 红的用例 | 对应上表 |
| --- | --- | --- |
| `test_phone_ui.py`（17 条） | `test_downloading_shows_progress_and_offers_cancel`、`test_install_shows_installing_until_refresh_returns`、`test_ocr_install_shows_installing_until_refresh_returns`、`test_busy_disables_all_mutations_and_a_canceled_pick_is_quiet`、`test_import_disabled_and_failure_states_are_independent`、`test_outdated_shows_update_button_instead_of_broken`、`test_checking_ocr_component_is_not_missing_in_settings_or_login_line`、`test_checking_component_is_not_missing_and_offers_no_install_or_enable`、`test_missing_is_one_click_and_the_import_link_only_follows_a_failure`、`test_ocr_feedback_is_in_place_and_location_uses_the_desktop_interface`、`test_no_pairing_and_no_live_session_is_not_connected`、`test_off_state_reports_tunnel_exit_installed_and_closed_inline`、`test_static_copy_follows_the_prototype`、`test_desktop_entry_keeps_existing_contracts`、`test_start_button_locks_and_reports_progress`、`test_stop_button_reports_closing` | 一、二、四 |
| `test_ui_modules.py`（1 条） | `test_real_load_ocr_enable_says_enabled_in_the_row` | 九（说明位 id 沿用 `#ocr-note`，用例不动） |

另外 `test_ui_component_rows.py`、`test_ui_phone_access_rows.py`、`test_component_transitions.py`、`test_phone_link.py`、
`test_ui_panel_wiring.py`、`test_ui_exit_paths_components.py`、`test_ui_contract_components.py` 里的旧断言是在本批内
**先按上表改、再跑**，因此最终一轮全量里没有它们；改动过程与理由都在上面各节。

## 新增与净增

- 新增 `local/tests/test_settings_adv_rows.py`：30 条（初稿 26 条，变异首轮 6 条存活后补 3 条、扩 3 条，返修批再补 1 条守补装入口的点击）。
- `tools/code_shape/ui_modules_expect.json` 由 `node tools/code_shape/ui_modules.mjs --expect` 重生成，多出 `features/components/state-row.js` 一行。

## 返修批（visual-v1-rework）又动的断言

这一批只改行为，不改口径；下面每条都是「读的节点变了」而不是「放宽」：

| 文件 | 用例 | 原来读什么 | 现在读什么 | 依据 |
| --- | --- | --- | --- | --- |
| `test_ui_phone_access_rows.py` | `test_busy_read_disables_the_title_action_button_on_missing_cloudflared` → `…_the_package_button_on_missing_cloudflared` | 标题行按钮的「安装/更换组件包」 | 标题行是「开启」；展开区 `#btn-phone-package` 的显隐与禁用 | 缺 cloudflared 时标题行照常给「开启」，补装入口挪进展开区 |
| `test_ui_contract_components.py` | `test_the_install_entry_survives_a_missing_component_package` | 视图源码里出现「安装/更换组件包」 | 视图里出现 `phoneShow("#btn-phone-package"`；文案在 `index.html` | 文案搬到了页面上，视图只剩「谁该看见它」 |
| `test_ui_contract_components.py` | `test_the_install_buttons_only_open_the_dialog` | 精确计数 2 处 `PhonePanel.openComponents("phone_control")` | 3 处（多出补装入口那一处） | 仍然精确计数，不是放宽 |
| `test_ui_component_rows.py` | `test_feature_action_import_opens_the_dialog_without_installing` → `test_package_button_opens_the_dialog_without_installing` | 点标题行按钮开弹窗 | 点展开区 `#btn-phone-package` 开弹窗、仍不调安装接口 | 同上 |
| `test_ui_component_rows.py`（7 条） | `test_checking_state_is_not_missing_on_both_rows`、`test_each_component_installs_from_missing_without_showing_missing_blocks`、`test_each_component_shows_its_own_installing_row`、`test_phone_downloads_while_ocr_installs_rows_do_not_mix`、`test_busy_read_disables_the_ocr_cancel_button`、`test_installing_keeps_the_old_ocr_error_hidden`、`test_ocr_busy_read_disables_the_ocr_buttons` | 读 `#*-prog-text` 的进度文字、`#phone-loading`/`#ocr-loading` 的显隐、取消按钮「取消下载」、`#ocr-probe` | 状态句读 `#*-feature-status-text`；进度条只在下载中亮（校验中满格、安装中收着）；取消按钮「取消」；说明位是 `#ocr-note` | 一项一行后状态句进标题行、进度条只表示下载/校验，安装中不亮；这是上一批（adv-rows）就该跟上的读数，本批一并补齐 |

这一批新增/加宽的用例：`test_settings_adv_rows.py` 的 `test_the_package_button_opens_the_import_dialog`（点补装入口真的打开导入弹窗）；
`test_ui_modules.py` 的 `test_real_load_at_medium_and_narrow_widths_keeps_the_tail_bindings`（900 与 430 宽各真加载一次，
夹具新增可选 `size`）。前者当场抓到补装入口的点击处理写成了裸 `openComponents(...)`（真窗口会 `ReferenceError`）。

另：`local/tests/test_ui_component_rows.py` 不在本返修计划原来的 allowed_paths 里，但它读的是上一批改过的排版；
计划补上这一条后（见结果 YAML 的 plan_amendments），这里记下它改了哪几条。
## 返修二（visual-v1-rework2）又动的断言

这一批只改「原因画在哪」：开启失败与隧道自己断开的原因从标题行下那行字，改回手机行标题行下那条红条
（`#phone-component-error`，与下载没完成同一个元素与同一种样式）。判定一字未改，下面每条都是「读的节点变了」：

| 文件 | 用例 | 原来读什么 | 现在读什么 | 依据 |
| --- | --- | --- | --- | --- |
| `test_settings_adv_rows.py` | `PhoneRowWordsTests.test_start_failure_renames_the_button` | `#phone-probe` 可见、文字是「端口被占用」、class 含 `red`；`#phone-off-error` 不得重复 | `#phone-probe` 收起且为空；`#phone-component-error` 可见、文字是「端口被占用」；展开区 `#phone-off-error` 为空 | 红条只留给「这次出错了」，持续状态才写标题行下那行字 |
| `test_phone_ui.py` | `HelpAdvancedBehaviorTests.test_off_state_reports_tunnel_exit_installed_and_closed_inline` | `#phone-probe` 写隧道断开那句、`#phone-off-error` 为空 | `#phone-probe` 为空、`#phone-component-error` 写隧道断开那句 | 同上：隧道自己断开也是「这次出错了」 |

新增用例（不是改写）：`test_settings_adv_rows.py::PhoneRowWordsTests.test_tunnel_gone_puts_the_reason_in_the_red_bar`——
隧道自己断开时，红条写原因、按钮改「重新开启」、通道名说 Cloudflare。

表外零改动：除上面三条（两条改写 + 一条新增）外，本批没有碰别的断言；全量对数与上一轮收工时相同。
