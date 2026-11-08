# L8 无障碍名称静态审计正式报告（2026-11-08）

**对象**：`local/ui/index.html`（桌面，正式窗口 WebView2，断行以 Edge 为准）与 `local/ui/m/index.html`（手机页）
**日期**：2026-11-08　**基准**：WCAG 2.2 AA，本表聚焦 4.1.2 名称、角色、值（可访问名称计算按 accname 优先级）
**素材**：`<过程留证>/l8-a11y.md`（逐个判定）、`<过程留证>/l8-raw.txt`（脚本输出原文逐字保留）
**方法**：Python 3.12 html.parser 纯静态解析；`python -I` 隔离运行、输入文件以参数传入、解释器不在仓库目录内启动。脚本：<过程留证>/l8_audit.py
**性质**：正式收录版。素材三张表（129 + 30 + 11）全量搬运、逐行无增删；分母与汇总数字经 grep 与独立解析脚本双向交叉复核（见文末「抽查复核」）。全部判定**【已复现】**。

## 判定口径

- button 名称来源优先级：aria-labelledby（目标 id 存在且带文本）> aria-label > 文本内容 > title > 无。
- input/select/textarea 名称来源优先级：aria-labelledby > aria-label > label[for] > label 包裹 > placeholder > title > 无；**placeholder 一律不算合格名称**，仅作备注区分。
- type 缺省：button 缺 type 视为 submit（本批 0 例，无需标注）；input 缺 type 视作 text 并标注「type缺省→text」；select 元素本就没有 type 属性，不标缺省。
- hidden：元素自身带 hidden 属性或任一祖先带 hidden 属性（静态不可见）均计入分母，逐行标注「自身 / 祖先」。
- 对话框口径：原生 `<dialog>` 元素 + 显式 role="dialog"/"alertdialog" 的容器。按此口径得 11 个，与任务书分母一致；任务书备选口径「id 以 dlg- 开头的容器」经核对与实际结构重合（dlg-* 容器全部是原生 dialog），m/index.html 无对话框。
- 全部判定基于静态 HTML；JS 运行时改名/填充（如 #tour-title、#btn-login-text、日志按钮文案）不在静态范围，涉及处单独标注。

## 分母复算（脚本输出 + grep 交叉验证）

- button：129 = 110（index.html）+ 19（m/index.html）——与任务书 129 = 110 + 19 **对上**
- input/select/textarea：30 = 22（index.html）+ 8（m/index.html）——与任务书 30 **对上**（两文件均无 textarea）
- 对话框：11 = 11（index.html）+ 0（m/index.html）——与任务书 11 **对上**（5 个原生 dialog + 6 个 role="dialog" 容器；role="alertdialog" 为 0）
- 差额解释：无差额。静态 HTML 与任务书分母完全一致，不存在需要用「JS 动态创建的按钮」解释的缺口；JS 动态创建的控件不列入静态审计。

## 表1 button（共 129）

| 序号 | 文件 | 行号 | id | 可见文本 | 名称来源 | type | form内 | hidden |
|---|---|---|---|---|---|---|---|---|
| 1 | index.html | 20 | clock | 北京时间--:--:-- | aria-label | button | 否 | - |
| 2 | index.html | 21 | pill | 登录状态未知 | aria-label | button | 否 | - |
| 3 | index.html | 22 | phone-badge | 手机 | aria-label | button | 否 | 自身 |
| 4 | index.html | 26 | btn-refresh | 刷新 | 文本内容 | button | 否 | - |
| 5 | index.html | 27 | btn-settings | 设置 | aria-label | button | 否 | - |
| 6 | index.html | 28 | btn-help | 帮助 | aria-label | button | 否 | - |
| 7 | index.html | 37 |  | 可报名 | 文本内容 | button | 否 | - |
| 8 | index.html | 37 |  | 已报名 | 文本内容 | button | 否 | - |
| 9 | index.html | 37 |  | 全部 | 文本内容 | button | 否 | - |
| 10 | index.html | 47 | empty-action | 刷新 | 文本内容 | button | 否 | 自身+祖先 |
| 11 | index.html | 52 | btn-clear-plan | 清空 | 文本内容 | button | 否 | - |
| 12 | index.html | 52 | btn-plan-back | 返回列表 | 文本内容 | button | 否 | 自身 |
| 13 | index.html | 67 | btn-board-pick | 选这一场 | 文本内容 | button | 否 | 自身 |
| 14 | index.html | 68 | btn-policy | 修改 | 文本内容 | button | 否 | - |
| 15 | index.html | 85 | btn-plan | 开始报名计划 | 文本内容 | button | 否 | - |
| 16 | index.html | 87 | btn-edit-restore | 放弃修改，按原计划继续 | 文本内容 | button | 否 | 自身 |
| 17 | index.html | 89 | btn-reselect | 重新选择未成功的场次 | 文本内容 | button | 否 | 祖先 |
| 18 | index.html | 89 | btn-finish | 完成，回到活动列表 | 文本内容 | button | 否 | 祖先 |
| 19 | index.html | 90 | btn-modify | 修改计划 | 文本内容 | button | 否 | 祖先 |
| 20 | index.html | 90 | btn-stop | 停止计划 | 文本内容 | button | 否 | 祖先 |
| 21 | index.html | 94 | btn-stop-keep | 继续计划 | 文本内容 | button | 否 | 祖先 |
| 22 | index.html | 94 | btn-stop-yes | 停止计划 | 文本内容 | button | 否 | 祖先 |
| 23 | index.html | 99 | btn-dock-open | 查看计划 | 文本内容 | button | 否 | 祖先 |
| 24 | index.html | 99 | btn-dock-start | 开始 | 文本内容 | button | 否 | 自身+祖先 |
| 25 | index.html | 102 | btn-log-copy | 复制 | 文本内容 | button | 否 | - |
| 26 | index.html | 102 | btn-log-clear | 清空 | 文本内容 | button | 否 | - |
| 27 | index.html | 102 | btn-log-folder | 打开数据目录 | 文本内容 | button | 否 | - |
| 28 | index.html | 102 | btn-log-toggle | 展开 | 文本内容 | button | 否 | - |
| 29 | index.html | 112 |  | (空) | aria-label | submit | 是 | - |
| 30 | index.html | 117 | btn-terms-recheck | 重新确认状态 | 文本内容 | button | 否 | 自身 |
| 31 | index.html | 119 |  | 《用户协议》 | 文本内容 | button | 否 | - |
| 32 | index.html | 119 |  | 《隐私政策》 | 文本内容 | button | 否 | - |
| 33 | index.html | 127 | btn-terms-full | 查看完整条款 | 文本内容 | button | 否 | - |
| 34 | index.html | 141 | tab-terms-agreement | 用户协议 | 文本内容 | button | 否 | 祖先 |
| 35 | index.html | 141 | tab-terms-privacy | 隐私政策 | 文本内容 | button | 否 | 祖先 |
| 36 | index.html | 141 | tab-terms-license | MIT 许可证 | 文本内容 | button | 否 | 祖先 |
| 37 | index.html | 146 |  | 随包 LICENSE | 文本内容 | button | 否 | 祖先 |
| 38 | index.html | 174 | btn-license-retry | 重新读取 | 文本内容 | button | 否 | 自身+祖先 |
| 39 | index.html | 185 |  | 《用户协议》 | 文本内容 | button | 否 | - |
| 40 | index.html | 185 |  | 《隐私政策》 | 文本内容 | button | 否 | - |
| 41 | index.html | 185 | btn-terms-close | 关闭 | 文本内容 | button | 否 | 自身 |
| 42 | index.html | 185 | btn-terms-decline | 暂不使用 | 文本内容 | button | 否 | - |
| 43 | index.html | 185 | btn-terms-accept | 我已阅读并同意 | 文本内容 | button | 否 | - |
| 44 | index.html | 191 |  | (空) | aria-label | submit | 是 | - |
| 45 | index.html | 203 | btn-help-tour | 重看引导 | 文本内容 | button | 否 | - |
| 46 | index.html | 203 |  | 知道了 | 文本内容 | submit | 是 | - |
| 47 | index.html | 208 | btn-settings-close | (空) | aria-label | button | 否 | 祖先 |
| 48 | index.html | 209 |  | 高级功能 | 文本内容 | button | 否 | 祖先 |
| 49 | index.html | 209 |  | 登录 | 文本内容 | button | 否 | 祖先 |
| 50 | index.html | 209 |  | 程序 | 文本内容 | button | 否 | 祖先 |
| 51 | index.html | 216 | btn-phone-feature-install | 启用手机控制 | 文本内容 | button | 否 | 自身+祖先 |
| 52 | index.html | 216 | btn-phone-component-install | 下载并安装 | 文本内容 | button | 否 | 祖先 |
| 53 | index.html | 216 | btn-phone-component-cancel | 取消下载 | 文本内容 | button | 否 | 自身+祖先 |
| 54 | index.html | 224 | btn-phone-import | 导入已下载的组件包 | 文本内容 | button | 否 | 祖先 |
| 55 | index.html | 239 | btn-phone-start | 开启手机访问 | 文本内容 | button | 否 | 祖先 |
| 56 | index.html | 239 | btn-tailscale-recheck | 重新检测 | 文本内容 | button | 否 | 自身+祖先 |
| 57 | index.html | 244 | btn-phone-cred-go | 去保存 | 文本内容 | button | 否 | 祖先 |
| 58 | index.html | 252 | btn-phone-address-copy | 复制 | 文本内容 | button | 否 | 祖先 |
| 59 | index.html | 255 | btn-phone-stop-cancel | 先不关闭 | 文本内容 | button | 否 | 祖先 |
| 60 | index.html | 255 | btn-phone-stop-confirm | 确认关闭 | 文本内容 | button | 否 | 祖先 |
| 61 | index.html | 256 | btn-phone-stop | 关闭手机访问 | 文本内容 | button | 否 | 祖先 |
| 62 | index.html | 256 | btn-phone-add-pair | 再配对一台手机 | 文本内容 | button | 否 | 自身+祖先 |
| 63 | index.html | 259 | btn-phone-open-loc | 打开所在文件夹 | 文本内容 | button | 否 | 祖先 |
| 64 | index.html | 265 | btn-ocr-download | 下载并安装 | 文本内容 | button | 否 | 祖先 |
| 65 | index.html | 265 | btn-ocr-enable | 启用 | 文本内容 | button | 否 | 自身+祖先 |
| 66 | index.html | 265 | btn-ocr-feature-install | 重新导入组件包 | 文本内容 | button | 否 | 自身+祖先 |
| 67 | index.html | 265 | btn-ocr-cancel | 取消下载 | 文本内容 | button | 否 | 自身+祖先 |
| 68 | index.html | 271 | btn-ocr-import | 导入已下载的组件包 | 文本内容 | button | 否 | 祖先 |
| 69 | index.html | 278 | btn-ocr-open-loc | 打开所在文件夹 | 文本内容 | button | 否 | 祖先 |
| 70 | index.html | 285 | btn-credentials-manage | 填写账号密码 | 文本内容 | button | 否 | 祖先 |
| 71 | index.html | 297 | btn-credentials-save | 保存到本机 | 文本内容 | button | 否 | 祖先 |
| 72 | index.html | 297 | btn-credentials-cancel | 取消 | 文本内容 | button | 否 | 祖先 |
| 73 | index.html | 299 | btn-relogin-clear-cancel | 先不清除 | 文本内容 | button | 否 | 祖先 |
| 74 | index.html | 299 | btn-relogin-clear-confirm | 确认清除 | 文本内容 | button | 否 | 祖先 |
| 75 | index.html | 300 | btn-credentials-clear | 清除已保存 | 文本内容 | button | 否 | 祖先 |
| 76 | index.html | 312 | btn-update-install | 下载并安装 | 文本内容 | button | 否 | 自身+祖先 |
| 77 | index.html | 312 | btn-update-confirm | 确认下载 | 文本内容 | button | 否 | 自身+祖先 |
| 78 | index.html | 312 | btn-update-launch | 启动安装程序 | 文本内容 | button | 否 | 自身+祖先 |
| 79 | index.html | 312 | btn-update-cancel | 取消 | 文本内容 | button | 否 | 自身+祖先 |
| 80 | index.html | 312 | btn-update-close | 关闭本工具… | 文本内容 | button | 否 | 自身+祖先 |
| 81 | index.html | 312 | btn-update-check | 检查更新 | 文本内容 | button | 否 | 祖先 |
| 82 | index.html | 312 | btn-help-latest | 前往下载页 | 文本内容 | button | 否 | 祖先 |
| 83 | index.html | 316 | btn-help-data | 打开数据目录 | 文本内容 | button | 否 | 祖先 |
| 84 | index.html | 320 | btn-help-terms | 查看条款 | 文本内容 | button | 否 | 祖先 |
| 85 | index.html | 320 | btn-terms-withdraw | 撤回同意 | 文本内容 | button | 否 | 祖先 |
| 86 | index.html | 326 | btn-terms-withdraw-cancel | 先不撤回 | 文本内容 | button | 否 | 祖先 |
| 87 | index.html | 326 | btn-terms-withdraw-confirm | 确认撤回 | 文本内容 | button | 否 | 祖先 |
| 88 | index.html | 341 | tour-skip | 跳过引导 | 文本内容 | button | 否 | 祖先 |
| 89 | index.html | 343 | tour-prev | 上一步 | 文本内容 | button | 否 | 祖先 |
| 90 | index.html | 344 | tour-next | 下一步 | 文本内容 | button | 否 | 祖先 |
| 91 | index.html | 355 | btn-login-check | 检查登录 | 文本内容 | button | 否 | 祖先 |
| 92 | index.html | 355 | btn-login | 登录 | 文本内容 | button | 否 | 祖先 |
| 93 | index.html | 361 | btn-phone-manage | 管理手机访问 | 文本内容 | button | 否 | 祖先 |
| 94 | index.html | 365 | btn-rl-close | (空) | aria-label | button | 否 | - |
| 95 | index.html | 370 | btn-rl-auto | 自动登录一次 | 文本内容 | button | 否 | 祖先 |
| 96 | index.html | 379 | btn-rl-form | 登录 | 文本内容 | button | 否 | 祖先 |
| 97 | index.html | 388 | btn-rl-code | 提交验证码 | 文本内容 | button | 否 | 祖先 |
| 98 | index.html | 391 | btn-rl-done | 知道了 | 文本内容 | button | 否 | 祖先 |
| 99 | index.html | 393 | btn-rl-browser | 改用浏览器登录 | 文本内容 | button | 否 | - |
| 100 | index.html | 404 | btn-close-exit-back | 返回 | 文本内容 | button | 否 | 祖先 |
| 101 | index.html | 404 | btn-close-exit-confirm | 仍然退出 | 文本内容 | button | 否 | 祖先 |
| 102 | index.html | 407 | btn-close-hide | 隐藏到后台运行 窗口收起来，电脑继续推送、手机照常可用、报名计划不停… | 文本内容 | button | 否 | - |
| 103 | index.html | 412 | btn-close-minimize | 最小化到任务栏 推荐 只是把窗口缩下去，任务栏还留着按钮，点一下就回… | 文本内容 | button | 否 | - |
| 104 | index.html | 416 | btn-close-exit | 直接退出 手机访问和报名计划都会立刻停止，未完成的计划不会自己继续。 | 文本内容 | button | 否 | - |
| 105 | index.html | 423 | btn-close-cancel | 先不关 | 文本内容 | button | 否 | - |
| 106 | index.html | 438 | btn-comp-phone-pick | 选择文件… | 文本内容 | button | 否 | 祖先 |
| 107 | index.html | 446 | btn-comp-ocr-pick | 选择文件… | 文本内容 | button | 否 | - |
| 108 | index.html | 454 | btn-comp-close | 取消 | 文本内容 | button | 否 | - |
| 109 | index.html | 455 | btn-comp-phone-install | 安装这份 | 文本内容 | button | 否 | 自身 |
| 110 | index.html | 456 | btn-comp-ocr-install | 安装这份 | 文本内容 | button | 否 | - |
| 111 | m/index.html | 26 | btn-pair | 配对 | 文本内容 | button | 否 | - |
| 112 | m/index.html | 37 | btn-refresh | 刷新 | 文本内容 | button | 否 | 祖先 |
| 113 | m/index.html | 50 | btn-start | 开始报名计划 | 文本内容 | button | 否 | 祖先 |
| 114 | m/index.html | 51 | btn-stop | 停止计划 | 文本内容 | button | 否 | 自身+祖先 |
| 115 | m/index.html | 55 | btn-cancel-start | 取消等待 | 文本内容 | button | 否 | 自身+祖先 |
| 116 | m/index.html | 56 | btn-cancel-task | 取消这一场 | 文本内容 | button | 否 | 自身+祖先 |
| 117 | m/index.html | 80 |  | 全部 | 文本内容 | button | 否 | 祖先 |
| 118 | m/index.html | 81 |  | 可报名 | 文本内容 | button | 否 | 祖先 |
| 119 | m/index.html | 82 |  | 已报名 | 文本内容 | button | 否 | 祖先 |
| 120 | m/index.html | 85 |  | 不限 | 文本内容 | button | 否 | 祖先 |
| 121 | m/index.html | 86 |  | 今天 | 文本内容 | button | 否 | 祖先 |
| 122 | m/index.html | 87 |  | 7 天内 | 文本内容 | button | 否 | 祖先 |
| 123 | m/index.html | 108 | btn-show-window | 显示电脑窗口 | 文本内容 | button | 否 | 祖先 |
| 124 | m/index.html | 122 | btn-relogin-submit | 提交验证码 | 文本内容 | button | 否 | 自身+祖先 |
| 125 | m/index.html | 123 | btn-relogin-refresh | 换一张图 | 文本内容 | button | 否 | 自身+祖先 |
| 126 | m/index.html | 124 | btn-relogin-cancel | 取消 | 文本内容 | button | 否 | 自身+祖先 |
| 127 | m/index.html | 136 | btn-relogin | 重新登录 | 文本内容 | button | 否 | 祖先 |
| 128 | m/index.html | 147 | btn-review-start | 开始报名计划 | 文本内容 | button | 否 | 祖先 |
| 129 | m/index.html | 148 | btn-review-back | 返回 | 文本内容 | button | 否 | 祖先 |

## 表2 input/select/textarea（共 30）

| 序号 | 文件 | 行号 | id | 元素[type] | 名称来源 | 备注 |
|---|---|---|---|---|---|---|
| 1 | index.html | 36 | q | input[type=search] | aria-label | placeholder="搜活动名或地点" |
| 2 | index.html | 38 | time | select | aria-label | - |
| 3 | index.html | 39 | sort | select | aria-label | - |
| 4 | index.html | 40 | checkin | select | aria-label | - |
| 5 | index.html | 41 | checkout | select | aria-label | - |
| 6 | index.html | 71 | retry-for | select | aria-label | hidden(祖先)；label@71 for=retry-for「尝试时长2 分钟10 分钟3…」 |
| 7 | index.html | 72 | max-attempts | input[type=number] | aria-label | hidden(祖先)；label@72 for=max-attempts「最多提交次数（0=不限）」 |
| 8 | index.html | 73 | headed | input[type=checkbox] | label[for] | hidden(祖先)；label@73 for=headed「改用页面点击时显示浏览器」 |
| 9 | index.html | 185 | chk-terms-agree | input[type=checkbox] | label[for] | label@185 for=chk-terms-agree「我已阅读并同意《用户协议》与…」 |
| 10 | index.html | 236 | phone-chan-tailscale | input[type=radio] | label包裹 | hidden(祖先) |
| 11 | index.html | 237 | phone-chan-cloudflare | input[type=radio] | label包裹 | hidden(祖先) |
| 12 | index.html | 293 | credential-user | input[type=text] | aria-label | hidden(祖先) |
| 13 | index.html | 294 | credential-pass | input[type=password] | aria-label | hidden(祖先) |
| 14 | index.html | 295 | credential-once | input[type=checkbox] | label包裹 | hidden(祖先) |
| 15 | index.html | 308 | close-pref | select | aria-label | hidden(祖先) |
| 16 | index.html | 374 | rl-user | input[type=text] | label包裹 | hidden(祖先) |
| 17 | index.html | 375 | rl-pass | input[type=password] | label包裹 | hidden(祖先) |
| 18 | index.html | 376 | rl-save | input[type=checkbox] | label包裹 | hidden(祖先) |
| 19 | index.html | 385 | rl-code | input[type=text] | label包裹 | hidden(祖先) |
| 20 | index.html | 421 | dlg-close-remember | input[type=checkbox] | label包裹 | - |
| 21 | index.html | 437 | comp-phone-path | input[type=text] | aria-label | hidden(祖先)；placeholder="还没有选择文件" |
| 22 | index.html | 445 | comp-ocr-path | input[type=text] | aria-label | placeholder="还没有选择文件" |
| 23 | m/index.html | 24 | pair-code | input[type缺省→text] | aria-label | placeholder="6 位数字" |
| 24 | m/index.html | 78 | q | input[type=search] | aria-label | hidden(祖先)；placeholder="搜活动名或地点" |
| 25 | m/index.html | 94 | retry-for | select | aria-label | hidden(祖先) |
| 26 | m/index.html | 97 | max-attempts | input[type=number] | aria-label | hidden(祖先) |
| 27 | m/index.html | 119 | code | input[type缺省→text] | aria-label | hidden(祖先)；placeholder="4 位字母数字" |
| 28 | m/index.html | 130 | relogin-user | input[type缺省→text] | aria-label | hidden(祖先) |
| 29 | m/index.html | 131 | relogin-pass | input[type=password] | aria-label | hidden(祖先) |
| 30 | m/index.html | 132 | relogin-save | input[type=checkbox] | label包裹 | hidden(祖先) |

## 表3 对话框（共 11）

| 序号 | 文件 | 行号 | 元素 | aria-modal | aria-labelledby | 目标id有效性 | 其他名称来源 | hidden |
|---|---|---|---|---|---|---|---|---|
| 1 | index.html | 94 | div#plan-stop-ask[role=dialog] | 有,值=true | plan-stop-title | 有效: 行94 h2「停止报名计划？」 | - | 自身 |
| 2 | index.html | 109 | dialog#dlg-terms | 无 | dlg-terms-title | 有效: 行111 h2「使用条款与隐私告知」 | 原生dialog(showModal隐式modal) | - |
| 3 | index.html | 188 | dialog#help | 无 | help-title | 有效: 行190 h2「使用帮助」 | 原生dialog(showModal隐式modal) | - |
| 4 | index.html | 207 | aside#settings[role=dialog] | 有,值=false | settings-title | 有效: 行208 h2「设置」 | - | 自身 |
| 5 | index.html | 336 | div#tour-card[role=dialog] | 有,值=true | tour-title | 存在但静态文本为空(行338 h3,JS填充) | - | 祖先 |
| 6 | index.html | 349 | div#clock-pop[role=dialog] | 无 | 无 | - | aria-label="北京时间详情" | 自身 |
| 7 | index.html | 351 | div#login-pop[role=dialog] | 无 | 无 | - | aria-label="登录详情" | 自身 |
| 8 | index.html | 358 | div#phone-pop[role=dialog] | 无 | 无 | - | aria-label="手机访问详情" | 自身 |
| 9 | index.html | 364 | dialog#dlg-relogin | 无 | dlg-relogin-title | 有效: 行365 h2「重新登录」 | 原生dialog(showModal隐式modal) | - |
| 10 | index.html | 396 | dialog#dlg-close | 无 | dlg-close-title | 有效: 行398 h2「要关闭这个窗口吗？」 | 原生dialog(showModal隐式modal) | - |
| 11 | index.html | 429 | dialog#dlg-components | 无 | dlg-components-title | 有效: 行431 h2「导入验证码识别组件」 | 原生dialog(showModal隐式modal) | - |

## 汇总（问题计数）【已复现】

- **无可访问名称的 button：0 / 129**（129 个全部有名称：aria-label 9 个、文本内容 120 个；依赖 title 兜底的 0 个；aria-labelledby 的 0 个）
- **缺 type 属性的 button：0 / 129**；type=submit 共 3 个（行 112、191、203 的 dlg-x 与「知道了」），全部位于 `<form method="dialog">` 内，属对话框关闭/确认的正确用法；其余 126 个均为显式 type="button"
- **缺有效名称的输入：0 / 30**（名称来源：aria-label 19、label[for] 2、label 包裹 9；placeholder 出现 6 处，全部只是与 aria-label 并存的补充提示，无一例仅靠 placeholder 撑名称）
- **对话框：缺 aria-modal 属性 8 / 11** = 5 个原生 `<dialog>`（dlg-terms、help、dlg-relogin、dlg-close、dlg-components；经 showModal() 打开时 UA 隐式 modal，缺失不构成 WCAG 违规）+ 3 个 role="dialog" 非模态弹层（#clock-pop、#login-pop、#phone-pop，建议补 aria-modal="false"）；另有 1 个 #settings 显式 aria-modal="false"（非模态抽屉的正确语义，不在「缺」之列）；aria-modal="true" 2 个（#plan-stop-ask、#tour-card）；**aria-labelledby 无效 1 个**（#tour-card 指向静态空元素，见问题清单 P1）
- **hidden 标注**（自身或祖先带 hidden，静态不可见但全部计入分母并逐行标注）：button 93/129、输入 21/30、对话框 6/11

## 问题清单（文件:行号 + 当前属性）

1. **index.html:336 `div#tour-card`** — role="dialog" aria-modal="true" aria-labelledby="tour-title" tabindex="-1"（祖先 #tour hidden）。aria-labelledby 指向行 338 `h3#tour-title`：id 存在但静态文本为空（JS 填充），静态判为**无效名称目标**。若运行时先开弹窗后填标题，读屏只念「对话框」无名称（WCAG 4.1.2）。修法：先填 #tour-title 再显示，或给 h3 预置第一步标题。
2. **index.html:349 `div#clock-pop`** — role="dialog" aria-label="北京时间详情" hidden。无 aria-modal、无 aria-labelledby；名称本身有效。非模态弹层建议显式补 aria-modal="false"。
3. **index.html:351 `div#login-pop`** — role="dialog" aria-label="登录详情" hidden。无 aria-modal、无 aria-labelledby；同上。
4. **index.html:358 `div#phone-pop`** — role="dialog" aria-label="手机访问详情" hidden。无 aria-modal、无 aria-labelledby；同上。
5. **index.html:207 `aside#settings`** — role="dialog" aria-modal="false" aria-labelledby="settings-title" hidden。名称链有效；aria-modal=false 是非模态抽屉的正确语义（非缺陷），但 role=dialog 且非模态的焦点边界行为需动态核验（超出静态审计范围）。
6. **index.html:109 `dialog#dlg-terms`** — aria-labelledby="dlg-terms-title" aria-describedby="dlg-terms-sub"，无 aria-modal。原生 dialog 静态无 open（showModal 打开，UA 隐式 modal），不构成 WCAG 违规；如需兼容个别不认原生 modal 语义的读屏组合，可补 aria-modal="true"（与 showModal 语义一致）。
7. **index.html:188 `dialog#help`** — aria-labelledby="help-title"，无 aria-modal。同上。
8. **index.html:364 `dialog#dlg-relogin`** — aria-labelledby="dlg-relogin-title"，无 aria-modal。同上。
9. **index.html:396 `dialog#dlg-close`** — aria-labelledby="dlg-close-title"，无 aria-modal。同上。
10. **index.html:429 `dialog#dlg-components`** — aria-labelledby="dlg-components-title"，无 aria-modal。同上。

## 最严重 5 条

1. **#tour-card 空标题（P1，index.html:336→338）**：唯一「写了 aria-labelledby 但静态无效」的对话框，也是最可能在运行时真的变成无名弹窗的一条（读屏只念「对话框」）。
2. **三个 .pop 状态弹层缺 aria-modal（P2-P4，index.html:349/351/358）**：#clock-pop / #login-pop / #phone-pop 是 role="dialog" 的非模态弹层，建议补 aria-modal="false" 以把非模态语义写明；属低风险增强项。
3. **#settings 非模态抽屉的焦点边界需动态核验（P5，index.html:207）**：aria-modal=false 名称链有效，但 Tab 是否困住/逸出背景内容静态审计无法判定，需在 WebView2（Edge）里动态验证。
4. **五个原生 dialog 缺显式 aria-modal="true"（P6-P10）**：showModal 打开时 UA 隐式 modal 不构成违规，属信息项；个别读屏组合不认原生 modal 语义时可补，与 showModal 语义一致。
5. **静态审计的固有盲区**：JS 运行时填充/改名的名称（#tour-title、#btn-login-text、日志按钮文案等）与 m 页运行时行为不在本表范围，问题 1 的实际影响、问题 3 的焦点边界都依赖动态核验收口。

补充说明：P1 是唯一一处「写了 aria-labelledby 但静态无效」的对话框；P2-P4 的三张状态弹层缺 aria-modal 属低风险增强项；P6-P10 为信息项。

## 附: hidden 统计与 label[for] 细节

hidden 计数: button 93/129; input等 21/30; 对话框 6/11
  index.html label@71 for=retry-for 文本「尝试时长2 分钟10 分钟30 分钟1 小时自动…」
  index.html label@72 for=max-attempts 文本「最多提交次数（0=不限）」
  index.html label@73 for=headed 文本「改用页面点击时显示浏览器」
  index.html label@185 for=chk-terms-agree 文本「我已阅读并同意《用户协议》与《隐私政策》」

## 抽查复核（2026-11-08，搬运后由主流程执行）

1. **grep 正向计数**：`grep -o '<button'` → index.html 110、m/index.html 19，合计 129；`<input>+<select>+<textarea>` → 16+6+0=22、7+1+0=8，合计 30；`<dialog` 5 + `role="dialog"` 6 = 11。三项与分母一致。【已复现】
2. **python html.parser 独立解析**（含 hidden 祖先链跟踪，两文件一并喂入）：button 129/hidden 93、inputs 30/hidden 21、dialogs 11/hidden 6——与素材脚本输出及 hidden 标注完全一致。【已复现】
3. `grep -n 'aria-modal' local/ui/index.html` → 恰 3 处：行 94（true）、207（false）、336（true）→「缺 aria-modal 8/11、显式 false 1、true 2」成立。【已复现】
4. `sed -n '336,339p' local/ui/index.html` → `div#tour-card` aria-labelledby="tour-title"，行 338 `<h3 id="tour-title"></h3>` 静态为空（JS 填充）。【已复现】
5. 汇总内部自洽核验：button 名称来源 9（aria-label）+120（文本内容）=129；输入名称来源 19+2+9=30；placeholder 6 处（表2 序号 1/21/22/23/24/27）；type=submit 3 个（表1 序号 29/44/46，行 112/191/203）；hidden 逐行标注计数与解析器一致。【已复现】

## 对抗复核（2026-11-08）

对抗双方（A 实质反证、B 机械核验；B 为 L8 原分析者、仅限机械项，身份已披露）独立复算与本表全部一致：三类分母 129=110+19、30=22+8、11=11+0，170 控件逐格比对 0 不一致，124 行非省略号文本逐字 0 实质差异，红牌 0。
重点复核 6 项全部通过：#tour-card 静态口径定性、3 个 .pop 增强项定性、#settings aria-modal=false、6 处 placeholder 并存、3 个 submit 在 form method=dialog、hidden 93/21/6。
旁证：5 个原生 dialog 的 showModal 调用落实于 terms.js:265/348、relogin.js:62、window.js:74、phone.js:695。
观察项（非红牌）：任务书所写 controllers/tour.js 实为 views/tour.js（本报告未指认 JS 路径，不构成错误）；「最严重 5 条」第 4、5 条为 P 编号汇总引用。
详见同目录 ADVERSARIAL-L8.md；本表与判定未改动。
