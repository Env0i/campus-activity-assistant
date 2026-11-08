# 架构与数据流

服务器上一共四个 systemd 服务（含一个飞书机器人进程，单应用 combined 双入口）、一个 timer、十一条 cron。所有脚本都跑在 `/root/campus-activity-watch`，
只有登录态文件放在 `/root/campus-login`，机器人跑在 `/root/campus-bot`。

三个业务入口对应三条权限边界：**自动推送只发消息、群查询只回答问题、owner 私聊才动手**。
其中群 @ 查询与 owner 私聊由**同一个飞书自建应用**承载，`BOT_ROLE=combined` 的单个长连接进程按
`chat_type` 分流；三个入口共用同一份「学校公开活动」数据，但不共享任何个人执行状态。

## 认证边界（谁登录、谁能做什么）

全项目只有**一个学校账号会话**：部署者本人的。谁都没有第二条登录路径。

| 入口 | 登录来源 | 可见数据 | 允许的动作 | 明确禁止 |
|---|---|---|---|---|
| 本机版 GUI/CLI | 使用者本人手动登录（浏览器输入，密码不落盘） | 本人账号的活动与报名状态 | 本人账号的报名计划 | 代他人报名、批量提交 |
| 群 webhook 推送 | 服务器上的部署者会话 | 公开活动字段 | 只发消息 | 任何报名动作 |
| 自建应用机器人（combined） | 服务器上的部署者会话 | 群事件：公开活动字段；owner p2p：本人清单 | 群 @ 只读回答；p2p 本人报名与取消 | 群内任何报名动作、替群成员报名 |

要点：**群成员不登录学校系统、也不向机器人提供任何学校凭证**；服务器仍需部署者会话才能
查询公开活动。群查询不是"匿名访问学校接口"，而是部署者会话的只读代答。私聊动作只认
`PRIVATE_OWNER_OPEN_ID` 对应的部署者本人。数据边界与告知义务见
[USER_AGREEMENT.md](USER_AGREEMENT.md) 与 [PRIVACY_POLICY.md](PRIVACY_POLICY.md)。

## 数据流

```
                 ┌──────────────────────────── cron ────────────────────────────┐
                 │ 07:00/10:30/16:30/21:30 run.py   */5 scan.py  */15 token_probe │
                 │ */1 activity_watch.py（自己按 next_poll_at 控频）              │
                 └───────────────┬──────────────────────────┬───────────────────┘
                                 │                          │
        ┌────────────────────────▼───────────┐   ┌──────────▼──────────┐
        │ data/session.json (token, 600)     │◄──┤ campus-login daemon  │  每 2h 校验
        └────────────────────────┬───────────┘   │ server_refresh.js   │  storage_state.json
                                 │               └──────────┬──────────┘
                     fetch.py ───┤                          │ 失效时
                                 ▼                          ▼
             POST /dr/api/rjyHd/listActivity        auto_login.py（验证码 OCR，≤3 次）
                                 │                          │
                 ┌───────────────┴────────────────┐         │
                 │ 公开活动 + 去重（state.json）  │         │
                 │ 发现时刻/状态（activity_watch）│         │
                 └───────┬───────────────┬────────┘         │
                         ▼               ▼                  │
    run.py ──► notify.py ──► 飞书群卡片 │                    │
    activity_watch.py ──► run.send_watch_events ──► 群卡片   │
    scan.py（临近提醒）─────────────────┘                    │
                         │                                   │
    bot.js（combined，单进程）── 群 @ 只读查询 ──► query.py ─────┘
                              └── owner p2p 按钮 ──► watchlist.py ──► watchlist_runner.py
                                                                        │
                                                          到点 systemd-run grab_signup.py
                                                                        │
                                                                  结果私聊回报
```

## 模块职责

| 文件 | 职责 | 谁调用 |
|------|------|--------|
| `server/scripts/common.py` | 学校地址唯一来源、会话读写、原子写、跨进程锁、业务北京时间、动态监测配置 | 所有脚本 |
| `server/scripts/fetch.py` | 取 token → 分页拉活动 → 归一化（含公开字段白名单）→ 公开状态分类 | run/scan/query/activity_watch |
| `server/scripts/activity_watch.py` | 公共活动动态发现：指纹、首次发现、状态转移、改期事件、固定节奏轮询、单飞锁、退避；首轮只建静默基线 | cron（每分钟唤醒） |
| `server/scripts/run.py` | 一轮推送：抓取 → 卡片 → 群推送 → 私聊预报名卡；动态事件聚合通知入口 | cron / activity_watch |
| `server/scripts/scan.py` | 每 5 分钟：开放前 10 分钟的临近提醒（只报时间） | cron |
| `server/scripts/remind.py` | 07:05 当天活动私聊提醒 | cron |
| `server/scripts/card.py` | 飞书卡片 JSON 构造：公共只读卡片 + 私聊预报名卡片，状态词唯一来源 | run/scan/remind/query/bot |
| `server/scripts/render.py` | 文案排版（纯文本与卡片共用） | card/run/scan |
| `server/scripts/notify.py` | 推送通道：webhook / 飞书应用、卡片、私聊、更新卡片 | 全部发送方 |
| `server/scripts/token_probe.py` | token 有效性探针 + 连续失败告警 | cron |
| `server/scripts/token_report.py` | token 寿命汇总 | cron |
| `server/scripts/net_probe.py` | 出网自检（静态页，不带 token） | cron |
| `server/scripts/grab_card.py` | 预报名卡片的发送快照与整卡刷新 | run / bot / watchlist |
| `server/scripts/watchlist.py` | 预报名清单状态机（queued/running/done/failed/missed） | bot / runner |
| `server/scripts/watchlist_runner.py` | 每分钟对齐清单，到点 `systemd-run` 拉起抓取 | cron |
| `server/scripts/trigger_server.py` | HTTP 一键触发（`/run/<token>`） | 手机浏览器 |
| `server/deploy/server_refresh.js` | 常驻守护：每 2h 校验并回写会话 | systemd |
| `server/deploy/auto_login.py` | 失效时无人值守重登：验证码 OCR + 页面提交 + 原子写会话 | timer（5 分钟） |
| `server/deploy/grab_signup.py` | 到点进详情页点「立即报名」，结果私聊回报 | watchlist_runner |
| `server/deploy/set_credentials.py` | 交互写入 `credentials.json`（唯一放账号密码的地方） | 人工一次 |
| `server/bot/bot.js` | 飞书长连接：`BOT_ROLE=combined` 单进程按 `chat_type` 分流——群 @ 只读查询 / owner p2p 个人动作 | systemd（一个实例） |

## 接口清单

| 接口 | 方法 | 用途 |
|------|------|------|
| `/dr/api/rjyHd/listActivity` | POST | 活动列表（分页，`pageSize` 最大 500） |
| `/dr/api/rjyHd/getInfo/<id>` | GET | 活动详情（`qxbm` 映射为 `cancel_allowed`，`sfkybm` 映射为 `can_sign`，决策 016） |
| `/dr/api/rjyHdCyr/getJoinInfo/<id>` | POST | 我是否报名（`data` 非 null 即已报；取消报名后的复查也用它） |
| `/dr/api/rjyHdCyr/cancel/<id>` | GET | 取消报名（明文活动 id，无 hash、无请求体；**结果以 `getJoinInfo` 复查为准**，回包只作参考，决策 016） |
| `/dr/api/rjyHdCyr/signUp/<hash>` | GET | 报名（hash 用运行时密钥现算；直发为主，点击兜底，见下节） |
| `/dr/api/upms/security/runtime/profile` | POST | 取 16 位运行时密钥（开抢前每场一次，只放内存，不落盘、不写日志） |
| `/dr/api/auth/captcha` | POST | 登录验证码（`{client,userType}` → `{key,image}`） |
| `/dr/api/auth/login` | POST | 登录（带签名头，只能用真实页面提交） |

失效响应统一是 `{"code":4001,"message":"身份验证失败！"}`，`fetch.py` 见到即抛 `PermissionError`、退出码 2。

## 去重机制与状态文件

### `data/state.json`（推送进度）

| 键 | 语义 | 写入时机 |
|----|------|----------|
| `announced` | 已推送过的活动（id → 首次推送时间） | **推送成功后**才写 |
| `last_push_ts` | 上一次成功推送的时间戳 | 同上 |
| `reminded_signup` | 已提醒过「报名开始」的活动 | 临近提醒成功后 |

`run.py` 用 `data/.state.lock` 在锁内先占位、推送成功再落盘；
进程崩溃或推送失败会回滚占位，所以「失败」不会被误记成「已推送」。
`GUARD_MINUTES=60` 防同一时点重复跑。

### `data/activity_watch.json`（动态发现）

| 键 | 语义 |
|----|------|
| `initialized_at` | 首次成功抓取建立基线的时间；空串 = 还没建过基线 |
| `baseline_initialized` | 基线是否已建立。为 `true` 后即使活动库被清空也不再重建基线，避免把之后的第一条新活动静默吞掉 |
| `activities[id].discovered_at` | **本次发现时刻**（第一次在活动库里看到这条的时间） |
| `activities[id].sign_start` | **原定开放时间**（学校字段，两者必须分开保存） |
| `activities[id].first_status` | 首次发现时的状态（`open` 说明是一发现就已经开放） |
| `activities[id].status` | 上次判定的状态（pending/open/closed/unknown） |
| `activities[id].missing_rounds` | 连续几轮没抓到（满 3 轮才移除，不推断「已结束」） |
| `pending_events` | 已生成、还没推送成功的事件；推成功才清空。**首轮建基线时恒为空**，所以升级上线不会补发历史活动 |

三份状态互不覆盖：清空 `announced` 不会让动态监测重发历史事件，反之亦然。
`activity_watch.py` 不读也不写 `watchlist.json`。首次成功抓取只建立基线、
不发送通知的完整理由见 [TIMING_AND_DEDUP_ANALYSIS.md](TIMING_AND_DEDUP_ANALYSIS.md) §7.7。

## 推送节奏

| 时间 | 内容 | 通道 |
|------|------|------|
| 07:00 | 今日/待开放活动日报 + 私聊预报名卡 | 群 + owner 私聊 |
| 07:05 | 「今天要参加的活动」 | 仅 owner 私聊 |
| 10:30 / 16:30 | 增量日报 | 群 |
| 21:30 | 晚归签到提醒 + 已开放清单 | 群 |
| 每 5 分钟 | 临近提醒（≤10 分钟开放的活动，只报时间） | 群 |
| 每分钟唤醒 | 动态监测：白天每 3 分钟、夜间每 10 分钟真正访问学校（固定节奏，不做临近加密） | 群（有事件才发） |
| 每 15 分钟 | token 探针（不推送，仅告警） | 私聊 |

请求量账本见 [TIMING_AND_DEDUP_ANALYSIS.md](TIMING_AND_DEDUP_ANALYSIS.md) §3.1。

## 告警链路

| 探针 | 频率 | 判定 | 文案 |
|------|------|------|------|
| `token_probe.py` | 15 分钟 | 连续 2 次 `fail`（`ok` 清零） | 登录态失效，需要重新登录 |
| `token_probe.py` | 15 分钟 | 连续 2 次 `http-error`/`bad-json` | 学校接口探测不通，多半是出网/带宽问题 |
| `net_probe.py` | 5 分钟 | 连续 2 次取不到学校静态页 | 区分「整机断网」与「仅学校站点不通」 |
| `auto_login.py` | 5 分钟（timer） | 3 次登录失败 | 自动登录失败，需人工介入 |
| `activity_watch.py` | 每次成功抓取后 | 连续失败按 120/300/900 秒退避 | 只写 `data/activity_watch.log`，不往群里发技术错误 |

告警一律优先私聊 owner，失败回落群通道；同一失效周期只发一次，恢复后自动清零。

## 本机工具（local/）分层

本机版按 Clean/Hexagonal 方向分层，依赖只准向下：

```
ui/（WebView 界面）→ app.py（Api 外观/组合根）→ application/（用例）→ domain/（纯规则）
                                                   └→ infrastructure/（副作用适配器，由外观注入端口）
```

| 层 | 模块 | 做什么 | 谁调用 | 依赖什么 |
|----|------|--------|--------|----------|
| domain | `login_rules` | 登录三态快照分类、check 四态结论、来源行归因 | app 外观、application | 无（纯函数） |
| domain | `retry_rules` | `[retry]` 行解析、次数归并、telemetry 载荷、策略归一 | application | 无 |
| domain | `plan_rules` | 计划项归一化/截止门禁、列表合并、任务终态分类 | app 外观、application | 无（classify_mode/validate_fn/epoch_of 由 app.py 注入） |
| domain | `cancel_rules` | 取消报名回包的清洗（去控制字符、截 80 字）与 worker 输出归一化；grab 与 app 共用一份 | grab、app 外观 | 无（纯函数） |
| domain | `lifecycle_rules` | 跨关闭时长/质量记账（v1 文本 / v2 epoch） | infrastructure | 无 |
| domain | `time_text` / `worker_lines` / `demo_data` / `errors` | 时间文本换算、worker 行解析、演示样例、语义类型 | 各层 | 无（换算/格式化函数由 app.py 注入；不读墙钟，此刻值由调用方传入） |
| application | `plan_service` | 单场 worker 的启动、监督、终态收尾（端口注入） | app.Api._run_plan_task | domain + 注入端口 |
| application | `update_service` | 更新检查/下载校验用例（fetch/download 端口注入） | app.Api 更新方法 | 注入端口 |
| application | `login_service` | check 事件载荷与 done 结论整理 | app.Api._do_check_inner/_pump | domain |
| infrastructure | `prefs_store` | ui.json 跨进程锁 + 原子读-合并-写 | app 外观、lifecycle_store | 无 |
| infrastructure | `process_tree` | Windows Job Object 进程树所有权、taskkill 整树终止 | app 外观（spawn 端口） | 无 |
| infrastructure | `lifecycle_store` | 启动冻结/心跳/正常关闭的 ui.json 记账 | app.get_lifecycle | prefs_store + domain |
| interface | `app.py` | Api 49 个公开方法、条款门禁、事件发射、worker 命令装配、main；composition root：向 domain/application 注入 signup_plan 纯函数、time_contract 换算、business_clock 异常类型 | pywebview / 测试 | 全部下层（裸名注入缝保持 app.X 可替换） |
| interface | `ui/state/**` | 状态仓库 S 与纯投影（clock/plan/login/filters/labels/time/task-display） | controllers/views | 无（store.js 仅 `$` 选择器工具；login.js 一处 body 就绪守卫） |
| interface | `ui/controllers/**` | 用例编排与桥接（bridge/refresh/plan/plan-events/clock/terms/update/prefs/tick） | app.js 事件绑定 | state + api()；terms/update 两个 controller 零 DOM（结构契约测试守护） |
| interface | `ui/views/**` | DOM 呈现（list/board/login/clock/clock-pop/log/selection/terms/help/update/tour） | render/tick 与 controller 调用 | state 投影（不发桥接请求）；terms/update 的 DOM 查询与呈现全部在此 |

前端脚本按 index.html 的加载序执行（保持原 app.js 的顶层初始化依赖；views/terms.js、
views/update.js 排在消费它们的 controller 之前），app.js 只保留 boot 初始化、
`window.onBackend` 事件分发和 DOM 事件绑定。状态唯一持有者是 `state/store.js` 的 `S`；
契约测试按「前端脚本联合源码」核对（`read_ui_scripts()`，led.js 除外），行为测试用
node 沙箱按同一加载序回放。

兼容入口边界（重构未删旧名）：`app.py` 保留旧模块级名字的兼容包装/再导出（测试按
`app.X` 注入与 patch 的语义不变）；`views/update.js` 的 `paintUpdate` 同时是
`views/help.js` 消费的更新呈现入口。DOM 分离是**局部完成**而非全局：条款/更新两个
controller 已零 DOM（结构契约测试 `LayerBoundaryContractTests` 守护），但
`controllers/tick.js` 仍做每秒增量 DOM 更新、`app.js` 事件绑定直接触 DOM——全局
controller/view DOM 分离不在本轮范围。

### 启动与单实例（GL01）

图形界面启动（`local/app.py` 的 `main`）先过单实例守卫（`infrastructure/single_instance.py`）。`--demo` 与 worker 子命令不经过它。
- 判定：Windows 用具名互斥量（名字只含产品标识）。拿到的是第一份；发现已存在的是第二份。
- 第一份在 `127.0.0.1` 的随机端口开一个只收「唤回」的监听，端口、进程号与随机口令写进数据目录下的 `instance.json`，口令不进日志。口令错、格式不对的请求一律不回应。
- 第二份读 `instance.json`、发出唤回后退出，不建时钟、不建 Api、不起窗口。唤回失败（文件缺失、连不上、超时、被拒）时弹出原生消息框「工具已经开着」再退出。
- 第一份收到唤回：还原并显示本窗口，再推 `second_open` 事件（见 UI_SPEC §5.2）。
- 守卫出错一律放行第一份（fail-open）；非 Windows 直接放行。窗口关闭后先停监听，收尾完成后再删 `instance.json`、放互斥量；进程崩溃时系统回收互斥量。
- worker 子进程（`grab.py`、`grab-worker.exe`）不经过守卫，不受影响。

### 报名链路（决策 015）

- **直发为主、点击兜底**：开抢前调 `runtime/profile` 取运行时密钥（`fetch_runtime_key`），
  经 `parse_runtime_key` 校验形状后交给 `build_signup_hash` 现算签名；只有三种情况退回点击
  ——取不到密钥、重取后仍「版本不兼容」、同一条未识别回包连续 3 次。每场写
  「报名路径：直发 / 点击（原因）」并发出 `kind=path` 事件。
- **回包分类**：`local/domain/signup_reply.py` 的 `classify_signup_reply` 把 `code` 与 `message`
  关键短语归一成一种 kind；日志记学校完整原文，界面只看 `stop_reason_label` 给出的短结论。
- **终态核对**：每场结束都用 `getJoinInfo` 查一次，单独 3 秒预算（`FINAL_CHECK_S`）；
  原预算用完、报名截止之后也查，核对失败不重发。
- **登录失效先复查**：只读检查收到一次 4001 时，隔 `LOGIN_RECHECK_S`（1.5 秒）复查，
  两次都是 4001 才算失效；提交中确认失效后停发、等在途落定，再复查决定继续或收口。
- **登录失效后交接**：worker 用 `--relogin-wait`（45 秒）等界面换上新登录态；
  期间发 `kind=login_wait`，换到新 token 且复查有效后发 `kind=login_resumed`，
  重取运行时密钥继续；等待不计提交次数。
- **登录态单一写入口**：`grab.py` 的 `save_session` 用进程内锁 + `session.json.lock`
  跨进程锁；命令行登录、手机重登中继、`storage_state.json` 双文件事务都走它。
- **日志**：`log_event` 每行带北京时间、级别、来源、活动 ID、事件名；`grab.log`
  超过 5 MB 轮转成 `grab.log.1…5`；界面进程的自动登录事件也追加到同一份日志。

### 取消报名与列表筛选（决策 016）

- **列表筛选（R1）**：`local/grab.py` 的 `keep_in_list(act, now)`。原有的 `still_relevant` 为真，或者活动已报名、`act_end` 能解析且不早于业务北京时间，这两种情况都留在列表里。已报名但 `act_end` 缺失或解析不了的，仍按原规则筛掉。`--all` 与北京时间不可用时的行为不变。补回后，界面的冲突判断和计划冲突基线都能看到这些已报名活动。
- **详情映射（R2）**：`parse_attendance_detail` 追加 `cancel_allowed`（`qxbm`：1 为真、0 为假、缺失为 null）和 `can_sign`（`sfkybm`，同样三态，只映射不展示）。`list --json` 每行输出这两个键。
- **取消子命令（X2）**：`python local/grab.py cancel --id <id> --json`，由 `cmd_cancel` 调 `run_cancel`。stdout 恰好一行 JSON，日志走 stderr；退出码为 0 仅表示 `cancelled`，其余为 2。
  - 流程：登录（只有学校明确说失效才报 `login_expired`）→ 北京时间可用 → 是否已报名（三态，只有真才往下走）→ 详情 `qxbm` 为 1 且业务北京时间在 `[报名开始, 报名截止]` 内 → 调 `GET /dr/api/rjyHdCyr/cancel/<id>` 一次，不重试 → 用 `getJoinInfo` 复查。
  - 前置不满足或查不到时不调取消接口，结果为 `precheck_failed` 并带原因。
- **界面进程（X1、X3、X4）**：`app.Api.cancel_signup(activity_id)`。先过条款门，id 必须在当前列表缓存里且为已报名；与计划、刷新、登录、另一场取消互斥（`_cancelling` 并入忙碌判定）。成功后发一次 `activities` 事件刷新列表。
- **手机端不做取消**：`phone_rules.ACTION_PARAMS` 不含 `cancel_signup`，手机页不得调用。
- 结果句与清洗规则在 `local/domain/cancel_rules.py`，worker 与界面进程共用一份，学校原话只回给界面、不写运行记录。
