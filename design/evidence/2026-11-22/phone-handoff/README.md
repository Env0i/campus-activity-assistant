# 手机页转人工判断改用后端 `handoff` 字段（2026-11-22）

## 范围

- 将 `local/ui/m/model-relogin.js` 的 `PhoneModel.relHandoff(flow)` 从前端猜次数改为直接读后端 `login_relay.public_state` 下发的 `live` 与 `handoff` 两字段，并删除已无任何调用方的 `PhoneModel.REL_HANDOFF_AFTER`。
- 将 `PhoneModel.relLead` 与原型 `design/prototype/workbench-2026-11/Phone.dc.html` 中的转人工引导句统一为「电脑没认出验证码，换你来输。账号密码由电脑自动填写。」；`PhoneModel.relNeedAcct` 仍经 `PhoneModel.relHandoff(flow)` 收起账号密码输入。
- 同步 `design/specs/copywriting.md` 与 `docs/UI_SPEC.md` 中的手机页登录行与转人工口径，并在 `local/tests/test_phone_ui.py` 更新两处旧夹具与引导句期望、补充规则与场景回归用例。
- 不改后端、不改桌面前端、不改手机快照字段、不改登录四态判法与门禁。

## 三处不一致（改前）

后端 `local/application/login_relay_service.py` 的 `public_state` 已直接提供 `handoff`（自动识别认满阈值或识别结果不合规时由电脑置位，终态或本场结束后清掉）。原手机页 `relHandoff` 仅看 `mode === "manual" && live && (attempts >= 3 || auto_failures >= 3)`，与后端存在三处不一致：

1. **识别结果不合规的交接（第 1 张即认不出，`attempts = 1`）**：后端已置 `handoff = true`，但 `attempts < 3`，手机误判为未交接，既不出交接引导句也不收起账号密码输入。
2. **手机主动发起的人工场连错 3 次（`origin = "phone"`、`handoff = false`、`attempts = 3`）**：电脑从未参与自动认图，但手机误判为交接，错显「电脑连续 3 次没认对验证码」并错误收起账号密码输入。
3. **`auto_failures` 字段不存在于 `public_state`**：`login_relay_service.public_state` 根本不输出 `auto_failures`，原后半段 `auto_failures >= REL_HANDOFF_AFTER` 判断恒不生效。

## 新判法

1. **交接判定（`PhoneModel.relHandoff(flow)`）**：仅当 `flow` 为非数组对象、`flow.live === true` 且 `flow.handoff === true` 时返回 `true`，其余一律返回 `false`；删除 `PhoneModel.REL_HANDOFF_AFTER`（已全仓扫描 `local/` 验证无其余调用点）。
2. **引导句（`PhoneModel.relLead`）**：由于交接原因包含「认满阈值」与「识别结果不合规」两种，且用户手动重输阶段 `attempts` 会继续增长，手机引导句不再硬写次数，统一返回「电脑没认出验证码，换你来输。账号密码由电脑自动填写。」。
3. **账号收起（`PhoneModel.relNeedAcct`）**：`relHandoff(flow)` 为真时返回 `false`（电脑自动填账号密码，隐藏输入区），否则按 `!setup.saved || !!setup.paused` 判定。

## 测试与变异结果

- **代码检查**：`node --check local/ui/m/model-relogin.js` 通过，`python tools/code_shape/check.py` 通过（`reloginView` 行数未增加）。
- **单测结果（清除代理环境变量）**：
  - 改动前基线：`test_phone_ui.py` 245 OK，`test_ui_contracts.py` 374 OK。
  - 改动后：`test_phone_ui.py` 248 OK（+3 条新用例，两处放行修改见 [changed-tests.md](changed-tests.md)），`test_ui_contracts.py` 374 OK，`test_code_shape.py` 15 OK。
  - 本机全量 `local/tests`：2794 项通过，2 项按环境跳过，0 失败。
- **五条变异反证**：5 条变异全部在系统临时副本中命中新增用例变红（`exit_code=1`），首个失败用例与详情见 [mutations.md](mutations.md)。

## 未验证项

- 真实校园网环境下电脑自动识别认错阈值转人工、识别结果不合规即时转人工、以及手机手动连错 3 次的真机联调（仅由离线模拟测试覆盖）。

## 复现命令

在仓库根执行（先清除代理环境变量；测试只跑内存替身与临时目录，不访问学校与 `local/data/`）：

```powershell
Remove-Item Env:http_proxy,Env:HTTP_PROXY,Env:https_proxy,Env:HTTPS_PROXY,Env:all_proxy,Env:ALL_PROXY -ErrorAction SilentlyContinue
node --check local/ui/m/model-relogin.js
python tools/code_shape/check.py
python -m unittest discover -s local/tests -p "test_phone_ui.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_code_shape.py"
```
