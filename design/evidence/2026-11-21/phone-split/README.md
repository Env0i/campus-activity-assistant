# 手机页脚本按原样拆分为 12 份普通脚本

- **分支**：`refactor/phone-page`
- **基线提交**：`c68d426`

## 1. 拆分范围

将 `local/ui/m/app.js`（原 3365 行）按原逻辑、原命名与原相对次序拆分为 `local/ui/m/` 下 12 份普通脚本，删除 `local/ui/m/app.js`，并同步完成以下配套调整：

- `local/ui/m/index.html`：将 `<script src="app.js"></script>` 替换为按依赖顺序排列的 12 个普通 `<script src="...">` 标签（不加 `defer`、`async` 或 `type`）；
- `local/infrastructure/phone_http.py`：在 `PHONE_STATIC` 中移除 `/app.js`，按同顺序登记 12 条 `text/javascript; charset=utf-8` 静态条目；
- `tools/code_shape/baseline.json`：移除 `local/ui/m/app.js` 文件超限条目，并将 `buildRow`、`ingest`、`wire`、`buildWhy`、`ingestRelogin`、`reloginView`、`renderBoard`、`renderItems` 8 个函数的键改为对应新文件路径（数值与 reason 不变）；
- `local/tests/test_phone_ui.py`、`local/tests/test_phone_infra.py`、`local/tests/test_retry_policy.py`：测试脚本装载改以 `index.html` 清单为唯一来源（并让假 DOM 的 `getElementById` 兼容前导 `#`），新增静态表与脚本清单双向守卫、顶格声明唯一性与加载顺序/单点启动守卫，不改任何原有业务断言（详情见 `changed-tests.md`）。

## 2. 12 份新文件清单与行数

按 `local/ui/m/index.html` 加载顺序排列：

| 序号 | 文件名 | 行数 | 装载内容 |
|---:|---|---:|---|
| 1 | `model.js` | 232 | 原文件头注释、`PhoneModel` 核心成员（`newRequestId` 至 `actionable`） |
| 2 | `model-conflict.js` | 282 | 经 `Object.assign(PhoneModel, ...)` 补齐冲突原因、跨天时段、报后可退、可取消至、顶底栏摘要成员 |
| 3 | `model-list.js` | 273 | 经 `Object.assign(PhoneModel, ...)` 补齐列表与详情板聚合成员 |
| 4 | `model-run.js` | 341 | 经 `Object.assign(PhoneModel, ...)` 补齐运行与等待、结果页与条款态、核对计划与更多面板成员 |
| 5 | `model-relogin.js` | 263 | 经 `Object.assign(PhoneModel, ...)` 补齐重新登录面板与配对点阵屏成员，末尾保留 `globalThis.PhoneModel` 导出 |
| 6 | `ui-session.js` | 296 | DOM 层分隔注释、`$`、`REQUEST_TIMEOUT_MS`、`readCookie`、`model` 状态对象及请求与配对轮询 15 个函数 |
| 7 | `ui-status.js` | 362 | 提示条、离线与条款告警、控件门禁、底栏、计划板、四站进度、任务卡与日志共 13 个函数 |
| 8 | `ui-list.js` | 339 | `LIST_ZONES` 常量、列表行与原因面板构造、跳转已报名行、列表重画与整页搜索开合 |
| 9 | `ui-sync.js` | 221 | 整秒时钟/点阵屏/行倒计时局部刷新（4 个函数）与快照增量摄入 `ingest` |
| 10 | `ui-plan.js` | 251 | 计划启停、对账、取消等待/单场、结果重置、重试设置与核对抽屉共 13 个函数 |
| 11 | `ui-relogin.js` | 282 | 重新登录抽屉呈现、打开入口、验证码图控制、提交/取消/换图与流程状态摄入共 8 个函数 |
| 12 | `ui-shell.js` | 279 | `SHEET_TITLES`、抽屉外壳与确认槽、`wire`、`globalThis.PhoneUI` 导出与末尾 `readyState` 启动两行（须排最后） |
| **合计** | **12 份** | **3421** | 每份均未超过 500 行上限 |

## 3. 为什么采用普通脚本而非 ES Modules

根据两次 iPhone Safari 实测（`design/evidence/2026-11-12/esm-verify/` 与 `design/evidence/2026-11-21/keepalive-probe/`）：

- 在 Cloudflare 临时隧道上，40 个普通脚本在 15 次实测中全部在 10 秒内完成加载与执行；
- 40 个 ES 模块的三种加载形态（`flat`、`chain`、`preload-chain`）无论是否开启 HTTP/1.1 连接复用（`keepalive`），都在 Cloudflare 隧道上出现过 10 秒内未执行任何模块的情况，且服务端请求日志显示缺失的子模块请求根本没有到达电脑（卡在隧道或浏览器前）。

Cloudflare 临时隧道是 Tailscale 不可用时的备用通道，因此手机页采用少量按 `index.html` 顺序加载的普通脚本，不赌 ES Modules 在临时隧道上的并发加载稳定性。

## 4. 验证汇总

| 检查项 | 结论 | 详细说明与证据 |
|---|---|---|
| `move-check` 逐字核对 | **PASS**（0 项失败） | 101 个 `PhoneModel` 成员、72 个 DOM 顶层声明（67 函数 + 5 常量）及 3296 行非空原文频次与 `HEAD:local/ui/m/app.js` 逐字一致，见 `move-check.md` |
| 代码形状检查 | **PASS** | `python tools/code_shape/check.py` 与 `test_code_shape.py`（15/15）全部通过 |
| 手机相关测试（改前基线） | **全部通过** | `test_phone_ui.py`：237 通过 / 0 失败 / 0 跳过；`test_phone_infra.py`：46 通过 / 0 失败 / 0 跳过；`test_retry_policy.py`：74 通过 / 0 失败 / 0 跳过 |
| 手机相关测试与本机全量（改后） | **全部通过** | `test_phone_ui.py`：239 通过（+2 守卫）；`test_phone_infra.py`：47 通过（+1 守卫）；`test_retry_policy.py`：74 通过；`test_ui_contracts.py`：374 通过；本机全量 `local/tests`：2785 通过 / 0 失败 / 2 跳过（另已完成 10 项守卫变红反证，见 `changed-tests.md`） |
| `net-after-move` 安全网复跑 | **PASS**（0 条偏差） | 72 条单点变异在新文件 `ui-session.js` 位置复跑结果与 `phone-net/after.md` 完全一致（66 条行为守、6 条等价），见 `net-after-move.md` |
| `load-order` 加载顺序反证 | **PASS**（3 次全红） | 删去 `ui-plan.js`、`ui-shell.js` 前置、对调 `model.js` 与 `model-conflict.js` 三次反证均使 `test_phone_ui.py` 立即变红，第 1 次同时使 `test_phone_infra.py` 变红，见 `load-order.md` |
| `edge-load` 真 Edge 加载核对 | **PASS** | 无头 Edge（`390×844`）下工作区 12 份脚本全部 HTTP 200（`text/javascript; charset=utf-8`），控制台/页面/请求错误均为 0；73 个顶格声明与 `about:blank` `window` 自带属性交集为空；配对前后规整 `body` DOM 与 `HEAD` 完全一致，见 `edge-load.md` 与 `edge/` |
| `device` iPhone 真机核对 | **PASS** | Tailscale 与 Cloudflare 临时通道均已确认通过，见下方第 5 节 |

## 5. 真机核对结果（iPhone Safari）

用户从源码启动产品并在「设置 → 手机访问」开启手机访问，按清单核对结果如下：

1. **Tailscale 通道**：**通过**（iPhone Safari 配对后正常显示主界面，且能打开再关上「更多」面板）。
2. **Cloudflare 临时通道**：**通过**（登记本机通过校验的 `cloudflared` 后开启 Cloudflare 临时通道，iPhone Safari 配对后正常显示主界面，且能打开再关上「更多」面板）。

## 6. 未验证项

- 打包后的 EXE（PyInstaller 冻结态）内手机页静态资源加载未实测；
- 安卓手机浏览器与微信内置浏览器未实测。

## 7. 复现命令

在仓库根执行（Python 3.12；运行前清空 `http_proxy` / `HTTP_PROXY` / `https_proxy` / `HTTPS_PROXY` / `all_proxy`，证据脚本使用 `tempfile.gettempdir()` 下的独立临时目录）：

```bash
# 1. 逐字核对与代码形状检查
python design/evidence/2026-11-21/phone-split/scripts/move_check.py
python tools/code_shape/check.py

# 2. 手机相关单测与本机全量
python -m unittest discover -s local/tests -p "test_phone_ui.py" -v
python -m unittest discover -s local/tests -p "test_phone_infra.py" -v
python -m unittest discover -s local/tests -p "test_retry_policy.py" -v
python -m unittest discover -s local/tests -p "test_code_shape.py" -v
python -m unittest discover -s local/tests -p "test_*.py"

# 3. 安全网复跑与无头 Edge 核对
python design/evidence/2026-11-21/phone-split/scripts/net_after_move.py --workers 4
python design/evidence/2026-11-21/phone-split/scripts/edge_load.py
```
