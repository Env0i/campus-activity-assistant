# 服务器目录迁移与环境变量改造记录（2026-11-24）

- **日期**：2026-11-24
- **范围**：同步全仓库目录结构整理后的服务器脚本布局，并将部署路径与报名单元前缀改为环境变量可覆盖。

## 实测部署布局

应用目录下直接是 `scripts/`（含 `lib/`、`login/`、`push/`、`signup/`、`ops/` 五个分组子目录）、`bot/`、`deploy/`、`data/`、`reports/`，不带 `server/` 这一层。

- `config.json` 已补齐 `site.base`（学校站点根地址，未配置时 `site_target` 会拒绝请求）。
- 线上用的是另一个前缀，经环境变量注入。

## 逐字节核对结论

迁移完成后将线上脚本与仓库逐字节比对，差异仅限部署前缀相关的 **5 个文件 8 行**：

1. `auto_login.py`（`LOGIN_DIR`、`APP_DIR`）
2. `grab_signup.py`（`LOGIN_DIR`、`APP_DIR`）
3. `watchlist_runner.py`（`GRAB` 默认脚本路径、`unit_name` 单元前缀）
4. `run.py`（告警文案中的 `cron.log` 路径）
5. `bot.js`（`APP_DIR`，此前已支持环境变量，systemd 已注入）

## 验证项与备份保留期

- **验证项**：crontab 路径已切换至 `scripts/<分类>/...`；`auto_login.py --check`、`watchlist_runner.py --dry-run`、日报与动态监测、机器人长连接均正常运行。
- **备份保留期**：迁移前旧目录与脚本备份保留 7 天，确认连续稳定运行无异常后清理。

## 本次改动上线步骤（补环境变量并同步文件）

1. **补充环境变量**（线上用的是另一个前缀，经环境变量注入）：
   - 在 `campus-autologin.service`（或 drop-in）中注入 `APP_DIR`、`LOGIN_DIR`。
   - 确认 `campus-bot.service`（或 drop-in）已注入 `APP_DIR`。
   - 在 `watchlist_runner.py` 的 crontab 行中注入 `APP_DIR`、`LOGIN_DIR`、`GRAB_UNIT_PREFIX`（`watchlist_runner.py` 会将已设置的 `APP_DIR`、`LOGIN_DIR`、`GRAB_LOG_FILE`、`PRIVATE_OWNER_OPEN_ID` 通过 `systemd-run --setenv` 透传给临时报名单元）。
2. **同步文件**：
   - 将仓库中的 `server/deploy/login/auto_login.py`、`server/deploy/signup/grab_signup.py` 同步到线上登录目录。
   - 将 `server/scripts/signup/watchlist_runner.py`、`server/scripts/push/run.py` 同步到线上应用目录 `scripts/` 对应子目录。
   - 同步后线上这 5 个文件与仓库逐字节一致，后续升级不再手工改路径。
3. **上线复核**：
   - 执行 `python3 scripts/signup/watchlist_runner.py --dry-run`，确认输出的单元名前缀与环境变量一致。
   - 执行 `python3 <登录目录>/auto_login.py --check` 与 `systemctl status campus-bot campus-login campus-autologin.timer`，确认状态正常。
