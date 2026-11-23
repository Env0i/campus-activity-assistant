# 第四组第一批（面板渲染、收尾清图与快照摄入）补测后结论

- **范围**：`local/ui/m/ui-relogin.js` 里 `renderRelogin`（9 条）、`endReloginControls`（1 条）与 `ingestRelogin`（15 条）在补测前无人守的 **25 条**变异。
- **补测后结论**：本批 25 条全部转为 **行为守（25）**，等价 **0**、无人守 **0**、字面守 **0**、无效 **0**（`scripts/equiv.json` 为空对象 `{}`）。
- **全量 129 条复跑**：行为守 **104**（补测前 79 条全部保持行为守，无退化）、无人守 **25**（均为第二批三个请求函数的目标编号）、字面守 **0**、无效 **0**、等价 **0**。

## 1. 本批 25 条补测后逐条结论

| 编号 | 类 | 函数 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例 |
|---|---|---|---|---|---|---|
| M001 | 乙 | `renderRelogin` | `if (model.sheetId === "relogin")` | `if (!(model.sheetId === "relogin"))` | 行为守 | `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` |
| M002 | 己 | `renderRelogin` | `$("sheet-title").textContent = PhoneModel.loginCopy( ↵       model.relFirstLogin ? "never" : "expired", false).reloginEntry;` | `void 0;` | 行为守 | `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` |
| M005 | 丙 | `renderRelogin` | `$("rel-err").hidden = !view.err;` | `void 0;` | 行为守 | `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` |
| M009 | 丙 | `renderRelogin` | `$("rel-text").hidden = !view.text;` | `void 0;` | 行为守 | `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` |
| M015 | 丙 | `renderRelogin` | `$("rel-auto").hidden = !view.autoCap;` | `void 0;` | 行为守 | `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` |
| M016 | 己 | `renderRelogin` | `$("rel-save-gain").textContent = view.saveLine;` | `void 0;` | 行为守 | `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` |
| M017 | 丙 | `renderRelogin` | `$("btn-relogin-auto").hidden = view.mainKind !== "auto";` | `void 0;` | 行为守 | `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` |
| M020 | 丙 | `renderRelogin` | `$("rel-second-row").hidden = !(view.refresh \|\| view.cancel);` | `void 0;` | 行为守 | `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` |
| M023 | 丙 | `renderRelogin` | `$("btn-relogin-done").hidden = !view.done;` | `void 0;` | 行为守 | `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` |
| M030 | 己 | `endReloginControls` | `$("captcha").removeAttribute("src");` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_captcha_src_attribute_cleared_on_non_png_and_flow_end` |
| M037 | 甲 | `ingestRelogin` | `    model.challenge = null; ↵     model.reloginSubmitting = false; ↵     model.reloginStarting = false;` | `    void 0; ↵     model.reloginSubmitting = false; ↵     model.reloginStarting = false;` | 行为守 | `PhoneReloginRecoveryTests.test_auto_mode_idle_explains_who_will_solve_the_captcha（超时）` |
| M038 | 甲 | `ingestRelogin` | `    model.challenge = null; ↵     model.reloginSubmitting = false; ↵     model.reloginStarting = false;` | `    model.challenge = null; ↵     void 0; ↵     model.reloginStarting = false;` | 行为守 | `PhoneReloginRecoveryTests.test_auto_snapshot_clears_challenge_submitting_and_starting_locks` |
| M039 | 甲 | `ingestRelogin` | `model.reloginStarting = false;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_auto_snapshot_clears_challenge_submitting_and_starting_locks` |
| M050 | 己 | `ingestRelogin` | `img.removeAttribute("src");` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_captcha_src_attribute_cleared_on_non_png_and_flow_end` |
| M053 | 甲 | `ingestRelogin` | `    model.reloginSubmitting = false; ↵     $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;` | `    void 0; ↵     $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;` | 行为守 | `PhoneReloginRecoveryTests.test_starting_and_verifying_snapshots_reset_submitting_and_pick_mode_note` |
| M056 | 甲 | `ingestRelogin` | `    model.reloginSubmitting = false; ↵     $("relogin-note").textContent = String(info.mode \|\| "") === "auto"` | `    void 0; ↵     $("relogin-note").textContent = String(info.mode \|\| "") === "auto"` | 行为守 | `PhoneReloginRecoveryTests.test_starting_and_verifying_snapshots_reset_submitting_and_pick_mode_note` |
| M057 | 己 | `ingestRelogin` | `$("relogin-note").textContent = String(info.mode \|\| "") === "auto" ↵       ? PhoneModel.RELOGIN_BUSY.prepare : PhoneModel.RELOGIN_BUSY.needCode;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_starting_and_verifying_snapshots_reset_submitting_and_pick_mode_note` |
| M058 | 乙 | `ingestRelogin` | `String(info.mode \|\| "") === "auto" ↵       ?` | `!(String(info.mode \|\| "") === "auto") ↵       ?` | 行为守 | `PhoneReloginRecoveryTests.test_starting_and_verifying_snapshots_reset_submitting_and_pick_mode_note` |
| M060 | 甲 | `ingestRelogin` | `  } else if (relayState === "success") { ↵     model.challenge = null;` | `  } else if (relayState === "success") { ↵     void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_terminal_snapshots_unlock_sheet_and_reset_challenge` |
| M061 | 甲 | `ingestRelogin` | `  } else if (relayState === "success") { ↵     model.challenge = null; ↵     model.reloginSubmitting = false;` | `  } else if (relayState === "success") { ↵     model.challenge = null; ↵     void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_terminal_snapshots_unlock_sheet_and_reset_challenge` |
| M066 | 甲 | `ingestRelogin` | `  } else if (relayState === "failed" \|\| relayState === "canceled") { ↵     model.challenge = null;` | `  } else if (relayState === "failed" \|\| relayState === "canceled") { ↵     void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_terminal_snapshots_unlock_sheet_and_reset_challenge` |
| M067 | 甲 | `ingestRelogin` | `  } else if (relayState === "failed" \|\| relayState === "canceled") { ↵     model.challenge = null; ↵     model.reloginSubmitting = false;` | `  } else if (relayState === "failed" \|\| relayState === "canceled") { ↵     model.challenge = null; ↵     void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_terminal_snapshots_unlock_sheet_and_reset_challenge` |
| M070 | 乙 | `ingestRelogin` | `else if (relayState && relayState !== "waiting_code")` | `else if (!(relayState && relayState !== "waiting_code"))` | 行为守 | `PhoneReloginRecoveryTests.test_idle_snapshot_clears_captcha_and_locks_unlike_waiting_without_id` |
| M071 | 甲 | `ingestRelogin` | `    model.challenge = null; ↵     model.reloginSubmitting = false; ↵     endReloginControls(); ↵   }` | `    void 0; ↵     model.reloginSubmitting = false; ↵     endReloginControls(); ↵   }` | 行为守 | `PhoneReloginRecoveryTests.test_idle_snapshot_clears_captcha_and_locks_unlike_waiting_without_id` |
| M072 | 甲 | `ingestRelogin` | `    model.challenge = null; ↵     model.reloginSubmitting = false; ↵     endReloginControls(); ↵   }` | `    model.challenge = null; ↵     void 0; ↵     endReloginControls(); ↵   }` | 行为守 | `PhoneReloginRecoveryTests.test_idle_snapshot_clears_captcha_and_locks_unlike_waiting_without_id` |

> 注：`M037` 因未清理挑战导致 `test_auto_snapshot_clears_challenge_submitting_and_starting_locks` 发出挂起请求而在前置测试后触及 90 秒单次运行上限，按 `mutate_relogin.py` 口径记为行为守并标注「超时」。

## 2. 本批新增用例清单（共 6 条）

全部写入 `local/tests/test_phone_ui.py` 对应既有测试类（测试文件总数保持 39 个），仅断言用户可见结果或替身请求：

| 测试类 / 用例名 | 守的用户可见结果 | 对应变异编号 |
|---|---|---|
| `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` | 标题不越页覆盖并按预期恢复，错误/正文/自动认图/保存附言与页脚三组按钮双向显隐及写入 | `M001`、`M002`、`M005`、`M009`、`M015`、`M016`、`M017`、`M020`、`M023` |
| `PhoneReloginRecoveryTests.test_captcha_src_attribute_cleared_on_non_png_and_flow_end` | 无有效 PNG 与流程结束收起验证码图时清除 `src` 属性并隐藏元素 | `M030`、`M050` |
| `PhoneReloginRecoveryTests.test_auto_snapshot_clears_challenge_submitting_and_starting_locks` | `auto` 快照解除挑战、提交锁与开始锁，允许收起抽屉并允许后续再点开始 | `M037`、`M038`、`M039` |
| `PhoneReloginRecoveryTests.test_starting_and_verifying_snapshots_reset_submitting_and_pick_mode_note` | `starting`/`verifying` 解锁提交态，`starting` 按手动等待写 `#relogin-note` 与进度提示 | `M053`、`M056`、`M057`、`M058` |
| `PhoneReloginRecoveryTests.test_terminal_snapshots_unlock_sheet_and_reset_challenge` | `success` 与 `failed` 终态解锁抽屉关闭并清除旧挑战以便同编号新图重现 | `M060`、`M061`、`M066`、`M067` |
| `PhoneReloginRecoveryTests.test_idle_snapshot_clears_captcha_and_locks_unlike_waiting_without_id` | 缺 `challenge_id` 的等待态不误清理，进入 `idle` 才隐藏旧图、解锁关闭与重置挑战 | `M070`、`M071`、`M072` |

## 3. 全部 129 条复跑统计

### 总体变化

| 结论分类 | 补测前（`before.md`） | 第一批后（本次复跑） | 变化 |
|---|---:|---:|---:|
| 行为守 | 79 | **104** | +25 |
| 字面守 | 0 | 0 | 0 |
| 无人守 | 50 | **25** | -25 |
| 无效 | 0 | 0 | 0 |
| 等价 | 0 | 0 | 0 |
| **总计** | **129** | **129** | **0** |

### 按变异口径统计（129 条）

| 变异口径 | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---:|---:|---:|---:|---:|---:|
| 甲类（`model.字段` 写换 `void 0`） | 22 | 0 | 6 | 0 | 0 | 28 |
| 乙类（条件 `C` 换 `!(C)`） | 32 | 0 | 3 | 0 | 0 | 35 |
| 丙类（`.hidden = X` 写换 `void 0`） | 18 | 0 | 1 | 0 | 0 | 19 |
| 丁类（请求载荷属性与 `args.*` 写入变异） | 8 | 0 | 7 | 0 | 0 | 15 |
| 戊类（`return true`/`false` 互换） | 3 | 0 | 0 | 0 | 0 | 3 |
| 己类（`.textContent`/`.value`/`.src`/`removeAttribute` 写换 `void 0`） | 21 | 0 | 8 | 0 | 0 | 29 |

### 按函数统计（129 条）

| 函数 | 口径（甲 / 乙 / 丙 / 丁 / 戊 / 己） | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---|---:|---:|---:|---:|---:|---:|
| `renderRelogin` | 0 / 2 / 15 / 0 / 0 / 7 | 24 | 0 | 0 | 0 | 0 | 24 |
| `openRelogin` | 2 / 2 / 0 / 0 / 0 / 0 | 4 | 0 | 0 | 0 | 0 | 4 |
| `endReloginControls` | 0 / 0 / 1 / 0 / 0 / 1 | 2 | 0 | 0 | 0 | 0 | 2 |
| `ingestRelogin` | 15 / 15 / 2 / 0 / 0 / 10 | 42 | 0 | 0 | 0 | 0 | 42 |
| `beginRelogin` | 8 / 7 / 0 / 5 / 0 / 5 | 17 | 0 | 8 | 0 | 0 | 25 |
| `submitRelogin` | 2 / 6 / 0 / 7 / 0 / 6 | 8 | 0 | 13 | 0 | 0 | 21 |
| `cancelRelogin` | 1 / 2 / 1 / 3 / 3 / 0 | 6 | 0 | 4 | 0 | 0 | 10 |
| `refreshRelogin` | 0 / 1 / 0 / 0 / 0 / 0 | 1 | 0 | 0 | 0 | 0 | 1 |

## 4. 第二批剩余无人守编号（25 条）

- `beginRelogin`（8 条）：`M076`、`M077`、`M078`、`M081`、`M082`、`M093`、`M094`、`M097`
- `submitRelogin`（13 条）：`M102`、`M103`、`M105`、`M108`、`M109`、`M110`、`M111`、`M113`、`M114`、`M115`、`M116`、`M117`、`M118`
- `cancelRelogin`（4 条）：`M122`、`M123`、`M126`、`M127`
