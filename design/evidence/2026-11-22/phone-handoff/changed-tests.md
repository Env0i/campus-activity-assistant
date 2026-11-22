# 手机页转人工字段改造涉及的测试记录

## 一、放行修改的旧用例

修改原因统一为：**后端 `public_state` 才是交接事实，旧夹具缺 `handoff` 字段。** 除以下两处明确列出的夹具与引导句期望外，其余既有断言未改动、未删除、未加 skip。

### 1. `ReloginSheetTests.test_lead_four_states_and_relbad_red_error`（`local/tests/test_phone_ui.py`）

- **第 1 条 `relLead` 调用输入**：
  - 改前：`PhoneModel.relLead({mode:"manual", live:true, attempts:3}, {saved:true, ocr_ready:true})`
  - 改后：`PhoneModel.relLead({mode:"manual", live:true, attempts:3, handoff:true}, {saved:true, ocr_ready:true})`
- **对应第 1 条期望**：
  - 改前：`"电脑连续 3 次没认对验证码，换你来输。账号密码由电脑自动填写。"`
  - 改后：`"电脑没认出验证码，换你来输。账号密码由电脑自动填写。"`
- 同用例第 2–5 条 `relLead` 调用与 `paused` 红错 DOM 断言均未动。

### 2. `ReloginSheetTests.test_handoff_lead_hides_account_fields`（`local/tests/test_phone_ui.py`）

- **`login_relay` 夹具输入**：
  - 改前：`{mode:"manual", state:"waiting_code", flow_id:"f", challenge_id:"c", image:png, live:true, attempts:3, auto_failures:0}`
  - 改后：`{mode:"manual", state:"waiting_code", flow_id:"f", challenge_id:"c", image:png, live:true, attempts:3, auto_failures:0, handoff:true}`
- **引导句期望（`values[0][0]`）**：
  - 改前：`"电脑连续 3 次没认对验证码，换你来输。账号密码由电脑自动填写。"`
  - 改后：`"电脑没认出验证码，换你来输。账号密码由电脑自动填写。"`
- 同用例其余显隐布尔期望（账号收起、验证码与按钮露出等 6 项）均未动。

## 二、新增用例清单（均位于 `local/tests/test_phone_ui.py`）

1. `ReloginSheetTests.test_rel_handoff_relies_on_live_and_handoff`：表驱动覆盖 `PhoneModel.relHandoff` 仅认 `live === true && handoff === true`（覆盖 `handoff` 缺/假、`live` 缺/假、仅 `attempts=3`、仅 `auto_failures=3`、`null`、数组、字符串、数字），并核对交接时 `relNeedAcct` 在未落盘保存账号下仍返回 `false`。
2. `ReloginSheetTests.test_invalid_ocr_handoff_hides_account_and_uses_handoff_lead`：验证识别结果不合规的交接场景（`mode=manual`、`live=true`、`attempts=1`、`handoff=true`、电脑已存账号），引导句切为「电脑没认出验证码，换你来输。账号密码由电脑自动填写。」、账号区收起、验证码区露出。
3. `ReloginSheetTests.test_phone_origin_manual_failures_do_not_trigger_handoff`：验证手机自己发起的人工场用户连续输错（`origin=phone`、`mode=manual`、`live=true`、`attempts=3`、`handoff=false`、未存账号），不误切交接句、账号区与验证码区均露出。
