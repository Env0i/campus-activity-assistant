# 契约测试逐条分类（local/tests/test_ui_contract_components.py 的 15 条）

- **基线提交**：`dda275e`。执行日期：2026-11-14。
- **量法**：逐条读用例断言什么、归入四类——照原型逐字的文案、无障碍名称、页面里有某个元素（含反向：不许有）、源码形状；再写它守的是什么、有没有跑 node 的用例守着同一件事（指名文件、用例名），以及本批为它补了哪一条。
- **跑 node 的用例**：指调用了 `fixtures/ui_harness` 的 `run_js`（整页脚本清单），或同文件里经子进程起 node 的 `run_phone_js`。
- **行为化的边界**：node 沙箱的元素桩对任意选择器自动创建元素，所以「HTML 里有没有这个元素 / 这段文案」在沙箱里证不了；这类条目保留字面断言，不硬凑。样式表不进沙箱，同类。文档同步条目管的是 `docs/` 与 README，也行为化不了。

| # | 用例 | 分类 | 它守的是什么 | 跑 node 的用例守同一件事吗 | 本批补的 |
|---|---|---|---|---|---|
| 1 | test_component_download_elements_exist | 页面里有某个元素 | 组件下载区的五个元素（状态字、进度条、红条、「下载并安装」「取消下载」按钮）在 index.html 里存在 | 无——沙箱桩自动建元素，行为用例证不了 HTML 存在性 | 不补（补不了） |
| 2 | test_component_state_is_announced | 无障碍名称 | 组件状态字 `aria-live="polite"`、结果提示 `role="status"`，读屏能念到 | 无（同上） | 不补（补不了） |
| 3 | test_progress_and_error_have_styles | 源码形状（样式表） | 进度条与红条有样式、组件区不引入渐变、进度条墨色不用蓝 | 无——沙箱不加载样式表 | 不补（补不了） |
| 4 | test_channels_say_long_lived_versus_temporary | 照原型逐字的文案 | 两张通道卡卡名照原型；Cloudflare 卡说明要重新扫码和配对 | 无（卡片结论文案没有行为用例） | `test_ui_phone_access_rows.py` 的 `test_channel_cards_say_long_lived_versus_temporary`：给两通道可用状态，断言卡片状态字与结论文字（地址固定、同一账号、组件里已带好、要重新扫码和配对）；变异验证——把 Cloudflare 文字里的「要重新扫码和配对」删掉，此用例红，第一条失败断言是「临时地址要说代价」 |
| 5 | test_import_fallback_sits_outside_missing_blocks | 源码形状（HTML 顺序） | 导入兜底行不能挂在「没装」块里——更新失败停在 outdated 时整块收着，兜底仍要看得见 | 有：`test_phone_ui.py` 的 `test_update_failure_reason_stays_visible_in_outdated_state`（更新失败后 phone/ocr 导入行都显示）与 `test_outdated_shows_update_button_instead_of_broken`（没失败不引导导入）守同一意图 | 不补（已有） |
| 6 | test_no_path_box_or_raw_binary_picker_for_normal_users | 页面里有某个元素（反向） | 不给普通用户 cloudflared 路径框与裸 exe 选择器 | 无——「不许存在」的行为化做不到 | 不补（补不了） |
| 7 | test_the_dialog_lists_one_row_per_component | 页面里有某个元素＋照原型逐字的文案 | 导入弹窗每个组件一行（路径、选择文件、结论、需要说明）、标题与说明句照原型 | 部分：`test_ui_component_rows.py` 的 `test_dialog_install_button_stays_disabled_until_a_file_passes` 断言弹窗标题随组件变（「导入手机控制组件」）；结构与说明句保留字面 | 不补（行为侧已部分覆盖） |
| 8 | test_nothing_is_installed_before_a_file_passes_the_check | 源码形状 | 安装按钮默认禁用：先选文件、自检通过才可点 | 无 | `test_ui_component_rows.py` 的 `test_dialog_install_button_stays_disabled_until_a_file_passes`：未选文件断言禁用、`inspectComponent` 通过后断言可点＋结论行；变异验证——把 `installEl.disabled = !verified` 换成恒 false，此用例红，第一条失败断言是「没选文件时安装按钮要禁用」 |
| 9 | test_the_install_buttons_only_open_the_dialog | 源码形状（调用计数） | 帮助页与标题行的安装按钮只开导入弹窗，不直接调安装接口 | 有（ocr 侧）：`test_phone_ui.py` 的 `test_missing_is_one_click_and_the_import_link_only_follows_a_failure` 断言导入链接打开的是 `relogin_ocr` 的弹窗 | `test_ui_component_rows.py` 的 `test_feature_action_import_opens_the_dialog_without_installing`（手机控制侧）：缺组件包时点标题行按钮，弹窗打开且安装接口零调用；变异验证——把 `PhonePanel.openComponents("phone_control")` 换成空语句，此用例红，第一条失败断言是「点了要打开导入弹窗」 |
| 10 | test_tailscale_and_bare_cloudflared_are_not_imported_here | 页面里有某个元素（反向）＋源码形状 | 导入弹窗没有 Tailscale 行、没有裸 cloudflared.exe 入口 | 无（反向） | 不补（补不了） |
| 11 | test_docs_point_at_the_component_package_not_the_path | 照原型逐字的文案（文档同步） | 文档不再教用户自备 cloudflared，写清组件包来源、版本与校验口径、两条通道的长期/临时差别 | 无——文档内容行为化不了 | 不补（补不了） |
| 12 | test_ui_copy_matches_the_bundled_binary | 照原型逐字的文案 | 界面文案与实际能力对得上：「组件包」「组件里已带好」 | 部分：`test_channel_cards_say_long_lived_versus_temporary` 断言 Cloudflare 卡文字含「组件里已带好」；HTML 侧的「组件包」字样保留字面 | 已由上条覆盖 |
| 13 | test_hide_choice_says_how_it_comes_back | 照原型逐字的文案 | 「隐藏到后台」交代托盘与手机页两条唤回路、说清什么时候不能隐藏 | 无——HTML 文案行为化不了 | 不补（补不了） |
| 14 | test_the_install_entry_survives_a_missing_component_package | 源码形状 | 通道报缺组件包（cloudflared_missing）时安装入口必须还看得见，不能把用户锁死 | 有：`test_phone_ui.py` 的 `test_missing_cloudflared_keeps_the_install_entry`（run_phone_js 行为用例，守同一意图；手机控制 off 行的变异它变红） | 不补（已有） |
| 15 | test_a_check_event_refreshes_the_desktop_relogin_card | 源码形状 | 重新登录成功走的 check 事件之后，右侧手机访问卡片要重取快照 | 无 | `test_ui_phone_access_rows.py` 的 `test_check_event_refreshes_the_phone_panel`：check 事件到达后面板重发快照请求；变异验证——把 app.js 里 `window.PhonePanel.refresh()` 换成空语句，此用例红，第一条失败断言是「check 事件后面板要重取快照」 |

## 汇总

- 15 条里：行为侧已有用例守着同一意图的 3 条（#5、#9 的 ocr 侧、#14）；本批补出行为用例的 4 条（#4、#8、#9 的手机控制侧、#15）；只能保留字面断言的 8 条（#1、#2、#3、#6、#7 的结构说明句、#10、#11、#13）——原因都是沙箱证不了 HTML/CSS/文档的存在性与文案，或属反向断言。
- 字面保留的条目没有一条的意图能用现有沙箱表达而未表达：凡意图能行为表达的（#4、#5、#8、#9、#14、#15）都已有跑 node 的用例。
- 复跑命令（仓库根）：
  `python -B -m unittest discover -s local/tests -p "test_ui_contract_components.py" -v`
  `python -B -m unittest discover -s local/tests -p "test_ui_phone_access_rows.py" -v`
  `python -B -m unittest discover -s local/tests -p "test_ui_component_rows.py" -v`
