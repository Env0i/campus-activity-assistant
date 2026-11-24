# 全仓库目录结构整理（2026-11-24）

- **日期**：2026-11-24
- **分支**：`refactor/layout`
- **范围**：只调整文件归属目录与对应导入路径、配置/守卫路径及现行文档路径（S1–S11），不改变函数体、类体、业务字符串、数据模型或学校接口契约；不留旧位置转发壳或软链接。
- **未搬迁 / 未改动边界**：
  - 桌面端界面源码 `local/ui/` 除手机页 `local/ui/m/` 外不动（`state/`、`views/`、`controllers/`、`features/`、`shared/`、`app.js`、`index.html`、`main.js`、`legacy-globals.js`、`boot-guard.js` 保持原位）。
  - 打包入口与构建脚本：`local/app.py`、`local/grab.py`、`local/update_launcher.py`、`local/advanced_helper.py`、`local/signup_plan.py`、`local/build/*`（含历史 `local/build/make_portable.py`）保持原位。
  - `local/tests/fixtures/`、`tools/code_shape/`、`server/scripts/dev/`、`server/bot/`、`server/tests/`、`server/deploy/legacy/`、`server/deploy/logrotate/` 保持原位。
  - 历史文档与设计真源（`design/decisions/`、`design/specs/`、`design/prototype/`、`design/archive/`、`docs/archive/`、`docs/superpowers/`、`docs/README.md` 2026-11-03 迁移表、`CHANGELOG.md`、`VERSION`）及根目录约定文件（根 `README.md`、`CLAUDE.md`、`aoci*`）保持原位、不做追改。

## 历史证据目录不回改声明

**所有早于本次整理的历史证据目录（`design/evidence/<更早日期>/`）一律不回改。**
其中记录的旧路径、变异脚本参数与复现命令属于当时执行现场的真实过程记录。
如需基于当前代码库复跑历史证据里的变异脚本、静态检查或回放命令，请使用下方「旧路径 → 新路径对照表」将涉及的旧路径逐项换算为新路径。

## 完整旧路径 → 新路径对照表（共 176 项，按 S1–S10 分节）

> 注：Python 新子目录（`local/domain/*`、`local/application/*`、`local/infrastructure/*`、`local/tests/*`、`server/scripts/*`）各新建空 `__init__.py`（共 41 个）；`tools/`、`server/deploy/`、`local/dev/`、`local/launchers/dev/`、`local/ui/m/` 不建 `__init__.py`。

### S1 application/（30 个）

| 旧路径 | 新路径 |
|---|---|
| `local/application/activity_list_service.py` | `local/application/activity/activity_list_service.py` |
| `local/application/advanced_component_service.py` | `local/application/components/advanced_component_service.py` |
| `local/application/auto_relogin.py` | `local/application/login/auto_relogin.py` |
| `local/application/clock_service.py` | `local/application/desktop/clock_service.py` |
| `local/application/component_actions.py` | `local/application/components/component_actions.py` |
| `local/application/component_projection.py` | `local/application/components/component_projection.py` |
| `local/application/desktop_lifecycle.py` | `local/application/desktop/desktop_lifecycle.py` |
| `local/application/desktop_window.py` | `local/application/desktop/desktop_window.py` |
| `local/application/login_recovery.py` | `local/application/login/login_recovery.py` |
| `local/application/login_relay_service.py` | `local/application/login/login_relay_service.py` |
| `local/application/login_service.py` | `local/application/login/login_service.py` |
| `local/application/phone_access_session.py` | `local/application/phone/phone_access_session.py` |
| `local/application/phone_service.py` | `local/application/phone/phone_service.py` |
| `local/application/plan_admission.py` | `local/application/plan/plan_admission.py` |
| `local/application/plan_service.py` | `local/application/plan/plan_service.py` |
| `local/application/relogin_entry.py` | `local/application/login/relogin_entry.py` |
| `local/application/signup_browser.py` | `local/application/signup/signup_browser.py` |
| `local/application/signup_cancellation.py` | `local/application/signup/signup_cancellation.py` |
| `local/application/signup_direct.py` | `local/application/signup/signup_direct.py` |
| `local/application/signup_finalize.py` | `local/application/signup/signup_finalize.py` |
| `local/application/signup_ledger.py` | `local/application/signup/signup_ledger.py` |
| `local/application/signup_outcome.py` | `local/application/signup/signup_outcome.py` |
| `local/application/signup_policy.py` | `local/application/signup/signup_policy.py` |
| `local/application/signup_run.py` | `local/application/signup/signup_run.py` |
| `local/application/signup_target.py` | `local/application/signup/signup_target.py` |
| `local/application/update_service.py` | `local/application/desktop/update_service.py` |
| `local/application/worker_activity_list.py` | `local/application/worker/worker_activity_list.py` |
| `local/application/worker_cancel.py` | `local/application/worker/worker_cancel.py` |
| `local/application/worker_login.py` | `local/application/worker/worker_login.py` |
| `local/application/worker_service.py` | `local/application/worker/worker_service.py` |

### S2 infrastructure/（19 个）

| 旧路径 | 新路径 |
|---|---|
| `local/infrastructure/activity_queries.py` | `local/infrastructure/school/activity_queries.py` |
| `local/infrastructure/advanced_features.py` | `local/infrastructure/components/advanced_features.py` |
| `local/infrastructure/component_packages.py` | `local/infrastructure/components/component_packages.py` |
| `local/infrastructure/credential_store.py` | `local/infrastructure/stores/credential_store.py` |
| `local/infrastructure/data_directory.py` | `local/infrastructure/stores/data_directory.py` |
| `local/infrastructure/feishu_webhook.py` | `local/infrastructure/notify/feishu_webhook.py` |
| `local/infrastructure/lifecycle_store.py` | `local/infrastructure/stores/lifecycle_store.py` |
| `local/infrastructure/login_session_store.py` | `local/infrastructure/stores/login_session_store.py` |
| `local/infrastructure/phone_http.py` | `local/infrastructure/phone/phone_http.py` |
| `local/infrastructure/phone_qr.py` | `local/infrastructure/phone/phone_qr.py` |
| `local/infrastructure/phone_session_store.py` | `local/infrastructure/stores/phone_session_store.py` |
| `local/infrastructure/prefs_store.py` | `local/infrastructure/stores/prefs_store.py` |
| `local/infrastructure/process_tree.py` | `local/infrastructure/desktop/process_tree.py` |
| `local/infrastructure/school_http.py` | `local/infrastructure/school/school_http.py` |
| `local/infrastructure/single_instance.py` | `local/infrastructure/desktop/single_instance.py` |
| `local/infrastructure/tray_icon.py` | `local/infrastructure/desktop/tray_icon.py` |
| `local/infrastructure/tunnel_manager.py` | `local/infrastructure/phone/tunnel_manager.py` |
| `local/infrastructure/webview_mime.py` | `local/infrastructure/desktop/webview_mime.py` |
| `local/infrastructure/worker_log.py` | `local/infrastructure/worker/worker_log.py` |

### S3 domain/（14 个）

| 旧路径 | 新路径 |
|---|---|
| `local/domain/cancel_rules.py` | `local/domain/signup/cancel_rules.py` |
| `local/domain/component_rules.py` | `local/domain/components/component_rules.py` |
| `local/domain/demo_data.py` | `local/domain/common/demo_data.py` |
| `local/domain/errors.py` | `local/domain/common/errors.py` |
| `local/domain/lifecycle_rules.py` | `local/domain/desktop/lifecycle_rules.py` |
| `local/domain/log_events.py` | `local/domain/worker/log_events.py` |
| `local/domain/login_rules.py` | `local/domain/login/login_rules.py` |
| `local/domain/phone_rules.py` | `local/domain/phone/phone_rules.py` |
| `local/domain/plan_rules.py` | `local/domain/plan/plan_rules.py` |
| `local/domain/retry_rules.py` | `local/domain/signup/retry_rules.py` |
| `local/domain/retry_window.py` | `local/domain/signup/retry_window.py` |
| `local/domain/signup_reply.py` | `local/domain/signup/signup_reply.py` |
| `local/domain/time_text.py` | `local/domain/common/time_text.py` |
| `local/domain/worker_lines.py` | `local/domain/worker/worker_lines.py` |

### S4 local/ 根模块归入 infrastructure/（10 个）

| 旧路径 | 新路径 |
|---|---|
| `local/business_clock.py` | `local/infrastructure/clock/business_clock.py` |
| `local/login_relay.py` | `local/infrastructure/login/login_relay.py` |
| `local/runtime_paths.py` | `local/infrastructure/stores/runtime_paths.py` |
| `local/signup_signing.py` | `local/infrastructure/signup/signup_signing.py` |
| `local/signup_transport.py` | `local/infrastructure/signup/signup_transport.py` |
| `local/site_target.py` | `local/infrastructure/school/site_target.py` |
| `local/time_contract.py` | `local/infrastructure/clock/time_contract.py` |
| `local/update_check.py` | `local/infrastructure/update/update_check.py` |
| `local/update_delta.py` | `local/infrastructure/update/update_delta.py` |
| `local/updater.py` | `local/infrastructure/update/updater.py` |

### S5 local/ 开发入口（3 个）

| 旧路径 | 新路径 |
|---|---|
| `local/dev_phone_preview.py` | `local/dev/dev_phone_preview.py` |
| `local/开发-启动界面.bat` | `local/launchers/dev/开发-启动界面.bat` |
| `local/开发-预览手机页.bat` | `local/launchers/dev/开发-预览手机页.bat` |

### S6 手机页 local/ui/m/（14 个）

| 旧路径 | 新路径 |
|---|---|
| `local/ui/m/apple-touch-icon.png` | `local/ui/m/assets/apple-touch-icon.png` |
| `local/ui/m/favicon.ico` | `local/ui/m/assets/favicon.ico` |
| `local/ui/m/model-conflict.js` | `local/ui/m/model/model-conflict.js` |
| `local/ui/m/model-list.js` | `local/ui/m/model/model-list.js` |
| `local/ui/m/model-relogin.js` | `local/ui/m/model/model-relogin.js` |
| `local/ui/m/model-run.js` | `local/ui/m/model/model-run.js` |
| `local/ui/m/model.js` | `local/ui/m/model/model.js` |
| `local/ui/m/ui-list.js` | `local/ui/m/ui/ui-list.js` |
| `local/ui/m/ui-plan.js` | `local/ui/m/ui/ui-plan.js` |
| `local/ui/m/ui-relogin.js` | `local/ui/m/ui/ui-relogin.js` |
| `local/ui/m/ui-session.js` | `local/ui/m/ui/ui-session.js` |
| `local/ui/m/ui-shell.js` | `local/ui/m/ui/ui-shell.js` |
| `local/ui/m/ui-status.js` | `local/ui/m/ui/ui-status.js` |
| `local/ui/m/ui-sync.js` | `local/ui/m/ui/ui-sync.js` |

### S7 测试 local/tests/（39 个）

| 旧路径 | 新路径 |
|---|---|
| `local/tests/test_application_services.py` | `local/tests/desktop/test_application_services.py` |
| `local/tests/test_business_clock.py` | `local/tests/desktop/test_business_clock.py` |
| `local/tests/test_cancel_signup.py` | `local/tests/signup/test_cancel_signup.py` |
| `local/tests/test_code_shape.py` | `local/tests/architecture/test_code_shape.py` |
| `local/tests/test_component_domain.py` | `local/tests/components/test_component_domain.py` |
| `local/tests/test_component_packages.py` | `local/tests/components/test_component_packages.py` |
| `local/tests/test_concurrency_guards.py` | `local/tests/architecture/test_concurrency_guards.py` |
| `local/tests/test_credential_store.py` | `local/tests/login/test_credential_store.py` |
| `local/tests/test_layer_boundaries.py` | `local/tests/architecture/test_layer_boundaries.py` |
| `local/tests/test_list_signed.py` | `local/tests/signup/test_list_signed.py` |
| `local/tests/test_login_relay.py` | `local/tests/login/test_login_relay.py` |
| `local/tests/test_login_relogin.py` | `local/tests/login/test_login_relogin.py` |
| `local/tests/test_network_policy.py` | `local/tests/school/test_network_policy.py` |
| `local/tests/test_phone_infra.py` | `local/tests/phone/test_phone_infra.py` |
| `local/tests/test_phone_rules.py` | `local/tests/phone/test_phone_rules.py` |
| `local/tests/test_phone_service.py` | `local/tests/phone/test_phone_service.py` |
| `local/tests/test_phone_ui.py` | `local/tests/phone/test_phone_ui.py` |
| `local/tests/test_qa_bridge_contract.py` | `local/tests/school/test_qa_bridge_contract.py` |
| `local/tests/test_real_data_contract.py` | `local/tests/school/test_real_data_contract.py` |
| `local/tests/test_retry_policy.py` | `local/tests/signup/test_retry_policy.py` |
| `local/tests/test_school_contract.py` | `local/tests/school/test_school_contract.py` |
| `local/tests/test_session_persistence.py` | `local/tests/login/test_session_persistence.py` |
| `local/tests/test_signup_plan.py` | `local/tests/signup/test_signup_plan.py` |
| `local/tests/test_signup_reply.py` | `local/tests/signup/test_signup_reply.py` |
| `local/tests/test_signup_signing.py` | `local/tests/signup/test_signup_signing.py` |
| `local/tests/test_signup_transport.py` | `local/tests/signup/test_signup_transport.py` |
| `local/tests/test_single_instance.py` | `local/tests/desktop/test_single_instance.py` |
| `local/tests/test_site_target.py` | `local/tests/school/test_site_target.py` |
| `local/tests/test_tunnel_manager.py` | `local/tests/phone/test_tunnel_manager.py` |
| `local/tests/test_ui_components_and_phone.py` | `local/tests/screens/test_ui_components_and_phone.py` |
| `local/tests/test_ui_contracts.py` | `local/tests/screens/test_ui_contracts.py` |
| `local/tests/test_ui_layers.py` | `local/tests/architecture/test_ui_layers.py` |
| `local/tests/test_ui_login.py` | `local/tests/screens/test_ui_login.py` |
| `local/tests/test_ui_main_window.py` | `local/tests/screens/test_ui_main_window.py` |
| `local/tests/test_ui_plan.py` | `local/tests/screens/test_ui_plan.py` |
| `local/tests/test_ui_reliability.py` | `local/tests/screens/test_ui_reliability.py` |
| `local/tests/test_updater.py` | `local/tests/desktop/test_updater.py` |
| `local/tests/test_worker_boundaries.py` | `local/tests/worker/test_worker_boundaries.py` |
| `local/tests/test_worker_logs.py` | `local/tests/worker/test_worker_logs.py` |

### S8 工具 tools/（13 个）

| 旧路径 | 新路径 |
|---|---|
| `tools/build_update_delta.py` | `tools/release/build_update_delta.py` |
| `tools/qa_business_clock_worker.py` | `tools/qa/qa_business_clock_worker.py` |
| `tools/qa_runtime_reliability.py` | `tools/qa/qa_runtime_reliability.py` |
| `tools/release.py` | `tools/release/release.py` |
| `tools/release_guards.py` | `tools/release/release_guards.py` |
| `tools/release_tests/test_dependency_pins.py` | `tools/release/tests/test_dependency_pins.py` |
| `tools/release_tests/test_installer_script.py` | `tools/release/tests/test_installer_script.py` |
| `tools/release_tests/test_lifecycle_release.py` | `tools/release/tests/test_lifecycle_release.py` |
| `tools/release_tests/test_release_audit.py` | `tools/release/tests/test_release_audit.py` |
| `tools/release_tests/test_release_guards.py` | `tools/release/tests/test_release_guards.py` |
| `tools/release_tests/test_runtime_bundle.py` | `tools/release/tests/test_runtime_bundle.py` |
| `tools/split_branches.py` | `tools/dev/split_branches.py` |
| `tools/verify_autologin_loop.py` | `tools/qa/verify_autologin_loop.py` |

### S9 服务器脚本 server/scripts/（21 个）

| 旧路径 | 新路径 |
|---|---|
| `server/scripts/activity_watch.py` | `server/scripts/push/activity_watch.py` |
| `server/scripts/card.py` | `server/scripts/lib/card.py` |
| `server/scripts/common.py` | `server/scripts/lib/common.py` |
| `server/scripts/fetch.py` | `server/scripts/lib/fetch.py` |
| `server/scripts/grab_card.py` | `server/scripts/signup/grab_card.py` |
| `server/scripts/login.py` | `server/scripts/login/login.py` |
| `server/scripts/net_probe.py` | `server/scripts/ops/net_probe.py` |
| `server/scripts/notify.py` | `server/scripts/lib/notify.py` |
| `server/scripts/query.py` | `server/scripts/push/query.py` |
| `server/scripts/regress.py` | `server/scripts/ops/regress.py` |
| `server/scripts/remind.py` | `server/scripts/push/remind.py` |
| `server/scripts/render.py` | `server/scripts/lib/render.py` |
| `server/scripts/run.py` | `server/scripts/push/run.py` |
| `server/scripts/scan.py` | `server/scripts/push/scan.py` |
| `server/scripts/selfcheck.py` | `server/scripts/ops/selfcheck.py` |
| `server/scripts/site_target.py` | `server/scripts/lib/site_target.py` |
| `server/scripts/token_probe.py` | `server/scripts/login/token_probe.py` |
| `server/scripts/token_report.py` | `server/scripts/login/token_report.py` |
| `server/scripts/trigger_server.py` | `server/scripts/ops/trigger_server.py` |
| `server/scripts/watchlist.py` | `server/scripts/signup/watchlist.py` |
| `server/scripts/watchlist_runner.py` | `server/scripts/signup/watchlist_runner.py` |

### S10 服务器部署 server/deploy/（13 个）

| 旧路径 | 新路径 |
|---|---|
| `server/deploy/atomic_json.js` | `server/deploy/login/atomic_json.js` |
| `server/deploy/auto_login.py` | `server/deploy/login/auto_login.py` |
| `server/deploy/campus-autologin.service` | `server/deploy/systemd/campus-autologin.service` |
| `server/deploy/campus-autologin.timer` | `server/deploy/systemd/campus-autologin.timer` |
| `server/deploy/campus-login.service` | `server/deploy/systemd/campus-login.service` |
| `server/deploy/deploy.sh` | `server/deploy/install/deploy.sh` |
| `server/deploy/grab_signup.py` | `server/deploy/signup/grab_signup.py` |
| `server/deploy/make_template.sh` | `server/deploy/install/make_template.sh` |
| `server/deploy/remote_install.sh` | `server/deploy/install/remote_install.sh` |
| `server/deploy/server_refresh.js` | `server/deploy/login/server_refresh.js` |
| `server/deploy/set_credentials.py` | `server/deploy/install/set_credentials.py` |
| `server/deploy/sync_token.sh` | `server/deploy/install/sync_token.sh` |
| `server/deploy/test_atomic_json.js` | `server/deploy/login/test_atomic_json.js` |
## 变更后关键守卫与期望值说明

- **存量名单等价搬迁**：
  - `tools/code_shape/baseline.json`：仅替换被搬迁文件的路径键，维持总条目数 **156**（`files.over800` 9、`files.over500` 11、`functions.over100` 30、`functions.over60` 83、`test_functions` 19、`classes` 4），数值、理由与分档原样保留（未顺手收紧）。
  - `ruff.toml`：`[lint.per-file-ignores]` 仅替换被搬迁文件路径键，维持 **28** 个文件条目、**30** 个规则码条目不变。
- **分层守卫递归与越层复核**：
  - `local/tests/architecture/test_layer_boundaries.py` 改为 `.rglob("*.py")` 递归扫描子目录，并同时匹配旧短名与点分模块路径（如 `infrastructure.clock.business_clock`）。
  - 在隔离临时副本中向 `domain/common/errors.py` 与 `application/activity/activity_list_service.py` 各注入一行 `from infrastructure.clock import business_clock`，运行 `test_layer_boundaries.py` 确认两条越层导入均被拦截失败（19 用例中 2 FAIL：`ImportBoundaryTests.test_domain_and_application_import_no_mixed_concrete_modules` 拦截 `domain/common/errors.py`，`LayerDirectionTests.test_inner_layers_import_only_allowed_directions` 同时拦截上述 `application/` 与 `domain/` 两处越层依赖），复核完成后已清除临时副本。
- **跨波次测试路径引用更新**：
  - `local/tests/school/test_qa_bridge_contract.py`：`ROOT / "tools" / "qa" / "qa_runtime_reliability.py"`
  - `local/tests/school/test_network_policy.py`：`LOCAL.parent / "tools" / "release" / "release.py"`
  - `local/tests/screens/test_ui_contracts.py`：注释更新为 `tools/qa/qa_runtime_reliability.py`
- **持续集成与提交钩子**：
  - `.github/workflows/ci.yml`：`server/deploy/login/test_atomic_json.js`（已核对全部脚本、依赖文件与测试路径存在，`local/ui/*.js local/ui/*/*.js local/ui/*/*/*.js` 覆盖全部 99 个 JS 文件）。
  - `.githooks/pre-commit`：`local/tests/architecture/test_layer_boundaries.py`、`local/tests/architecture/test_ui_layers.py`、`local/tests/architecture/test_code_shape.py`。

## 验证汇总（截至第四波收尾）

### 已验证（第四波直接执行通过）

- `python tools/code_shape/check.py`：exit 0（文件 >800 行 9、501–800 行 11；函数 >100 行 23、61–100 行 67；测试函数 >60 行 19；属性超标类 2）
- `python -m ruff check local server tools`：exit 0
- `python -m unittest discover -s local/tests -p "test_code_shape.py" -v`：15 run, OK
- `python -m unittest discover -s local/tests -p "test_layer_boundaries.py" -v`：19 run, OK（另在临时副本完成越层注入必红验证）
- `python -m unittest discover -s local/tests -p "test_ui_layers.py" -v`：31 run, OK
- `python -m unittest discover -s local/tests -p "test_qa_bridge_contract.py" -v`：4 run, OK
- `python -m unittest discover -s local/tests -p "test_network_policy.py" -v`：11 run, OK
- `python -m pytest server/tests -q`：123 passed, 0 failed, 0 skipped
- Node 离线测试：`node server/bot/test_bot_runtime.js`（37 pass, 0 fail）、`node server/bot/test_handled_messages.js`（8 pass）、`node server/deploy/login/test_atomic_json.js`（6 pass, 0 fail）
- 文档与配置残余旧路径只读扫描：0 残留；CI 与钩子引用路径存在性核对全部通过；中文乱码正则与严格 UTF-8 解码：0 命中

### 仍待收尾回归 / 未验证项

- **待后续收尾回归任务执行**：全仓库搬迁后的 `local/tests` 39 个文件全量单测回归、`python -m compileall`、`local/ui/**/*.js` 全量 `node --check`、`tools/release/tests` 回归，以及 `local/build/build_exe.py --mode onefile` 重新打包后的 `--demo` 窗口启动与 `grab-worker` 无联网加载验证。
- **本轮不具备执行条件 / 未授权项**：**服务器版未重新部署、真机 Safari 未复测**；根 `README.md` 属根目录约定文件未改（由收尾人工/指挥侧处理）；未执行 `git add` / `git commit` / `git push`。
