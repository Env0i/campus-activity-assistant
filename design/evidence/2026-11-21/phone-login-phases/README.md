# 手机页登录四态呈现（2026-11-21 – 2026-11-22）

## 范围

- 依据决策 006（未确认不得写成有效；首次使用显示「登录」、真实失效才显示「重新登录」，两词不混用）与决策 014（工作台原型作为 1:1 基准）：
  1. 在原型 `design/prototype/workbench-2026-11/Phone.dc.html` 补充 `never` 与 `unknown` 两种登录态与场景，新增 `PhoneNever.dc.html` 与 `PhoneLoginUnknown.dc.html` 并登记至 `canvas.json` 与 `README.md`。
  2. 在 `local/ui/m/` 新增 `PhoneModel.loginState`、`PhoneModel.loginCopy`、`PhoneModel.loginDoneText`，改写 `PhoneModel.loginLine`、横幅、底栏、更多面板与重登面板文案，并在打开重登面板时记录 `model.relFirstLogin` 避免成功后快照刷新导致标题与正文跳字。
  3. 不改后端、桌面前端、手机快照字段与报名门禁（`loginRaw`/`loginRecovering`/`loginExpired` 判定结果不变）。

## 四态判法

`PhoneModel.loginState(login)` 按下列优先级返回第一条命中：

1. `login` 不是非数组对象 → `"unknown"`
2. `login.session_present === false` → `"never"`（无会话先于失效）
3. `!!login.session_expired || login.last_check_state === "expired"` → `"expired"`
4. `login.last_check_state === "valid"` → `"valid"`
5. 其余情况（例如 `last_check_state === "unknown"` 或缺字段）→ `"unknown"`

## 四态与各位置文案对照表

| 位置 | `never`（未登录） | `unknown`（待确认） | `expired`（已失效） | `valid`（有效） |
|---|---|---|---|---|
| 失效横幅显隐 | 显示 | 隐藏 | 显示（非静默自动恢复中） | 隐藏 |
| 横幅标题 | 电脑上还没有登录 | — | 电脑上的登录已失效 | — |
| 横幅正文 | 可以在手机上登录，也可以回电脑处理。 | — | 可以在手机上重新登录，也可以回电脑处理。 | — |
| 横幅按钮 | 登录 | — | 重新登录 | — |
| 底栏副题 | 还差一步：登录 | 正常摘要/门禁提示 | 还差一步：重新登录 | 正常摘要/门禁提示 |
| 底栏主钮 | 登录 | 核对并开始 | 重新登录 | 核对并开始 |
| 自动登录中底栏副题 | 电脑正在自动登录，好了就能开始 | — | 电脑正在自动重新登录，好了就能开始 | — |
| 登录行前半句 | 电脑上还没有登录。 | 电脑上的登录状态还没确认。 | 电脑上的登录已失效。 | 电脑上的登录有效。 |
| 登录行后半句（按账号×识别） | 用「登录」四句（点「登录」后… / 登录时…） | 用「重新登录」四句（失效时… / 重新登录要…） | 同左 | 同左 |
| 自动登录中登录行 | 电脑正在自动登录。 | — | 电脑正在自动重新登录。 | — |
| 更多面板重登钮 | 在手机上登录 | 在手机上重新登录 | 在手机上重新登录 | 在手机上重新登录 |
| 重登面板标题（打开时锁定） | 在手机上登录 | 在手机上重新登录 | 在手机上重新登录 | 在手机上重新登录 |
| 重登成功句（闲时） | 登录成功，活动列表已刷新。 | 重新登录成功，活动列表已刷新。计划不会自动重新开始，要你重新核对后再点开始。 | 同左 | 同左 |
| 重登成功句（计划运行中） | 登录成功，报名计划照常继续。 | 重新登录成功，报名计划照常继续。 | 同左 | 同左 |

## 重登面板取态时刻

`ui-sync.js` 的 `ingest` 先喂入 `login_relay` 再更新 `model.login`，`refreshControls` 每轮重画面板；如果按当前 `model.login` 判断是否首次登录，第一次登录成功瞬间收到 `login=valid` 快照后，面板标题会从「在手机上登录」跳成「在手机上重新登录」。

改为在 `openRelogin` 真正打开重登面板时记录 `model.relFirstLogin = (PhoneModel.loginState(model.login) === "never")`，面板标题、`reloginView` 成功句与 `ingestRelogin` 的 `relogin-note` 成功句统一使用 `model.relFirstLogin`，关掉面板重开才重新取态；更多面板按钮、横幅、底栏与登录行仍跟随实时快照。

## 测试与变异结果

- 代码检查：`node --check`（改动脚本全部通过）、`python tools/code_shape/check.py` 通过（名单与函数行数均未增长）。
- 单测结果（2026-11-22，清除代理环境变量）：
  - `python -m unittest discover -s local/tests -p "test_phone_ui.py"`：245 项通过（+6 条四态与闪字回归用例；按决策 006 口径更新的两条旧断言明细见 [changed-tests.md](changed-tests.md)）。
  - `python -m unittest discover -s local/tests -p "test_ui_contracts.py"`：374 项通过。
  - `python -m unittest discover -s local/tests -p "test_code_shape.py"`：15 项通过。
  - `python -m unittest discover -s local/tests -p "test_*.py"`（本机全量）：2791 项通过，2 项按环境条件跳过，0 失败。
- 变异反证：6 条变异全部在临时副本中命中新增用例变红（`exit_code=1`），明细与首个失败用例见 [mutations.md](mutations.md)。

## 截图位置

全部截图在 `127.0.0.1` 随机端口、无头 `msedge`（视口 `390×844`）生成，控制台与页面错误均为 0：

- 手机页实际画面（`shots/`）：`phone-never.png`、`phone-never-relogin.png`、`phone-unknown.png`、`phone-expired.png`、`phone-valid.png`
- 原型画板画面（`shots/`，使用本机 `support.js`）：`proto-phone-never.png`、`proto-phone-login-unknown.png`、`proto-phone-expired.png`

## 未验证项

- 真实校园网环境下由零登录完成一次手机首次登录全流程及 4001 失效重登。
- Android 浏览器与微信内置浏览器实机渲染。
- 冻结 EXE 打包形态下的资源加载。

## 复现命令

在仓库根执行（先清除代理环境变量；临时数据目录指向系统 `%TEMP%`）：

```powershell
Remove-Item Env:http_proxy,Env:HTTP_PROXY,Env:https_proxy,Env:HTTPS_PROXY,Env:all_proxy,Env:ALL_PROXY -ErrorAction SilentlyContinue
python -m unittest discover -s local/tests -p "test_phone_ui.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_code_shape.py"
python tools/code_shape/check.py
python design/evidence/2026-11-21/phone-login-phases/scripts/shots.py
```
