# 变异反证记录

在 `%TEMP%` 下的独立副本先确认无变异基线通过（`ActPendingBlockTests` 4 项 OK，`exit=0`），随后依次注入以下五处单点变异并运行 `test_phone_ui.py`，五条变异均触发对应新用例失败（`exit=1`）：

1. **变异一：`canStart` 不看 `actBlock`**
   - 位置：`local/ui/m/model.js` `PhoneModel.canStart`
   - 改法：去掉 `&& PhoneModel.actBlock(model.items, model.selected) === null` 判断
   - 首个失败用例：`test_phone_ui.ActPendingBlockTests.test_act_block_text_and_can_start`（`exit=1`，`AssertionError: True is not false`；同轮亦触发两个 DOM 用例失败）

2. **变异二：`actBlock` 不查已报名**
   - 位置：`local/ui/m/model-conflict.js` `PhoneModel.actBlock`
   - 改法：去掉 `signedMissing` 筛选与 `{ kind: "signed", ... }` 返回分支
   - 首个失败用例：`test_phone_ui.ActPendingBlockTests.test_act_block_table`（`exit=1`，`AssertionError: None != {'kind': 'signed', 'names': ['已报缺时']}`；同轮亦触发 `test_act_block_text_and_can_start` 与 `test_dom_signed_pending_blocks_bar_and_start` 失败）

3. **变异三：`actBlock` 已报名优先于已选**
   - 位置：`local/ui/m/model-conflict.js` `PhoneModel.actBlock`
   - 改法：把 `signedMissing` 判断挪到 `selMissing` 之前
   - 首个失败用例：`test_phone_ui.ActPendingBlockTests.test_act_block_table`（`exit=1`，`AssertionError: {'kind': 'signed', 'names': ['已报缺时']} != {'kind': 'selected', 'names': ['乙活动']}`）

4. **变异四：`actBlockText` 多场也写名称**
   - 位置：`local/ui/m/model-conflict.js` `PhoneModel.actBlockText`
   - 改法：去掉 `block.names.length === 1` 分支区分，多场也按单场格式拼接首场名称
   - 首个失败用例：`test_phone_ui.ActPendingBlockTests.test_act_block_text_and_can_start`（`exit=1`，`AssertionError` 期望「已选的 2 场」与「已报名的 2 场」失败）

5. **变异五：`rowView` 不写「举办时间待公布」**
   - 位置：`local/ui/m/model-list.js` `PhoneModel.rowView`
   - 改法：去掉 `st === "pre" || st === "open"` 时回退 `"举办时间待公布"` 的分支
   - 首个失败用例：`test_phone_ui.ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck`（`exit=1`，`AssertionError: '举办时间待公布' not found in '14:00|48 小时后|缺时预报名|下一场|奖励同步中'`）
