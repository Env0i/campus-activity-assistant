# 使用点变异结论表（补测试之前）

- 基线提交：`dda275e`（行按「文件、函数、那一行的文字」定位，清单在 scripts/mutate_rows.py）
- 执行命令（仓库根，临时目录用占位符）：`python -B design/evidence/2026-11-14/components-net/scripts/mutate_reads.py --phase 补测试之前 --title 使用点变异结论表 --out <表名>.md`
- 测试集合：直接断言这两个视图文件行为或文字的相关测试文件（清单见 README.md），加两个新测试文件
- 结论口径：变红用例里至少一条跑 node 的用例即「行为测试已守」，全是字面断言即「只有字面断言守」，没有用例变红即「没人守」；「等价」与「页面里没有这个元素」由人工复判（mutate_rows.py 的 OVERRIDES）；整页清单一列看变红用例里有没有走整页脚本清单的，有则指名

| 编号 | 一行是什么 | 文件与函数 | 结论 | 有没有走整页清单的用例守着 | 变红的用例名（最多三条） | 先红用例的第一条失败断言 |
|---|---|---|---|---|---|---|
| busy-paint-remove | 面板重画：移除组件按钮禁用（页面里没有这个元素） | views/phone.js paint | 页面里没有这个元素 | 否 | test_phone_ui.HelpAdvancedBehaviorTests.test_busy_disables_all_mutations_and_a_canceled_pick_is_quiet | `self.assertEqual(values, [True, ["", ""]])` → AssertionError: Lists differ: [False, ['', '']] != [True, ['', '']] |
| busy-paintRelogin-manage | 登录恢复：入口按钮（填写账号密码/更换）禁用 | views/phone.js paintRelogin | 行为测试已守 | 是（test_ui_phone_access_rows.PaintBusyReadTests.test_busy_read_in_paint_relogin_disables_the_recovery_buttons） | test_ui_phone_access_rows.PaintBusyReadTests.test_busy_read_in_paint_relogin_disables_the_recovery_buttons | `self.assertTrue(data["manageDisabled"], "忙碌时登录恢复的入口按钮要禁用")` → AssertionError: False is not true : 忙碌时登录恢复的入口按钮要禁用 |
| busy-paintRelogin-clear | 登录恢复：「清除已保存」按钮禁用 | views/phone.js paintRelogin | 行为测试已守 | 是（test_ui_phone_access_rows.PaintBusyReadTests.test_busy_read_in_paint_relogin_disables_the_recovery_buttons） | test_ui_phone_access_rows.PaintBusyReadTests.test_busy_read_in_paint_relogin_disables_the_recovery_buttons | `self.assertTrue(data["clearDisabled"], "忙碌时清除账号按钮要禁用")` → AssertionError: False is not true : 忙碌时清除账号按钮要禁用 |
| pending-startingDef | 手机访问：starting 的来源（pending 与 "starting" 的比较） | views/phone.js paintPhoneAccess | 行为测试已守 | 否 | test_phone_ui.ReloginCardUiTests.test_start_button_locks_and_reports_progress | `self.assertIn("启动中", marks["pending"]["text"])` → AssertionError: '启动中' not found in '开启手机访问' |
| installing-loadingDef | 组件安装：loading 定义里的 installing（安装计入进度态） | views/phone.js paintPhoneAccess | 行为测试已守 | 否 | test_phone_ui.ComponentDownloadUiTests.test_install_shows_installing_until_refresh_returns | `self.assertFalse(during["loadingHidden"], "安装中进度区可见")` → AssertionError: True is not false : 安装中进度区可见 |
| busy-installBtn | 组件安装：标题行「下载并安装」禁用条件里的 busy | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| installing-installBtn | 组件安装：标题行「下载并安装」禁用条件里的 installing | views/phone.js paintPhoneAccess | 行为测试已守 | 否 | test_phone_ui.ComponentDownloadUiTests.test_install_shows_installing_until_refresh_returns | `self.assertTrue(during["installDisabled"], "安装中主按钮禁用")` → AssertionError: False is not true : 安装中主按钮禁用 |
| busy-cancelBtn | 组件安装：标题行「取消下载」禁用条件里的 busy | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| busy-featureBtn | 手机访问：标题行按钮（重新导入/启用/换包）禁用 | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| starting-lead | 手机访问：开启中的 lead 文案 | views/phone.js paintPhoneAccess | 行为测试已守 | 否 | test_phone_ui.ReloginCardUiTests.test_start_button_locks_and_reports_progress | `self.assertEqual(marks["pending"]["lead"], "正在开启，先不要切换通道。")` → AssertionError: '选一条通道再开启。没开启时不监听端口，手机连不上电脑。' != '正在开启，先不要切换通道。' |
| installing-missingShow | 组件安装：「没装」块显示条件里的 !installing | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| loading-loadingShow | 组件安装：进度块显示的 loading | views/phone.js paintPhoneAccess | 行为测试已守 | 是（test_ui_component_rows.InstallingRowTests.test_phone_downloads_while_ocr_installs_rows_do_not_mix） | test_phone_ui.ComponentDownloadUiTests.test_downloading_shows_progress_and_offers_cancel、test_phone_ui.ComponentDownloadUiTests.test_install_shows_installing_until_refresh_returns、test_phone_ui.PhoneAccessStateMachineTests.test_cancel_returns_to_not_installed_and_says_nothing_was_installed | `self.assertFalse(row["loadingHidden"])` → AssertionError: True is not false |
| installing-missingErr | 组件安装：没装红条条件里的 !installing | views/phone.js paintPhoneAccess | 行为测试已守 | 否 | test_phone_ui.ComponentDownloadUiTests.test_install_shows_installing_until_refresh_returns | `self.assertEqual(during["err"], "", "安装中不显示旧的失败红条")` → AssertionError: '下载没有完成：连不上发布页，可以重试。' != '' |
| installing-importLine | 组件安装：导入行显示条件里的 !installing | views/phone.js paintPhoneAccess | 行为测试已守 | 否 | test_phone_ui.ComponentDownloadUiTests.test_install_shows_installing_until_refresh_returns | `self.assertTrue(during["importHidden"], "安装中不显示导入行")` → AssertionError: False is not true : 安装中不显示导入行 |
| loading-locAfter | 组件安装：「装在」行显示条件里的 !loading | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| busy-openLoc | 组件安装：「打开所在文件夹」按钮禁用 | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| installing-progText | 组件安装：进度字「正在安装组件…」的 installing | views/phone.js paintPhoneAccess | 行为测试已守 | 是（test_ui_component_rows.InstallingRowTests.test_each_component_shows_its_own_installing_row） | test_phone_ui.ComponentDownloadUiTests.test_install_shows_installing_until_refresh_returns、test_ui_component_rows.InstallingRowTests.test_each_component_shows_its_own_installing_row | `self.assertEqual(during["progText"], "正在安装组件…")` → AssertionError: '正在下载手机控制组件' != '正在安装组件…' |
| loading-loadingErr | 组件安装：进度区错误行的 loading | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| busy-chanRadio | 手机访问：通道单选禁用条件里的 busy | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| pending-chanRadio | 手机访问：通道单选禁用条件里的 !!pending | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| busy-startBtn | 手机访问：「开启手机访问」禁用条件里的 busy | views/phone.js paintPhoneAccess | 行为测试已守 | 是（test_ui_phone_access_rows.PaintBusyReadTests.test_busy_read_in_paint_phone_access_disables_start） | test_ui_phone_access_rows.PaintBusyReadTests.test_busy_read_in_paint_phone_access_disables_start | `self.assertTrue(data["startDisabled"], "忙碌时开启按钮要禁用")` → AssertionError: False is not true : 忙碌时开启按钮要禁用 |
| pending-startBtn | 手机访问：「开启手机访问」禁用条件里的 !!pending | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| loading-startBtn | 手机访问：「开启手机访问」禁用条件里的 loading | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| starting-startText | 手机访问：「启动中…」按钮文案 | views/phone.js paintPhoneAccess | 行为测试已守 | 否 | test_phone_ui.ReloginCardUiTests.test_start_button_locks_and_reports_progress | `self.assertIn("启动中", marks["pending"]["text"])` → AssertionError: '启动中' not found in '开启手机访问' |
| starting-recheckShow | 手机访问：启动中收起「重新检测」 | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| busy-recheckBtn | 手机访问：「重新检测」按钮禁用 | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| starting-hint | 手机访问：Cloudflare 启动中的提示行 | views/phone.js paintPhoneAccess | 行为测试已守 | 否 | test_phone_ui.ReloginCardUiTests.test_start_button_locks_and_reports_progress | `self.assertEqual(marks["pending"]["hint"], "正在建立临时隧道，最多等 20 秒。")` → AssertionError: '' != '正在建立临时隧道，最多等 20 秒。' |
| busy-copyBtn | 手机访问：「复制」按钮禁用 | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| busy-stopBtn | 手机访问：「关闭手机访问」禁用条件里的 busy | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| pending-stopBtn | 手机访问：「关闭手机访问」禁用条件里的 !!pending | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| pending-stopText | 手机访问：「关闭中…」按钮文案的 pending 比较 | views/phone.js paintPhoneAccess | 行为测试已守 | 否 | test_phone_ui.ReloginCardUiTests.test_stop_button_reports_closing | `self.assertIn("关闭中", marks["pending"]["text"])` → AssertionError: '关闭中' not found in '关闭手机访问' |
| busy-addPairBtn | 手机访问：「再配对一台手机」按钮禁用 | views/phone.js paintPhoneAccess | 没人守 | 否 | （无） | （无） |
| installing-loadingDef-ocr | 验证码识别：loading 定义里的 installing | views/settings.js paintOcrDownload | 行为测试已守 | 是（test_ui_component_rows.InstallingRowTests.test_phone_downloads_while_ocr_installs_rows_do_not_mix） | test_phone_ui.ComponentDownloadUiTests.test_ocr_install_shows_installing_until_refresh_returns、test_ui_component_rows.InstallingRowTests.test_phone_downloads_while_ocr_installs_rows_do_not_mix | `self.assertFalse(during["loadingHidden"], "安装中进度区可见")` → AssertionError: True is not false : 安装中进度区可见 |
| busy-downloadBtn-ocr | 验证码识别：「下载并安装」禁用条件里的 busy | views/settings.js paintOcrDownload | 行为测试已守 | 是（test_ui_component_rows.OcrPanelBusyReadTests.test_ocr_busy_read_disables_the_ocr_buttons） | test_ui_component_rows.OcrPanelBusyReadTests.test_ocr_busy_read_disables_the_ocr_buttons | `self.assertTrue(data["downloadDisabled"], "面板忙碌时下载按钮要禁用")` → AssertionError: False is not true : 面板忙碌时下载按钮要禁用 |
| installing-downloadBtn-ocr | 验证码识别：「下载并安装」禁用条件里的 installing | views/settings.js paintOcrDownload | 行为测试已守 | 否 | test_phone_ui.ComponentDownloadUiTests.test_ocr_install_shows_installing_until_refresh_returns | `self.assertTrue(during["installDisabled"], "安装中主按钮禁用")` → AssertionError: False is not true : 安装中主按钮禁用 |
| busy-enableBtn-ocr | 验证码识别：「启用」按钮禁用 | views/settings.js paintOcrDownload | 行为测试已守 | 是（test_ui_component_rows.OcrPanelBusyReadTests.test_ocr_busy_read_disables_the_ocr_buttons） | test_ui_component_rows.OcrPanelBusyReadTests.test_ocr_busy_read_disables_the_ocr_buttons | `self.assertTrue(data["enableDisabled"], "面板忙碌时启用按钮要禁用")` → AssertionError: False is not true : 面板忙碌时启用按钮要禁用 |
| busy-reimportBtn-ocr | 验证码识别：「重新导入组件包」按钮禁用 | views/settings.js paintOcrDownload | 行为测试已守 | 否 | test_phone_ui.HelpAdvancedBehaviorTests.test_busy_disables_all_mutations_and_a_canceled_pick_is_quiet | `self.assertEqual(values, [True, ["", ""]])` → AssertionError: Lists differ: [False, ['', '']] != [True, ['', '']] |
| busy-cancelBtn-ocr | 验证码识别：「取消下载」禁用条件里的 busy | views/settings.js paintOcrDownload | 没人守 | 否 | （无） | （无） |
| installing-failText-ocr | 验证码识别：失败红条拼句条件里的 !installing | views/settings.js paintOcrDownload | 等价 | 否 | （无） | （无） |
| installing-errLine-ocr | 验证码识别：红条安装中清空的 installing | views/settings.js paintOcrDownload | 没人守 | 否 | （无） | （无） |
| installing-missingShow-ocr | 验证码识别：「没装」块显示条件里的 !installing | views/settings.js paintOcrDownload | 没人守 | 否 | （无） | （无） |
| installing-importLine-ocr | 验证码识别：导入行显示条件里的 !installing | views/settings.js paintOcrDownload | 行为测试已守 | 否 | test_phone_ui.ComponentDownloadUiTests.test_ocr_install_shows_installing_until_refresh_returns | `self.assertTrue(during["importHidden"], "安装中不显示导入行")` → AssertionError: False is not true : 安装中不显示导入行 |
| loading-loadingShow-ocr | 验证码识别：进度块显示的 loading | views/settings.js paintOcrDownload | 行为测试已守 | 是（test_ui_component_rows.InstallingRowTests.test_phone_downloads_while_ocr_installs_rows_do_not_mix） | test_phone_ui.ComponentDownloadUiTests.test_ocr_install_shows_installing_until_refresh_returns、test_phone_ui.OcrAndLoginRecoveryTests.test_checking_ocr_component_is_not_missing_in_settings_or_login_line、test_phone_ui.OcrAndLoginRecoveryTests.test_missing_is_one_click_and_the_import_link_only_follows_a_failure | `self.assertFalse(during["loadingHidden"], "安装中进度区可见")` → AssertionError: True is not false : 安装中进度区可见 |
| installing-progText-ocr | 验证码识别：进度字「正在安装组件…」的 installing | views/settings.js paintOcrDownload | 行为测试已守 | 是（test_ui_component_rows.InstallingRowTests.test_each_component_shows_its_own_installing_row） | test_phone_ui.ComponentDownloadUiTests.test_ocr_install_shows_installing_until_refresh_returns、test_ui_component_rows.InstallingRowTests.test_each_component_shows_its_own_installing_row、test_ui_component_rows.InstallingRowTests.test_phone_downloads_while_ocr_installs_rows_do_not_mix | `self.assertEqual(during["progText"], "正在安装组件…")` → AssertionError: '正在下载验证码识别组件' != '正在安装组件…' |
| loading-locAfter-ocr | 验证码识别：「装在」行显示条件里的 !loading | views/settings.js paintOcrDownload | 没人守 | 否 | （无） | （无） |
| busy-openLoc-ocr | 验证码识别：「打开所在文件夹」按钮禁用 | views/settings.js paintOcrDownload | 没人守 | 否 | （无） | （无） |
| checking-loadingDef-phone | 检查中探针：手机控制 loading 定义里认 checking 的那一项 | views/phone.js paintPhoneAccess | 行为测试已守 | 否 | test_phone_ui.PhoneAccessStateMachineTests.test_checking_component_is_not_missing_and_offers_no_install_or_enable | `self.assertEqual(values[0], {"phase": "checking", "install": True, "featureBtn": True,` → AssertionError: {'pha[75 chars]ing': True, 'loading': True, 'text': '正在检查组件…', 'start': True} != {'pha[75 chars]ing': True, 'loading': False, 'text': '正在检查组件…', 'start': True} |
| checking-loadingDef-ocr | 检查中探针：验证码识别 loading 定义里认 checking 的那一项 | views/settings.js paintOcrDownload | 行为测试已守 | 否 | test_phone_ui.OcrAndLoginRecoveryTests.test_checking_ocr_component_is_not_missing_in_settings_or_login_line | `self.assertEqual(values[0], {"phase": "checking", "btn": True, "missing": True, "loading": False,` → AssertionError: {'pha[53 chars]ng': True, 'text': '正在检查组件…', 'cancel': True, [26 chars]组件。'} != {'pha[53 chars]ng': False, 'text': '正在检查组件…', 'cancel': True,[27 chars]组件。'} |

汇总：没人守 22、行为测试已守 24、等价 1、页面里没有这个元素 1（共 48 行，其中 使用点 46、检查中场景探针 2）

## 与指挥会话量出的 19 处逐处对照

指挥会话按使用点逐个变异量出 19 处「没有任何用例变红」，与本表逐处对上如下；除一处按
人工复判记「等价」外，其余全部是没人守，对得上。

| 指挥会话的定位 | 本表编号 | 补测试之前的结论 |
|---|---|---|
| paintPhoneAccess「下载并安装」禁用条件里的 busy | busy-installBtn | 没人守 |
| paintPhoneAccess「取消下载」禁用条件里的 busy | busy-cancelBtn | 没人守 |
| paintPhoneAccess 标题行按钮的 busy | busy-featureBtn | 没人守 |
| paintPhoneAccess 打开组件位置按钮的 busy | busy-openLoc | 没人守 |
| paintPhoneAccess 通道单选禁用条件里的 busy | busy-chanRadio | 没人守 |
| paintPhoneAccess 通道单选禁用条件里的 pending | pending-chanRadio | 没人守 |
| paintPhoneAccess「开启手机访问」禁用条件里的 pending | pending-startBtn | 没人守 |
| paintPhoneAccess「开启手机访问」禁用条件里的 loading | loading-startBtn | 没人守 |
| paintPhoneAccess 重新检测按钮的 busy | busy-recheckBtn | 没人守 |
| paintPhoneAccess 复制地址按钮的 busy | busy-copyBtn | 没人守 |
| paintPhoneAccess「关闭手机访问」禁用条件里的 busy | busy-stopBtn | 没人守 |
| paintPhoneAccess「关闭手机访问」禁用条件里的 pending | pending-stopBtn | 没人守 |
| paintPhoneAccess「再配对一台手机」按钮的 busy | busy-addPairBtn | 没人守 |
| paintPhoneAccess「没装」块显示条件里的 !installing | installing-missingShow | 没人守 |
| paintOcrDownload「取消下载」禁用条件里的 busy | busy-cancelBtn-ocr | 没人守 |
| paintOcrDownload 失败文案条件里的 !installing | installing-failText-ocr | 等价（理由见下） |
| paintOcrDownload 红条那一行的 installing | installing-errLine-ocr | 没人守 |
| paintOcrDownload「没装」块显示条件里的 !installing | installing-missingShow-ocr | 没人守 |
| paintOcrDownload 打开位置按钮的 busy | busy-openLoc-ocr | 没人守 |

## 等价判定：installing-failText-ocr（失败红条拼句条件里的 !installing）

把 `!installing` 换成 `true` 后，用户看到的每一样东西和发出的请求都不变：

- `failText` 在 paintOcrDownload 里只有两个消费点。一个是红条一行
  `ocrText("#ocr-download-error", installing ? "" : (OcrPanel.error || failText))`——
  installing 为真时整条被 `installing ? ""` 拦成空串，failText 变不变都看不见；
  installing 为假时 `!installing` 本来就是真，换掉不改变表达式的值。
- 另一个是取消句 `!failText`（`#ocr-note` 的「下载已取消，没有装任何东西。」条件）——
  这句要求 `dlState === "cancelled"`，而 failText 非空要求 `failed`（即
  `dlState === "failed"`），两个条件互斥，failText 的差异永远到不了取消句。
- 这一处不发出任何桥接请求。

让它不变的是两行代码：settings.js 的红条一行（`installing ? ""` 兜住）与取消句一行里的
`dlState === "cancelled"` 条件。这一处不需要补用例。

## 页面里没有这个元素：busy-paint-remove

paint 里读出的 busy 唯一喂给 `if (phoneRemove) phoneRemove.disabled = busy`，而
`#btn-phone-feature-remove` 在页面里不存在——变红的是按路径加载的旧测试的桩（桩对任意
选择器自动建元素）。按口径单独记「页面里没有这个元素」，不补用例；这一行删不删由下一
批定。

## 检查中场景探针（两行，不是使用点）

checking-loadingDef-phone 与 checking-loadingDef-ocr 换掉的是两个 loading 定义里认
checking 的那一项，供「检查中」场景验证用，不计入使用点。补测试之前它们的结论是
「行为测试已守」，但整页清单一列是「否」——守它们的只有按路径加载的旧用例，走整页清单
的那条新用例没有断言进度块显示；这正是要修的场景（补测试之后重跑，整页清单应变「是」）。

## 补测试之前的结论数字

使用点 46 处：没人守 22、行为测试已守 22、等价 1、页面里没有这个元素 1（只走字面断言
守的 0 处）。另有检查中场景探针 2 行（行为测试已守，整页清单均为否；两行合计使全表的
行为测试已守为 24）。没人守的 22 处里，
指挥会话量出的 19 处占 18 处、另有等价 1 处，多出的 4 处是启动中收起「重新检测」、手机
控制与验证码识别两处「装在」行随 loading 收起、进度区错误行的 loading——这 22 处全部要
在补测试之后归零。
