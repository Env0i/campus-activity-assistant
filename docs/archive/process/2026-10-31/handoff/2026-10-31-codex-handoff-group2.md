# 交接给 Codex：组2 卡在哪、这一轮改了什么、又发现了什么

日期：2026-10-31（晚）
仓库状态：HEAD `3cab0d6`，`git status --short` 62 项（含入场 WIP），**零提交**
自动化：`python -X utf8 -m unittest discover -s local/tests -p "test_*.py"` → 1406 tests OK (skipped=4)

---

## 0 一句话

组1 全过，组2 的四步里 2.1、2.3、2.4 也过，**只有 2.2（Cloudflare 通道 / 安装手机控制组件）没过**。
为补它做的「组件与通道」对话框被用户判为「太麻烦，懒得用了」（原话见第 4 节），
所以这一块的**设计需要重做**，不是继续修。

---

## 1 现在到哪了

| 项 | 结论 | 依据 |
|---|---|---|
| 组1 正常使用与自适应刷新 | 通过 | 用户确认；`data/phone.log` 里同步间隔从每秒一次变为稀疏轮询 |
| 2.1 Tailscale 重启免配对 | 通过 | 用户确认；设备信任文件更新 |
| 2.2 Cloudflare 通道 / 安装组件 | **未通过** | 面板显示「Cloudflare 临时地址 不可用 / 没有找到 cloudflared」，且当时没有任何安装入口 |
| 2.3 会话失效回配对页 | 通过 | 日志：关闭访问撤销会话 → `GET /api/state 401 need_pair` → 重新配对成功 |
| 2.4 过时提示与错误提示 | 通过 | 用户确认「其他都没问题」 |

自动化侧：1406 tests OK，`compileall local server` 0，`node --check` 三支 JS 0，
`git -c core.whitespace=cr-at-eol diff --check` 干净。

---

## 2 你上次给的 plan 之外，我们又改了哪些（按轮次）

| 轮次 | 主题 | 主要文件 |
|---|---|---|
| A | 手机访问返修 6 任务：组件信任边界（`build_advanced.py` 缺 `--cloudflared` 必须失败、`component_packages` 强制声明 cloudflared、`tunnel_manager` 只认组件包）、合法 PNG 夹具、`submit_pending` 对账、隐藏唤回门禁、文档同步 | `local/build/build_advanced.py`、`local/infrastructure/{component_packages,tunnel_manager}.py`、`local/application/{login_relay_service,phone_service}.py`、`local/app.py`、`local/ui/{m/app.js,controllers/window.js,index.html,views/phone.js}`、`docs/PHONE_ACCESS.md`、`local/README.md` |
| B | 隐藏缺陷返修：隧道异常退出必须同轮收口且不被第二次 `status()` 降级；组件每次启动前重新校验；关闭偏好先做后记 | `local/app.py`、`local/infrastructure/tunnel_manager.py` |
| C | 真机发现 D1/D2/D3：写请求每次按当前 cookie 取 CSRF；`fetch` 8 秒超时；`idle` 快照不再写成「重登结束」 | `local/ui/m/app.js` |
| D | 自查 E1/E2：写动作统一 `postAction` 兜底；`401` 与 `403` 分流（403 不再踢回配对页） | `local/ui/m/app.js` |
| E | 验证码分工：`public_state()` 增 `origin`；`_MANUAL_RELOGIN_AFTER = 3`；OCR 就绪时手机不收图、`phone_relogin_begin` 转自动；手机页单飞锁 | `local/application/login_relay_service.py`、`local/app.py`、`local/ui/m/app.js` |
| F | 手机页第二轮：验证码整组（图+输入框+三个按钮）一起收；离线提示条、刷新按钮「刷新中…」、吸顶 | `local/ui/m/{index.html,app.js,styles.css}` |
| G | 自适应同步：空闲 15 秒 / 活动 2 秒、`staleAfterMs` 30 秒、未配对不发请求、401 停表、banner 带种类（只清 `stale_action`） | `local/ui/m/app.js` |
| H | 真机四缺陷：中继增 `live`（区分本场与历史快照）、自动重登不再把「被接管」记成失败、手机页历史成功只写「上次」、组件入口在缺组件时保持可见、`check` 去重后补查一次 + 桌面卡片随事件刷新 | `local/application/{login_relay_service,auto_relogin}.py`、`local/app.py`、`local/ui/{m/app.js,views/phone.js,app.js}` |
| I | 「组件与通道」对话框（本轮新增，见第 4 节） | `local/infrastructure/component_packages.py`、`local/app.py`、`local/ui/{index.html,views/phone.js,styles.css}` |

证据与结论都在 `design/evidence/2026-10-31/mobile-ui-polling-repair.md`（第一至九节）与
`design/evidence/2026-10-31/phone-access-repair-acceptance.md`（第五至七节）。

---

## 3 组2 的 2.2 到底卡在哪

用户看到的：

- 「安装手机控制」按钮**不存在**（`local/ui/views/phone.js` 当时 `phoneInstall.hidden = phoneReady`，
  而源码版 `feature_ready()` 只查 `module_available`，segno 在即 ready，于是按钮永远藏起来）。
- 通道选 Cloudflare 时面板写「没有找到 cloudflared」，但界面上没有任何补装入口。

根因是两条叠在一起：

1. 任务 A 把 `resolve_cloudflared()` 改成**只认组件包**（删掉了 `resource_root/bin` 与 PATH 回退），
   而源码版根本不可能有「手机控制」组件包 → Cloudflare 在源码版里彻底不可用；
2. 打包版才走「导入组件包」这条路，源码版的 `install_advanced_feature()` 走的是 `pip install`，
   点下去既没有文件框也没有回执。

---

## 4 为补 2.2 做的「组件与通道」对话框，以及为什么被判失败

实现：点「安装/更换」弹 `#dlg-components`，三行（手机控制 / 无人值守重登 / Tailscale），
每行「选择文件… → 自检 → 安装这份」，自检会说清选错的是什么（Tailscale 的 exe、别的组件的包、
不是 ZIP、清单不合法、版本不符）。选定的 cloudflared 收进 `data/advanced/cloudflared/`，
manifest 记 version + sha256，复制后再跑一次 `--version` 才认。

用户对这条路线的评价（原话）：

- m02588：「装组件包 完全不正确。这部分设计完全就是依托狗屎……而且这段都不该我告诉你吧？这不都该你想到的吗？」
- m02847：「不对不对，唉，太费劲了你，整的太麻烦了 我是用户我都懒得用了真的。让codex来吧 就组2有问题了。」

结论：**对话框把「装一个组件」变成了用户自己的工作流**（找文件、粘贴路径、自检、再安装），
代价明显高于收益。设计需要重做，方向由 Codex 定；我这轮只把实现留在代码里，不继续加功能。

可考虑的方向（供参考，不是结论）：

- 源码版干脆**不需要组件包**：把 cloudflared 的合法来源收敛成「构建时随包携带」或
  「首次使用一键下载官方二进制并校验哈希」，把选择文件降级成高级选项；
- 或者 Cloudflare 通道在源码版直接不可用、界面只留 Tailscale，把这条路的复杂度全部删掉；
- 若保留手动导入，入口只保留一个「选择 cloudflared.exe」，其余（校验、落盘、通道刷新）全自动，
  不再暴露「自检」这类二级动作。

---

## 5 已知残留与坑（都会让人误判）

1. `local/README.md` 整文件 CRLF：`git diff --check` 会报 22 行 trailing whitespace，
   加 `-c core.whitespace=cr-at-eol` 后 exit 0。**不要为了变绿重写行尾**。
2. `test_signup_plan.WorkerStopLifecycleTests.test_stop_kills_tree...` 在全量并发下偶发
   `ValueError: invalid literal for int() ... ''`（假 worker 还没写 pidfile），单独跑稳定通过，
   属既有测试时序竞态，与这一轮改动无关。
3. 手机页测试装置（`local/tests/test_phone_ui.py` 的 node-vm harness）：`setTimeout` 是登记式替身、
   回调不自动执行，`globalThis.__fetch` 必须返回 `{status, json: async () => ({...})}`。
4. `local/data/phone.log` 是排查手机写请求失败的第一手证据：「GET 200 与 POST 403 bad_csrf 同段出现」
   ≈ 读通写不通（令牌过期/网关错误）。
5. 组2 的 2.2 之后，Cloudflare 通道**从未在真机跑通过**：出临时域名、手机重新扫码都还没验证。

---

## 6 测试与命令

```bash
python -X utf8 -m unittest discover -s local/tests -p "test_*.py"   # 全量 1406
python -X utf8 -m unittest local.tests.test_phone_ui               # 手机页 75
python -X utf8 -m unittest local.tests.test_ui_contract            # 界面契约 233
python -X utf8 -m unittest local.tests.test_application_services   # 应用层 55
python -X utf8 -m unittest local.tests.test_component_packages     # 组件包 14
python -X utf8 -m compileall local server
node --check local/ui/app.js && node --check local/ui/m/app.js && node --check local/ui/views/phone.js
git -c core.whitespace=cr-at-eol diff --check
```

`test_auto_relogin` 必须用 `discover -p test_auto_relogin.py` 跑（它 `from test_login_relay import ...`，
按包路径跑会 ModuleNotFoundError）。

---

## 7 硬约束（沿用 `AGENTS.md` 与既有决策）

- 只服务本人账号：不做多账号、不批量占位、不代他人报名。
- 不改数据模型、登录态机制、学校接口契约。
- 不引入新依赖，除非任务明确要求。
- 提交权在用户手上；本仓库这个工作区可能有别的 agent 同时在改，**不要 `git add -A`**。
- 界面里不出现账号、密码、验证码、token、配对码。
