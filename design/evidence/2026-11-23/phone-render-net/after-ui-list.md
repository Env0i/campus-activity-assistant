# 手机页渲染组安全网补测第三批：`ui-list.js` 34 条结论对照

- **范围**：针对 `design/evidence/2026-11-23/phone-render-net/before.md` 中 `local/ui/m/ui-list.js` 在前两批后剩余的全部 **34 条**无人守变异（`M085`、`M088`、`M089`、`M090`、`M091`、`M096`、`M097`、`M098`、`M101`、`M104`、`M105`、`M106`、`M107`、`M108`、`M109`、`M110`、`M111`、`M112`、`M113`、`M114`、`M115`、`M116`、`M117`、`M121`、`M124`、`M125`、`M128`、`M130`、`M131`、`M134`、`M140`、`M142`、`M143`、`M144`），分布于 `goSigned`（12 条）、`buildRow`（9 条）、`renderItems`（8 条）、`toggleSearch`（4 条）、`buildWhy`（1 条）。
- **执行方式**：只读复用 `scripts/mutate_render.py`，在 `tempfile.gettempdir()` 下由 `git archive HEAD` 导出并叠加工作区 `local/tests/test_phone_ui.py` 的独立临时副本中先跑 34 条定向复跑，再跑全组 226 条回归复跑（`--workers 4`，配合 `scripts/equiv.json`）。所有显隐用例均先将被断言元素的 `hidden` 设为与预期相反值。产品代码零改动。

## 1. 本批 34 条逐条结论

| 编号 | 类 | 文件 | 函数 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例 |
|---|---|---|---|---|---|---|---|
| M085 | 乙 | `ui-list.js` | `buildRow` | `model.flashId === row.id ?` | `!(model.flashId === row.id) ?` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M088 | 乙 | `ui-list.js` | `buildRow` | `if (row.timeCls)` | `if (!(row.timeCls))` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M089 | 乙 | `ui-list.js` | `buildRow` | `if (row.hasLeft)` | `if (!(row.hasLeft))` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M090 | 乙 | `ui-list.js` | `buildRow` | `if (row.leftCls)` | `if (!(row.leftCls))` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M091 | 乙 | `ui-list.js` | `buildRow` | `f.cls ?` | `!(f.cls) ?` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M096 | 乙 | `ui-list.js` | `buildRow` | `if (row.hasPlace)` | `if (!(row.hasPlace))` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M097 | 乙 | `ui-list.js` | `buildRow` | `if (row.rw && row.rw.text)` | `if (!(row.rw && row.rw.text))` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M098 | 乙 | `ui-list.js` | `buildRow` | `if (row.hasWarn)` | `if (!(row.hasWarn))` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M101 | 乙 | `ui-list.js` | `buildRow` | `if (event && event.preventDefault)` | `if (!(event && event.preventDefault))` | 行为守 | `PhoneRowDomTests.test_clash_row_click_prevents_default_and_go_button_stops_bubbling` |
| M104 | 乙 | `ui-list.js` | `buildWhy` | `if (event && event.stopPropagation)` | `if (!(event && event.stopPropagation))` | 行为守 | `PhoneRowDomTests.test_clash_row_click_prevents_default_and_go_button_stops_bubbling` |
| M105 | 甲 | `ui-list.js` | `goSigned` | `model.whyId = "";` | `void 0;` | 行为守 | `PhoneRowDomTests.test_clash_row_click_prevents_default_and_go_button_stops_bubbling` |
| M106 | 乙 | `ui-list.js` | `goSigned` | `if (!shown)` | `if (!(!shown))` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M107 | 甲 | `ui-list.js` | `goSigned` | `model.filter = { q: "", status: "all", time: "all" };` | `void 0;` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M108 | 乙 | `ui-list.js` | `goSigned` | `if ($("q"))` | `if (!($("q")))` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M109 | 乙 | `ui-list.js` | `goSigned` | `if ($("search-q"))` | `if (!($("search-q")))` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M110 | 乙 | `ui-list.js` | `goSigned` | `b.dataset.status === "all" ?` | `!(b.dataset.status === "all") ?` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M111 | 乙 | `ui-list.js` | `goSigned` | `b.dataset.time === "all" ?` | `!(b.dataset.time === "all") ?` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M112 | 乙 | `ui-list.js` | `goSigned` | `if ($("signed-summary"))` | `if (!($("signed-summary")))` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M113 | 甲 | `ui-list.js` | `goSigned` | `model.flashId = id;` | `void 0;` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M114 | 乙 | `ui-list.js` | `goSigned` | `if (row && row.scrollIntoView)` | `if (!(row && row.scrollIntoView))` | 行为守 | `PhoneRowDomTests.test_clash_row_click_prevents_default_and_go_button_stops_bubbling` |
| M115 | 甲 | `ui-list.js` | `goSigned` | `model.flashId = "";` | `void 0;` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M116 | 乙 | `ui-list.js` | `goSigned` | `if (row && row.classList)` | `if (!(row && row.classList))` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M117 | 甲 | `ui-list.js` | `renderItems` | `model.nowMs = Date.now();` | `void 0;` | 行为守 | `RunWaitDomTests.test_render_items_refreshes_clock_before_offline_board_render` |
| M121 | 乙 | `ui-list.js` | `renderItems` | `group.cls ?` | `!(group.cls) ?` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M124 | 丙 | `ui-list.js` | `renderItems` | `$("search-view").hidden = !showList \|\| !model.searchOpen;` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M125 | 丙 | `ui-list.js` | `renderItems` | `toggle.hidden = !(model.busy \|\| result);` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M128 | 丙 | `ui-list.js` | `renderItems` | `tip.hidden = !showList \|\| !noMatch;` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M130 | 乙 | `ui-list.js` | `renderItems` | `if ($("upcoming-zone"))` | `if (!($("upcoming-zone")))` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M131 | 丙 | `ui-list.js` | `renderItems` | `$("upcoming-zone").hidden = !showList \|\| noMatch;` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M134 | 乙 | `ui-list.js` | `renderItems` | `if (result)` | `if (!(result))` | 行为守 | `ResultTermsDomTests.test_signed_summary_items_populate_only_in_result_state` |
| M140 | 丙 | `ui-list.js` | `toggleSearch` | `$("search-view").hidden = !model.searchOpen;` | `void 0;` | 行为守 | `ListDetailModelTests.test_toggle_search_reveals_box_before_focus_and_clears_queries` |
| M142 | 甲 | `ui-list.js` | `toggleSearch` | `model.filter.q = "";` | `void 0;` | 行为守 | `ListDetailModelTests.test_toggle_search_reveals_box_before_focus_and_clears_queries` |
| M143 | 乙 | `ui-list.js` | `toggleSearch` | `if ($("q"))` | `if (!($("q")))` | 行为守 | `ListDetailModelTests.test_toggle_search_reveals_box_before_focus_and_clears_queries` |
| M144 | 乙 | `ui-list.js` | `toggleSearch` | `if (model.searchOpen && $("search-q").focus)` | `if (!(model.searchOpen && $("search-q").focus))` | 行为守 | `ListDetailModelTests.test_toggle_search_reveals_box_before_focus_and_clears_queries` |

### 本批 34 条分类合计

- 行为守：34（甲类 6、乙类 23、丙类 5）
- 等价：0
- 字面守：0
- 无人守：0
- 无效：0
- 总计：34

## 2. 新增行为用例清单

均写入 `local/tests/test_phone_ui.py` 对应主题测试类，仅断言用户可见结果（`hidden`、`textContent`、`className`、`value`、`open`、`aria-pressed`、滚动与焦点替身行为、看板状态），且显隐断言前均先预设相反的 `hidden` 初值：

| 测试类 / 用例名 | 守的用户可见结果 | 对应变异编号 |
|---|---|---|
| `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` | 待公布行大字写 `txt`、临近倒计时加 `soon`、旗标保留 `flag` 类、地点只现于未截止行、奖励条与重叠行警按状态渲染 | `M088`、`M089`、`M090`、`M091`、`M096`、`M097`、`M098` |
| `PhoneRowDomTests.test_clash_row_click_prevents_default_and_go_button_stops_bubbling` | 点重叠行阻止默认动作且缺 `preventDefault` 不崩；点「去已报名那场」阻止冒泡回行以免原因面板重开 | `M101`、`M104`（亦守 `M105`、`M114`） |
| `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` | 「去已报名那场」收起原因、重置隐藏该行的筛选与状态/时间片、展开已报名汇总、滚动定位、仅高亮目标行并在 2 秒后熄灭 | `M085`、`M105`、`M106`、`M107`、`M108`、`M109`、`M110`、`M111`、`M112`、`M113`、`M114`、`M115`、`M116` |
| `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` | 保留开放组 `.grp.open` 样式，按匹配与忙闲切换 `#upcoming-zone`、`#filter-empty`、`#search-view` 与 `#btn-toggle-list` 显隐 | `M121`、`M124`、`M125`、`M128`、`M130`、`M131` |
| `ListDetailModelTests.test_toggle_search_reveals_box_before_focus_and_clears_queries` | 展开搜索前先解除 `#search-view` 隐藏再让输入框获焦，清空 `#q`/`#search-q` 与列表筛选词，收起时不触发聚焦 | `M140`、`M142`、`M143`、`M144` |
| `ResultTermsDomTests.test_signed_summary_items_populate_only_in_result_state` | `#signed-items` 汇总行只在结果态填充，草稿态不重复填入 | `M134` |
| `RunWaitDomTests.test_render_items_refreshes_clock_before_offline_board_render` | 离线期间重绘列表先刷新 `nowMs`，使运行看板立即切换为离线过时提示与 dim 样式 | `M117` |

## 3. 全组 226 条回归复跑对照

| 统计维度 | 补测前（`before.md`） | 第一批后（`after-ui-sync.md`） | 第二批后（`after-ui-status.md`） | 第三批后（`after.md`） | 本批变化 |
|---|---:|---:|---:|---:|---:|
| 行为守 | 142 | 160 | 186 | 220 | +34 |
| 字面守 | 0 | 0 | 0 | 0 | 0 |
| 无人守 | 84 | 63 | 34 | **0** | -34（全组清零） |
| 无效 | 0 | 0 | 0 | 0 | 0 |
| 等价 | 0 | 3 | 6 | 6 | 0 |
| **总计** | **226** | **226** | **226** | **226** | **0** |

### 前两批后结论核对与按文件/口径分布

- **前两批后结论核对**：补测前 142 条行为守、第一批后 160 条行为守及第二批后 186 条行为守 + 6 条等价判定（`M025`、`M026`、`M027`、`M146`、`M150`、`M208`）全部保持一致，零退化。
- **按文件分布（本次 226 条）**：
  - `ui-sync.js`（82 条）：行为守 79、等价 3、**无人守 0**、字面守 0、无效 0
  - `ui-status.js`（83 条）：行为守 80、等价 3、**无人守 0**、字面守 0、无效 0
  - `ui-list.js`（61 条）：行为守 61、等价 0、**无人守 0**、字面守 0、无效 0
- **按变异口径单列统计（本次 226 条）**：
  - 甲类（`model.字段` 写换 `void 0`，40 条）：行为守 37、无人守 0、等价 3
  - 乙类（条件 `C` 换 `!(C)`，141 条）：行为守 139、无人守 0、等价 2
  - 丙类（`.hidden = X` 显隐写换 `void 0`，45 条）：行为守 44、无人守 0、等价 1

## 4. 复现命令

```bash
python -m unittest discover -s local/tests -p "test_phone_ui.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_code_shape.py"
python design/evidence/2026-11-23/phone-render-net/scripts/mutate_render.py \
  --ids M085,M088,M089,M090,M091,M096,M097,M098,M101,M104,M105,M106,M107,M108,M109,M110,M111,M112,M113,M114,M115,M116,M117,M121,M124,M125,M128,M130,M131,M134,M140,M142,M143,M144 \
  --workers 4 --phase 补测之后 \
  --equiv-json design/evidence/2026-11-23/phone-render-net/scripts/equiv.json
python design/evidence/2026-11-23/phone-render-net/scripts/mutate_render.py \
  --workers 4 --phase 补测之后 \
  --equiv-json design/evidence/2026-11-23/phone-render-net/scripts/equiv.json \
  --out design/evidence/2026-11-23/phone-render-net/after.md
```
