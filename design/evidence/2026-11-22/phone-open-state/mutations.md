# 变异反证记录

在 `%TEMP%` 下的独立副本中先跑通无变异基线（全绿），随后依次注入以下五处单点变异并运行对应测试文件，五条变异均触发测试失败（`exit=1`）：

1. **M1：后端 `raw_state` 不写入 `open_ts`**
   - 位置：`local/application/phone_service.py` `PhoneAccessController.raw_state`
   - 改法：去掉副本上 `item["open_ts"] = ...` 的赋值
   - 首个失败用例：`test_phone_service.ActivityTimestampProjectionTests.test_snapshot_adds_open_ts_and_close_ts_without_mutating_cache`（`exit=1`）

2. **M2：`openEpochOf` 在带 `open_ts` 键时仍退回解析 `sign_start`**
   - 位置：`local/ui/m/model.js` `PhoneModel.openEpochOf`
   - 改法：当 `item.open_ts` 为 `null` 时继续向下解析 `item.sign_start`
   - 首个失败用例：`test_phone_ui.ListDetailModelTests.test_open_epoch_uses_open_ts_key_only_and_strict_fallback`（`exit=1`）

3. **M3：`openEpochOf` 回退文本路径改回宽松正则**
   - 位置：`local/ui/m/model.js` `PhoneModel.openEpochOf`
   - 改法：恢复旧的 `[ T]`、可省略秒且无日历回验的正则与 `Date.UTC` 计算
   - 首个失败用例：`test_phone_ui.ListDetailModelTests.test_open_epoch_uses_open_ts_key_only_and_strict_fallback`（`exit=1`）

4. **M4：`stOf` 不读取 `close_ts`**
   - 位置：`local/ui/m/model-list.js` `PhoneModel.stOf`
   - 改法：忽略 `item.close_ts`，直接按 `PhoneModel.schoolSec(item && item.sign_end)` 判截止
   - 首个失败用例：`test_phone_ui.ListDetailModelTests.test_st_of_prefers_close_ts_over_sign_end_text`（`exit=1`）

5. **M5：`groupKeyOf` 在 `nowS` 为 `null` 时用 `Date.now()/1000` 作基准**
   - 位置：`local/ui/m/model-list.js` `PhoneModel.groupKeyOf`
   - 改法：`nowS` 为 `null` 时回退 `Date.now() / 1000` 并输出「今天 / 明天 / 后天 / 更晚开放」
   - 首个失败用例：`test_phone_ui.ListDetailModelTests.test_uncalibrated_clock_groups_by_beijing_open_day_ignoring_date_now`（`exit=1`）
