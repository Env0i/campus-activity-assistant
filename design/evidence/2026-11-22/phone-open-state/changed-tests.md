# 手机页开放与截止时刻变更用例清单

## 一、放行调整的既有旧用例

只涉及「删除已失效的 `wallS` 参数」一类（期望断言完全未动）；未发现时钟不可用（`nowS` 为 `null`）下断言旧相对组名的既有断言：

1. `test_phone_ui.ListDetailModelTests._view`（`local/tests/test_phone_ui.py`）
   - 改前：`PhoneModel.listView(items, { q: "", status: "all", time: "all" }, { nowS: %s, wallS: nowS, selected: %s, busy: %s })`
   - 改后：删去 `wallS: nowS` 实参，期望断言不变
   - 原因：参数已删除
2. `test_phone_ui.ListDetailModelTests.test_row_left_countdown_soon_and_clock_down`（`local/tests/test_phone_ui.py`，两处调用）
   - 改前：`PhoneModel.listView(items, {}, { nowS: nowS, wallS: nowS, selected: [], busy: false })` 与 `{ nowS: null, wallS: nowS, selected: [], busy: false }`
   - 改后：两处均删去 `wallS: nowS` 实参，期望断言不变
   - 原因：参数已删除
3. `test_phone_ui.ListDetailModelTests.test_pick_conflict_keeps_selection_and_warns`（`local/tests/test_phone_ui.py`，两处调用）
   - 改前：`PhoneModel.listView(items, {}, { nowS: nowS, wallS: nowS, selected: ["t1"], busy: false })` 与 `{ nowS: nowS, wallS: nowS, selected: ["t1"], busy: true }`
   - 改后：两处均删去 `wallS: nowS` 实参，期望断言不变
   - 原因：参数已删除

## 二、新增用例

### 后端快照投影（`local/tests/test_phone_service.py`）

- `test_phone_service.ActivityTimestampProjectionTests.test_snapshot_adds_open_ts_and_close_ts_without_mutating_cache`
  - 验证经过真实 `app.Api` 与 `domain.phone_rules.project_state` 后，合法 `sign_start` / `sign_end` 输出与 `time_contract.school_epoch` 一致的 `open_ts` / `close_ts`；`2026-02-30 09:00:00`、带 `T` 分隔、`缺秒` 等非法文本输出 `None`；活动缓存原件里不出现 `open_ts` / `close_ts`。

### 手机页纯规则与分组（`local/tests/test_phone_ui.py`）

- `test_phone_ui.ListDetailModelTests.test_open_epoch_uses_open_ts_key_only_and_strict_fallback`
  - 验证 `openEpochOf` 在对象带 `open_ts: null` 且 `sign_start` 合法时返回 `0`（不回退解析文本）；带有限正数 `open_ts` 时直接返回该值；缺失 `open_ts` 键时合法东八区时间返回对应秒数，而 `2026-02-30 09:00:00`、带 `T` 分隔及缺秒文本均返回 `0`。
- `test_phone_ui.ListDetailModelTests.test_st_of_prefers_close_ts_over_sign_end_text`
  - 验证 `stOf` 在带 `close_ts` 键且已到截止时判 `"closed"`（即使 `sign_end` 文本在未来），带 `close_ts: null` 时不退回解析过期的 `sign_end` 文本。
- `test_phone_ui.ListDetailModelTests.test_uncalibrated_clock_groups_by_beijing_open_day_ignoring_date_now`
  - 验证 `nowS` 为 `null` 时 `listView` 与 `groupKeyOf` 将 `pre` 场次按北京开放日升序归组（如 `11月4日 周三`、`11月6日 周五`，排在「待公布」「已报名」「已截止」之前），且同日场次合并为一组；在沙箱中将 `Date.now` 篡改至另一日期后，分组名称与顺序完全不变。
