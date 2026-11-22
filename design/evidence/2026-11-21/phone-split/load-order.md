# 加载顺序反证记录

在基于 `git archive HEAD` 叠加工作区改动的临时副本中，对 `local/ui/m/index.html` 的 `<script src>` 清单依次做三次破坏性改动，分别执行测试，验证错误会被测试立即拦下（运行后清理临时副本）。

| 序号 | 临时副本改法 | 测试文件 | 退出码 | 首个失败用例 | 报错摘要 |
|---|---|---|---:|---|---|
| 1 | 删掉 `index.html` 中 `<script src="ui-plan.js"></script>` 这一行 | `test_phone_ui.py` | 1 | `ExceptionStatesTests.test_alert_priority_chain_follows_prototype` | `m/ui-shell.js:272`：`ReferenceError: startPlan is not defined` |
| 1 | 同上（删掉 `ui-plan.js` 这一行） | `test_phone_infra.py` | 1 | `RoundTripTests.test_phone_static_matches_index_html_and_disk` | `AssertionError: 'ui-plan.js' not found in [...] : PHONE_STATIC 里的 ui-plan.js 未被 index.html 引用` |
| 2 | 把 `ui-shell.js` 挪到 `ui` 文件第一位（排在 `ui-session.js` 之前） | `test_phone_ui.py` | 1 | `ExceptionStatesTests.test_alert_priority_chain_follows_prototype` | `m/ui-shell.js:271`：`ReferenceError: model is not defined` |
| 3 | 对调 `model.js` 与 `model-conflict.js` 的先后顺序 | `test_phone_ui.py` | 1 | `ExceptionStatesTests.test_alert_priority_chain_follows_prototype` | `m/model-conflict.js:6`：`ReferenceError: PhoneModel is not defined` |

结论：三次反证均如期变红（`test_phone_ui.py` 三次全红，第 1 次 `test_phone_infra.py` 同步变红）。
