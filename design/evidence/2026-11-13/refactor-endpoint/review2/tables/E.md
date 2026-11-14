## review2 表 E 独立复算

| 文件 | 无障碍名称 | 文案 | 源码形状 | 合计 | node 沙箱测试函数 |
|---|---|---|---|---|---|
| `local/tests/test_ui_conflict_cancel.py` | 6 | 40 | 61 | 107 | 26 |
| `local/tests/test_ui_contract_clock.py` | 0 | 42 | 21 | 63 | 11 |
| `local/tests/test_ui_contract_components.py` | 2 | 18 | 32 | 52 | 0 |
| `local/tests/test_ui_contract_feedback.py` | 0 | 28 | 32 | 60 | 11 |
| `local/tests/test_ui_contract_list.py` | 7 | 120 | 119 | 246 | 22 |
| `local/tests/test_ui_contract_login.py` | 0 | 93 | 79 | 172 | 18 |
| `local/tests/test_ui_contract_plan.py` | 2 | 161 | 188 | 351 | 29 |
| `local/tests/test_ui_contract_settings.py` | 2 | 149 | 139 | 290 | 19 |
| `local/tests/test_ui_contract_shell.py` | 2 | 122 | 115 | 239 | 14 |
| `local/tests/test_ui_contract_terms.py` | 2 | 172 | 184 | 358 | 37 |
| `local/tests/test_ui_contract_update.py` | 3 | 28 | 29 | 60 | 29 |
| `local/tests/test_ui_layers.py` | 0 | 0 | 0 | 0 | 0 |
| `local/tests/test_ui_main_window_list.py` | 4 | 35 | 28 | 67 | 17 |
| `local/tests/test_ui_main_window_plan.py` | 0 | 51 | 19 | 70 | 16 |
| `local/tests/test_ui_reliability.py` | 0 | 166 | 131 | 297 | 84 |
| `local/tests/test_ui_rewards.py` | 4 | 3 | 37 | 44 | 2 |
| `local/tests/test_phone_ui.py` | 2 | 403 | 257 | 662 | 0 |
| 合计 | 36 | 1631 | 1471 | 3138 | 335 |

自校：三类之和 3138 = 收集总数 3138 -> 成立

### 三类抽样各 20（random.Random(20261113)，按 文件+行号+字面量 排序后抽）

| 类别 | 文件:行号 | 原文 |
|---|---|---|
| 无障碍名称 | `local/tests/test_ui_contract_list.py:888` | `aria-selected="false">可报名` |
| 无障碍名称 | `local/tests/test_phone_ui.py:5347` | `id="offline-note" class="alert bad" role="alert"` |
| 无障碍名称 | `local/tests/test_ui_contract_components.py:32` | `id="phone-component-state" aria-live="polite"` |
| 无障碍名称 | `local/tests/test_ui_contract_terms.py:385` | `aria-label="关闭条款"` |
| 无障碍名称 | `local/tests/test_phone_ui.py:3258` | `点钮展开列表并随动 aria-expanded/文案` |
| 无障碍名称 | `local/tests/test_ui_contract_list.py:891` | `chip.setAttribute("aria-selected"` |
| 无障碍名称 | `local/tests/test_ui_conflict_cancel.py:104` | `aria-describedby="cx-tip"` |
| 无障碍名称 | `local/tests/test_ui_contract_list.py:904` | `aria-expanded="false"` |
| 无障碍名称 | `local/tests/test_ui_conflict_cancel.py:499` | `title="正在刷新，等它结束再取消"` |
| 无障碍名称 | `local/tests/test_ui_conflict_cancel.py:498` | `data-cancel="s1" disabled title="计划在运行，先停下来再取消"` |
| 无障碍名称 | `local/tests/test_ui_rewards.py:62` | `<span class="rw-i" title="实践分 2，虚拟工资 20">2 分 · 工资 20</span>` |
| 无障碍名称 | `local/tests/test_ui_contract_list.py:888` | `button 上的 aria-selected 非法，必须用 aria-pressed` |
| 无障碍名称 | `local/tests/test_ui_contract_update.py:451` | `role="progressbar"` |
| 无障碍名称 | `local/tests/test_ui_contract_plan.py:998` | `data-tone="ok"><i aria-hidden="true">✓</i>` |
| 无障碍名称 | `local/tests/test_ui_contract_update.py:452` | `aria-label="安装包下载进度"` |
| 无障碍名称 | `local/tests/test_ui_contract_settings.py:32` | `#tour-card 是 role=dialog 且 aria-labelledby=tour-title：标题静态不能为空，否则引导没开始前读屏只念「对话框」` |
| 无障碍名称 | `local/tests/test_ui_contract_components.py:33` | `id="phone-status" role="status"` |
| 无障碍名称 | `local/tests/test_ui_main_window_list.py:132` | `aria-expanded 跟展开状态` |
| 无障碍名称 | `local/tests/test_ui_contract_settings.py:466` | `role="dialog"` |
| 无障碍名称 | `local/tests/test_ui_contract_list.py:903` | `role="button"` |
| 文案 | `local/tests/test_phone_ui.py:5318` | `电脑上还没有同意使用条款` |
| 文案 | `local/tests/test_phone_ui.py:826` | `填写账号密码` |
| 文案 | `local/tests/test_phone_ui.py:3823` | `电脑正在自动重新登录。` |
| 文案 | `local/tests/test_ui_contract_plan.py:35` | `工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。` |
| 文案 | `local/tests/test_ui_contract_terms.py:1957` | `打开阅读器绝不保存` |
| 文案 | `local/tests/test_phone_ui.py:414` | `后台恢复必须按事件游标补齐，且只读、不重放写操作` |
| 文案 | `local/tests/test_ui_contract_settings.py:149` | `计划运行中必须暂停引导` |
| 文案 | `local/tests/test_phone_ui.py:1994` | `后端原话` |
| 文案 | `local/tests/test_ui_contract_shell.py:85` | `帮助标题描述用途，正式名称仍由窗口标题表达` |
| 文案 | `local/tests/test_phone_ui.py:3868` | `底栏计数随动` |
| 文案 | `local/tests/test_phone_ui.py:3105` | `等待开放` |
| 文案 | `local/tests/test_phone_ui.py:1624` | `「启用」不能再打开导入弹窗` |
| 文案 | `local/tests/test_ui_contract_plan.py:660` | `开放瞬间不得换锚` |
| 文案 | `local/tests/test_phone_ui.py:1713` | `导入链接打开的是验证码识别的导入` |
| 文案 | `local/tests/test_ui_contract_shell.py:685` | `要关闭窗口吗？` |
| 文案 | `local/tests/test_phone_ui.py:3183` | `工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。` |
| 文案 | `local/tests/test_ui_contract_terms.py:978` | `使用条款更新了` |
| 文案 | `local/tests/test_ui_contract_list.py:798` | `点重试不得顺手清筛选把错误藏掉` |
| 文案 | `local/tests/test_phone_ui.py:1010` | `已复制` |
| 文案 | `local/tests/test_ui_contract_list.py:745` | `检查没结束时不得提前宣布「登录是有效的」` |
| 源码形状 | `local/tests/test_ui_contract_components.py:179` | `cloudflared_missing` |
| 源码形状 | `local/tests/test_phone_ui.py:1124` | `下载没有完成：GitHub 暂时无法响应，请稍后重试，可以重试。` |
| 源码形状 | `local/tests/test_ui_conflict_cancel.py:226` | `` |
| 源码形状 | `local/tests/test_ui_contract_plan.py:630` | `partial` |
| 源码形状 | `local/tests/test_ui_reliability.py:55` | `unknown` |
| 源码形状 | `local/tests/test_phone_ui.py:744` | `还差一步：装好 Tailscale 后点“重新检测”，或者改用 Cloudflare。` |
| 源码形状 | `local/tests/test_ui_contract_shell.py:108` | `cy="9.5"` |
| 源码形状 | `local/tests/test_phone_ui.py:3133` | `ok` |
| 源码形状 | `local/tests/test_ui_contract_terms.py:125` | `'terms': terms_state(prefs)` |
| 源码形状 | `local/tests/test_ui_conflict_cancel.py:242` | `b1` |
| 源码形状 | `local/tests/test_phone_ui.py:4246` | `汇总行集与计数同一口径（不过段钮过滤，R-P3-7）` |
| 源码形状 | `local/tests/test_phone_ui.py:2854` | `原型 submitPair：失败清空重输` |
| 源码形状 | `local/tests/test_ui_contract_settings.py:105` | `340px` |
| 源码形状 | `local/tests/test_phone_ui.py:2897` | `归零只放开呈现层（输入不再禁用；空输入仍不可提交），服务端是唯一闸门；UI-F6（原型 lockLeft 归零清 pairErr）：旧错误条一并收回` |
| 源码形状 | `local/tests/test_ui_contract_terms.py:1114` | `提交的 documentVersion 必须等于可见内嵌版本节点` |
| 源码形状 | `local/tests/test_phone_ui.py:4795` | `id="btn-phone-feature-install"` |
| 源码形状 | `local/tests/test_ui_contract_update.py:128` | `launching` |
| 源码形状 | `local/tests/test_ui_contract_plan.py:59` | `停止确认不再是原生 dialog` |
| 源码形状 | `local/tests/test_phone_ui.py:1927` | `id="relogin-ocr-status"` |
| 源码形状 | `local/tests/test_ui_contract_plan.py:42` | `class="dlg sm"` |

## 复核说明（UI 视觉验收设计师）

- 三类各抽 2 条共 6 条，原文逐字相符、类别判一致（含 test_phone_ui.py:3258 的关键字实参 msg 归调用行口径确认）；自写 ast 片段独立重数 test_phone_ui.py 2/403/257 与脚本一致；自校 36+1631+1471=3138 成立。
