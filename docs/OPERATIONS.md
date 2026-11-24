# 运维手册

## 1. 机器与目录

| 项 | 值 |
|----|----|
| 服务器 | `<你的服务器IP>`（Ubuntu 22.04.5，root） |
| 私钥 | 本机 `~/.ssh/<私钥文件名>`（下面 `scp` 命令里的同名占位符请替换为你自己的文件名） |
| 时区 | Asia/Shanghai |
| Python | 3.10.12（系统自带） |
| Node | v20.20.2（`/usr/local/bin/node`，playwright 要求 ≥18） |
| Chromium | `/root/.cache/ms-playwright/chromium-1248`（由 playwright 管理） |
| Swap | 1G（`/swapfile`，已写 fstab） |

```
/root/campus-activity-watch/      应用与脚本
├── scripts/                     生产脚本（cron 用相对路径调用）
│   ├── lib/                     公共库（common / fetch / notify / card / render / site_target / school_detail / mine_rules / mine_cards）
│   ├── login/                   登录探针与寿命统计（login / token_probe / token_report）
│   ├── push/                    日报推送、动态监测与提醒（run / remind / scan / activity_watch / query / attend_remind / personal_notice）
│   ├── signup/                  预报名清单、调度与取消（watchlist / watchlist_runner / grab_card / cancel_signup / cancel_actions.js）
│   └── ops/                     运维自检与触发（net_probe / regress / selfcheck / trigger_server）
├── bot/                         飞书长连接机器人（bot.js + node_modules）
├── deploy/                      部署脚本与 systemd 模板
├── data/                        运行数据（session.json、state.json、日志）
└── reports/                     推送产物

/root/campus-bot/                 机器人进程目录（从 2026-11-24 起改为软链：bot.js 软链自应用目录，data/ 与 node_modules/ 软链保留原数据与依赖）
/root/campus-login/               登录态守护与自动报名：server_refresh.js、storage_state.json、
                                 credentials.json、auto_login.py、preempt_guard.py、
                                 grab_signup.py、signup_*.py（同目录报名子模块）、refresh.log
```

权限约定：目录 700，`credentials.json` / `storage_state.json` / `data/session.json` 600。
`config.json` 需配置 `site.base`（学校站点根地址，或通过环境变量 `SCHOOL_ORIGIN` 注入）；未配置时 `site_target` 会拒绝所有学校请求。

## 2. systemd

| 单元 | 类型 | 作用 |
|------|------|------|
| `campus-login.service` | simple | `node server_refresh.js --daemon`：每 2h 校验 token，成功即刷新会话 |
| `campus-bot.service` | simple | `BOT_ROLE=combined`：一个长连接进程分流两个入口——群里被 @ 只读查询；owner 私聊才有个人查询与预报名/报名动作 |
| `campus-trigger.service` | simple | `python3 scripts/ops/trigger_server.py`：HTTP 一键触发（18080） |
| `campus-autologin.service` | oneshot | `python3 /root/campus-login/auto_login.py --preempt` |
| `campus-autologin.timer` | timer | `OnCalendar=*:0/5`，每 5 分钟唤起上面的 oneshot |

```bash
systemctl status campus-bot campus-login campus-trigger campus-autologin.timer
systemctl restart campus-bot            # 改完 bot.js 只重启这一个（一个进程两个入口）
systemctl restart campus-login          # 改完 server_refresh.js 必须重启
journalctl -u campus-bot -n 100 --no-pager
```

**同一个自建应用只能跑一个 `campus-bot.service`**：`BOT_ROLE=combined` 是唯一有效值，
拆分时代的 `group_query` / `private_owner` 已被代码拒绝启动。旧的双单元
`campus-bot-group.service` / `campus-bot-owner.service` 必须 `disable --now`，
否则同一 App 双开长连接会互抢事件。
（Webhook 群自定义机器人是另一条独立通道，只推送、没有进程。）

`PRIVATE_OWNER_OPEN_ID` 放在 `campus-bot.service.d/owner.conf` drop-in 里，
`campus-autologin.service` 里也单独配了一份——两个必须一致，否则私聊静默关闭。

### 部署路径环境变量

线上用的是另一个前缀，经环境变量注入（不改仓库代码），未设置时默认使用 `/root/campus-login`、`/root/campus-activity-watch` 与 `campus-grab-`：

| 变量 | 默认值 | 作用与读取方 |
|---|---|---|
| `APP_DIR` | `/root/campus-activity-watch` | 应用目录；`bot.js`、`auto_login.py`、`grab_signup.py` 读取，并由 `watchlist_runner.py` 经 `--setenv` 透传 |
| `LOGIN_DIR` | `/root/campus-login` | 登录目录；`auto_login.py`、`grab_signup.py`、`watchlist_runner.py` 读取，并由 `watchlist_runner.py` 经 `--setenv` 透传 |
| `GRAB_UNIT_PREFIX` | `campus-grab-` | `watchlist_runner.py` 临时报名单元名前缀；只允许小写字母、数字和短横线且以短横线结尾，不合规启动即报错退出 |
| `GRAB_SCRIPT` | `<LOGIN_DIR>/grab_signup.py` | 报名脚本路径；未设时由 `LOGIN_DIR` 拼出 |

注入位置：

- `campus-autologin.service`（或 drop-in）：配置 `APP_DIR`、`LOGIN_DIR`、`GRAB_UNIT_PREFIX`（线上单元实际带 `--preempt` 运行，仓库里的单元模板未写该参数；配置 `GRAB_UNIT_PREFIX` 后 `preempt_guard.py` 才会跳过正在运行的同名报名单元）。
- `campus-bot.service`（或 drop-in）：配置 `APP_DIR`。
- `watchlist_runner.py` 的 crontab 行：配置 `APP_DIR`、`LOGIN_DIR`、`GRAB_UNIT_PREFIX`（`systemd-run` 临时单元不继承调用方环境，`watchlist_runner.py` 会把已设置的 `APP_DIR`、`LOGIN_DIR`、`GRAB_LOG_FILE`、`PRIVATE_OWNER_OPEN_ID` 经 `--setenv` 传给报名进程）。

## 3. crontab

```cron
0 7  * * * cd /root/campus-activity-watch && PRIVATE_OWNER_OPEN_ID=ou_xxx /usr/bin/python3 scripts/push/run.py --with-grab >> data/cron.log 2>&1
5 7  * * * cd /root/campus-activity-watch && PRIVATE_OWNER_OPEN_ID=ou_xxx /usr/bin/python3 scripts/push/remind.py            >> data/remind.log 2>&1
30 10 * * * cd /root/campus-activity-watch && /usr/bin/python3 scripts/push/run.py                                          >> data/cron.log 2>&1
30 16 * * * cd /root/campus-activity-watch && /usr/bin/python3 scripts/push/run.py                                          >> data/cron.log 2>&1
30 21 * * * cd /root/campus-activity-watch && /usr/bin/python3 scripts/push/run.py --late-checkin --with-open                >> data/cron.log 2>&1
*/5  * * * * cd /root/campus-activity-watch && /usr/bin/python3 scripts/push/scan.py                                        >> data/scan.log 2>&1
*    * * * * cd /root/campus-activity-watch && PRIVATE_OWNER_OPEN_ID=ou_xxx /usr/bin/python3 scripts/push/activity_watch.py   >> data/activity_watch.log 2>&1
7-59/5 * * * * cd /root/campus-activity-watch && PRIVATE_OWNER_OPEN_ID=ou_xxx /usr/bin/python3 scripts/push/attend_remind.py >> data/attend_remind.log 2>&1
*/15 * * * * cd /root/campus-activity-watch && PRIVATE_OWNER_OPEN_ID=ou_xxx /usr/bin/python3 scripts/login/token_probe.py    >> data/token_probe.log 2>&1
*/30 * * * * cd /root/campus-activity-watch && /usr/bin/python3 scripts/login/token_report.py                                >> data/token_report.log 2>&1
*/5  * * * * cd /root/campus-activity-watch && PRIVATE_OWNER_OPEN_ID=ou_xxx /usr/bin/python3 scripts/ops/net_probe.py      >> data/net_probe.log 2>&1
*/1  * * * * cd /root/campus-activity-watch && PRIVATE_OWNER_OPEN_ID=ou_xxx /usr/bin/python3 scripts/signup/watchlist_runner.py >> data/watchlist.log 2>&1
```

要点：

- 只有需要发**私聊**的行才带 `PRIVATE_OWNER_OPEN_ID`；群推送不需要。
- `activity_watch.py` **每分钟唤醒，但不是每分钟访问学校**：它读 `data/activity_watch.json` 的
  `next_poll_at` 自己控频（白天 3 分钟 / 夜间 10 分钟；**没有**临近开放加密这一档）。
  这样「刚开放那一分钟」能被赶上，又不会变成全天每分钟打接口。
- `activity_watch.py` 那一行现在**必须带 `PRIVATE_OWNER_OPEN_ID`**：本人已报名或排队场次的改期、
  下架与冲突复核对内私聊 owner；没配时只记日志，公共群消息不受影响。`remote_install.sh`
  已给这一行带上该环境变量，老机器升级时如 crontab 里还没有，按需手动补齐。
- `attend_remind.py` 每 5 分钟唤醒（`7-59/5` 错开整点），只有落进提醒窗口的场次才查 `getInfo`，
  同一场当天只查一次；没有临近场次时一次 `getInfo` 都不调。去重状态在 `data/attend_remind.json`，
  发送成功才记，错过窗口不补发。
- 所有行都 `cd` 到应用目录——脚本里用的是 `data/...` 相对路径。
- 改完用 `crontab -l` 复核，别用编辑器覆盖整个 crontab（历史上因此丢过行）。

## 4. 日志

| 文件 | 内容 |
|------|------|
| `data/cron.log` | 定时推送的成功/失败、异常堆栈 |
| `data/remind.log` | 07:05 私聊提醒 |
| `data/scan.log` | 临近提醒（开放前 10 分钟） |
| `data/activity_watch.log` | 动态监测：每轮一行（活动库条数、事件数、下次时间、用时）；失败与退避、私聊变动通知是否发出也在这里 |
| `data/attend_remind.log` | 开始与签退提醒：每轮选中哪些场次、发了什么、没发的原因（未知详情、错过窗口、已发过） |
| `data/token_probe.log` | 每 15 分钟一行：`时间 token=指纹 saved_at=… age=… result=ok|fail|…` |
| `data/token_report.log` | token 寿命汇总 |
| `data/net_probe.log` | 出网自检：`result=ok|fail|http-error` |
| `data/watchlist.log` | 预报名状态流转 |
| `/root/campus-login/refresh.log` | 守护进程每次校验结果 |
| `/root/campus-login/auto_login.log` | 无人值守重登的尝试与结果 |

日志里**不应出现** token、姓名、学号、密码、验证码；看到这类内容按事故处理。

### 日志轮转

上面所有 `*.log` 都由 `deploy/logrotate/campus` 统一轮转：每周一次、保留 8 份、超过 5MB 提前切、切后 gzip。

```bash
sudo install -m 644 deploy/logrotate/campus /etc/logrotate.d/campus
sudo logrotate -d /etc/logrotate.d/campus   # 只看不切
```

配置用 `copytruncate` 而不是默认的"改名 + 新建"：cron 和服务都是 `>>` 追加写、不重开文件，改名会让它们继续写进已改名的旧文件，新文件一直是空的。原地截断则不换 inode，追加写自动接上。

## 5. 日常操作

```bash
# 手动跑一轮推送（不写去重状态）
cd /root/campus-activity-watch && python3 scripts/push/run.py --dry

# 强制真推一次（会写 announced，慎用）
cd /root/campus-activity-watch && python3 scripts/push/run.py --force

# 补发今天的私聊提醒（07:05 漏发时）
cd /root/campus-activity-watch && PRIVATE_OWNER_OPEN_ID=ou_xxx python3 scripts/push/remind.py

# 换 token（本机登录后）
scp -i ~/.ssh/<私钥文件名> data/storage_state.json root@<你的服务器IP>:/root/campus-login/
ssh root@<你的服务器IP> 'cd /root/campus-login && node server_refresh.js'

# 看预报名清单
cd /root/campus-activity-watch && python3 scripts/signup/watchlist.py list

# 动态监测：只看这一轮会发什么，不发送、不写状态
cd /root/campus-activity-watch && python3 scripts/push/activity_watch.py --dry-run --force

# 动态监测：忽略排期立刻跑一轮（真发）
cd /root/campus-activity-watch && python3 scripts/push/activity_watch.py --force

# 手动跑一轮开始/签退提醒（真发；已发过的按 data/attend_remind.json 去重）
cd /root/campus-activity-watch && PRIVATE_OWNER_OPEN_ID=ou_xxx python3 scripts/push/attend_remind.py

# 对比某条活动的「原定开放 / 本次发现 / 上次状态」
python3 -c "
import json;d=json.load(open('/root/campus-activity-watch/data/activity_watch.json'))
for k,v in d['activities'].items(): print(k, v['status'], v['sign_start'], v['discovered_at'])"

# 手工加/删预报名
python3 scripts/signup/watchlist.py add --id <id> --name <名称> --at "2026-10-30 12:00:00"
python3 scripts/signup/watchlist.py remove --id <id>
```

## 6. 部署更新

本地改完 → 自检 → 传文件 → 重启对应服务：

```bash
# 1) 本地自检（不联网、不发消息）
python -m compileall server/scripts
node --check server/bot/bot.js
python server/tests/test_endpoints.py && python server/tests/test_notify.py
python -m unittest server.tests.test_activity_watch -v
node server/bot/test_bot_runtime.js

# 2) 传文件（只传改动的那几个，别整套覆盖 data/）
scp -i ~/.ssh/<私钥文件名> server/scripts/<分类>/<file>.py root@<你的服务器IP>:/root/campus-activity-watch/scripts/<分类>/
scp -i ~/.ssh/<私钥文件名> server/bot/bot.js        root@<你的服务器IP>:/root/campus-bot/bot.js

# 3) 重启（combined 只有一个进程）
ssh root@<你的服务器IP> 'systemctl restart campus-bot && systemctl is-active campus-bot'
```

### 直发签名报名上线清单（2026-11-24）

1. **安装新依赖**：在服务器 Python 环境安装 `cryptography`（`python3 -m pip install -r server/requirements.txt` 或单独装 `cryptography>=41.0`）；缺失或加载失败时脚本会自动退回点击兜底，不自造加密。
2. **同步登录目录全部同目录模块**：`grab_signup.py` 按文件路径运行并从同目录导入子模块，务必把 `server/deploy/signup/grab_signup.py` 与所有 `signup_*.py` 一起同步到 `<LOGIN_DIR>`，把 `server/deploy/login/auto_login.py` 与 `preempt_guard.py` 一起同步到 `<LOGIN_DIR>`（同目录，不要只拷入口文件）。
3. **补全 `campus-autologin.service` drop-in**：补充 `Environment=GRAB_UNIT_PREFIX=<你的前缀>`（与 `watchlist_runner.py` 一致），并确认线上 `ExecStart` 带 `--preempt`。
4. **上线前先跑一次只读演练**（不发 `signUp`、不发私聊，需在服务器上由操作人手动执行）：

```bash
APP_DIR=/root/campus-activity-watch LOGIN_DIR=/root/campus-login \
  python3 /root/campus-login/grab_signup.py --activity-id <活动id> --at "2026-11-24 12:00:00" --rehearse
```

`data/` 与 `config.json` 属于线上状态，**不要**从本地覆盖。
`data/activity_watch.json` 属于线上状态：删掉它会让现有活动全部重发一轮「首次发现」，
升级时不要顺手清理。

## 7. 回滚

- 脚本级：保留上一版文件（`scp` 前先 `cp x.py x.py.bak-YYYYMMDD`），出问题换回并重启服务。
- 整机级：历史迁移时旧服务器（<旧服务器IP>）已清理，回滚只能靠本仓库代码 + `data/state.json` 重建；
  如需再迁移，按「备份 → 还原目录 → 装 cron/systemd → 校验 token → 手工推一轮」的顺序做。

## 8. 故障处理

| 现象 | 排查顺序 |
|------|----------|
| 群里没消息 | `cron.log` 有没有 `[✓] 飞书 卡片推送成功` → 失败看错误码（11232 = 飞书整点限流，已自动重试）→ 再看 token |
| 新活动过了很久才出现 | `activity_watch.log` 尾部：`未到下一轮时间` 说明控频正常；`第 N 次连续失败` 说明抓取在退避；两者都没有但无事件，看 `data/activity_watch.json` 里该活动是否已有 `discovered_at` |
| 动态监测完全不动 | `config.json` 的 `watch.enabled` 是否被写成 false；`data/activity_watch.json` 是否损坏（日志会写「解析失败」，原文件不会被动） |
| 私聊没消息 | `remind.log` / `watchlist.log` 是否出现「未配置 PRIVATE_OWNER_OPEN_ID」；`users.json` 的 p2p 记录与 `private_chat_id` 是否一致 |
| 开始 / 签退提醒没到 | `attend_remind.log`：cron 行是否为 `7-59/5`、是否出现「未配置 PRIVATE_OWNER_OPEN_ID」；`data/attend_remind.json` 的 `sent` 里是否已有「场次 + start/checkout」；错过窗口不补发是设计 |
| 场次变动没收到私聊 | `activity_watch.py` 的 cron 行是否带 `PRIVATE_OWNER_OPEN_ID`；`data/personal_notice.json` 里是否还压着发不出去的通知；公共群消息有没有照常到达 |
| 私聊点「取消报名」没出确认卡 | `journalctl -u campus-bot` 里 `cancel confirm card failed`；在应用目录手跑 `python3 scripts/signup/cancel_signup.py confirm --id <id> --name <名称>` 看那一行 JSON |
| 登录态失效 | `token_probe.log` 尾部 `result=fail` → 看 `/root/campus-login/auto_login.log` 是否已自动重登 → 不行就本机 `login.py` 后传 `storage_state.json` |
| 接口 timeout / handshake | `net_probe.log`：`net=school-only` 是学校侧，`net=down` 是整机断网；ECS 带宽为 0 时表现为 TLS 握手超时 |
| 自动登录失败 | `auto_login.log` 里 `login_rejected` / `ocr_incomplete`；确认 `credentials.json` 存在且 600、账号密码没改 |
| 机器人不响应 | `systemctl status campus-bot`、`journalctl -u campus-bot -n 50`；长连接断开会自动重连，反复断查应用凭据 |
| 机器人进程 failed 且日志有 `BOT_ROLE` | 单元里写的是拆分时代的旧值（或缺失）；改成 `BOT_ROLE=combined` 的单 `campus-bot.service` |
| 群里点预报名没反应 | 群入口只读（设计如此）；要预报名请用 owner 私聊里的卡片，或本机工具 |
| 按钮点了没反应 | 私聊卡片按钮只对 owner 私聊生效（`operator.open_id` + 会话 chat_id 双校验）；群里点会 toast 拒绝；`journalctl` 里看 `card action ... -> chat:` 是否解析到了会话语境 |

## 9. 迁移记录（2026-10-21）

- 从 `<旧服务器IP>`（Alibaba Cloud Linux 3）迁到 `<你的服务器IP>`（Ubuntu 22.04）。
- 旧机：cron 行注释前缀 `#MIGRATED-20261021-2230`、服务 `disable --now`，验证后于 2026-10-22 彻底删除应用目录、systemd 单元、nginx 中的 trigger 路由与备份。
- 教训：迁移当夜新 ECS 出口带宽为 0，表现为「TCP 能连、SSH banner 超时、TLS 握手超时」，一度误判为 fail2ban；这类故障先查带宽/安全组。
- 旧机上手机一键触发链接（`<你的域名>/0f4b…` → `127.0.0.1:18080`）随旧机清理失效；如需恢复，应在新机部署 HTTPS 反代指向 `campus-trigger`。
