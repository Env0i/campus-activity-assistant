# server 使用情况与 token 寿命材料核对（2026-11-02）

## 结论

1. 本仓库里的 server 侧数据**停在 2026-10-21 00:08**，此后没有任何运行落盘。但这只能说明「桌面端这份副本没有新数据」，不能说明远程没在跑——2026-10-21 做过整机迁移，真实运行数据在新 ECS 上，不在本仓库。
2. `server/reports/token-lifetime.md` **不存在**。`server/reports/` 只有 3 份日报（10-19 / 10-20 / 10-21）和 `latest.md`。
3. 「17.5 小时」只作为**单次观测**出现在三处，没有任何报告文件支撑；也没有「同一登录失败后又恢复」的记录可查。

## 证据

| 项 | 值 | 出处 |
|---|---|---|
| 报告最新一份 | 2026-10-21 00:08 | `server/reports/latest.md`（内容与 `2026-10-21.md` 相同） |
| `last_run` | `2026-10-21 00:08:32` | `server/data/state.json` |
| `last_push_ts` | 与 `last_run` 同一时刻 | 同上 |
| 迁移 | 2026-10-21 迁到新 ECS；旧机 10-22 删除应用目录、systemd 单元、nginx 路由 | `docs/OPERATIONS.md` §9（`:192-195`） |
| 17.5 小时 | 单次观测 | `CHANGELOG.md:379`、`design/decisions/008-lifecycle-version-release.md:32`、`design/README.md:105` |
| 10–17 小时 | 现行口径「实测约 10–17 小时，仅提醒」 | `design/README.md:105` |

## 能回答 / 不能回答

- **能回答**：桌面端副本里 server 最后一次运行是 2026-10-21 00:08，此后无写入；`token-lifetime.md` 从未生成过。
- **不能回答**：远程 ECS 现在是否在运行、群卡片还有多少人看、最近 7 天成功/失败。这些都在新机上，桌面端没有任何代理证据。
- **需要什么**：对新 ECS 做一次只读检查（`systemctl status`、最近 7 天日志摘要），或由维护者贴结果。

## 复现

```bash
ls -l server/reports
python -c "import json;print(json.load(open('server/data/state.json'))['last_run'])"
ls server/reports/token-lifetime.md    # 预期 No such file or directory
```

> `server/data/` 与 `server/reports/` 在部署机上生成，本副本不含这两个目录；命令需在运行时机器上执行。
