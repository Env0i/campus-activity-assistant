# 变异反证记录

在 `%TEMP%` 下的独立副本中先跑通无变异基线（全绿，`exit=0`），随后依次注入以下五处单点变异并运行对应测试文件，五条变异均触发测试失败（`exit=1`）：

1. **M1：后端 `raw_state` 不写入 `act_start_ts`**
   - 位置：`local/application/phone_service.py` `_ACTIVITY_TIME_KEYS` / `_attach_activity_epochs`
   - 改法：从活动副本时刻映射表移除 `("act_start_ts", "act_start")`
   - 首个失败用例：`test_phone_service.ActivityTimestampProjectionTests.test_snapshot_adds_act_start_ts_and_act_end_ts_without_mutating_cache`（`exit=1`）

2. **M2：`tsOf` 在键值为 `null` 时退回解析文本**
   - 位置：`local/ui/m/model-conflict.js` `PhoneModel.tsOf`
   - 改法：仅在 `ts` 为有限数值时提前返回，值为 `null` 时继续落入 `PhoneModel.schoolSec(item[textKey])`
   - 首个失败用例：`test_phone_ui.PhoneClashRulesTests.test_ts_of_and_act_range_prefer_snapshot_keys_over_text`（`exit=1`）

3. **M3：`actRange` 改回直接读 `PhoneModel.schoolSec(act_start)`**
   - 位置：`local/ui/m/model-conflict.js` `PhoneModel.actRange`
   - 改法：将起始时刻获取改回 `PhoneModel.schoolSec(item && item.act_start)`
   - 首个失败用例：`test_phone_ui.PhoneClashRulesTests.test_signed_clash_prefers_act_ts_keys_when_text_differs`（`exit=1`）

4. **M4：`cancelWindowOpen` 改回读取 `sign_end` 文本**
   - 位置：`local/ui/m/model-conflict.js` `PhoneModel.cancelWindowOpen`
   - 改法：将截止时刻获取改回 `PhoneModel.schoolSec(item && item.sign_end)`
   - 首个失败用例：`test_phone_ui.PhoneCancelNoteTests.test_cancel_window_and_note_use_close_ts_over_sign_end_text`（`exit=1`）

5. **M5：`schoolSec` 重新接受 `T` 分隔**
   - 位置：`local/ui/m/model-conflict.js` `PhoneModel.schoolSec`
   - 改法：将日期时间分隔符正则表达式改回 `[ T]`
   - 首个失败用例：`test_phone_ui.PhoneTimeTextTests.test_school_sec_rejects_t_separator_and_keeps_space_format`（`exit=1`）

6. **M6：`cancelWindowOpen` 改回直接读 `sign_start` 文本**
   - 位置：`local/ui/m/model-conflict.js` `PhoneModel.cancelWindowOpen`
   - 改法：将 `const start = PhoneModel.tsOf(item, "open_ts", "sign_start");` 改回 `const start = PhoneModel.schoolSec(item.sign_start);`
   - 首个失败用例：`test_phone_ui.PhoneCancelNoteTests.test_cancel_window_start_uses_open_ts_over_sign_start_text`（`exit=1`）

7. **M7：`clashWay` 改回直接读 `sign_end` 文本**
   - 位置：`local/ui/m/model-conflict.js` `PhoneModel.clashWay`
   - 改法：将 `const end = PhoneModel.tsOf(sg, "close_ts", "sign_end");` 改回 `const end = PhoneModel.schoolSec(sg.sign_end);`
   - 首个失败用例：`test_phone_ui.PhoneClashRulesTests.test_clash_way_deadline_uses_close_ts_over_sign_end_text`（`exit=1`）