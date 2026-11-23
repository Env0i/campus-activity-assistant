# 手机页第四组（「重新登录」）安全网

- **执行日期**：2026-11-23
- **分支与基线**：`refactor/phone-page`（只增改 `local/tests/test_phone_ui.py` 与本目录证据文件；`local/ui/m/` 全部产品代码零改动）。
- **核心结论**：针对 `local/ui/m/ui-relogin.js` 的 8 个顶层函数生成六类共 **129 条**单点变异；补测前行为守 79、无人守 50；经两批共补入 **13 条**纯行为用例（第一批面板渲染与快照摄入 6 条、第二批开始/提交/取消请求 7 条）并给出 **1 条**带全调用方证明的等价判定后，最终结论为 **行为守 128、等价 1、无人守 0、字面守 0、无效 0**。

## 1. 范围与六类变异口径

- **目标范围**：按 `design/evidence/2026-11-22/phone-net/move-facts.md` 归入「重新登录」组的 `local/ui/m/ui-relogin.js` 全部 **8 个**顶层函数（`renderRelogin`、`openRelogin`、`endReloginControls`、`ingestRelogin`、`beginRelogin`、`submitRelogin`、`cancelRelogin`、`refreshRelogin`），函数边界通过 `tools/code_shape/jsscan.mjs` 求得，共产生 129 条单点变异。
- **六类单点变异口径**：
  - **甲类（28 条）**：函数体内每一处 `model.字段` 写操作整条替换为 `void 0`。
  - **乙类（35 条）**：函数体内每一个 `if`、`else if` 与三元表达式条件 `C` 替换为 `!(C)`。
  - **丙类（19 条）**：函数体内每一处 `.hidden = X` 显隐写入整条替换为 `void 0`。
  - **丁类（15 条）**：函数体内每一处 `postAction` 与 `api` 调用的对象字面量里（含嵌套 `body`、`args`、`method`），每个属性的值替换为 `undefined`（简写属性 `code` 先展开为 `code: undefined`），以及 `beginRelogin` 里对局部载荷 `args` 的每一处属性赋值（`args.username`、`args.password`、`args.save`）整条替换为 `void 0`。
  - **戊类（3 条）**：函数体内每一处 `return true` 与 `return false` 互换（`cancelRelogin` 的三处返回）。
  - **己类（29 条）**：函数体内每一处 `.textContent`、`.value`、`.src` 的赋值整条替换为 `void 0`，每一处 `removeAttribute` 调用整条替换为 `void 0`。
- **执行环境与方法**：在 `%TEMP%`（`tempfile.gettempdir()`）下由 `git archive HEAD` 导出、再叠加工作区 `local/tests/test_phone_ui.py` 的独立临时副本中运行 `scripts/mutate_relogin.py`，每条变异先过 `node --check`，再跑 `local/tests/test_phone_ui.py` 全量用例；跑完删除临时副本。单条测试超时（90 秒）按失败计并在报告里标注「超时」（本组 `M037` 即 `ingestRelogin` 在 `auto` 分支漏清 `model.challenge` 导致后续挂起请求触发首个用例超时，记入行为守并标注「超时」）。

## 2. 8 个函数对照

| 函数 | 变异数 | 口径（甲 / 乙 / 丙 / 丁 / 戊 / 己） | 补测前（行为守 / 无人守） | 第一批后（行为守 / 无人守） | 第二批后（行为守 / 等价 / 无人守） |
|---|---:|---|---|---|---|
| `renderRelogin` | 24 | 0 / 2 / 15 / 0 / 0 / 7 | 15 / 9 | 24 / 0 | 24 / 0 / 0 |
| `openRelogin` | 4 | 2 / 2 / 0 / 0 / 0 / 0 | 4 / 0 | 4 / 0 | 4 / 0 / 0 |
| `endReloginControls` | 2 | 0 / 0 / 1 / 0 / 0 / 1 | 1 / 1 | 2 / 0 | 2 / 0 / 0 |
| `ingestRelogin` | 42 | 15 / 15 / 2 / 0 / 0 / 10 | 27 / 15 | 42 / 0 | 42 / 0 / 0 |
| `beginRelogin` | 25 | 8 / 7 / 0 / 5 / 0 / 5 | 17 / 8 | 17 / 8 | 24 / 1 / 0 |
| `submitRelogin` | 21 | 2 / 6 / 0 / 7 / 0 / 6 | 8 / 13 | 8 / 13 | 21 / 0 / 0 |
| `cancelRelogin` | 10 | 1 / 2 / 1 / 3 / 3 / 0 | 6 / 4 | 6 / 4 | 10 / 0 / 0 |
| `refreshRelogin` | 1 | 0 / 1 / 0 / 0 / 0 / 0 | 1 / 0 | 1 / 0 | 1 / 0 / 0 |
| **合计（8 个函数）** | **129** | **28 / 35 / 19 / 15 / 3 / 29** | **79 / 50** | **104 / 25** | **128 / 1 / 0** |

## 3. 补测前后三档统计对照

| 结论分类 | 补测前（`before.md`） | 第一批后（`after-render-ingest.md`） | 第二批后（`after.md`） | 总变化 |
|---|---:|---:|---:|---:|
| 行为守 | 79 | 104 | **128** | +49 |
| 字面守 | 0 | 0 | 0 | 0 |
| 无人守 | 50 | 25 | **0** | -50 |
| 无效 | 0 | 0 | 0 | 0 |
| 等价 | 0 | 0 | **1** | +1 |
| **总计** | **129** | **129** | **129** | **0** |

按口径分布（补测后最终态）：
- 甲类（28 条）：行为守 27、等价 1、无人守 0
- 乙类（35 条）：行为守 35、等价 0、无人守 0
- 丙类（19 条）：行为守 19、等价 0、无人守 0
- 丁类（15 条）：行为守 15、等价 0、无人守 0
- 戊类（3 条）：行为守 3、等价 0、无人守 0
- 己类（29 条）：行为守 29、等价 0、无人守 0

## 4. 两批新增行为用例清单（共 13 条）

全部写入 `local/tests/test_phone_ui.py` 对应主题既有测试类（测试文件总数保持 39 个），仅断言用户可见 DOM、请求方法/CSRF 头/载荷或定时器排程（丙类显隐与己类文字用例开场先设为与预期相反的值；账号、密码、验证码均使用一眼可辨的假值）：

### 第一批：面板渲染、收尾清图与快照摄入（6 条，详见 `after-render-ingest.md`）

| 测试类 / 用例名 | 守的用户可见结果 | 对应变异编号 |
|---|---|---|
| `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` | 标题不越页覆盖并按预期恢复，错误/正文/自动认图/保存附言与页脚三组按钮双向显隐及写入 | `M001`、`M002`、`M005`、`M009`、`M015`、`M016`、`M017`、`M020`、`M023` |
| `PhoneReloginRecoveryTests.test_captcha_src_attribute_cleared_on_non_png_and_flow_end` | 无有效 PNG 与流程结束收起验证码图时清除 `src` 属性并隐藏元素 | `M030`、`M050` |
| `PhoneReloginRecoveryTests.test_auto_snapshot_clears_challenge_submitting_and_starting_locks` | `auto` 快照解除挑战、提交锁与开始锁，允许收起抽屉并允许后续再点开始 | `M037`、`M038`、`M039` |
| `PhoneReloginRecoveryTests.test_starting_and_verifying_snapshots_reset_submitting_and_pick_mode_note` | `starting`/`verifying` 解锁提交态，`starting` 按手动等待写 `#relogin-note` 与进度提示 | `M053`、`M056`、`M057`、`M058` |
| `PhoneReloginRecoveryTests.test_terminal_snapshots_unlock_sheet_and_reset_challenge` | `success` 与 `failed` 终态解锁抽屉关闭并清除旧挑战以便同编号新图重现 | `M060`、`M061`、`M066`、`M067` |
| `PhoneReloginRecoveryTests.test_idle_snapshot_clears_captcha_and_locks_unlike_waiting_without_id` | 缺 `challenge_id` 的等待态不误清理，进入 `idle` 才隐藏旧图、解锁关闭与重置挑战 | `M070`、`M071`、`M072` |

### 第二批：开始、提交、取消请求（7 条，详见 `after-requests.md`）

| 测试类 / 用例名 | 守的用户可见结果或请求载荷 | 对应变异编号 |
|---|---|---|
| `ReloginSheetTests.test_begin_relogin_clears_confirm_and_previous_account_postscript` | 发起开始立即收起确认层并切入忙态；下一轮未在手机端输账号时，完成态不残留上一轮附言 | `M076`、`M077` |
| `ReloginSheetTests.test_begin_relogin_empty_credentials_recovers_lock_and_manual_note` | 账号或密码为空时写入必填提示并解除开始锁以允许补填重发；手动受理后写入要验证码提示 | `M081`、`M082`、`M097` |
| `ReloginSheetTests.test_begin_relogin_failure_distinguishes_plan_late_and_other_errors` | 发起重登被拒时区分计划临近来不及与一般原因并写入 `#relogin-note` | `M093`、`M094` |
| `PhoneReloginRecoveryTests.test_submit_relogin_sends_post_csrf_and_full_payload_and_clears_code` | 提交验证码发 `POST`、带 `X-Campus-Csrf` 头及完整 `flow_id`/`challenge_id`/`code`，成功后清空 `#code` 并触发轮询 | `M105`、`M108`、`M109`、`M110`、`M111`、`M113`、`M118` |
| `PhoneReloginRecoveryTests.test_submit_relogin_stale_challenge_mismatch_updates_note_and_clears_code` | 当前流程挑战换代时提示换新图、清空 `#code` 且不发提交请求 | `M102`、`M103` |
| `PhoneReloginRecoveryTests.test_submit_relogin_duplicate_keeps_lock_while_other_error_unlocks_with_reason` | 重复提交维持锁定并提示等结果、补轮询；其他失败写明拒绝原因并解除提交锁以允许重试 | `M113`、`M114`、`M115`、`M116`、`M117` |
| `PhoneReloginRecoveryTests.test_cancel_relogin_sends_flow_id_hides_captcha_and_clears_challenge` | 取消重登带 `args.flow_id`，成功后隐藏 `#captcha`、清空挑战以禁用提交钮并阻断后续提交 | `M122`、`M123`、`M126`、`M127` |

## 5. 等价判定摘要（1 条）

完整理由与全目录扫描证明见 `design/evidence/2026-11-23/phone-relogin-net/scripts/equiv.json` 与 `after.md` 末尾：

- **`M078`**（`ui-relogin.js:beginRelogin`）：`model.relSavedChoice = false;` 改 `void 0;`。`beginRelogin` 第 171 行先将 `model.relEnteredAcct` 置 `false`，随后第 173 行 `refreshControls()` 调用 `renderRelogin()` 传入 `entered: false`，`PhoneModel.reloginView`（`model-relogin.js:158`）按 `o.entered` 短路而不读取 `savedChoice`；全目录 12 份手机页脚本中仅 `ui-relogin.js:190` 会将 `model.relEnteredAcct` 置 `true`，且同一同步块的下一行 `ui-relogin.js:191` 紧邻无分支覆写 `model.relSavedChoice = args.save`。因此去掉第 172 行清零对任何 DOM、请求、定时器与返回值均无影响。

## 6. 未覆盖项

- 手机真机与打包后的电脑端 WebView2 冻结窗口未实测，所有行为用例均在受控 Node `vm` 沙箱与本机离线单元测试运行。
- 本组安全网仅覆盖 `local/ui/m/ui-relogin.js` 的 8 个顶层函数；其余手机页脚本的「请求与配对会话」「摄入与渲染」「计划操作」另见同级证据目录，外壳与接线不在本组范围。

## 7. 复现命令

在仓库根执行（Python 3.12；运行前清空 `http_proxy` / `HTTP_PROXY` / `https_proxy` / `HTTPS_PROXY` / `all_proxy`，并设 `PYTHONIOENCODING=utf-8`）：

```bash
python -m unittest discover -s local/tests -p "test_phone_ui.py"
python -m unittest discover -s local/tests -p "test_ui_contracts.py"
python -m unittest discover -s local/tests -p "test_code_shape.py"
python design/evidence/2026-11-23/phone-relogin-net/scripts/mutate_relogin.py --list
python design/evidence/2026-11-23/phone-relogin-net/scripts/mutate_relogin.py --baseline
python design/evidence/2026-11-23/phone-relogin-net/scripts/mutate_relogin.py \
  --ids M076,M077,M078,M081,M082,M093,M094,M097,M102,M103,M105,M108,M109,M110,M111,M113,M114,M115,M116,M117,M118,M122,M123,M126,M127 \
  --workers 4 --phase 补测之后 \
  --equiv-json design/evidence/2026-11-23/phone-relogin-net/scripts/equiv.json
python design/evidence/2026-11-23/phone-relogin-net/scripts/mutate_relogin.py \
  --workers 4 --phase 补测之后 \
  --equiv-json design/evidence/2026-11-23/phone-relogin-net/scripts/equiv.json \
  --out design/evidence/2026-11-23/phone-relogin-net/after.md
```
