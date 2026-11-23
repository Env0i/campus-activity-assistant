# 手机页分支收口：全量离线回归与合回主干前提

- **日期**：2026-11-23
- **分支**：`refactor/phone-page`，开工 HEAD `7c6f998`
- **结论**：全量离线回归通过，0 失败；相对 `main`（`7922aa2`）领先 67 个提交、落后 0 个，合回主干是快进。合并与推送没有执行，由用户完成。

## 1. 全量离线回归

跑之前清空 `http_proxy` / `HTTP_PROXY` / `https_proxy` / `HTTPS_PROXY` / `all_proxy`，设 `PYTHONIOENCODING=utf-8`；本机版全量在后台运行，跑完再读结果。

| 检查项 | 命令 | 结果 | 用时 |
|---|---|---|---|
| 本机版全量 | `python -m unittest discover -s local/tests -p "test_*.py"` | **2,877 项，0 失败，2 跳过，OK** | 219.4 秒 |
| 服务器版 pytest | `python -m pytest server/tests --ignore=server/tests/test_dedup.py --ignore=server/tests/test_endpoints.py --ignore=server/tests/test_notify.py` | **123 项通过，0 失败，0 跳过** | 1.17 秒 |
| Node 机器人运行时 | `node server/bot/test_bot_runtime.js` | **37 项，0 失败** | 0.3 秒 |
| Node 已处理消息 | `node server/bot/test_handled_messages.js` | **8 项通过** | 0.1 秒 |
| Node 原子写 | `node server/deploy/test_atomic_json.js` | **6 项，0 失败** | 0.2 秒 |
| 语法检查 | `python -m compileall -q local server` | **退出码 0** | 0.3 秒 |
| 前端脚本语法 | `local/ui` 下递归 99 份 `.js` 逐个 `node --check` | **99 份，0 失败** | 5.9 秒 |
| 代码形状 | `python tools/code_shape/check.py` | **通过**：文件 >800 行 9 个、501–800 行 11 个；函数 >100 行 23 个、61–100 行 67 个；测试函数 >60 行 19 个；属性超标的类 2 个 | 1.8 秒 |
| 静态检查 | `python -m ruff check local server tools` | **All checks passed** | 0.2 秒 |

- 全量输出里有既有的 `ResourceWarning` 与旧数据迁移提示，没有测试失败。
- 本轮没有出现偶发失败，因此没有单测文件需要单独重跑。
- 服务器版跳过三个脚本式文件：`test_dedup.py` 会改写 `server/data/state.json`，`test_endpoints.py` 与 `test_notify.py` 在 `server/tests/` 的说明里列为脚本式运行，pytest 收集不到。

## 2. 合回主干前提

| 项目 | 值 |
|---|---|
| `main` | `7922aa2` |
| 分支 HEAD（开工时） | `7c6f998` |
| `git rev-list --count main..HEAD` | 67 |
| `git rev-list --count HEAD..main` | 0 |
| 合并方式 | 快进，无冲突 |
| 开工工作区 | 干净 |

本轮没有 merge、rebase、提交或推送；合并由用户在审计后执行。

## 3. 手机页这一段的交付摘要

| 批次 | 交付 | 关键数字 | 证据 |
|---|---|---|---|
| 拆分 | `local/ui/m/app.js` 按原逻辑、原命名、原顺序拆成 12 份普通脚本 | 3,365 行 → 12 份、合计 3,421 行，单份 ≤500 行；无头 Edge 加载通过 | [phone-split](../../2026-11-21/phone-split/README.md) |
| 会话收拢 | 请求与配对会话组三处重复收成 `adoptCookieCsrf`、`showAppView`、`showPairView`、`sessionVerdict` | 72 条变异复跑仍为行为守 66、等价 6、无人守 0 | [phone-session-tidy](../phone-session-tidy/README.md) |
| 安全网 | 五组 DOM 层函数逐组做单点变异并补行为用例 | 67 个函数、665 条变异；补测后行为守 645、等价 20、无人守 0 | [phone-net](../../2026-11-22/phone-net/README.md)、[phone-render-net](../phone-render-net/README.md)、[phone-plan-net](../phone-plan-net/README.md)、[phone-relogin-net](../phone-relogin-net/README.md)、[phone-shell-net](../phone-shell-net/README.md) |
| 顺带修复 | 同一分支上的修复：举办时间待公布时开始前拦截；业务时钟未校准时分组不读手机时钟；开放、截止、冲突与取消时刻改读电脑给的值；时间筛选不再全空、重选跳过已截止；重登失败原因在抽屉红条可见；另有登录结论四态、转人工标记、桌面列表截止判定与登录转人工提示等 | `fix(` 开头的提交共 11 个（手机页 9、桌面 2），用 `git log --oneline main..HEAD --grep="^fix("` 列出 | [phone-act-pending](../phone-act-pending/README.md)、[phone-open-state](../../2026-11-22/phone-open-state/README.md)、[phone-conflict-times](../../2026-11-22/phone-conflict-times/README.md)、[real-env-smoke](../real-env-smoke/README.md) |
| 验收 | 真实 Chromium 与重打包 EXE 两环境冒烟；iPhone Safari 真机复测 | 包内 `ui/m` 16 份资源与源码逐字节一致；窗口 1280×820 正常渲染 | [real-env-smoke](../real-env-smoke/README.md) |

五组安全网的分布：

| 分组 | 目标文件（函数数） | 变异总数 | 补测后（行为守 / 等价 / 无人守） |
|---|---|---:|---|
| 请求与配对会话 | `ui-session.js`（16） | 72 | 66 / 6 / 0 |
| 摄入与渲染 | `ui-sync.js`、`ui-status.js`、`ui-list.js`（23） | 226 | 220 / 6 / 0 |
| 计划操作 | `ui-plan.js`（13） | 97 | 96 / 1 / 0 |
| 重新登录 | `ui-relogin.js`（8） | 129 | 128 / 1 / 0 |
| 外壳与接线 | `ui-shell.js`（7） | 141 | 135 / 6 / 0 |
| **合计** | **67 个 DOM 函数** | **665** | **645 / 20 / 0** |

## 4. 仍未验

与 [real-env-smoke](../real-env-smoke/README.md) 第 5、8 节一致，不增不减：

- Android Chrome 与真机触摸事件（iPhone Safari 已复测）。
- 真实 Tailscale / Cloudflare 通道、真实学校接口与真实登录失效链路。
- 真实学校的手机重登验证码提交与成功回调（离线替身已走通，未连学校）。
- 设备信任 cookie 在程序重启后的免配对恢复。
- 抽屉点遮罩关闭、焦点归还与屏幕阅读器语义。
- 打包 EXE 里开启手机访问组件的端到端路径。
- 高 DPI、多显示器与最小窗口尺寸下的布局。

## 5. 证据目录

- [phone-split（2026-11-21）](../../2026-11-21/phone-split/README.md)
- [phone-net（2026-11-22）](../../2026-11-22/phone-net/README.md)
- [phone-open-state（2026-11-22）](../../2026-11-22/phone-open-state/README.md)
- [phone-conflict-times（2026-11-22）](../../2026-11-22/phone-conflict-times/README.md)
- [phone-session-tidy（2026-11-23）](../phone-session-tidy/README.md)
- [phone-render-net（2026-11-23）](../phone-render-net/README.md)
- [phone-plan-net（2026-11-23）](../phone-plan-net/README.md)
- [phone-relogin-net（2026-11-23）](../phone-relogin-net/README.md)
- [phone-shell-net（2026-11-23）](../phone-shell-net/README.md)
- [phone-act-pending（2026-11-23）](../phone-act-pending/README.md)
- [real-env-smoke（2026-11-23）](../real-env-smoke/README.md)

## 6. 复现命令

在仓库根执行（Python 3.12）：

```bash
python -m unittest discover -s local/tests -p "test_*.py"
python -m pytest server/tests --ignore=server/tests/test_dedup.py --ignore=server/tests/test_endpoints.py --ignore=server/tests/test_notify.py
node server/bot/test_bot_runtime.js
node server/bot/test_handled_messages.js
node server/deploy/test_atomic_json.js
python -m compileall -q local server
python tools/code_shape/check.py
python -m ruff check local server tools
git rev-list --count main..HEAD
git rev-list --count HEAD..main
```

前端脚本逐个检查（PowerShell）：

```powershell
Get-ChildItem local/ui -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
```
