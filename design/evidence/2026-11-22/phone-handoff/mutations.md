# 五条变异反证记录

说明：每条变异仅在系统临时目录复制的 `local/` 副本中施加，运行 3 条新增用例（共运行 3 项，含表驱动子断言）并确认变红，原工作区未留变异改动。

| 序号 | 变异位置与改法 | 运行结果 | 首个失败用例（含完整类名） |
|---|---|---|---|
| 1 | `local/ui/m/model-relogin.js` `relHandoff`：不看 `flow.handoff`，直接 `return false;` | FAIL（exit=1） | `test_phone_ui.ReloginSheetTests.test_invalid_ocr_handoff_hides_account_and_uses_handoff_lead` |
| 2 | `local/ui/m/model-relogin.js` `relHandoff`：去掉 `flow.live === true` 条件，只返回 `flow.handoff === true` | FAIL（exit=1） | `test_phone_ui.ReloginSheetTests.test_rel_handoff_relies_on_live_and_handoff` |
| 3 | `local/ui/m/model-relogin.js` `relHandoff`：换回 `mode === "manual" && !!live && attempts >= 3` 旧判法 | FAIL（exit=1） | `test_phone_ui.ReloginSheetTests.test_invalid_ocr_handoff_hides_account_and_uses_handoff_lead` |
| 4 | `local/ui/m/model-relogin.js` `relLead`：交接句换回旧原文「电脑连续 3 次没认对验证码，换你来输。账号密码由电脑自动填写。」 | FAIL（exit=1） | `test_phone_ui.ReloginSheetTests.test_invalid_ocr_handoff_hides_account_and_uses_handoff_lead` |
| 5 | `local/ui/m/model-relogin.js` `relNeedAcct`：去掉 `if (PhoneModel.relHandoff(flow)) return false;` 交接分支 | FAIL（exit=1） | `test_phone_ui.ReloginSheetTests.test_rel_handoff_relies_on_live_and_handoff` |
