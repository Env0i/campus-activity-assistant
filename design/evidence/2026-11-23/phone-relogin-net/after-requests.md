# 第四组第二批（开始、提交、取消请求）补测后结论

- **范围**：`local/ui/m/ui-relogin.js` 里 `beginRelogin`（8 条）、`submitRelogin`（13 条）与 `cancelRelogin`（4 条）在第一批后仍无人守的 **25 条**变异。
- **补测后结论**：本批 25 条中 **行为守 24**、**等价 1**（`M078`）、无人守 **0**、字面守 **0**、无效 **0**。
- **全量 129 条复跑**：行为守 **128**（补测前 79 条与第一批 25 条共 104 条全部保持行为守，无退化）、等价 **1**、无人守 **0**、字面守 **0**、无效 **0**。

## 1. 本批 25 条补测后逐条结论

| 编号 | 类 | 函数 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例 |
|---|---|---|---|---|---|---|
| M076 | 甲 | `beginRelogin` | `model.relConfirm = false;` | `void 0;` | 行为守 | `ReloginSheetTests.test_begin_relogin_clears_confirm_and_previous_account_postscript` |
| M077 | 甲 | `beginRelogin` | `model.relEnteredAcct = false;` | `void 0;` | 行为守 | `ReloginSheetTests.test_begin_relogin_clears_confirm_and_previous_account_postscript` |
| M078 | 甲 | `beginRelogin` | `model.relSavedChoice = false;` | `void 0;` | 等价 | — |
| M081 | 甲 | `beginRelogin` | `      model.reloginStarting = false; ↵       $("relogin-note").textContent = "账号和密码都要填。";` | `      void 0; ↵       $("relogin-note").textContent = "账号和密码都要填。";` | 行为守 | `ReloginSheetTests.test_begin_relogin_empty_credentials_recovers_lock_and_manual_note` |
| M082 | 己 | `beginRelogin` | `$("relogin-note").textContent = "账号和密码都要填。";` | `void 0;` | 行为守 | `ReloginSheetTests.test_begin_relogin_empty_credentials_recovers_lock_and_manual_note` |
| M093 | 己 | `beginRelogin` | `$("relogin-note").textContent = body && body.error === "plan_late" ↵       ? "现在来不及重新登录：" + String(body.text \|\| "有场次正在提交，或者离开放不到 100 秒。") ↵       : "还不能开始：" + String((body && body.text) \|\| (body && body.error) \|\| "请到电脑上准备账号");` | `void 0;` | 行为守 | `ReloginSheetTests.test_begin_relogin_failure_distinguishes_plan_late_and_other_errors` |
| M094 | 乙 | `beginRelogin` | `body && body.error === "plan_late" ↵       ?` | `!(body && body.error === "plan_late") ↵       ?` | 行为守 | `ReloginSheetTests.test_begin_relogin_failure_distinguishes_plan_late_and_other_errors` |
| M097 | 己 | `beginRelogin` | `$("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.needCode;` | `void 0;` | 行为守 | `ReloginSheetTests.test_begin_relogin_empty_credentials_recovers_lock_and_manual_note` |
| M102 | 己 | `submitRelogin` | `$("relogin-note").textContent = "验证码已换代，请看新图";` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_submit_relogin_stale_challenge_mismatch_updates_note_and_clears_code` |
| M103 | 己 | `submitRelogin` | `    $("relogin-note").textContent = "验证码已换代，请看新图"; ↵     $("code").value = "";` | `    $("relogin-note").textContent = "验证码已换代，请看新图"; ↵     void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_submit_relogin_stale_challenge_mismatch_updates_note_and_clears_code` |
| M105 | 丁 | `submitRelogin` | `method: "POST",` | `method: undefined,` | 行为守 | `PhoneReloginRecoveryTests.test_submit_relogin_duplicate_keeps_lock_while_other_error_unlocks_with_reason` |
| M108 | 丁 | `submitRelogin` | `args: { ↵         flow_id: model.challenge.flow_id, ↵         challenge_id: model.challenge.challenge_id, code }` | `args: undefined` | 行为守 | `PhoneReloginRecoveryTests.test_submit_relogin_sends_post_csrf_and_full_payload_and_clears_code` |
| M109 | 丁 | `submitRelogin` | `flow_id: model.challenge.flow_id,` | `flow_id: undefined,` | 行为守 | `PhoneReloginRecoveryTests.test_submit_relogin_sends_post_csrf_and_full_payload_and_clears_code` |
| M110 | 丁 | `submitRelogin` | `challenge_id: model.challenge.challenge_id,` | `challenge_id: undefined,` | 行为守 | `PhoneReloginRecoveryTests.test_submit_relogin_sends_post_csrf_and_full_payload_and_clears_code` |
| M111 | 丁 | `submitRelogin` | `code } } });` | `code: undefined } } });` | 行为守 | `PhoneReloginRecoveryTests.test_submit_relogin_sends_post_csrf_and_full_payload_and_clears_code` |
| M113 | 乙 | `submitRelogin` | `if (!result \|\| result.status !== 200 \|\| !result.body \|\| !result.body.ok)` | `if (!(!result \|\| result.status !== 200 \|\| !result.body \|\| !result.body.ok))` | 行为守 | `PhoneReloginRecoveryTests.test_submit_relogin_duplicate_keeps_lock_while_other_error_unlocks_with_reason` |
| M114 | 乙 | `submitRelogin` | `if (error === "duplicate_submit")` | `if (!(error === "duplicate_submit"))` | 行为守 | `PhoneReloginRecoveryTests.test_submit_relogin_duplicate_keeps_lock_while_other_error_unlocks_with_reason` |
| M115 | 己 | `submitRelogin` | `    if (error === "duplicate_submit") { ↵       // 服务端说同一张图还有在途提交：别解锁，等它的结论再放行 ↵       // RL02：旧句「验证码正在提交，请等待结果」同样归并进「正在登录，请等结果」 ↵       $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;` | `    if (error === "duplicate_submit") { ↵       // 服务端说同一张图还有在途提交：别解锁，等它的结论再放行 ↵       // RL02：旧句「验证码正在提交，请等待结果」同样归并进「正在登录，请等结果」 ↵       void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_submit_relogin_duplicate_keeps_lock_while_other_error_unlocks_with_reason` |
| M116 | 甲 | `submitRelogin` | `model.reloginSubmitting = false;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_submit_relogin_duplicate_keeps_lock_while_other_error_unlocks_with_reason` |
| M117 | 己 | `submitRelogin` | `$("relogin-note").textContent = String( ↵       (result && result.body && (result.body.text \|\| result.body.error)) ↵         \|\| "提交没有被接受");` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_submit_relogin_duplicate_keeps_lock_while_other_error_unlocks_with_reason` |
| M118 | 己 | `submitRelogin` | `  $("code").value = ""; ↵   void poll(true);` | `  void 0; ↵   void poll(true);` | 行为守 | `PhoneReloginRecoveryTests.test_submit_relogin_sends_post_csrf_and_full_payload_and_clears_code` |
| M122 | 丁 | `cancelRelogin` | `args: { flow_id: flowId }` | `args: undefined` | 行为守 | `PhoneReloginRecoveryTests.test_cancel_relogin_sends_flow_id_hides_captcha_and_clears_challenge` |
| M123 | 丁 | `cancelRelogin` | `flow_id: flowId` | `flow_id: undefined` | 行为守 | `PhoneReloginRecoveryTests.test_cancel_relogin_sends_flow_id_hides_captcha_and_clears_challenge` |
| M126 | 甲 | `cancelRelogin` | `model.challenge = null;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_cancel_relogin_sends_flow_id_hides_captcha_and_clears_challenge` |
| M127 | 丙 | `cancelRelogin` | `$("captcha").hidden = true;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_cancel_relogin_sends_flow_id_hides_captcha_and_clears_challenge` |

### 等价判定理由与调用方证明

- **M078**（`ui-relogin.js:beginRelogin`）：`beginRelogin` 第 171 行先将 `model.relEnteredAcct` 置为 `false`，随后第 173 行 `refreshControls()` 调 `renderRelogin()`（`ui-relogin.js:18-19`）传入 `entered: false`，`PhoneModel.reloginView`（`model-relogin.js:158`）按 `o.entered ? (o.savedChoice ? ... : ...) : ""` 短路而不读取 `savedChoice`；之后仅当第 177 行进入输账号分支且通过第 180 行非空校验时，第 190 行才把 `model.relEnteredAcct` 置为 `true`，紧接着同一同步块的下一句第 191 行（中间无分支、无 `await`、无异常）立即以 `model.relSavedChoice = args.save` 覆写该字段，未进入该分支时 `model.relEnteredAcct` 始终为 `false`。去掉第 172 行写入不会影响任何 DOM、fetch 请求、定时器或返回值。调用方证明：全局扫描 `local/ui/m/*.js` 全部 `relSavedChoice`、`savedChoice` 与 `relEnteredAcct` 引用：(1) 唯一读取方为 `renderRelogin`（`ui-relogin.js:19`）读取 `model.relSavedChoice` 并与 `entered: model.relEnteredAcct`（`ui-relogin.js:18`）一同传入 `PhoneModel.reloginView`，仅在 `model-relogin.js:158` `o.entered` 为真时读 `o.savedChoice`；(2) 写入方仅有 `ui-session.js:53`（初始 `false`）与 `beginRelogin`（`ui-relogin.js:171-172`、`190-191`），第 190 与 191 行同步紧邻，不存在 `relEnteredAcct` 为真而未执行第 191 行覆写的路径；(3) `beginRelogin` 的全部调用方（`ui-shell.js:185`、`ui-shell.js:187`、`ui-relogin.js:284`、`ui-shell.js:277`）及其余 9 份脚本均不读写 `relSavedChoice` 与 `relEnteredAcct`。

## 2. 本批新增用例清单（共 7 条）

全部写入 `local/tests/test_phone_ui.py` 对应既有测试类（测试文件总数保持 39 个），仅断言用户可见结果或替身 `fetch` 请求：

| 测试类 / 用例名 | 守的用户可见结果或请求载荷 | 对应变异编号 |
|---|---|---|
| `ReloginSheetTests.test_begin_relogin_clears_confirm_and_previous_account_postscript` | 发起开始立即收起确认层并切入忙态；下一轮未在手机端输账号时，完成态不残留上一轮附言 | `M076`、`M077` |
| `ReloginSheetTests.test_begin_relogin_empty_credentials_recovers_lock_and_manual_note` | 账号或密码为空时写入必填提示并解除开始锁以允许补填重发；手动受理后写入要验证码提示 | `M081`、`M082`、`M097` |
| `ReloginSheetTests.test_begin_relogin_failure_distinguishes_plan_late_and_other_errors` | 发起重登被拒时区分计划临近来不及与一般原因并写入 `#relogin-note` | `M093`、`M094` |
| `PhoneReloginRecoveryTests.test_submit_relogin_sends_post_csrf_and_full_payload_and_clears_code` | 提交验证码发 `POST`、带 `X-Campus-Csrf` 头及完整 `flow_id`/`challenge_id`/`code`，成功后清空 `#code` 并触发轮询 | `M105`、`M108`、`M109`、`M110`、`M111`、`M113`、`M118` |
| `PhoneReloginRecoveryTests.test_submit_relogin_stale_challenge_mismatch_updates_note_and_clears_code` | 当前流程挑战换代时提示换新图、清空 `#code` 且不发提交请求 | `M102`、`M103` |
| `PhoneReloginRecoveryTests.test_submit_relogin_duplicate_keeps_lock_while_other_error_unlocks_with_reason` | 重复提交维持锁定并提示等结果、补轮询；其他失败写明拒绝原因并解除提交锁以允许重试 | `M113`、`M114`、`M115`、`M116`、`M117` |
| `PhoneReloginRecoveryTests.test_cancel_relogin_sends_flow_id_hides_captcha_and_clears_challenge` | 取消重登带 `args.flow_id`，成功后隐藏 `#captcha`、清空挑战以禁用提交钮并阻断后续提交 | `M122`、`M123`、`M126`、`M127` |

## 3. 全部 129 条复跑统计

### 总体变化

| 结论分类 | 补测前（`before.md`） | 第一批后（`after-render-ingest.md`） | 第二批后（`after.md`） | 总变化 |
|---|---:|---:|---:|---:|
| 行为守 | 79 | 104 | **128** | +49 |
| 字面守 | 0 | 0 | 0 | 0 |
| 无人守 | 50 | 25 | **0** | -50 |
| 无效 | 0 | 0 | 0 | 0 |
| 等价 | 0 | 0 | **1** | +1 |
| **总计** | **129** | **129** | **129** | **0** |

### 按变异口径统计（129 条）

| 变异口径 | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---:|---:|---:|---:|---:|---:|
| 甲类（`model.字段` 写换 `void 0`） | 27 | 0 | 0 | 0 | 1 | 28 |
| 乙类（条件 `C` 换 `!(C)`） | 35 | 0 | 0 | 0 | 0 | 35 |
| 丙类（`.hidden = X` 写换 `void 0`） | 19 | 0 | 0 | 0 | 0 | 19 |
| 丁类（请求载荷属性与 `args.*` 写入变异） | 15 | 0 | 0 | 0 | 0 | 15 |
| 戊类（`return true`/`false` 互换） | 3 | 0 | 0 | 0 | 0 | 3 |
| 己类（`.textContent`/`.value`/`.src`/`removeAttribute` 写换 `void 0`） | 29 | 0 | 0 | 0 | 0 | 29 |

### 按函数统计（129 条）

| 函数 | 口径（甲 / 乙 / 丙 / 丁 / 戊 / 己） | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---|---:|---:|---:|---:|---:|---:|
| `renderRelogin` | 0 / 2 / 15 / 0 / 0 / 7 | 24 | 0 | 0 | 0 | 0 | 24 |
| `openRelogin` | 2 / 2 / 0 / 0 / 0 / 0 | 4 | 0 | 0 | 0 | 0 | 4 |
| `endReloginControls` | 0 / 0 / 1 / 0 / 0 / 1 | 2 | 0 | 0 | 0 | 0 | 2 |
| `ingestRelogin` | 15 / 15 / 2 / 0 / 0 / 10 | 42 | 0 | 0 | 0 | 0 | 42 |
| `beginRelogin` | 8 / 7 / 0 / 5 / 0 / 5 | 24 | 0 | 0 | 0 | 1 | 25 |
| `submitRelogin` | 2 / 6 / 0 / 7 / 0 / 6 | 21 | 0 | 0 | 0 | 0 | 21 |
| `cancelRelogin` | 1 / 2 / 1 / 3 / 3 / 0 | 10 | 0 | 0 | 0 | 0 | 10 |
| `refreshRelogin` | 0 / 1 / 0 / 0 / 0 / 0 | 1 | 0 | 0 | 0 | 0 | 1 |
