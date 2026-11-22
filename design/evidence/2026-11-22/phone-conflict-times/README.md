# 手机页冲突与取消时刻统一证据

日期：2026-11-22

## 范围

- 后端手机快照投影：`local/application/phone_service.py`（`_ACTIVITY_TIME_KEYS`、`_attach_activity_epochs` 与 `PhoneAccessController.raw_state`）。`local/app.py`、`local/domain/`、活动缓存原件与桌面列表载荷均未改动。
- 手机页纯规则：`local/ui/m/model-conflict.js`（`PhoneModel.schoolSec`、`tsOf`、`actRange`、`cancelWindowOpen`、`cancelNote`、`clashWay`）。
- 文档与测试：`docs/PHONE_ACCESS.md`、`local/tests/test_phone_service.py`、`local/tests/test_phone_ui.py`、`changed-tests.md`、`mutations.md`。

## 清单第四节逐条核对结论

对照 `design/evidence/2026-11-22/phone-net/rule-dups.md` 第四节（冲突与可取消成员）：

1. **唯一真分歧——`schoolSec` 对 `T` 分隔符宽容**：`schoolSec` 旧正则允许日期与时间之间写 `T`（如 `"2026-11-20T09:00:00"`），而电脑端 `time_contract.parse_school_time` 与桌面 `toTs` 只接受单个空格；这连带使 `actRange`、`cancelWindowOpen`、`clashWay`、`cancelNote` 在遇到 `T` 分隔文本时可能与电脑端结论不一致。
2. **两条在生产上不生效的差异及原因**：
   - `signedClash` 读取 `item.closed`：真实电脑活动缓存与手机快照不输出 `closed` 字段，该分支只在旧测试夹具输入中出现。
   - `refundFlag` 不检查开放状态直接放行：真实列表中 `rowView` 已先限定仅在 `st === "open" || st === "pre"` 时调用 `refundFlag`，待公布行不会进入该函数。
3. **其余成员**（`overlapFirst`、`actRange`、`spanDays`、`endsAtMidnight`、`lastDayOf`、`actSpan`、`cancelWindowOpen`、`cancelNote`、`clashWay`、`whyView`）：半开区间、跨天计算、截止包含与四种解除路径的条件和文案均与桌面及后端一致。

## 新字段与新取法

- **后端快照新字段**：`local/application/phone_service.py` 将活动副本四个时刻键的补写抽进模块级 `_attach_activity_epochs`（`open_ts`、`close_ts`、`act_start_ts`、`act_end_ts`），由注入的 `time_contract.school_epoch` 端口分别对 `sign_start`、`sign_end`、`act_start`、`act_end` 求值（缺失或非法文本为 `None`），`raw_state` 仅调用该函数并保持原缓存字典不被改写。
- **`PhoneModel.tsOf(item, tsKey, textKey)`**：在 `local/ui/m/model-conflict.js` 新增统一读取入口；只要 `item` 自带 `tsKey` 属性，就只认该属性是否有限数值（为 `null` 或非有限值直接返回 `null`，不再解析对应文本），仅在缺键时退回 `PhoneModel.schoolSec(item[textKey])`。
- **调用切换与严格格式**：`actRange` 改用 `tsOf(item, "act_start_ts", "act_start")` 与 `tsOf(item, "act_end_ts", "act_end")`；`cancelWindowOpen` 改用 `tsOf(item, "open_ts", "sign_start")` 与 `tsOf(item, "close_ts", "sign_end")`；`cancelNote` 与 `clashWay` 截止展示改用 `tsOf(item, "close_ts", "sign_end")`；同时将 `PhoneModel.schoolSec` 收紧为只认日期与时间之间单个空格（退回路径也与电脑严格对齐）。规则判定与展示文案全部保持不变。

## 测试与变异结果

- 既有旧用例未作任何修改。
- `local/tests/test_phone_service.py`：动手前 68 通过 → 动手后 69 通过（新增 `ActivityTimestampProjectionTests.test_snapshot_adds_act_start_ts_and_act_end_ts_without_mutating_cache`）。
- `local/tests/test_phone_ui.py`：动手前 252 通过 → 动手后 256 通过（新增 4 条用例覆盖 `tsOf`、`actRange`、`signedClash`、`cancelWindowOpen`、`cancelNote` 与 `schoolSec`）。
- `local/tests/test_ui_contracts.py`：374 通过 / 0 失败 / 0 跳过。
- `local/tests/test_code_shape.py`：15 通过 / 0 失败；`tools/code_shape/check.py` 与 `test_layer_boundaries.py` 通过（未改 `baseline.json`）。
- 本机全量（`local/tests`）：`Ran 2804 tests in 241.428s`，`OK (skipped=2)`。
- 五条变异反证：在 `%TEMP%` 独立副本先确认无变异基线全绿，随后五条单点变异全部命中对应新用例失败（`exit=1`），详情见 `mutations.md`。

## 不做的体验缺口

- 手机端在勾选活动时仍不提前拦下「活动时间待确认」或「已报名活动时间待确认」（当前仍到电脑 `start_plan` 校验时拒收），需待补充原型设计后另行安排。

## 未验证项

- 真实手机连接电脑与真实学校列表（含真实取消接口）场景下的真机端到端联调尚未执行。
- 本机全量测试中既有的 2 条环境条件跳过用例（`skipped=2`）未在本机覆盖。

## 复现命令

```bash
python tools/code_shape/check.py
python -m unittest discover -s local/tests -p "test_layer_boundaries.py"
python -m unittest discover -s local/tests -p "test_phone_service.py"
python -m unittest discover -s local/tests -p "test_phone_ui.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_code_shape.py"
python -m unittest discover -s local/tests -p "test_*.py"
```