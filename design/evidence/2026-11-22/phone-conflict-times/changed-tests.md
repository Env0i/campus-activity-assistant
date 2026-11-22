# 手机页冲突与取消时刻变更用例清单

## 一、既有旧用例

本批**没有修改任何既有旧用例**（全部原有断言、夹具与期望保持原样且全绿通过）。

## 二、新增用例

### 后端快照投影（`local/tests/test_phone_service.py`）

- `test_phone_service.ActivityTimestampProjectionTests.test_snapshot_adds_act_start_ts_and_act_end_ts_without_mutating_cache`
  - 守卫规则：经过真实 `app.Api` 与 `domain.phone_rules.project_state` 后，活动副本对合法 `act_start` / `act_end` 补写等于 `time_contract.school_epoch` 的 `act_start_ts` / `act_end_ts`，对 `T` 分隔、缺秒、不存在日期返回 `None`，且活动缓存原件不被写入这两个键。

### 手机页纯规则（`local/tests/test_phone_ui.py`）

- `test_phone_ui.PhoneClashRulesTests.test_ts_of_and_act_range_prefer_snapshot_keys_over_text`
  - 守卫规则：`PhoneModel.tsOf` 在对象带 `tsKey` 时只读该数值（为 `null` 时不退回解析文本），缺键才退回 `PhoneModel.schoolSec`；`actRange` 在 `act_start_ts` 为 `null` 时返回 `null`。
- `test_phone_ui.PhoneClashRulesTests.test_signed_clash_prefers_act_ts_keys_when_text_differs`
  - 守卫规则：`PhoneModel.signedClash` 基于 `act_start_ts` / `act_end_ts` 按半开区间判定举办时段重叠，即使文本字段给出不同时段也以数值时刻键为准。
- `test_phone_ui.PhoneTimeTextTests.test_school_sec_rejects_t_separator_and_keeps_space_format`
  - 守卫规则：`PhoneModel.schoolSec` 与电脑 `time_contract.parse_school_time` 及桌面 `toTs` 一致，拒绝 `T` 分隔和非法日历日期，仅接受空格分隔的 `YYYY-MM-DD HH:MM:SS`。
- `test_phone_ui.PhoneCancelNoteTests.test_cancel_window_and_note_use_close_ts_over_sign_end_text`
  - 守卫规则：`PhoneModel.cancelWindowOpen` 与 `cancelNote` 在快照带 `open_ts` / `close_ts` 时只以这两个数值键为准，即使 `sign_end` 文本滞后或超前也不误判。