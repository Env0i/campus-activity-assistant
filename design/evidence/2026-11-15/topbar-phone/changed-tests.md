# 要改的旧断言（顶栏手机标识与手机详情卡）

先按读代码列初稿；产品改完以实际跑出来的红补全，表外的用例变红就停下报告。

## 表一：`local/tests/test_phone_link.py`

| 用例 | 原断言 | 新断言 | 依据 |
|---|---|---|---|
| `__view()` 里的观察点 | `badge = [hidden, text, className, dataset.link]`；`cardChip = [text, tone]`；`cardBig`；`pairRows = #phone-pop-rows.textContent` | `badge` 末尾加一项 `#phone-badge-spin.hidden`；`cardChip` 末尾加 `#phone-pop-cap.textContent`；新增 `cardSub = #phone-pop-sub.textContent`、`cardCap`、`cardNote = #phone-pop-note.textContent`、`rows = #phone-pop-rows` 里 dt/dd 的成对文本 | 标识多了转圈这个元素（只在开启中、停止中出现），详情卡多了小标与底部提醒两处（对照 `PopPhone.dc.html`、`PhGoneTop.dc.html`） |
| `test_waiting_says_waiting_in_drawer_badge_and_card` | `badge == [False, "等手机连接", "pill phone-badge", "waiting"]`；`cardChip == ["等手机连接", "warn"]` | `badge == [False, "等手机连接", "pill phone-badge is-warn blink", "waiting", True]`；`cardChip == ["等连接", "warn", "长期地址"]`；`cardSub == "用手机扫码打开页面，再输入配对码"` | 原型 `phTopView` 给「等手机连接」的是 `warn blink`（琥珀点慢闪）；详情卡的小 chip 只写「等连接」，右边小标写「长期地址」（`phoneCard`） |
| `test_connected_says_connected_everywhere` | `badge == [False, "手机已连接", "pill phone-badge is-ok", "connected"]`；`cardChip == ["已连接", "ok"]` | `badge == [False, "手机已连接", "pill phone-badge is-ok", "connected", True]`；`cardChip == ["已连接", "ok", "长期地址"]`；`cardSub == "在手机上能看活动、开始和停止计划"` | 同上；转圈在不忙时为收起 |
| `test_disconnected_shows_how_long_ago_the_phone_left` | `badge == [False, "已断开 · 2 分钟前", "pill phone-badge", "disconnected"]`；`cardChip == ["已断开", ""]` | `badge` 加 `True`；`cardChip == ["已断开", "", "长期地址"]`；`cardSub == "手机一段时间没来访问，不算出错；手机回来会自动变成已连接"` | 原型给「已断开」不加色调档、副句是这句 |
| `test_not_running_hides_the_badge_and_says_not_enabled` | `badge[3] == "off"` | 不变（`hidden` 为真、`data-link` 为 `off`）；补一条断言：`#phone-badge-spin` 收起 | 标识收起时转圈也不该在页面上出现 |
| `test_missing_link_falls_back_to_the_pairing_rule` / `test_unknown_and_off_links_also_fall_back` | 只断言 `chip` | 不变（这两条读的是抽屉 chip，本批不动） | 退回规则与判定一字不改 |

## 表二：`local/tests/test_phone_ui.py`

| 用例 | 原断言 | 新断言 | 依据 |
|---|---|---|---|
| `LayoutStaticTests` 里读 `#phone-badge-text` 的那处 | 只读文字 | 不变 | 本批不动标识文字，只动样式档与 aria |

结论：`test_phone_ui.py` 本批预计零改动；若出现表外变红就停下报告。

## 表三：新增（`local/tests/test_topbar_phone.py`）

一种样子一条：开启中、停止中、等手机连接、已连接、已断开（含秒数为空）、没开收起；详情卡按三种连接状态各一条，Cloudflare 与 Tailscale 各一条，配过对与没配过对各一条；「开启中点标识不开详情卡」一条；`aria-label` 随状态变一条。

## 实际变红（改完产品后回填）

只有 `local/tests/test_phone_link.py` 一个文件变红，正好是表里那几条，没有表外：

- `test_waiting_says_waiting_in_drawer_badge_and_card`、`test_connected_says_connected_everywhere`、
  `test_disconnected_shows_how_long_ago_the_phone_left`、`test_disconnected_without_a_contact_time_says_only_disconnected`、
  `test_phone_comes_back_and_the_words_return`、`test_not_running_hides_the_badge_and_says_not_enabled`：
  `__view()` 的观察点少一项（转圈）与详情卡三处（小标、副句、底部提醒），补上后按新样子断言。
- `test_unknown_and_off_links_also_fall_back`：`cardChip` 多了小标一项。
- `test_pairing_blocks_do_not_follow_the_link`：详情卡原来只有一行「配对」，
  现在配对行写「1 台手机」并多出「手机最近访问」，于是这条改成「除最近访问那一行外一字不变」，
  那不是放宽——配对事实与连接事实原本就要分开，只是以前卡片里没有第二行可看。

`test_phone_ui.py` 一条没红（表二的判断成立），表外为零。

## 顺手改到的读法

- `__rows()` 改成读 `#phone-pop-rows` 的 innerHTML 再断言 `<dt>…</dt><dd>…</dd>`：
  沙箱的 DOM 桩没有 querySelectorAll，行是 `cardRows()` 拼出来的串。
- 详情卡的「手机最近访问」在已连接时也写得出「12 秒前」，所以 `state-link.js` 的 `withAgo()`
  要把 `ago`（多久以前）单独带出来，不能只拼在标题后面。
