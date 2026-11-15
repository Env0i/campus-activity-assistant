# 接线变异重跑与 import、挂回的变异

## 接线变异重跑（35 处绑定）

- 重跑上一批的接线变异：35 处事件绑定（面板 wire 里 29 处、设置页 wireSettings 里
  验证码识别 6 处）的动作行逐处换成空语句，看哪条用例变红。清单与执行器沿用
  `design/evidence/2026-11-14/phone-panel-move/scripts/mutate_wiring.py`
  （`--stage 搬之后`），只在临时目录下的仓库副本里做，仓库本体不动。
- 复跑命令（仓库根）：
  `python -B design/evidence/2026-11-14/phone-panel-move/scripts/mutate_wiring.py --stage 搬之后`
- 对照方式：与上一批搬完后的机器可读结果（上一批结果目录的 wiring-after.json）逐条
  比对编号、结论、变红用例集合、先红用例的第一条失败断言原文。结果：**35/35 逐条
  相同，无一例外**（汇总都是「红在绑定自己的断言 35」）。逐条比对输出在结果目录
  wiring-compare.txt。这 35 处绑定全在本批没动的文件里（actions-panel.js 的 wire、
  settings.js 的 wireSettings），结论不变是预期。

## import 与挂回的变异（五条）

- 做法：每条在临时目录下的仓库副本里删掉指定行（副本按 git ls-files 复制，config.json
  与两个 data 目录不进副本），先 node --check，再逐份跑六份相关测试
  （test_phone_ui、test_ui_component_rows、test_ui_modules、test_reason_maps、
  test_ui_contract_components、test_ui_contract_settings）；未变异时这六份在本仓库全绿。
  执行器 `scripts/mutate_imports.py`，逐条完整输出在结果目录 import-mutations.json。
- 复跑命令（仓库根）：
  `python -B design/evidence/2026-11-15/ocr-panel-move/scripts/mutate_imports.py`

| 编号 | 变异 | 变红的用例 | 不红的文件 |
|---|---|---|---|
| m1-view-ocr-downloadfail | 删 view-ocr.js 引 downloadFailText 的 import | test_ui_modules：test_problem_sections_are_empty（守卫缺 import 一类非空）、test_real_load_ocr_failed_download_paints_the_retry_bar（红条退回兜底文案，见 real-load-output.md） | 其余五份全绿（拼接类测试发现不了缺 import） |
| m2-actions-ocrpanel | 删 components/actions.js 引 OcrPanel 的 import | test_ui_modules：test_problem_sections_are_empty（守卫缺 import 一类非空） | 其余五份全绿：真加载下行为不坏，因为 OcrPanel 经过渡名单挂在 window 上，typeof 兜底仍拿得到——守卫是这一处的防线 |
| m3-view-paintocrdownload | 删 phone-access/view.js 引 paintOcrDownload 的 import | test_ui_modules：test_problem_sections_are_empty；test_phone_ui：11 例（view-ocr.js 退出装配文件的引用图，识别一节不再绘制——test_ocr_install_shows_installing_until_refresh_returns、test_busy_disables_all_mutations_and_a_canceled_pick_is_quiet、test_import_disabled_and_failure_states_are_independent、test_outdated_shows_update_button_instead_of_broken、test_update_failure_reason_stays_visible_in_outdated_state、test_checking_ocr_component_is_not_missing_in_settings_or_login_line、test_enable_calls_the_enable_interface_and_never_opens_the_import_dialog、test_enable_failure_is_said_in_place、test_import_success_closes_the_dialog_and_says_so_in_the_ocr_section、test_missing_is_one_click_and_the_import_link_only_follows_a_failure、test_ocr_feedback_is_in_place_and_location_uses_the_desktop_interface） | 其余四份全绿 |
| m4-attach-ocrpanel | 过渡名单去掉挂回的 OcrPanel（连同 import） | test_ui_modules：test_lists_match_expectation（挂回名单少了 OcrPanel）、test_problem_sections_are_empty（普通脚本引用了没挂回的名字一档非空）、test_real_load_settings_drawer_asks_the_ocr_component_location 与 test_real_load_ocr_enable_says_enabled_in_the_row（真加载下 settings.js 一查 OcrPanel 就是 ReferenceError） | 其余五份全绿 |
| m5-attach-paintocrdownload | 过渡名单去掉挂回的 paintOcrDownload（连同 import） | test_ui_modules：test_lists_match_expectation、test_problem_sections_are_empty、test_real_load_settings_drawer_asks_the_ocr_component_location、test_real_load_ocr_enable_says_enabled_in_the_row、test_real_load_ocr_failed_download_paints_the_retry_bar（真加载下 paintSettings 一调 paintOcrDownload 就是 ReferenceError） | 其余五份全绿 |

- 五条变异里三条删 import 的都证明同一件事：拼接类用例（按夹具清单剥壳拼起来跑）
  对「缺 import」免疫，只有模块图守卫与真加载断言能抓——这正是本批要显式写
  import、并在真加载下补看得见断言的原因。
