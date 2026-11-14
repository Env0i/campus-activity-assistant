## review2 表 D 独立复算

| 组 | 文件数 | 函数数 | 都标了 | 一部分 | 完全没标 |
|---|---|---|---|---|---|
| local/domain | 14 | 83 | 16 | 49 | 18 |
| local/application | 8 | 96 | 46 | 30 | 20 |
| local/infrastructure | 13 | 208 | 74 | 48 | 86 |
| local 根目录 | 15 | 614 | 325 | 87 | 202 |
| server | 29 | 261 | 87 | 28 | 146 |
| local/build | 4 | 45 | 31 | 0 | 14 |
| local 其他子目录 | 0 | 0 | 0 | 0 | 0 |

全部函数合计：1307；都标了 579、一部分 242、完全没标 486。

### 每组函数最多的十个文件

| 组 | 文件 | 函数数 | 都标 | 部分 | 没标 |
|---|---|---|---|---|---|
| local/domain | `local/domain/phone_rules.py` | 28 | 0 | 18 | 10 |
| local/domain | `local/domain/login_rules.py` | 11 | 6 | 5 | 0 |
| local/domain | `local/domain/retry_rules.py` | 7 | 3 | 4 | 0 |
| local/domain | `local/domain/retry_window.py` | 7 | 0 | 0 | 7 |
| local/domain | `local/domain/plan_rules.py` | 6 | 0 | 6 | 0 |
| local/domain | `local/domain/log_events.py` | 5 | 0 | 5 | 0 |
| local/domain | `local/domain/time_text.py` | 5 | 0 | 5 | 0 |
| local/domain | `local/domain/lifecycle_rules.py` | 4 | 3 | 0 | 1 |
| local/domain | `local/domain/cancel_rules.py` | 3 | 1 | 2 | 0 |
| local/domain | `local/domain/signup_reply.py` | 3 | 0 | 3 | 0 |
| local/application | `local/application/phone_service.py` | 27 | 19 | 7 | 1 |
| local/application | `local/application/login_relay_service.py` | 22 | 7 | 14 | 1 |
| local/application | `local/application/advanced_component_service.py` | 20 | 14 | 3 | 3 |
| local/application | `local/application/auto_relogin.py` | 11 | 0 | 0 | 11 |
| local/application | `local/application/update_service.py` | 8 | 1 | 3 | 4 |
| local/application | `local/application/plan_service.py` | 6 | 4 | 2 | 0 |
| local/application | `local/application/login_service.py` | 2 | 1 | 1 | 0 |
| local/application | `local/application/__init__.py` | 0 | 0 | 0 | 0 |
| local/infrastructure | `local/infrastructure/component_packages.py` | 70 | 0 | 8 | 62 |
| local/infrastructure | `local/infrastructure/phone_http.py` | 31 | 13 | 2 | 16 |
| local/infrastructure | `local/infrastructure/single_instance.py` | 20 | 10 | 8 | 2 |
| local/infrastructure | `local/infrastructure/tunnel_manager.py` | 17 | 4 | 8 | 5 |
| local/infrastructure | `local/infrastructure/credential_store.py` | 13 | 13 | 0 | 0 |
| local/infrastructure | `local/infrastructure/lifecycle_store.py` | 12 | 10 | 2 | 0 |
| local/infrastructure | `local/infrastructure/process_tree.py` | 12 | 6 | 5 | 1 |
| local/infrastructure | `local/infrastructure/tray_icon.py` | 10 | 8 | 2 | 0 |
| local/infrastructure | `local/infrastructure/advanced_features.py` | 8 | 3 | 5 | 0 |
| local/infrastructure | `local/infrastructure/phone_session_store.py` | 8 | 4 | 4 | 0 |
| local 根目录 | `local/app.py` | 218 | 184 | 22 | 12 |
| local 根目录 | `local/grab.py` | 161 | 10 | 4 | 147 |
| local 根目录 | `local/business_clock.py` | 50 | 41 | 9 | 0 |
| local 根目录 | `local/login_relay.py` | 38 | 0 | 9 | 29 |
| local 根目录 | `local/signup_plan.py` | 26 | 26 | 0 | 0 |
| local 根目录 | `local/update_check.py` | 24 | 14 | 10 | 0 |
| local 根目录 | `local/update_delta.py` | 18 | 9 | 8 | 1 |
| local 根目录 | `local/updater.py` | 18 | 6 | 10 | 2 |
| local 根目录 | `local/update_launcher.py` | 17 | 10 | 5 | 2 |
| local 根目录 | `local/time_contract.py` | 13 | 5 | 7 | 1 |
| server | `server/deploy/grab_signup.py` | 41 | 0 | 0 | 41 |
| server | `server/deploy/auto_login.py` | 29 | 1 | 0 | 28 |
| server | `server/scripts/card.py` | 22 | 3 | 1 | 18 |
| server | `server/scripts/notify.py` | 20 | 10 | 10 | 0 |
| server | `server/scripts/activity_watch.py` | 19 | 14 | 5 | 0 |
| server | `server/scripts/common.py` | 16 | 11 | 1 | 4 |
| server | `server/scripts/fetch.py` | 14 | 10 | 3 | 1 |
| server | `server/scripts/watchlist.py` | 12 | 8 | 3 | 1 |
| server | `server/scripts/run.py` | 10 | 7 | 2 | 1 |
| server | `server/scripts/render.py` | 8 | 0 | 0 | 8 |
| local/build | `local/build/build_advanced.py` | 14 | 0 | 0 | 14 |
| local/build | `local/build/make_portable.py` | 13 | 13 | 0 | 0 |
| local/build | `local/build/build_installer.py` | 12 | 12 | 0 | 0 |
| local/build | `local/build/build_exe.py` | 6 | 6 | 0 | 0 |

## 复核说明（软件架构师）

- find 独立复算各组文件数全一致（local 根 15、domain 14、application 8、infrastructure 13、build 4、server 29、其他 0）；自写 ast 片段重数 local/app.py 218/184/22/12、tunnel_manager.py 17/4/8/5，与脚本一致；合计等式 1307=579+242+486 机械核对通过。
