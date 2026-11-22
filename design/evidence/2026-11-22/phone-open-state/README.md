# 手机页开放与截止时刻统一证据

日期：2026-11-22

## 范围

- 后端只读投影：`local/application/phone_service.py`（`PhoneAccessController.raw_state`）与 `local/app.py`（`_make_phone_controller` 注入 `school_epoch` 端口）。不改动活动缓存原件、worker 输出或桌面列表载荷。
- 手机页纯规则与视图同步：`local/ui/m/model.js`、`local/ui/m/model-list.js`、`local/ui/m/ui-list.js`、`local/ui/m/ui-sync.js`。
- 原型：`design/prototype/workbench-2026-11/Phone.dc.html`（时钟未校准场景 `s.pcClock === 'down'`）。
- 规格与文档：`design/specs/copywriting.md`、`docs/PHONE_ACCESS.md`。
- 测试与反证：`local/tests/test_phone_service.py`、`local/tests/test_phone_ui.py`、`changed-tests.md`、`mutations.md`。

## 两处分歧与例子

1. **开放与截止时刻解析口径不一致**
   - 改前：`PhoneModel.openEpochOf` 使用宽松正则解析 `sign_start`（允许 `T` 分隔、允许省略秒、且不做日历回验），而电脑端 `time_contract.school_epoch` 与桌面 `toTs` 只接受严格 `YYYY-MM-DD HH:MM:SS` 并拒绝无效日历日期。
   - 例子：`sign_start = "2026-02-30 09:00:00"` 或 `"2026-11-05T09:00:00"` 时，电脑端判为时间未知（`None`），手机页改前会滚算成 `2026-03-02` 或解析通过。
2. **业务时钟未校准时分组读取手机本机时钟**
   - 改前：`nowS` 为 `null` 时，`PhoneModel.groupKeyOf`、`listView`、`ui-list.js` 与 `ui-sync.js` 使用手机 `wallS`（`Date.now() / 1000`）或当天秒数折算北京日历日并输出「今天 / 明天 / 后天 / 更晚开放」，违反决策 012「未校准时不读本机时钟」。
   - 例子：当 `business_clock` 不可用（`nowS === null`）且篡改手机本地日期为另一天时，改前同一场 `2026-11-04 14:30:00` 活动会随手机系统日期在「今天 / 明天 / 更晚开放」间漂移；桌面端此时按开放日绝对日期分组。

## 新字段与新判法

- **后端手机快照新字段**：`PhoneAccessController.raw_state` 在复制出的 `state.activities[]` 副本上追加只读字段 `open_ts` 与 `close_ts`，通过注入的 `time_contract.school_epoch` 对 `sign_start`、`sign_end` 求值（有限浮点 epoch 秒，缺失或非法为 `None`），并已确认不会被 `domain/phone_rules.strip_sensitive` 过滤；原活动缓存字典不写这两个键。
- **`PhoneModel.openEpochOf(item)`**：只要对象自身带 `open_ts` 键，就只读 `open_ts`（有限正数返回，否则返回 `0`），不再解析文本；只有缺失 `open_ts` 键的旧测试夹具或开发预览才退回严格 `YYYY-MM-DD HH:MM:SS` 格式检查并调用 `PhoneModel.schoolSec` 做日历回验。
- **`PhoneModel.stOf(item, nowS)`**：判断截止时若对象自身带 `close_ts` 键，就只读 `close_ts`（有限数值才算有截止），否则沿用 `PhoneModel.schoolSec(item && item.sign_end)`；其余分支先后不变。
- **`PhoneModel.groupKeyOf(item, st, nowS)` 与 `listView`**：移除 `wallS` 参数；`nowS` 为 `null` 时 `pre` 场次由纯成员 `openDayLabel` 按北京开放日输出「M月D日 周X」（与桌面 `relDayText` 在时钟不可用时同写法），同日归为一组并按开放日期升序排在「待公布」「已报名」「已截止」之前；`local/ui/m/` 内不再存在 `wallS` 或用 `Date.now()` 换算日历日的路径。原型 `Phone.dc.html` 在 `s.pcClock === 'down'` 时 `pre` 行组名同步改为「11月4日 周三 / 11月5日 周四 / 11月6日 周五」。

## 测试与变异结果

- `local/tests/test_phone_service.py`：动手前 67 通过 → 动手后 68 通过（新增 `ActivityTimestampProjectionTests.test_snapshot_adds_open_ts_and_close_ts_without_mutating_cache`）。
- `local/tests/test_phone_ui.py`：动手前 248 通过 → 动手后 251 通过（按两类放行清单删除 5 处 `wallS` 实参，新增 `openEpochOf`、`stOf`、`groupKeyOf/listView` 三条用例）。
- `local/tests/test_ui_contracts.py`：374 通过 / 0 失败 / 0 跳过。
- `local/tests/test_code_shape.py`：15 通过 / 0 失败；`tools/code_shape/check.py` 通过（未改 `baseline.json`）。
- 本机全量（`local/tests`）：`Ran 2798 tests in 238.012s`，`OK (skipped=2)`。
- 变异反证：在 `%TEMP%` 独立副本先确认无变异基线全绿，随后五条单点变异均按预期失败（`exit=1`），详情见 `mutations.md`。

## 未验证项

- 真实手机浏览器连接真机桌面工具并模拟业务时钟未校准（`business_clock` unavailable）及真实校园网列表返回非标准时间文本的端到端视觉联调尚未在真机执行。
- 本机全量测试中既有的 2 条环境条件跳过用例（`skipped=2`）未在本机覆盖。

## 复现命令

```bash
python tools/code_shape/check.py
python -m unittest discover -s local/tests -p "test_phone_service.py"
python -m unittest discover -s local/tests -p "test_phone_ui.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_code_shape.py"
python -m unittest discover -s local/tests -p "test_*.py"
```
