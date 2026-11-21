# 手机页第 0 批：结构清点与「请求与配对会话」组安全网

- **执行日期**：2026-11-21
- **基线提交**：`7922aa2`（分支 `refactor/phone-page`；只增改测试与证据，产品代码 `local/ui/m/`、`local/infrastructure/phone_http.py` 及其他非测试文件零改动）。

## 1. 范围与口径

- **五组清点范围**：按 `local/ui/m/app.js` DOM 层 67 个顶层函数划分的五组——「请求与配对会话」（16 个）、「摄入与渲染」（23 个）、「外壳与接线」（7 个）、「计划操作」（13 个）、「重新登录」（8 个），另单列未归组顶层常量与状态对象 5 项、PhoneModel 成员 101 项及页面加载静态白名单（见 `move-facts.md`）；重复规则对照见 `rule-dups.md`。
- **两类变异口径**：仅覆盖「请求与配对会话」这一组的 16 个函数（`readCookie`、`api`、`postAction`、`renderPair`、`setPairError`、`beginPairLock`、`schedulePairTick`、`stopPairLock`、`applyPairFailure`、`pair`、`poll`、`onPollFail`、`onNeedPair`、`onForbidden`、`schedule`、`probeExistingSession`），共 72 条单点变异：
  - **甲类（32 条）**：函数体内每一处 `model.字段` 写操作（赋值、复合赋值、自增自减与原地修改），将整条写语句替换为 `void 0`。
  - **乙类（40 条）**：函数体内每一个 `if`、`else if` 与三元表达式的条件 `C`，替换为 `!(C)`。
- **执行方式**：在 `tempfile.gettempdir()` 下由 `git archive` 导出的独立临时副本（含工作区未提交的 `local/tests/test_phone_ui.py`）中逐条变异，先过 `node --check`，再跑 `local/tests/test_phone_ui.py` 全部用例（不联网、不起真服务，跑完清理临时副本）。

## 2. 变异前后统计对照

| 结论分类 | 补测前（`before.md`） | 补测后（`after.md`） | 变化 |
|---|---:|---:|---:|
| 行为守（至少 1 条 node 行为用例失败） | 48 | 66 | +18 |
| 字面守（仅源码文本断言失败） | 0 | 0 | 0 |
| 无人守（全绿） | 18 | 0 | -18 |
| 无效（语法不过或定位失败） | 0 | 0 | 0 |
| 等价（人工复判，附全部调用方证明） | 6 | 6 | 0 |
| **总计** | **72** | **72** | **0** |

6 条等价变异（`M23`、`M28`、`M40`、`M58`、`M60`、`M66`）的完整调用方排查与等价理由见 `before.md` 与 `after.md` 末尾。

## 3. 新增行为用例清单

全部写进 `local/tests/test_phone_ui.py` 对应主题测试类，仅断言受控 DOM（`textContent`、`hidden`、`disabled`、`className`）、替身 `fetch` 请求与 `__timerDelays()` 定时器排程，测试文件总数保持 39 个：

| 测试类 / 用例名 | 守的用户可见结果 | 对应变异编号 |
|---|---|---|
| `PhoneReloginRecoveryTests.test_poll_preserves_in_memory_csrf_and_caches_cookie_csrf` | 轮询不以空 cookie 覆盖内存 CSRF，且恢复会话后记住 cookie 里的写权限 | `M43`、`M44` |
| `PhoneReloginRecoveryTests.test_initial_wire_probes_cookie_session_once_without_repeating` | 首屏带会话 cookie 进入自动探测一次恢复主界面，重复接线不重发请求 | `M70`、`M71` |
| `MobileWriteResilienceTests.test_api_clears_abort_timeout_after_request_settles` | 请求正常返回后清掉 8 秒超时定时器，不残留悬空定时器 | `M15` |
| `MobileWriteResilienceTests.test_action_401_clears_active_poll_and_tick_timers` | 写请求 401 退回配对页时同时停掉轮询与整秒计时器 | `M52`、`M57`、`M59` |
| `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` | 403 不以空 cookie 抹掉内存 CSRF，读到新 cookie 缓存并按退避周期延后重拉 | `M37`、`M61`、`M62`、`M64` |
| `PairStatesDomTests.test_pair_led_renders_lit_dots_and_clears_old_error_on_submit` | 点阵屏正确区分亮暗点，再次提交配对在途期间先清掉旧错误条 | `M17`、`M33` |
| `PairStatesDomTests.test_pair_success_sends_csrf_and_keeps_retry_if_first_poll_fails` | 配对成功无 cookie 也带回 CSRF 发写请求，首轮拉状态失败仍按退避排期重连 | `M37`、`M38` |
| `PairStatesDomTests.test_stopping_pair_lock_cancels_pending_countdown_timer` | 退回配对或停锁时清掉锁定倒计时定时器，避免旧定时器继续改写配对提示 | `M27` |
| `PhoneSyncPolicyTests.test_poll_success_resets_backoff_and_replaces_old_poll_timer` | 同步成功重置退避基线为 1 秒，重排时清掉旧轮询定时器不堆积 | `M51`、`M65` |
| `PhoneSyncPolicyTests.test_poll_restores_paired_sync_and_second_tick_timers` | 从未配对态恢复会话拉到 200 后排好轮询与整秒计时器 | `M52` |

## 4. 复现命令

在仓库根执行（Python 3.12，临时副本目录由 `tempfile.gettempdir()` 自动创建并在运行后删除；跑测试前需清空代理环境变量 `http_proxy` / `https_proxy` / `all_proxy`）：

```bash
# 1. 清点核对与生成 move-facts.md
python design/evidence/2026-11-22/phone-net/scripts/move_facts.py
python design/evidence/2026-11-22/phone-net/scripts/move_facts.py --check

# 2. 变异清单定位核对与未变异基线检查
python design/evidence/2026-11-22/phone-net/scripts/mutate_phone.py --list
python design/evidence/2026-11-22/phone-net/scripts/mutate_phone.py --baseline

# 3. 重跑全部 72 条变异（4 路独立副本并行）
python design/evidence/2026-11-22/phone-net/scripts/mutate_phone.py \
  --workers 4 --phase 补测之后 \
  --equiv-json design/evidence/2026-11-22/phone-net/scripts/equiv.json \
  --out design/evidence/2026-11-22/phone-net/after.md

# 4. 离线测试与代码结构检查
python -B -m unittest discover -s local/tests -p test_phone_ui.py
python -B -m unittest discover -s local/tests -p test_phone_service.py
python -B -m unittest discover -s local/tests -p test_phone_infra.py
python -B -m unittest discover -s local/tests -p test_code_shape.py
```

## 5. 未验证项

- 真机（iOS Safari）与真实远程通道（Tailscale / Cloudflare 临时隧道）未实测，所有行为用例均在受控 Node `vm` 沙箱与本机离线环境运行。
- 本批安全网变异仅覆盖第一组（「请求与配对会话」）的 16 个函数；其余四组（「摄入与渲染」「外壳与接线」「计划操作」「重新登录」）未纳入本批变异范围。
