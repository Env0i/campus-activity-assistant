# 模块级 DEMO

- 生成脚本：`scripts/field_map.py`（ast 读 local/app.py 与 local/tests/*.py）
- 命令：`python -B design/evidence/<日期>/api-coordination/scripts/field_map.py --head 788b25c`
- 基线：`788b25c`；DEMO 读点 22 个函数、31 处；测试打补丁 27 处

## 读点（按将来归属的服务归）

| 函数/方法 | 功能 | 读处 | 行 |
|---|---|---|---|
| `Api.__init__` | 其他 | 1 | 976 |
| `Api._cancel_signup_run` | 计划 | 1 | 2448 |
| `Api._clock_now` | 时钟 | 1 | 981 |
| `Api._clock_payload` | 时钟 | 1 | 1022 |
| `Api._do_check_inner` | 登录恢复 | 1 | 2261 |
| `Api._do_list_inner` | 活动列表 | 1 | 2539 |
| `Api._log_event` | 其他 | 1 | 1957 |
| `Api._push_login_expired` | 登录恢复 | 1 | 2231 |
| `Api._relogin_entry_gate` | 登录恢复 | 1 | 3975 |
| `Api._silent_relogin_ready` | 登录恢复 | 1 | 1809 |
| `Api._start_plan_inner` | 计划 | 5 | 2862、2869、2877、3022、3054 |
| `Api._terms_gate` | 其他 | 1 | 1134 |
| `Api.bootstrap` | 其他 | 2 | 1148、1181 |
| `Api.grab` | 其他 | 1 | 2641 |
| `Api.login` | 登录恢复 | 1 | 2622 |
| `Api.phone_relogin_begin` | 登录恢复 | 1 | 4072 |
| `Api.run` | 其他 | 1 | 3841 |
| `Api.runner` | 其他 | 1 | 3022 |
| `Api.schedule_component_auto_update` | 更新 | 2 | 3828、3841 |
| `Api.sync_clock` | 时钟 | 2 | 1053、1059 |
| `main` | 其他 | 3 | 4654、4671、4683 |
| `phone_log` | 手机访问 | 1 | 157 |

按功能汇总：更新 1、手机访问 1、登录恢复 6、计划 2、活动列表 1、时钟 3、其他 8

## 测试打补丁的地方

| 测试文件 | 补丁次数 |
|---|---|
| `local/tests/test_application_services.py` | 11 |
| `local/tests/test_cancel_signup.py` | 3 |
| `local/tests/test_relogin_busy_order.py` | 1 |
| `local/tests/test_retry_phone_policy.py` | 1 |
| `local/tests/test_runtime_bundle.py` | 6 |
| `local/tests/test_session_persistence.py` | 2 |
| `local/tests/test_silent_relogin.py` | 1 |
| `local/tests/test_single_instance.py` | 2 |

## 与 2026-11-12 审计的对照

审计（基线 `7e2d31c`）：DEMO 被 22 个函数读、测试补丁 24 次。本次：22 个函数、27 次。

读点数与审计一致（22 个函数）。补丁数比审计多 3 处，两头都核过：

- 按本脚本的口径（只数 `patch.object` / `patch("app.X")` / `setattr` 的调用点），基线 `7e2d31c` 是 26 处，审计的 24 少 2 —— 少的是`for patch in (mock.patch.object(..., "DEMO", ...),)` 这种先收集后启动的元组写法，审计只数了 `mock.patch.object(...)` 直接出现的行。
- 26 → 27 的那 1 处是 `local/tests/test_relogin_busy_order.py`：基线没有这个文件，它是 `636da16` 之后新增的用例文件。

另有一种不走 patch 的注入：`local/tests/test_terms_consent.py` 把 DEMO 写进伪模块的命名空间字典（`{"DEMO": demo, ...}`），再用它 exec 模块级函数——2 处，不计入上表，因为它替换的是整个模块而不是属性。

