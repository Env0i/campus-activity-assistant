# online.md——联网试跑（表 H，计划 D10）

- 授权依据：用户下达任务时写明「允许联网安装一次（mypy、coverage、ruff 装进 tempfile.mkdtemp() 的 --target 目录），并跑一遍带覆盖率的本机全量」。
- 安装与运行全部发生在 tempfile.mkdtemp() 新建的空目录；下文一律写作 `<临时目录>`。落盘前已把命令与输出里的临时目录真路径替换成 `<临时目录>`；该目录收工删除，真实路径不留档。
- 只联网这一次（pip install）；此后 H1、H2、H3 均为离线运行。

## 工具版本与安装

- 安装命令（一次）：`python -m pip install --quiet --target <临时目录>/site mypy coverage ruff==0.17.5`
- 实际版本：mypy 2.4.1（compiled: yes）；coverage 7.17.3（with C extension）；ruff 0.17.5。
- 调用方式：把 `<临时目录>/site` 放进 PYTHONPATH；未装进任何 Python 环境，未在仓库新建任何配置文件（mypy.ini、pyproject.toml、.coveragerc、package.json 都没有建）。

## H1 mypy（D10 H1）

第二轮复核（design/evidence/2026-11-13/refactor-endpoint/review2/tables/H.md）用同版本（mypy 2.4.1）同命令、各自新建缓存目录把 H1 的六条命令重跑了一遍：错误总数 61（默认）与 1270（--strict）两轮相同；「目录×错误码」的分布两轮不同（默认模式如 local/infrastructure × assignment 第一轮 14、第二轮 13，local/domain × arg-type 第一轮 3、第二轮 7；--strict 模式如 local/infrastructure × no-untyped-call 第一轮 254、第二轮 429）。总数可复现，按目录×错误码的分布不可跨轮复现。下面把第二轮的分布与第一轮并排列出：第一轮值取自本文件下文原表，第二轮值取自 design/evidence/2026-11-13/refactor-endpoint/review2/tables/H.md；本节按本计划 decisions D3 落盘，不重跑。

默认严格度（两轮的组合都全列：第一轮 14 个、第二轮 12 个；某轮没有的组合记 0）：

| 目录 | 错误码 | 第一轮条数 | 第二轮条数 |
|---|---|---|---|
| local/application | arg-type | 3 | 0 |
| local/application | assignment | 1 | 1 |
| local/application | misc | 4 | 4 |
| local/application | union-attr | 6 | 6 |
| local/application | valid-type | 1 | 1 |
| local/application | var-annotated | 4 | 1 |
| local/domain | arg-type | 3 | 7 |
| local/domain | assignment | 1 | 2 |
| local/infrastructure | arg-type | 1 | 0 |
| local/infrastructure | assignment | 14 | 13 |
| local/infrastructure | attr-defined | 10 | 10 |
| local/infrastructure | index | 1 | 1 |
| local/infrastructure | return-value | 6 | 6 |
| local/infrastructure | var-annotated | 6 | 9 |

（第一轮列合计 61、第二轮列合计 61，与各自错误总数一致。）

--strict（两轮都只落到各自前 20：第一轮前 20 合计 1242、第二轮前 20 合计 1250，都小于总数 1270；「不在前 20」指该组合没进那一轮的前 20，条数未知，不代表 0）：

| 目录 | 错误码 | 第一轮条数 | 第二轮条数 |
|---|---|---|---|
| local/application | assignment | 5 | 不在前 20 |
| local/application | index | 35 | 35 |
| local/application | no-untyped-call | 246 | 16 |
| local/application | no-untyped-def | 186 | 50 |
| local/application | type-arg | 73 | 42 |
| local/application | union-attr | 25 | 19 |
| local/application | var-annotated | 5 | 不在前 20 |
| local/domain | arg-type | 不在前 20 | 7 |
| local/domain | assignment | 6 | 16 |
| local/domain | no-any-return | 不在前 20 | 9 |
| local/domain | no-untyped-call | 29 | 84 |
| local/domain | no-untyped-def | 72 | 177 |
| local/domain | type-arg | 28 | 54 |
| local/infrastructure | assignment | 19 | 13 |
| local/infrastructure | attr-defined | 10 | 10 |
| local/infrastructure | no-any-return | 11 | 9 |
| local/infrastructure | no-untyped-call | 254 | 429 |
| local/infrastructure | no-untyped-def | 175 | 206 |
| local/infrastructure | return-value | 6 | 不在前 20 |
| local/infrastructure | type-arg | 44 | 45 |
| local/infrastructure | union-attr | 6 | 12 |
| local/infrastructure | untyped-decorator | 不在前 20 | 6 |
| local/infrastructure | var-annotated | 7 | 11 |

（第一轮列有数的 20 格合计 1242，第二轮列有数的 20 格合计 1250。）

量什么：local/domain、local/application、local/infrastructure 各跑两遍（默认严格度一遍、加 --strict 一遍），按「目录×错误码」和「文件」两种方式计数，各列前二十。

命令（六个，各一行，均从仓库根执行）：

```bash
PYTHONPATH=<临时目录>/site python -m mypy --ignore-missing-imports --no-error-summary --show-error-codes --cache-dir <临时目录>/mypy-cache local/domain
PYTHONPATH=<临时目录>/site python -m mypy --ignore-missing-imports --no-error-summary --show-error-codes --cache-dir <临时目录>/mypy-cache local/application
PYTHONPATH=<临时目录>/site python -m mypy --ignore-missing-imports --no-error-summary --show-error-codes --cache-dir <临时目录>/mypy-cache local/infrastructure
PYTHONPATH=<临时目录>/site python -m mypy --ignore-missing-imports --no-error-summary --show-error-codes --cache-dir <临时目录>/mypy-cache --strict local/domain
PYTHONPATH=<临时目录>/site python -m mypy --ignore-missing-imports --no-error-summary --show-error-codes --cache-dir <临时目录>/mypy-cache --strict local/application
PYTHONPATH=<临时目录>/site python -m mypy --ignore-missing-imports --no-error-summary --show-error-codes --cache-dir <临时目录>/mypy-cache --strict local/infrastructure
```

计数口径：只数带 `[错误码]` 结尾的 error 行（--no-error-summary 下每条错误一行；note 行不计）。

### H1 mypy 计数

#### H1-A（默认严格度）

错误总数：61

目录×错误码（前 20）：

| 目录 | 错误码 | 条数 |
|---|---|---|
| local/infrastructure | assignment | 14 |
| local/infrastructure | attr-defined | 10 |
| local/application | union-attr | 6 |
| local/infrastructure | return-value | 6 |
| local/infrastructure | var-annotated | 6 |
| local/application | misc | 4 |
| local/application | var-annotated | 4 |
| local/application | arg-type | 3 |
| local/domain | arg-type | 3 |
| local/application | assignment | 1 |
| local/application | valid-type | 1 |
| local/domain | assignment | 1 |
| local/infrastructure | arg-type | 1 |
| local/infrastructure | index | 1 |

文件（前 20）：

| 文件 | 条数 |
|---|---|
| `local/infrastructure/single_instance.py` | 10 |
| `local/infrastructure/phone_http.py` | 7 |
| `local/application/plan_service.py` | 6 |
| `local/application/update_service.py` | 6 |
| `local/infrastructure/component_packages.py` | 6 |
| `local/infrastructure/tray_icon.py` | 6 |
| `local/domain/phone_rules.py` | 3 |
| `local/infrastructure/lifecycle_store.py` | 3 |
| `local/infrastructure/tunnel_manager.py` | 3 |
| `local/domain/lifecycle_rules.py` | 2 |
| `local/domain/plan_rules.py` | 2 |
| `local/domain/worker_lines.py` | 2 |
| `local/infrastructure/advanced_features.py` | 2 |
| `local/infrastructure/credential_store.py` | 2 |
| `local/application/login_relay_service.py` | 1 |

#### H1-B（--strict）

错误总数：1270

目录×错误码（前 20）：

| 目录 | 错误码 | 条数 |
|---|---|---|
| local/infrastructure | no-untyped-call | 254 |
| local/application | no-untyped-call | 246 |
| local/application | no-untyped-def | 186 |
| local/infrastructure | no-untyped-def | 175 |
| local/application | type-arg | 73 |
| local/domain | no-untyped-def | 72 |
| local/infrastructure | type-arg | 44 |
| local/application | index | 35 |
| local/domain | no-untyped-call | 29 |
| local/domain | type-arg | 28 |
| local/application | union-attr | 25 |
| local/infrastructure | assignment | 19 |
| local/infrastructure | no-any-return | 11 |
| local/infrastructure | attr-defined | 10 |
| local/infrastructure | var-annotated | 7 |
| local/domain | assignment | 6 |
| local/infrastructure | return-value | 6 |
| local/infrastructure | union-attr | 6 |
| local/application | assignment | 5 |
| local/application | var-annotated | 5 |

文件（前 20）：

| 文件 | 条数 |
|---|---|
| `local/infrastructure/component_packages.py` | 582 |
| `local/domain/phone_rules.py` | 150 |
| `local/application/login_relay_service.py` | 73 |
| `local/domain/retry_window.py` | 57 |
| `local/infrastructure/phone_http.py` | 40 |
| `local/domain/plan_rules.py` | 38 |
| `local/application/phone_service.py` | 27 |
| `local/infrastructure/tunnel_manager.py` | 27 |
| `local/domain/time_text.py` | 24 |
| `local/infrastructure/single_instance.py` | 23 |
| `local/application/update_service.py` | 22 |
| `local/domain/login_rules.py` | 20 |
| `local/domain/retry_rules.py` | 20 |
| `local/application/auto_relogin.py` | 18 |
| `local/infrastructure/process_tree.py` | 17 |
| `local/domain/lifecycle_rules.py` | 16 |
| `local/application/plan_service.py` | 15 |
| `local/infrastructure/advanced_features.py` | 14 |
| `local/infrastructure/prefs_store.py` | 14 |
| `local/application/advanced_component_service.py` | 13 |

## H2 ruff（D10 H2）

量什么：对 local server tools 依次试 E、W、B、UP、SIM、I、C90、PL、RUF 九组规则，每组一行总数加前五个规则码；只查不改，不带 --fix。

命令模板（每组一行，`<组>` 取九组之一）：

```bash
PYTHONPATH=<临时目录>/site python -m ruff check local server tools --select <组> --config "lint.per-file-ignores = {}" --statistics --no-cache
```

### H2 ruff 分组统计

命令（每组一行）：`python -m ruff check local server tools --select <组> --config "lint.per-file-ignores = {}" --statistics --no-cache`，只查不改。

| 规则组 | 总数 | 前五个规则码（条数）|
|---|---|---|
| E | 3783 | E501 3749；E402 22；E741 6；E701 4；E731 1 |
| W | 0 | 无 |
| B | 58 | B904 29；B905 12；B023 11；B007 4；B008 1 |
| UP | 1601 | UP031 1381；UP009 123；UP037 62；UP015 12；UP021 9 |
| SIM | 190 | SIM105 103；SIM117 48；SIM115 23；SIM102 9；SIM103 4 |
| I | 100 | I001 100 |
| C90 | 92 | C901 92 |
| PL | 946 | PLC0415 436；PLR2004 133；PLR0913 71；PLR0911 65；PLR0912 54 |
| RUF | 22016 | RUF002 9722；RUF003 6530；RUF001 5293；RUF100 321；RUF059 79 |

E 组两轮对照（本计划 decisions D4）：review2 的对账行写「E 组 3784（第一轮）vs 3783（第二轮）差 1，原因没有定位」，本计划 decisions D4 沿用这一写法。但第一轮与第二轮各自落盘的实测值都是 3783：上表 E 组 3783（前五个规则码 E501 3749、E402 22、E741 6、E701 4、E731 1，合计 3782，另有 1 条未列；第二轮同码表的并列第五码为 E702=1）；design/evidence/2026-11-13/refactor-endpoint/review2/tables/H.md 的 E 组同为 3783，前五码与条数逐项相同。「3784」在本证据目录与 .claude/results/ 下两份结果文件里做字符串检索都查不到出处，只出现在 review2 的对账文字里（3 处）。按「对不上写明差在哪、不凑数」处理：上表第一轮实测值 3783 照原文保留，不改成双值；「两轮相差 1」只是对账行的原文转述，原因没有定位，本节不重跑。

## H3 覆盖率（D10 H3）

量什么：按 AGENTS.md 的本机版全量命令带覆盖率跑一遍（`--source=local`，数据文件放 `<临时目录>`），导出 JSON 后用 ast 把 local/app.py 与 local/grab.py 的每个函数（含方法与嵌套）对上覆盖数据，列出每个函数的已执行行数与总行数，并列出一行都没执行到的函数。

命令（从仓库根执行）：

```bash
PYTHONPATH=<临时目录>/site python -B -m coverage run --source=local --data-file <临时目录>/.coverage -m unittest discover -s local/tests -p "test_*.py" -v
PYTHONPATH=<临时目录>/site python -m coverage json --data-file <临时目录>/.coverage -o <临时目录>/coverage.json
python -B design/evidence/2026-11-13/refactor-endpoint/scripts/coverage_by_function.py <临时目录>/coverage.json
```

测试结果：`Ran 2581 tests in 214.826s`；`OK (skipped=5)`；失败 0、错误 0、通过 2576、跳过 5。

跳过的 5 条用例（名称）：

1. non_windows_raises_signer_unavailable
2. path_escape_is_rejected
3. 真实查询成功且无此 tag：空串（不是错误）
4. 真实轻量 tag：单行值即提交
5. 真实附注 tag：双 pattern 下 peeled 行确实返回，最终提交解析正确

共同跳过原因（后三条的原文，前两条同一机制）：「真实 Git fixture（临时仓库 init/commit/tag/push/ls-remote）需单独授权：确认后设 CAMPUS_GIT_FIXTURE_AUTH=1 再运行；本轮只定义不执行」。

## local/app.py

| 限定名 | 起止行 | 总行数（不含 def 行）| 已执行行数 |
|---|---|---|---|
| `resolve_worker_path` | 97-103 | 6 | 3 |
| `_credential_store_available` | 131-143 | 12 | 5 |
| `phone_log` | 151-172 | 21 | 2 |
| `read_version` | 175-195 | 20 | 6 |
| `license_candidates` | 198-204 | 6 | 0 |
| `update_version_paths` | 210-223 | 13 | 7 |
| `terms_unknown_payload` | 239-242 | 3 | 1 |
| `terms_state` | 245-256 | 11 | 1 |
| `_feishu_webhook` | 259-268 | 9 | 0 |
| `_component_title` | 271-273 | 2 | 1 |
| `auto_update_outdated_components` | 281-319 | 38 | 24 |
| `_retry_options_payload` | 322-340 | 18 | 1 |
| `worker_problem` | 356-372 | 16 | 10 |
| `_component_error` | 375-380 | 5 | 1 |
| `demo_items` | 391-393 | 2 | 1 |
| `_env` | 400-411 | 11 | 6 |
| `worker_command` | 414-418 | 4 | 2 |
| `resolve_update_launcher_path` | 421-425 | 4 | 0 |
| `update_launcher_command` | 428-442 | 14 | 8 |
| `version_sweep_target` | 445-455 | 10 | 6 |
| `sweep_versions_in_background` | 458-486 | 28 | 18 |
| `sweep_versions_in_background._run` | 474-482 | 8 | 8 |
| `version_switch_available` | 489-504 | 15 | 9 |
| `load_prefs` | 517-518 | 1 | 1 |
| `_phone_access_prefs` | 528-537 | 9 | 7 |
| `_phone_qr_data` | 544-557 | 13 | 10 |
| `now` | 569-570 | 1 | 1 |
| `bounds` | 572-573 | 1 | 1 |
| `elapsed_s` | 575-576 | 1 | 0 |
| `state` | 578-579 | 1 | 0 |
| `reason` | 582-583 | 1 | 0 |
| `request_resync` | 585-586 | 1 | 0 |
| `snapshot` | 588-589 | 1 | 1 |
| `_credential_id` | 592-594 | 2 | 1 |
| `save_session_timing_anchor` | 597-605 | 8 | 2 |
| `update_prefs` | 616-629 | 13 | 8 |
| `defer_close_action` | 635-651 | 16 | 6 |
| `defer_close_action._run` | 643-647 | 4 | 2 |
| `handle_window_close` | 654-673 | 19 | 15 |
| `resolve_close_action` | 676-689 | 13 | 8 |
| `login_state` | 692-723 | 31 | 18 |
| `_last_check_fields` | 726-742 | 16 | 8 |
| `_now_text` | 752-754 | 2 | 0 |
| `_seconds_until` | 757-759 | 2 | 1 |
| `_task_deadline` | 762-764 | 2 | 0 |
| `get_lifecycle` | 782-789 | 7 | 4 |
| `__init__` | 795-797 | 2 | 2 |
| `terminate` | 799-804 | 5 | 3 |
| `__init__` | 814-980 | 166 | 69 |
| `_clock_now` | 983-987 | 4 | 3 |
| `_clock_ready` | 989-997 | 8 | 4 |
| `_wait_for_list_clock` | 999-1020 | 21 | 16 |
| `_clock_payload` | 1022-1034 | 12 | 3 |
| `clock_snapshot` | 1036-1044 | 8 | 4 |
| `sync_clock` | 1046-1066 | 20 | 0 |
| `sync_clock.run` | 1053-1063 | 10 | 0 |
| `_start_clock_monitor` | 1068-1094 | 26 | 0 |
| `_start_clock_monitor.monitor` | 1074-1092 | 18 | 0 |
| `_emit` | 1097-1124 | 27 | 13 |
| `_terms_gate` | 1127-1146 | 19 | 8 |
| `bootstrap` | 1149-1210 | 61 | 22 |
| `_find_request_id` | 1212-1219 | 7 | 4 |
| `_bootstrap_plan_snapshot` | 1221-1243 | 22 | 11 |
| `help` | 1245-1263 | 18 | 1 |
| `_resolve_component_asset` | 1266-1312 | 46 | 17 |
| `_stop_cloudflare_checked` | 1314-1324 | 10 | 5 |
| `_install_downloaded_component` | 1326-1337 | 11 | 8 |
| `_commit_downloaded_component_group` | 1339-1349 | 10 | 5 |
| `_component_finished` | 1351-1375 | 24 | 15 |
| `_component_installed` | 1377-1385 | 8 | 0 |
| `_install_downloaded_ocr` | 1387-1395 | 8 | 0 |
| `_commit_downloaded_ocr_group` | 1397-1405 | 8 | 0 |
| `_ocr_component_installed` | 1407-1413 | 6 | 0 |
| `_component_service_for` | 1415-1423 | 8 | 3 |
| `download_advanced_feature` | 1425-1450 | 25 | 17 |
| `cancel_advanced_feature_download` | 1452-1457 | 5 | 3 |
| `enable_advanced_feature` | 1459-1486 | 27 | 15 |
| `advanced_component_location` | 1488-1504 | 16 | 7 |
| `open_advanced_component_dir` | 1506-1523 | 17 | 12 |
| `advanced_features_state` | 1525-1604 | 79 | 28 |
| `inspect_advanced_component` | 1606-1622 | 16 | 8 |
| `pick_advanced_component` | 1624-1642 | 18 | 9 |
| `install_advanced_feature` | 1644-1686 | 42 | 23 |
| `_install_selected_feature` | 1688-1731 | 43 | 5 |
| `remove_advanced_feature` | 1733-1768 | 35 | 0 |
| `save_relogin_credentials` | 1770-1793 | 23 | 11 |
| `clear_relogin_credentials` | 1795-1803 | 8 | 0 |
| `_silent_relogin_ready` | 1805-1827 | 22 | 11 |
| `_silent_relogin_state` | 1829-1850 | 21 | 11 |
| `_auto_relogin_eligible` | 1852-1859 | 7 | 4 |
| `_once_credentials_staged` | 1861-1869 | 8 | 3 |
| `_auto_relogin_paused` | 1871-1881 | 10 | 5 |
| `_relogin_blocked_locked` | 1883-1893 | 10 | 3 |
| `_request_auto_relogin` | 1895-1899 | 4 | 0 |
| `_relogin_wait_s` | 1901-1903 | 2 | 1 |
| `_relogin_ocr_ready` | 1905-1908 | 3 | 1 |
| `_manual_relogin_wanted` | 1910-1927 | 17 | 9 |
| `_phone_relay_view` | 1929-1950 | 21 | 14 |
| `_log_event` | 1952-1988 | 36 | 20 |
| `_begin_auto_relogin` | 1990-2010 | 20 | 10 |
| `_begin_auto_relogin_once` | 2012-2044 | 32 | 21 |
| `_classify_captcha` | 2046-2050 | 4 | 0 |
| `front_ready` | 2052-2055 | 3 | 0 |
| `check_update` | 2057-2090 | 33 | 24 |
| `_do_check_update` | 2092-2097 | 5 | 1 |
| `_publish_update` | 2099-2115 | 16 | 13 |
| `update_download` | 2117-2141 | 24 | 20 |
| `_do_update_download` | 2143-2169 | 26 | 7 |
| `update_cancel` | 2171-2175 | 4 | 3 |
| `update_launch` | 2177-2249 | 72 | 38 |
| `check` | 2252-2281 | 29 | 17 |
| `list_activities` | 2283-2305 | 22 | 7 |
| `_do_check` | 2307-2337 | 30 | 20 |
| `_note_login_conclusion` | 2339-2368 | 29 | 19 |
| `_push_login_expired` | 2370-2399 | 29 | 0 |
| `_push_login_expired.send` | 2387-2397 | 10 | 0 |
| `_do_check_inner` | 2401-2461 | 60 | 30 |
| `_pc_clock_text` | 2463-2471 | 8 | 2 |
| `_note_pc_list_error` | 2473-2486 | 13 | 3 |
| `_do_list` | 2488-2515 | 27 | 15 |
| `_cancel_busy_reason_locked` | 2532-2546 | 14 | 12 |
| `_cancel_refusal` | 2548-2553 | 5 | 5 |
| `cancel_signup` | 2555-2586 | 31 | 20 |
| `_cancel_signup_run` | 2588-2609 | 21 | 16 |
| `_after_cancelled` | 2611-2631 | 20 | 13 |
| `_confirm_signed` | 2639-2664 | 25 | 15 |
| `_merge_list_activities` | 2666-2677 | 11 | 3 |
| `_do_list_inner` | 2679-2759 | 80 | 50 |
| `login` | 2762-2778 | 16 | 10 |
| `grab` | 2780-2796 | 16 | 0 |
| `_prune_finished_plans_locked` | 2803-2808 | 5 | 2 |
| `_protect_start` | 2810-2824 | 14 | 7 |
| `_remember_start` | 2826-2841 | 15 | 12 |
| `_start_replay` | 2843-2852 | 9 | 6 |
| `start_request_state` | 2854-2889 | 35 | 22 |
| `cancel_start_request` | 2891-2921 | 30 | 18 |
| `start_plan` | 2923-2992 | 69 | 35 |
| `_start_plan_inner` | 2994-3232 | 238 | 127 |
| `_start_plan_inner.annotated` | 3086-3097 | 11 | 9 |
| `_start_plan_inner.emit` | 3099-3159 | 60 | 34 |
| `_start_plan_inner.runner` | 3161-3185 | 24 | 6 |
| `cancel_task` | 3234-3240 | 6 | 0 |
| `stop_plan` | 3242-3252 | 10 | 6 |
| `_terminate_plan_procs` | 3254-3269 | 15 | 10 |
| `plan_active_for_close` | 3271-3279 | 8 | 7 |
| `_close_plan_burden` | 3281-3308 | 27 | 14 |
| `ask_window_close` | 3310-3332 | 22 | 11 |
| `request_window_close` | 3334-3379 | 45 | 28 |
| `_remember_close_action` | 3381-3386 | 5 | 4 |
| `hide_window` | 3389-3410 | 21 | 11 |
| `_notify_window_hidden` | 3412-3425 | 13 | 5 |
| `show_window` | 3427-3441 | 14 | 10 |
| `window_visibility` | 3443-3451 | 8 | 2 |
| `_on_window_minimized` | 3453-3454 | 1 | 0 |
| `_on_window_restored` | 3456-3457 | 1 | 0 |
| `_on_second_open` | 3459-3476 | 17 | 8 |
| `_plan_source_of` | 3478-3480 | 2 | 2 |
| `_notify_plan_done` | 3482-3494 | 12 | 2 |
| `_ensure_tray` | 3496-3510 | 14 | 7 |
| `_stop_tray` | 3512-3519 | 7 | 3 |
| `shutdown` | 3521-3619 | 98 | 56 |
| `stop` | 3621-3650 | 29 | 20 |
| `_phone_raw_state` | 3653-3716 | 63 | 23 |
| `_phone_relogin_setup` | 3718-3732 | 14 | 8 |
| `_cloudflare_status_snapshot` | 3734-3744 | 10 | 4 |
| `_reconcile_cloudflare_lifecycle` | 3746-3765 | 19 | 12 |
| `phone_access_state` | 3767-3810 | 43 | 10 |
| `start_phone_access` | 3812-3814 | 2 | 2 |
| `_start_phone_access` | 3816-3881 | 65 | 41 |
| `_remember_phone_channel` | 3883-3888 | 5 | 2 |
| `_forget_phone_autostart` | 3890-3895 | 5 | 2 |
| `set_phone_access_preferences` | 3897-3911 | 14 | 8 |
| `restore_phone_access` | 3913-3935 | 22 | 11 |
| `schedule_phone_restore` | 3937-3961 | 24 | 0 |
| `schedule_phone_restore.run` | 3943-3956 | 13 | 0 |
| `schedule_component_auto_update` | 3963-3992 | 29 | 0 |
| `schedule_component_auto_update.run` | 3972-3990 | 18 | 0 |
| `_wait_component_settled` | 3994-4015 | 21 | 0 |
| `stop_phone_access` | 4017-4022 | 5 | 4 |
| `_stop_phone_access` | 4024-4040 | 16 | 12 |
| `prepare_phone_relogin` | 4043-4073 | 30 | 20 |
| `_commit_pending_save` | 4075-4090 | 15 | 5 |
| `_relogin_late_answer` | 4092-4112 | 20 | 4 |
| `_relogin_entry_gate` | 4114-4124 | 10 | 6 |
| `_relogin_manual_case` | 4126-4133 | 7 | 0 |
| `_begin_typed_relogin` | 4135-4150 | 15 | 8 |
| `relogin_begin` | 4153-4180 | 27 | 4 |
| `relogin_submit` | 4182-4184 | 2 | 0 |
| `relogin_cancel` | 4186-4192 | 6 | 3 |
| `relogin_auto_once` | 4194-4209 | 15 | 0 |
| `phone_relogin_begin` | 4211-4242 | 31 | 14 |
| `phone_relogin_submit` | 4244-4246 | 2 | 0 |
| `phone_relogin_cancel` | 4248-4255 | 7 | 0 |
| `_spawn_relay_worker` | 4257-4275 | 18 | 11 |
| `_relay_finished` | 4277-4331 | 54 | 29 |
| `open_data` | 4333-4342 | 9 | 0 |
| `open_latest_release` | 4344-4355 | 11 | 0 |
| `get_license_text` | 4357-4374 | 17 | 0 |
| `save_prefs` | 4376-4381 | 5 | 2 |
| `accept_terms` | 4383-4407 | 24 | 0 |
| `withdraw_terms` | 4409-4425 | 16 | 0 |
| `_is_busy_locked` | 4428-4438 | 10 | 8 |
| `_is_busy` | 4440-4442 | 2 | 2 |
| `_run_plan_task` | 4444-4462 | 18 | 1 |
| `_trace` | 4464-4473 | 9 | 0 |
| `_run` | 4475-4518 | 43 | 24 |
| `_spawn` | 4520-4549 | 29 | 18 |
| `_anchor_login_success` | 4551-4581 | 30 | 15 |
| `_pump` | 4583-4620 | 37 | 21 |
| `_parse_retry_line` | 4642-4644 | 2 | 1 |
| `_check_reason_line` | 4647-4649 | 2 | 1 |
| `_check_result` | 4652-4654 | 2 | 1 |
| `_check_hint` | 4657-4659 | 2 | 1 |
| `_runtime_check_main` | 4677-4737 | 60 | 35 |
| `_screen_size` | 4740-4746 | 6 | 0 |
| `_window_geometry` | 4749-4767 | 18 | 9 |
| `main` | 4770-4869 | 99 | 56 |
| `main._closing` | 4840-4842 | 2 | 0 |

一行都没执行到的函数，共 46 个：
- `license_candidates`（198-204，6 行）
- `_feishu_webhook`（259-268，9 行）
- `resolve_update_launcher_path`（421-425，4 行）
- `elapsed_s`（575-576，1 行）
- `state`（578-579，1 行）
- `reason`（582-583，1 行）
- `request_resync`（585-586，1 行）
- `_now_text`（752-754，2 行）
- `_task_deadline`（762-764，2 行）
- `sync_clock`（1046-1066，20 行）
- `sync_clock.run`（1053-1063，10 行）
- `_start_clock_monitor`（1068-1094，26 行）
- `_start_clock_monitor.monitor`（1074-1092，18 行）
- `_component_installed`（1377-1385，8 行）
- `_install_downloaded_ocr`（1387-1395，8 行）
- `_commit_downloaded_ocr_group`（1397-1405，8 行）
- `_ocr_component_installed`（1407-1413，6 行）
- `remove_advanced_feature`（1733-1768，35 行）
- `clear_relogin_credentials`（1795-1803，8 行）
- `_request_auto_relogin`（1895-1899，4 行）
- `_classify_captcha`（2046-2050，4 行）
- `front_ready`（2052-2055，3 行）
- `_push_login_expired`（2370-2399，29 行）
- `_push_login_expired.send`（2387-2397，10 行）
- `grab`（2780-2796，16 行）
- `cancel_task`（3234-3240，6 行）
- `_on_window_minimized`（3453-3454，1 行）
- `_on_window_restored`（3456-3457，1 行）
- `schedule_phone_restore`（3937-3961，24 行）
- `schedule_phone_restore.run`（3943-3956，13 行）
- `schedule_component_auto_update`（3963-3992，29 行）
- `schedule_component_auto_update.run`（3972-3990，18 行）
- `_wait_component_settled`（3994-4015，21 行）
- `_relogin_manual_case`（4126-4133，7 行）
- `relogin_submit`（4182-4184，2 行）
- `relogin_auto_once`（4194-4209，15 行）
- `phone_relogin_submit`（4244-4246，2 行）
- `phone_relogin_cancel`（4248-4255，7 行）
- `open_data`（4333-4342，9 行）
- `open_latest_release`（4344-4355，11 行）
- `get_license_text`（4357-4374，17 行）
- `accept_terms`（4383-4407，24 行）
- `withdraw_terms`（4409-4425，16 行）
- `_trace`（4464-4473，9 行）
- `_screen_size`（4740-4746，6 行）
- `main._closing`（4840-4842，2 行）

## local/grab.py

| 限定名 | 起止行 | 总行数（不含 def 行）| 已执行行数 |
|---|---|---|---|
| `configure_business_clock` | 91-95 | 4 | 4 |
| `business_now` | 98-102 | 4 | 4 |
| `business_bounds` | 105-109 | 4 | 3 |
| `clock_meta` | 112-122 | 10 | 4 |
| `setup_business_clock` | 125-144 | 19 | 6 |
| `setup_console` | 158-164 | 6 | 0 |
| `_school_open` | 167-181 | 14 | 5 |
| `_log_file_lock` | 191-216 | 25 | 15 |
| `rotate_log_file` | 219-241 | 22 | 17 |
| `_stderr_note` | 244-252 | 8 | 5 |
| `_stdout_to_stderr` | 256-273 | 17 | 10 |
| `log` | 276-299 | 23 | 20 |
| `_append_log_line_unlocked` | 302-307 | 5 | 5 |
| `log_event` | 314-322 | 8 | 1 |
| `read_json` | 325-336 | 11 | 8 |
| `write_json_atomic` | 339-349 | 10 | 6 |
| `_session_write_lock` | 362-387 | 25 | 15 |
| `_write_login_file` | 390-399 | 9 | 7 |
| `save_session` | 402-406 | 4 | 2 |
| `save_storage_state` | 409-413 | 4 | 3 |
| `_unlink_quiet` | 416-420 | 4 | 2 |
| `_snapshot_bytes` | 423-429 | 6 | 5 |
| `save_verified_files` | 432-445 | 13 | 7 |
| `_save_verified_files_locked` | 448-485 | 37 | 23 |
| `_restore_original` | 488-512 | 24 | 17 |
| `_rollback_note` | 515-521 | 6 | 3 |
| `token` | 524-526 | 2 | 2 |
| `_hmac_sha256_hex` | 529-530 | 1 | 1 |
| `_xor_base64` | 533-537 | 4 | 2 |
| `_encode_x_token` | 540-546 | 6 | 3 |
| `sign_request_headers` | 551-573 | 22 | 6 |
| `_request_nonce` | 576-579 | 3 | 2 |
| `_remember_school_date` | 588-604 | 16 | 13 |
| `school_date_now` | 607-610 | 3 | 2 |
| `clear_school_date` | 613-615 | 2 | 1 |
| `_post` | 618-666 | 48 | 22 |
| `_get` | 669-688 | 19 | 11 |
| `clock_sample` | 691-751 | 60 | 37 |
| `clock_skew` | 754-757 | 3 | 0 |
| `_tri_state` | 761-772 | 11 | 10 |
| `_activity_flag` | 775-780 | 5 | 4 |
| `_activity_time` | 813-819 | 6 | 5 |
| `_reward_number` | 822-837 | 15 | 8 |
| `_detail_fields` | 840-845 | 5 | 3 |
| `parse_attendance_detail` | 848-887 | 39 | 15 |
| `fetch_activity_detail` | 890-905 | 15 | 12 |
| `_apply_attendance` | 908-948 | 40 | 30 |
| `enrich_attendance_items` | 951-973 | 22 | 17 |
| `_map_activity` | 976-1001 | 25 | 1 |
| `fetch_activities` | 1004-1031 | 27 | 17 |
| `_join_state` | 1034-1053 | 19 | 8 |
| `is_joined` | 1056-1074 | 18 | 5 |
| `parse_ts` | 1077-1086 | 9 | 4 |
| `still_relevant` | 1089-1097 | 8 | 5 |
| `keep_in_list` | 1100-1116 | 16 | 8 |
| `sign_state` | 1119-1134 | 15 | 11 |
| `launch_browser` | 1138-1154 | 16 | 0 |
| `new_context` | 1157-1161 | 4 | 4 |
| `page_local_storage` | 1164-1167 | 3 | 1 |
| `session_from_items` | 1170-1184 | 14 | 9 |
| `_cmd_login_relay` | 1188-1234 | 46 | 0 |
| `_cmd_login_relay.__init__` | 1205-1206 | 1 | 0 |
| `_cmd_login_relay.now` | 1208-1209 | 1 | 0 |
| `_cmd_login_relay.sleep` | 1211-1212 | 1 | 0 |
| `_cmd_login_relay.new_id` | 1214-1215 | 1 | 0 |
| `_cmd_login_relay.open_page` | 1217-1222 | 5 | 0 |
| `_cmd_login_relay.post` | 1224-1225 | 1 | 0 |
| `_cmd_login_relay.save_verified` | 1227-1230 | 3 | 0 |
| `cmd_login` | 1237-1313 | 76 | 41 |
| `cmd_check` | 1316-1330 | 14 | 0 |
| `cmd_list` | 1333-1475 | 142 | 70 |
| `cmd_list._emit_list_timing` | 1339-1350 | 11 | 4 |
| `cmd_list.rank` | 1403-1412 | 9 | 6 |
| `_cancel_facts` | 1489-1502 | 13 | 6 |
| `_cancel_joined` | 1505-1511 | 6 | 5 |
| `run_cancel` | 1514-1589 | 75 | 55 |
| `run_cancel.refuse` | 1519-1521 | 2 | 2 |
| `cmd_cancel` | 1592-1605 | 13 | 9 |
| `candidates` | 1608-1624 | 16 | 7 |
| `candidates.rank` | 1616-1621 | 5 | 2 |
| `pick_activity` | 1627-1643 | 16 | 0 |
| `notify` | 1646-1671 | 25 | 0 |
| `wait_until` | 1674-1691 | 17 | 11 |
| `_by_index_or_name` | 1694-1720 | 26 | 10 |
| `_at_or_now` | 1723-1736 | 13 | 5 |
| `resolve_target` | 1739-1786 | 47 | 22 |
| `retry_anchor` | 1790-1799 | 9 | 2 |
| `compute_retry_window` | 1819-1833 | 14 | 4 |
| `attempts_allowed` | 1836-1838 | 2 | 1 |
| `next_submit_gap` | 1849-1857 | 8 | 7 |
| `wait_before_next_submit` | 1860-1867 | 7 | 4 |
| `__init__` | 1930-1959 | 29 | 24 |
| `_now` | 1962-1967 | 5 | 0 |
| `_wall_now` | 1969-1989 | 20 | 10 |
| `_elapsed` | 1991-1993 | 2 | 1 |
| `_recompute_streak` | 1996-2017 | 21 | 16 |
| `_derive_min_gap` | 2019-2044 | 25 | 14 |
| `phase` | 2048-2050 | 2 | 2 |
| `current_phase` | 2052-2054 | 2 | 1 |
| `_golden_time_up` | 2056-2061 | 5 | 4 |
| `_apply_level` | 2063-2090 | 27 | 17 |
| `_exit_golden` | 2092-2104 | 12 | 6 |
| `_refresh_phase` | 2106-2120 | 14 | 5 |
| `_seed_backoff` | 2122-2124 | 2 | 1 |
| `interval_s` | 2126-2144 | 18 | 12 |
| `next_interval_after_wait` | 2146-2155 | 9 | 4 |
| `can_attempt` | 2157-2165 | 8 | 7 |
| `extend_deadline_for_adaptive` | 2167-2180 | 13 | 8 |
| `register_request` | 2183-2204 | 21 | 11 |
| `settle` | 2206-2239 | 33 | 16 |
| `_maybe_extend_window` | 2241-2249 | 8 | 2 |
| `pending_ids` | 2251-2253 | 2 | 1 |
| `pending_count` | 2255-2256 | 1 | 1 |
| `inflight_count` | 2258-2275 | 17 | 10 |
| `settled_kind` | 2277-2279 | 2 | 2 |
| `stop` | 2282-2287 | 5 | 4 |
| `stopped` | 2290-2291 | 1 | 1 |
| `_classify_response` | 2294-2317 | 23 | 12 |
| `_decode_body` | 2320-2335 | 15 | 9 |
| `_recognizable_code` | 2338-2353 | 15 | 11 |
| `_ts_text` | 2356-2360 | 4 | 2 |
| `_checkpoint_event` | 2363-2379 | 16 | 9 |
| `_retry_event` | 2382-2389 | 7 | 2 |
| `_probe_list` | 2399-2403 | 4 | 1 |
| `_direct_headers` | 2406-2409 | 3 | 1 |
| `fetch_runtime_key` | 2412-2431 | 19 | 9 |
| `probe_token` | 2434-2466 | 32 | 21 |
| `check_token` | 2469-2472 | 3 | 0 |
| `_known_policy_start` | 2475-2482 | 7 | 4 |
| `_policy_window` | 2485-2487 | 2 | 2 |
| `cmd_grab` | 2502-3968 | 1466 | 851 |
| `cmd_grab.terminal` | 2553-2627 | 74 | 55 |
| `cmd_grab._clock_stop` | 2632-2641 | 9 | 3 |
| `cmd_grab._budget_stop` | 2658-2660 | 2 | 2 |
| `cmd_grab._wait_for_relogin` | 2665-2699 | 34 | 24 |
| `cmd_grab._downgrade` | 2927-2933 | 6 | 4 |
| `cmd_grab._rekey_after_version` | 2935-2949 | 14 | 7 |
| `cmd_grab._is_signup_url` | 2977-2978 | 1 | 1 |
| `cmd_grab._sync_pending` | 2980-2984 | 4 | 4 |
| `cmd_grab.on_request` | 2986-3004 | 18 | 10 |
| `cmd_grab.on_response` | 3006-3018 | 12 | 6 |
| `cmd_grab.on_requestfailed` | 3020-3033 | 13 | 6 |
| `cmd_grab._sync_budget_window` | 3035-3048 | 13 | 4 |
| `cmd_grab._apply_conclusion` | 3050-3123 | 73 | 49 |
| `cmd_grab._reason_with_raw` | 3125-3129 | 4 | 3 |
| `cmd_grab._settle_one` | 3131-3187 | 56 | 32 |
| `cmd_grab._settle_failed` | 3189-3202 | 13 | 8 |
| `cmd_grab._register_request` | 3204-3218 | 14 | 10 |
| `cmd_grab._settle_pending` | 3220-3232 | 12 | 10 |
| `cmd_grab._settle_direct_event` | 3234-3347 | 113 | 79 |
| `cmd_grab._drain_direct` | 3349-3358 | 9 | 9 |
| `cmd_grab._try_direct_fire` | 3360-3421 | 61 | 30 |
| `cmd_grab._pump_wait` | 3423-3456 | 33 | 20 |
| `cmd_grab._may_fire` | 3458-3492 | 34 | 22 |
| `cmd_grab._fallback_terminal` | 3494-3509 | 15 | 7 |
| `cmd_grab._finalize` | 3511-3528 | 17 | 7 |
| `cmd_grab._finalize_once` | 3530-3609 | 79 | 50 |
| `cmd_grab._precheck_send` | 3611-3666 | 55 | 24 |
| `cmd_grab._precheck_before_open` | 3668-3708 | 40 | 26 |
| `cmd_selftest` | 3970-3994 | 24 | 0 |
| `main` | 3997-4072 | 75 | 0 |

一行都没执行到的函数，共 18 个：
- `setup_console`（158-164，6 行）
- `clock_skew`（754-757，3 行）
- `launch_browser`（1138-1154，16 行）
- `_cmd_login_relay`（1188-1234，46 行）
- `_cmd_login_relay.__init__`（1205-1206，1 行）
- `_cmd_login_relay.now`（1208-1209，1 行）
- `_cmd_login_relay.sleep`（1211-1212，1 行）
- `_cmd_login_relay.new_id`（1214-1215，1 行）
- `_cmd_login_relay.open_page`（1217-1222，5 行）
- `_cmd_login_relay.post`（1224-1225，1 行）
- `_cmd_login_relay.save_verified`（1227-1230，3 行）
- `cmd_check`（1316-1330，14 行）
- `pick_activity`（1627-1643，16 行）
- `notify`（1646-1671，25 行）
- `_now`（1962-1967，5 行）
- `check_token`（2469-2472，3 行）
- `cmd_selftest`（3970-3994，24 行）
- `main`（3997-4072，75 行）

局限（按计划 D10 注明）：经子进程启动的 worker 不在统计内。coverage JSON 的文件键在本机带反斜杠，coverage_by_function.py 先归一成正斜杠再取数。「已执行行数」不含 def 行本身（模块导入就会执行 def 行，计入会把每个函数都算成执行过），单行 def 以 def 行计。

局限补两条（本计划 decisions D5）：

- ast 抽取求值的测试不计入：有的测试不 import local/app.py，而是用 ast 把 Api 的方法抽出来单独求值（local/tests/test_terms_consent.py 文件头写明了这种做法），这样被运行到的代码 coverage 记不到 local/app.py 头上；上文两份「一行都没执行到的函数」清单只能当「可能没测到」的上限（名字在测试里出现次数的对照见下节）。
- 每个文件的行覆盖率：原计划 D10 要求的「输出每个文件的行覆盖率」没有产出；覆盖率原始数据已随 `<临时目录>` 删除，本计划不重跑，记为未产出。

## 零执行函数名在测试里出现的次数（H3 补充，本计划 decisions D6）

量什么：online.md 里 local/app.py 与 local/grab.py 的两份「一行都没执行到的函数」清单（共 64 个），对每个函数取限定名里第一个点号之前的部分，数它作为完整单词（左右两侧都不是字母、数字或下划线）在 local/tests 下全部 .py 文件文本里出现的次数；只做文本统计，注释与字符串里的出现也计入。清单从 online.md 原文解析。

| 文件 | 函数 | 行数 | 在测试里出现的次数 |
|---|---|---|---|
| `local/app.py` | `license_candidates` | 6 | 4 |
| `local/app.py` | `_feishu_webhook` | 9 | 0 |
| `local/app.py` | `resolve_update_launcher_path` | 4 | 4 |
| `local/app.py` | `elapsed_s` | 1 | 25 |
| `local/app.py` | `state` | 1 | 1387 |
| `local/app.py` | `reason` | 1 | 175 |
| `local/app.py` | `request_resync` | 1 | 4 |
| `local/app.py` | `_now_text` | 2 | 0 |
| `local/app.py` | `_task_deadline` | 2 | 0 |
| `local/app.py` | `sync_clock` | 20 | 3 |
| `local/app.py` | `sync_clock.run` | 10 | 3 |
| `local/app.py` | `_start_clock_monitor` | 26 | 1 |
| `local/app.py` | `_start_clock_monitor.monitor` | 18 | 1 |
| `local/app.py` | `_component_installed` | 8 | 0 |
| `local/app.py` | `_install_downloaded_ocr` | 8 | 0 |
| `local/app.py` | `_commit_downloaded_ocr_group` | 8 | 0 |
| `local/app.py` | `_ocr_component_installed` | 6 | 0 |
| `local/app.py` | `remove_advanced_feature` | 35 | 0 |
| `local/app.py` | `clear_relogin_credentials` | 8 | 6 |
| `local/app.py` | `_request_auto_relogin` | 4 | 0 |
| `local/app.py` | `_classify_captcha` | 4 | 4 |
| `local/app.py` | `front_ready` | 3 | 6 |
| `local/app.py` | `_push_login_expired` | 29 | 4 |
| `local/app.py` | `_push_login_expired.send` | 10 | 4 |
| `local/app.py` | `grab` | 16 | 559 |
| `local/app.py` | `cancel_task` | 6 | 23 |
| `local/app.py` | `_on_window_minimized` | 1 | 1 |
| `local/app.py` | `_on_window_restored` | 1 | 1 |
| `local/app.py` | `schedule_phone_restore` | 24 | 1 |
| `local/app.py` | `schedule_phone_restore.run` | 13 | 1 |
| `local/app.py` | `schedule_component_auto_update` | 29 | 0 |
| `local/app.py` | `schedule_component_auto_update.run` | 18 | 0 |
| `local/app.py` | `_wait_component_settled` | 21 | 0 |
| `local/app.py` | `_relogin_manual_case` | 7 | 0 |
| `local/app.py` | `relogin_submit` | 2 | 0 |
| `local/app.py` | `relogin_auto_once` | 15 | 3 |
| `local/app.py` | `phone_relogin_submit` | 2 | 4 |
| `local/app.py` | `phone_relogin_cancel` | 7 | 3 |
| `local/app.py` | `open_data` | 9 | 15 |
| `local/app.py` | `open_latest_release` | 11 | 8 |
| `local/app.py` | `get_license_text` | 17 | 10 |
| `local/app.py` | `accept_terms` | 24 | 57 |
| `local/app.py` | `withdraw_terms` | 16 | 17 |
| `local/app.py` | `_trace` | 9 | 4 |
| `local/app.py` | `_screen_size` | 6 | 1 |
| `local/app.py` | `main._closing` | 2 | 139 |
| `local/grab.py` | `setup_console` | 6 | 0 |
| `local/grab.py` | `clock_skew` | 3 | 3 |
| `local/grab.py` | `launch_browser` | 16 | 4 |
| `local/grab.py` | `_cmd_login_relay` | 46 | 0 |
| `local/grab.py` | `_cmd_login_relay.__init__` | 1 | 0 |
| `local/grab.py` | `_cmd_login_relay.now` | 1 | 0 |
| `local/grab.py` | `_cmd_login_relay.sleep` | 1 | 0 |
| `local/grab.py` | `_cmd_login_relay.new_id` | 1 | 0 |
| `local/grab.py` | `_cmd_login_relay.open_page` | 5 | 0 |
| `local/grab.py` | `_cmd_login_relay.post` | 1 | 0 |
| `local/grab.py` | `_cmd_login_relay.save_verified` | 3 | 0 |
| `local/grab.py` | `cmd_check` | 14 | 0 |
| `local/grab.py` | `pick_activity` | 16 | 0 |
| `local/grab.py` | `notify` | 25 | 7 |
| `local/grab.py` | `_now` | 5 | 0 |
| `local/grab.py` | `check_token` | 3 | 10 |
| `local/grab.py` | `cmd_selftest` | 24 | 0 |
| `local/grab.py` | `main` | 75 | 139 |

出现次数大于 0 的：37 个（共 64 个）。
对照：计划 decisions D6 的参照数是「64 个函数里 37 个大于 0」，本次 64 个里 37 个大于 0 -> 一致

复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/zero_exec_in_tests.py`

## selfcheck 终态输出（收工）

命令（从仓库根执行）：

```bash
python -B design/evidence/2026-11-13/refactor-endpoint/scripts/selfcheck.py
```

输出原文：

```text
通过
```
