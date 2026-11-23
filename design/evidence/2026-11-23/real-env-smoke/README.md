# 真实浏览器与冻结 EXE 两环境冒烟

- **执行日期**：2026-11-23
- **分支与基线**：`refactor/phone-page`，HEAD `850ce84`（`chore(aoci): 索引同步外壳与接线组安全网`）
- **核心结论**：手机页在 Chromium 内核的真实浏览器里跑通了配对、列表渲染、筛选、抽屉外壳、计划开始/停止与重登入口；当前源码重新打成 onefile EXE 后，WebView2 窗口正常渲染，包内 `ui/m` 资源与工作区源码逐字节一致。真实手机、真实通道与真实学校链路仍未实测，清单见第 5 节。

## 1. 环境

| 项目 | 值 |
|---|---|
| 系统 | Windows 11 家庭版中文版 10.0.26300 |
| Python | 3.12.9 |
| PyInstaller | 6.22.3 |
| 浏览器自动化 | Trae 内置浏览器会话（Chromium 内核） |
| 本机 Edge | 158.0.4370.33 |
| 本机 Chrome | 157.0.8103.79 |
| WebView2 Runtime | 157.0.4341.60 |

手机页由 `local/dev_phone_preview.py` 在 127.0.0.1 起离线替身服务，静态资源来自真实的 `local/ui/m/`，数据来自 `domain.demo_data`；不连学校、不读真实配置与登录态。没有使用真实手机，也没有开 Tailscale 或 Cloudflare。

## 2. 手机页四组

| 分组 | 做了什么 | 观察到什么 | 结论 |
|---|---|---|---|
| 请求与配对会话 | 打开首页，输入 6 位配对码，点「配对」；随后点顶栏刷新 | 配对页消失，主界面出现，右上角显示「已连接」；刷新后勾选与列表保持 | 通过 |
| 摄入与渲染 | 依次点「可报名」「已报名」「全部」；看板与列表 | 计数分别为 9 / 2 / 11，行数与计数一致；分组头「正在开放 现在就能报 4 场」「今天 3 场」「明天 2 场」；LED 倒计时按北京时间走动；过期登录时顶部出现「电脑上的登录已失效」红条 | 通过 |
| 计划操作 | 勾选「网络安全·数字时代大长城」，点「核对并开始」，在抽屉里选「直到报名截止」后点「开始报名计划」；再点「停止计划」并确认 | 底栏显示「已选 1 场」；核对抽屉列出该场、尝试时长与最多提交次数；开始后进入「即将开放 / 准备报名」看板，出现任务卡与「停止计划」；停止弹「停止报名计划？」（继续计划 / 停止计划），确认后回到活动列表 | 通过（后端为临时离线替身，见第 6 节） |
| 重新登录 | 过期登录态下点红条里的「重新登录」，再点「取消」 | 抽屉标题「在手机上重新登录」，说明「电脑会自动填账号密码，你只要输验证码。」，有登录/取消；取消后回到活动列表 | 入口与外壳通过；验证码提交未触发 |
| 外壳与接线 | 点顶栏「更多」，按 Esc；看抽屉分节 | 抽屉标题「更多」，含「开放时间」「登录」「电脑窗口」「运行记录」四节；Esc 能关掉 | 通过；点遮罩关闭未单独触发 |

截图：`phone-expired-list.jpg`（过期登录 + 列表）、`phone-plan-running.jpg`（计划运行看板与停止钮）、`phone-plan-stop-confirm.jpg`（停止确认）、`phone-plan-stopped.jpg`（停止后回列表）、`phone-relogin-sheet.jpg`（重登抽屉）。

补充观察：浏览器标签在后台时轮询会暂停，超过 30 秒后点「开始」会被「状态已过时，先刷新再开始」拦下；开始前点一次刷新即可受理。这与前台真机行为不同，不是缺陷。

## 3. 冻结 EXE 与 WebView2

构建命令：`python local/build/build_exe.py --mode onefile`。

| 项目 | 构建前旧产物 | 构建后当前源码 |
|---|---|---|
| 构建时间 | 2026-11-21 | 2026-11-23 |
| 大小 | 141,849,385 字节 | 141,870,389 字节 |
| SHA-256 | `68927F95EF5C2E940BF7CE1DE3122D7FBF93F355B9E8020E90BDEEA2622C7BC3` | `0E2E1A63A93D861CDA76C097AAA1C833718738C6B60157607DF9B7FDB7234733` |
| 包内 `ui/m` | 5 个（只有旧的 `app.js`，没有拆出的 `ui-*.js`） | 16 个（12 个脚本 + 首页 + 样式 + 2 个图标） |

以 `--demo` 启动后，主窗口标题为「校园活动预报名工具」，窗口 1280×820；WebView2 正常渲染中文、图标、时刻表与右侧计划栏，无白屏与缺字。首次启动显示五步引导浮层（产品自带）。截图 `exe-demo.png`。

打包回归：`scripts/check_exe_phone_assets.py` 从 PyInstaller 归档取出 `ui/m` 全部 16 个成员与 `local/ui/m/` 逐个比对 SHA-256，结论为「一致」，且旧的 `ui/m/app.js` 已不在包内。

## 4. 真机待验收清单（需用户执行）

以下各项本次没有条件执行，不能算通过：

1. 在 iPhone Safari 与 Android Chrome 上通过真实 Tailscale 地址打开手机页，完成扫码 + 配对码配对。
2. 375 / 390 / 430 宽度与横竖屏切换，确认无横向滚动、底部操作条不被安全区遮挡。
3. 故意输错配对码，确认 3 次后锁定与 60 秒倒计时文案。
4. 手机锁屏或切到后台再回前台，确认轮询暂停后按事件游标补齐，不重复发写操作。
5. 断网后确认「离线」红条与「重试」按钮，恢复后状态自动回新。
6. 真机上勾选活动、核对、开始报名计划、停止计划、取消单场（本组只在替身后端上验证过）。
7. 真实登录失效时在手机上走完验证码重登（本次只验证到表单与取消）。
8. 把手机页加入主屏，核对标签图标与主屏图标。
9. 打包 EXE 在 125% / 150% 缩放下检查窗口，确认布局与滚动正常；最小窗口 980×700 下检查关键按钮可达。
10. 在打包 EXE 里安装「手机控制」组件并开启手机访问，确认真实通道能从手机打开。

## 5. 未覆盖项

- 真实手机浏览器（iOS Safari / Android Chrome）与真机触摸事件。
- 真实 Tailscale / Cloudflare 通道、真实学校接口与真实登录失效链路。
- 手机重登的验证码提交与成功回调（离线替身没有对应动作）。
- 设备信任 cookie 在程序重启后的免配对恢复。
- 抽屉点遮罩关闭、焦点归还与屏幕阅读器语义（本轮只触发了 Esc 与取消）。
- 打包 EXE 里开启手机访问组件的端到端路径。
- 高 DPI、多显示器与最小窗口尺寸下的布局。

## 6. 方法说明

- 手机页的四组验证在真实 Chromium 浏览器里通过 DOM 交互完成，不是复用 Node vm 用例的结论。
- 只读态用 `local/dev_phone_preview.py --state valid` 与 `--state expired --saved` 两轮。
- 计划运行/停止需要一个能改状态的离线替身后端（补 `start_plan` / `stop_plan` / `cancel_task`），本轮在临时目录构造后使用，未入库；它不连真实 Api，也不产生任何真实报名。
- EXE 截图只截应用窗口矩形，不截整屏；构建会覆盖 `dist/campus-grab-exe` 下的旧产物，`data` 目录保留。

## 7. 复现命令

在仓库根执行（Python 3.12；先清空 `http_proxy` / `HTTP_PROXY` / `https_proxy` / `HTTPS_PROXY` / `all_proxy`，并设 `PYTHONIOENCODING=utf-8`）：

```bash
python design/evidence/2026-11-23/real-env-smoke/scripts/probe_phone_http.py
python local/dev_phone_preview.py --state valid --port 8791 --no-browser
python local/dev_phone_preview.py --state expired --saved --port 8791 --no-browser
python local/build/build_exe.py --mode onefile
python design/evidence/2026-11-23/real-env-smoke/scripts/check_exe_phone_assets.py
powershell -NoProfile -ExecutionPolicy Bypass -File design/evidence/2026-11-23/real-env-smoke/scripts/capture_exe_window.ps1
```
