# 本机版 Api 收口：交付口径与真窗口验收清单

- 日期：2026-11-20
- 分支：`refactor/api-coordinator`，开工 HEAD `628a42d`（main 为其祖先）
- 状态：离线回归通过；真窗口十条已做（7 通过 / 1 部分 / 1 未覆盖 / 1 受限，见第八节）；未覆盖项列在文里
- 本批没有起真实窗口：以下清单是合回主干前必须由人照做的那一遍

## 一、本批做了什么

- **重登入口整体搬家。** `Api` 上的重登入口与自动重登门搬进
  `application/relogin_entry.py`，26 个方法在 `Api` 上保留同名转发；阻挡判断本身
  收在 `domain.login_rules.auto_relogin_blocked`，不再另留一份转发；登录失效推送体
  另归 `login_recovery.py`。`AutoReloginMonitor`、手机动作表与谁挡谁矩阵的接线点
  一个都没改名。
- **判断抽成纯函数。** 自动重登资格、迟到回答窗口、手工重登分流、静默重登就绪
  四类判断落进 `domain/login_rules.py`，参数全显式、不读墙钟、不拿锁；
  `test_login_relogin.py` 补表驱动用例，每个分支至少覆盖一次。
- **窗口外壳整体搬家。** 关窗三选、隐藏与唤回、托盘、二次打开、计划结束提醒搬进
  `application/desktop_window.py`；`_window` / `_tray` / `_window_hidden` /
  `_window_minimized` / `_close_approved` 五个旧字段名由字段代理类提供，
  `main()` 与各动作的读写语义不变。
- **失效推送归位。** 登录失效推飞书的消息体并入 `application/login_recovery.py`
  （「同一次失效只推一次」的判定本来就在那里），`Api._push_login_expired` 只做装配。
- **文档。** 进度表按实测重写；架构文档补 `login_recovery` / `relogin_entry` /
  `desktop_window` 三个服务的职责。

硬边界没有动：学校接口契约、登录态机制、数据模型、报名时序、前端脚本与
`grab.py` 一行未改。

## 二、行数前后值

| 对象 | 开工 | 收尾 |
|---|---|---|
| `local/app.py` | 3,112 | 2,558 |
| `Api` 类 | 2,038 | 1,471 |
| `Api.__init__` | 148 | 139 |
| `Api` 方法数 | 166 | 167（新增两个 `_make_` 装配函数，删掉一个多余的转发） |
| `Api` 里 4 行以内的转发 | 85 | 123 |
| `application/relogin_entry.py` | — | 485 |
| `application/desktop_window.py` | — | 320 |
| `application/login_recovery.py` | 245 | 277 |
| `domain/login_rules.py` | 247 | 324 |

## 三、Api 上保留的转发名单

重登入口（26 个，全部 3 行以内）：
`save_relogin_credentials`、`clear_relogin_credentials`、`_silent_relogin_ready`、
`_silent_relogin_state`、`_auto_relogin_eligible`、`_once_credentials_staged`、
`_auto_relogin_paused`、`_request_auto_relogin`、
`_relogin_wait_s`、`_relogin_ocr_ready`、`_manual_relogin_wanted`、`_phone_relay_view`、
`_begin_auto_relogin`、`_begin_auto_relogin_once`、`prepare_phone_relogin`、
`_commit_pending_save`、`_relogin_late_answer`、`_relogin_entry_gate`、
`_relogin_manual_case`、`_begin_typed_relogin`、`relogin_begin`、`relogin_cancel`、
`relogin_auto_once`、`phone_relogin_begin`、`phone_relogin_cancel`、`_anchor_login_success`

窗口外壳（15 个，全部 3 行以内）：
`plan_active_for_close`、`_close_plan_burden`、`ask_window_close`、
`request_window_close`、`_remember_close_action`、`hide_window`、
`_notify_window_hidden`、`show_window`、`window_visibility`、
`_on_window_minimized`、`_on_window_restored`、`_on_second_open`、
`_notify_plan_done`、`_ensure_tray`、`_stop_tray`

`relogin_submit`、`phone_relogin_submit` 仍直接调中继，没进这两个服务（它们只做
转发与来源标记，没有可搬的状态）。

## 四、全量与静态检查

- 开工基线：`Ran 2702`，失败 2（都是双进程文件锁在共享盘上偶发超时），跳过 2。
- 收尾全量：`Ran 2720`，失败 1（同一类双进程文件锁），跳过 2。
- 逐用例对比：**新增 18 项**（全部是本次补的纯函数表驱动用例）、**消失 0 项**、
  状态变化 1 项（开工时偶发超时的登录态双进程用例这次通过）。
  **没有出现开工基线里没有的失败。**
- `tools/code_shape/check.py`、`ruff check local`、`py -3.12 -m compileall -q local`
  全通过；测试文件仍是 **39 个**，没有新建 `test_*.py`。
- 两条已知环境噪声：双进程写锁用例在共享盘上偶发超时；有宿主代理时手机 HTTP
  用例会恒得 502——本机跑全量前已清空代理变量。

## 五、测试改动表

只改落点，可观察结论一条没动。新增的表驱动用例（148 行）不计入本表预算。

| 文件 | 用例 | 改了什么 | 为什么结论不变 | 行数 |
|---|---|---|---|---|
| `test_login_relogin.py` | `AutoStartFailureEmitTests` 两条 | 替身从 `Api._begin_auto_relogin_once` 挪到 `Api._relogin_entry._begin_auto_relogin_once` | 仍在验证「发起失败要推一次中继状态、busy 不推也不落盘」 | 5 |
| `test_login_relay.py` | `DesktopReloginWiringTests._source` | 改为先查 `application/relogin_entry.py`，再回 `app.py` 找装配函数 | 断言的仍是同一份真实实现：凭据只在成功后落盘、三个入口共用一道「来不及」门 | 20 |
| `test_application_services.py` | 手机重登两条 + 推送文案一条 | 替身挪到 `Api._relogin_entry`；推送文案源码改读 `login_recovery.py` | 仍在验证「点重登真的开一场」「消息里不带账号字段」 | 13 |
| `test_ui_main_window.py` | `AutoReloginTermsGateTests` | 改为用真实的条款门禁 + 真实的 `ReloginEntry`（其余端口用内存替身）跑资格判定；`_school_action_node` 增加 `phone_relogin_begin` 的新落点 | 仍在验证「未同意条款 / 旧版同意 / 撤回后都不自动登录，同意当前版才放行」 | 78 |
| `test_concurrency_guards.py` | 锁序守卫 | 服务清单加 `relogin_entry.py` / `desktop_window.py`；`_lock_id` 认这两个类的 `_lock` 与 `ReloginEntry._credential_lock`；`_ctor` 认两个新装配函数 | 规则一条没放宽：两个新服务持的仍是同一把协调锁，谁挡谁 140 格原样绿 | 13 |
| `test_ui_contracts.py` | 关窗两条 | 源码断言从 `app.py` 改读 `application/desktop_window.py`，并保留 `app.py` 里 `hide_window` / `show_window` / `_ensure_tray` 的签名断言 | 仍在验证「记住的偏好键还在同一条路」「隐藏必须有活的唤回入口」 | 12 |

合计 141 行，在 300 行预算内。

## 六、真窗口验收清单（合回主干前照做）

前提：源码态起窗（不带 `--demo`），登录用本人账号；跑完一条再看下一条。
「对应改动」列指出这条在守本批的哪一块。

### 1. 启动与条款

1. 启动程序，看首屏是否正常渲染、无白屏、无乱码。
2. 若弹出条款，点「查看条款」读全文，再点同意；关掉设置抽屉里的条款入口再进一次。
3. **算过**：首屏出得来；同意后学校动作不再被拦；不同意时点刷新会被条款门禁拦住并提示。
   **对应改动**：窗口服务搬家（首屏与窗口对象赋值）、条款门禁留在组合根。

### 2. 登录、登录检查与自动重登

1. 点登录，在打开的学校页面完成登录；回窗口看顶栏是否变「已登录」。
2. 点刷新触发一次登录检查，看顶栏「上次校验」是否更新。
3. 在设置里**先撤回条款同意**，等一轮检查（约 1 分钟），确认顶栏没有出现「自动登录中」。
4. 重新同意条款，等下一轮检查，确认自动重登按原逻辑判断（有账号 + 识别已装才会动）。
5. **算过**：撤回条款期间自动登录一次都不发起；重新同意后行为与分支前一致。
   **对应改动**：`ReloginEntry._auto_relogin_eligible` 与 `_silent_relogin_ready` 的条款门。

### 3. 手工重登与手机重登对话框

1. 点「重新登录」，不填账号密码直接确定：看是否提示需要输入（保存过账号时直接走保存的那份）。
2. 填账号密码（勾「保存到这台电脑」）再走一遍：看验证码框是否正常出现、能否提交。
3. 取消这次重登，再点一次，确认不会起第二场。
4. 手机页点「重新登录」，看电脑端是否出现同一场流程（不是两场）。
5. **算过**：四种情况（填了 / 没填有保存 / 密码被拒过 / 来不及）都给对提示；同一时间只有一场。
   **对应改动**：`relogin_begin` / `phone_relogin_begin` / `relogin_cancel` 的搬家与门禁。

### 4. 活动列表刷新与取消报名

1. 点刷新拉列表，看行、分组与计数是否正常。
2. 对一场**已报名**的活动点取消报名，等结果条。
3. **算过**：列表与分支前一致；取消成功后在列表里变回未报名。
   **对应改动**：本批只搬窗口与重登，列表/取消链路未动——这条是回归基线。

### 5. 开始、停止计划与终态

1. 勾一场活动，核对右侧计划，点「开始报名计划」。
2. 看任务状态从等待到开放、结果的每一跳是否都有显示。
3. 中途点「停止计划」，确认任务收尾、按钮回到可开始。
4. **算过**：状态逐场推进、停止后没有残留的「进行中」。
   **对应改动**：计划服务未动；本批只改了「计划结束时窗口不在眼前要不要通知」这一跳。

### 6. 组件下载、安装与移除

1. 设置里对验证码识别点「下载并安装」，看进度与结果。
2. 装好后点「移除」，再点一次安装（可选手动导入）。
3. **算过**：进度条、失败原因与安装/移除结论与分支前一致。
   **对应改动**：组件链路未动，仅确认窗口对象仍能被组件对话框拿到（`Api._window` 代理）。

### 7. 手机访问开关与换通道

1. 打开手机访问，扫二维码在手机浏览器里打开；看手机页能否看到列表与登录状态。
2. 切一次通道（本地 / Tailscale / Cloudflare），确认旧通道关掉、新地址可用。
3. 关掉手机访问，确认手机上立刻失效。
4. **算过**：开关、换通道、二维码与失效都与分支前一致。
   **对应改动**：手机链路未动；本批只改了窗口隐藏后手机页「显示电脑窗口」那一条路。

### 8. 隐藏到后台、托盘唤回、手机唤回、最小化还原

1. 点右上角 X，选「隐藏到后台」：看托盘是否出现、是否弹一次「窗口已隐藏」气泡。
2. 双击托盘图标唤回窗口。
3. 再隐藏一次，这次用手机页的「显示电脑窗口」唤回。
4. 点 X 选「最小化到任务栏」，从任务栏还原。
5. **这条单独看**：最小化再还原后界面是否白屏。分支上曾有过一次最小化还原白屏的记录，
   本批把最小化/还原的两个标志搬了家；还原后必须整屏正常（列表、计划栏、日志都在）。
6. **算过**：三条唤回路径都通；最小化还原不白屏；托盘建不起来时隐藏会被拒绝并说明原因。
   **对应改动**：`DesktopWindow.hide_window` / `show_window` / `window_visibility` /
   `_on_window_minimized` / `_on_window_restored`。

### 9. 关闭窗口时计划在跑的确认与关停收尾

1. 起一个计划（可以让它停在等待开放），点 X：应弹出三选，并列出「还没提交的场数、下一批时刻」。
2. 选「先不关」，确认计划继续跑。
3. 再点 X，选「退出程序」，在二次确认里点确认：程序退出，回来查任务管理器没有残留进程。
4. **算过**：三选里的数字是真的；退出后进程树收干净。
   **对应改动**：`ask_window_close` / `request_window_close` / `_close_plan_burden` 搬家；
   关停屏障仍归 `desktop_lifecycle`。

### 10. 第二次打开程序

1. 程序开着（可先隐藏到后台），再双击一次程序图标。
2. **算过**：第二份直接退出，第一份被唤回前台，界面出「又打开了一次」的提示与一条运行记录。
   **对应改动**：`_on_second_open` 搬家，单实例监听仍指向 `Api` 上的同名方法。

## 七、收尾验证记录（K8）

复跑命令（仓库根，清空代理变量，用装齐依赖的 3.12）：

```
py -3.12 -B -m unittest discover -s local/tests -p "test_*.py" -v
python tools/code_shape/check.py
ruff check local
py -3.12 -m compileall -q local
ls local/tests/test_*.py | wc -l
```

| 项 | 结果 |
|---|---|
| 全量离线测试 | `Ran 2720`，`FAILED (failures=1, skipped=2)`；唯一失败是开工基线里就有的双进程写锁超时 |
| 逐用例对比 | 新增 18、消失 0、状态翻转 1（基线里偶发超时的登录态双进程用例这次通过）；无新增失败 |
| `tools/code_shape/check.py` | 通过：文件 >800 行 10 个、501–800 行 11 个；函数 >100 行 25 个、61–100 行 74 个；测试函数 >60 行 19 个；属性超标的类 2 个 |
| `ruff check local` | 通过（All checks passed） |
| `compileall -q local` | 通过（无输出、退出码 0） |
| 测试文件数 | 39（与开工一致，未新建 `test_*.py`） |
| 认知索引 | 本机没有 AOCI 维护工具，索引待同步（`aoci*.txt` 与 `.aoci/` 仍是开工时那份） |

## 八、真窗口验收记录（2026-11-20 下午，源码态起窗）

逐条对照第六节做完的记「通过」；没条件做的不算通过，按实记「未覆盖 / 受限」。

| # | 条目 | 结果 | 看到的现象 / 说明 |
|---|---|---|---|
| 1 | 启动与条款 | 通过 | 条款更新弹窗（r5→r6）→ 撤回后出黄条与胶囊「等同意条款」→ 重新同意后学校动作恢复；首屏无白屏无乱码 |
| 2 | 登录、登录检查与自动重登 | 部分 | 登录成功，顶栏「已登录 16:34 校验」；撤回条款期间没有出现「自动登录中」。**自动重登本身没触发**（没有制造失效），见第 3 条 |
| 3 | 手工重登与手机重登对话框 | 未覆盖 | 已登录状态点「重新登录」走的是登录表单（设计如此：只有失效/转人工才进重登流程）；用户暂不制造失效，重登对话框未验到 |
| 4 | 活动列表刷新与取消报名 | 通过（演示模式） | 刷新出 11 场，分组与计数正常；对「宿舍查寝」点取消：结果条「已取消…学校记录已核对」+ 运行记录一行。**行随后又显示「已报名」是演示数据所致**：取消成功后前端立刻发一次后台刷新（`ui/features/list/actions-cancel.js:54`），而 `--demo` 的列表每次都用常量样例重建（`application/activity_list_service.py:91-97`），把本地翻成未报名的那行刷了回去；真实模式这一步取的是学校最新列表 |
| 5 | 开始、停止计划与终态 | 通过（演示模式） | 勾「网络安全·数字时代大长城」（已开放）+「图书馆志愿服务（第 12 期）」（次日开放）后开始：前者走到提交→成功，后者停在等待；点「停止计划」后按钮回到可开始，没有残留「进行中」 |
| 6 | 组件下载、安装与移除 | 受限 | 源码态「已启用」= 解释器里能 import ddddocr，安装动作直接短路、不落组件目录；`_advanced\relogin_ocr` 本来就不存在，所以没有可移除的东西。真装/移除要在安装版（冻结态）验 |
| 7 | 手机访问开关与换通道 | 通过 | 开关与换通道正常，关掉后手机侧确认失效 |
| 8 | 隐藏、托盘唤回、手机唤回、最小化还原 | 通过 | 三条唤回路径都通；**最小化还原没有白屏** |
| 9 | 关窗三选与关停收尾 | 通过（演示模式） | 起一个只含「图书馆志愿服务」的计划停在等待，X 弹出的三选里列出了还没提交的场数；先「先不关」窗口仍在，再 X →「退出程序」二次确认后退出。退出后进程表无 python / grab / playwright 残留（三次退出样本一致）。演示从不校时，「下一批时刻」在演示里为空串，该字段的换算由 `test_application_services.py:494-539` 覆盖 |
| 10 | 第二次打开 | 通过 | 用同一入口再起一份：0.4 秒退出、退出码 0、不弹框，第一份被唤回前台并留「又打开了一次」运行记录 |

第 4、5、9 条用 `--demo` 补测（临时数据根、不联网、样例固定）：演示只证明界面与编排链路，不代表学校侧真实结果。

### 验收中发现的两处既有问题（均与本批改动无关）

1. **条款未同意时「检查登录」是禁用态且没有任何反馈。** 判定在 `ui/views/status-cards.js:118`
   （`termsLocked()` 直接置 `disabled`），样式 `.btn:disabled{opacity:.45}`；点它当然没反应，
   文案只在弹层里写了「同意使用条款后才会检查登录」。同一弹层里「登录」还会去弹条款，
   一个有一个没有，看着像按钮坏了。建议补一句提示或改用可点后弹条款。
2. **偏好写入偶发 `PermissionError [WinError 5]`。** `save_prefs` → `update_prefs` →
   `prefs_store.atomic_write` 的 `os.replace` 被拒，桥接层没兜异常，前端拿到的是 promise 拒绝
   而不是 `{ok:false}`。`load_prefs()` 的普通 `open()` 不带 `FILE_SHARE_DELETE` 是可疑来源；
   发生在「同意条款」上会让条款一直锁着。本批 `save_prefs` / `update_prefs` / `prefs_store`
   零改动，属既有竞态。

### 结论

结构重构本身没发现回归：动过的入口（重登门禁、窗口外壳、托盘、二次打开、关停收尾）都按原样工作。
十条里 7 条通过、1 条部分（第 2 条只看到登录与检查，自动重登没被触发）、1 条未覆盖（第 3 条：
已登录时点「重新登录」按设计走登录表单，重登对话框要制造一次真实失效才看得到）、
1 条受限（第 6 条：源码态没有可安装/可移除的组件目录，须用安装版验）。
第六节的收工线是「十条全过」，**这三条补完之前不能宣称全过**；上面两处既有问题建议另开计划修。

### 收工判定

十条全过、第 8 条的最小化还原不白屏、第 9 条退出后无残留进程，才可以把这条分支合回主干。
任何一条不过，按「文件:行号」记到返修卡，不要先合并再看。
