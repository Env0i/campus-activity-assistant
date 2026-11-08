# L7 测试卫生正式报告：`<tmp>` 字面量、time 计数与全量 unittest（2026-11-08）

- **素材**：`<过程留证>/l7-hygiene.md`（只读分析）、`<过程留证>/l7-unittest.log`（全量输出留证，2588 行，末行 `EXIT=1`）。
- **性质**：正式收录版。素材三节全量搬运（判定表逐行无增删），搬运后主流程逐项抽查复核，命令与结果见文末「抽查复核」节。
- **角色声明**：只读分析。未改任何断言、未加 skip、未跑 server 全量、未跑 `test_dedup.py`。
- **标注**：【已复现】= 命令/脚本输出直接支持；【静态推断】= 只读代码推断，未逐条运行。

## ① `<tmp>` 字面量复算与逐处判定

### 复算【已复现】

命令：`grep -rn '<tmp>' local/tests server/tests`

- 结果：**5 行命中、6 次出现**（`grep -o` 复核为 6）。`local/tests/test_component_builder.py:25` 一行含 2 个 `<tmp>` 字面量。
- 任务书「local 4 + server 2 = 6」按**出现次数**口径成立：local = 2（component_builder）+ 1（retry_policy）+ 1（updater）= 4；server = 2。
- 按 `grep -rn` 行数口径是 5 行，差异全部来自 component_builder.py:25 的双命中。

### 判定表（6 条，按字面量出现次数；对应 5 行，component_builder.py:25 一行两处）

| # | 文件:行号 | 原文（逐字） | 上下文摘要（±5 行） | 判定 | 依据 |
|---|---|---|---|---|---|
| 1 | local/tests/test_component_builder.py:25 | `for path in ("relative", "<tmp>", "<tmp>/../elsewhere", "<样例盘符路径>"):`（第 1 个字面量 `"<tmp>"`） | 24-27 行：`for path in (...): with self.subTest(path=path), self.assertRaises(ValueError): builder.output_root(path)` | **会执行，但属被测非法输入样本，非夹具路径——不出补丁（理由改写，见补丁判定专节）** | 字面量作为非法输入参数传进 `builder.output_root()` 并断言 ValueError；实现（build_advanced.py:27-33）只拒「非绝对路径 / root==temp / 不在 temp 下」三类、从不查 `<>` 字符，`"<tmp>"` 经 not is_absolute 分支抛 ValueError（与 "relative" 分支重复）；换成 `tempfile.gettempdir()` 仍经 root==temp 分支抛 ValueError，测试仍绿且补边界覆盖。是否替换（属改测试语义）记 DEFERRED-L7-1 待用户定 |
| 2 | local/tests/test_component_builder.py:25 | `for path in ("relative", "<tmp>", "<tmp>/../elsewhere", "<样例盘符路径>"):`（第 2 个字面量 `"<tmp>/../elsewhere"`） | 同上 | **同 #1——不出补丁（理由改写）** | 同上；`"<tmp>/../elsewhere"` 同经 not is_absolute 分支，换成 `gettempdir()+"/../elsewhere"` 仍经 not is_relative_to 分支抛 ValueError |
| 3 | local/tests/test_retry_policy.py:5 | `时间用例对应 <tmp>/campus-retry-policy-20261024/timeline-cases.json；` | 模块 docstring 第 3-9 行，其后是 import | **注释（不执行）** | docstring 文本，引用的是每周会被清理的死链路径（AGENTS.md 禁止的新增内容模式，历史遗留） |
| 4 | local/tests/test_updater.py:51 | `"""隔离目录基类：只在 <tmp> 下开目录，不写程序目录和数据目录。"""` | 50-65 行：setUp 用 `self.root = TEMP_BASE / ("campus-updater-test-" + uuid)` | **注释（不执行）** | 类 docstring；真实目录来自第 23 行 `TEMP_BASE = Path(tempfile.gettempdir())` |
| 5 | server/tests/test_runtime_safety.py:8 | `- 任何 fixture 只写 <tmp>/campus-runtime-hardening-20261020/（可用` | 模块 docstring 第 7-11 行「隔离约定」 | **注释（不执行）** | docstring 文本 |
| 6 | server/tests/test_activity_watch.py:4 | `所有 fixture 都落在 <tmp>（可用 CAMPUS_TEST_ROOT 覆盖）的临时目录里。` | 模块 docstring 第 1-12 行 | **注释（不执行）** | docstring 文本 |

- **结论【静态推断（判定部分），主流程已亲自复核判定】**：唯一「会执行」的是 #1/#2（test_component_builder.py:25），其余 4 处均为 docstring/注释、不执行。
- #1/#2 是**被测的非法输入样本，不是夹具路径**：字面量作为非法参数传入 `builder.output_root()` 并断言 `assertRaises(ValueError)`。实测实现（build_advanced.py:27-33）只拒「非绝对路径 / root==temp / 不在 temp 下」三类、从不查 `<>` 字符：两个字面量都经 not is_absolute 分支抛 ValueError（与 "relative" 样本分支重复、零独占覆盖）；换成 `tempfile.gettempdir()` 后两样本分别经 root==temp、not is_relative_to 分支**仍抛 ValueError**，测试仍绿且补上当前未覆盖的 root==temp 边界分支——原「替换即破坏断言」的机制主张经对抗审阅推翻（2026-11-08）。**不出补丁**的结论维持，理由改写为「`<tmp>` 在该行是被测输入样本而非夹具路径，AGENTS.md「夹具 `<tmp>` 即缺陷」规则的适用对象（夹具路径）不适用」；是否仍要替换（补边界覆盖，属改测试语义）记 DEFERRED-L7-1（见「补丁判定专节」）。
- #3 是死链引用，属卫生清理范畴，但按 AGENTS.md「旧记录不追改」（只约束新增内容），是否回改由用户定。

## ② time.time() / datetime.now() 计数与判定

### 计数复算【已复现】

| 口径 | 命令 | 结果 |
|---|---|---|
| local/tests + server/tests 内 | `grep -rn -E 'time\.time\(\)|datetime\.now\(\)' local/tests server/tests` | **94**（行数=出现次数，无双命中行） |
| local+server 全量（含 tests） | 同式，`--include='*.py'` 对 local、server | **184** |
| local+server 全量（严格不含 tests） | 同式 + `--exclude-dir=tests` | **90**（local 35 + server 55） |

- 任务书给的 94 一致。
- **口径澄清**：任务书把 184 标为「不含 tests」；实测 184 = **含 tests 的全量总数**（tests 94 + 非 tests 90），严格不含 tests 为 **90**。成因：Windows 下 grep 输出路径是反斜杠（`local\tests\...`），`grep -v '/tests/'`（正斜杠模式）滤掉 **0 行**——反斜杠模式下该模式不匹配，`local\tests\` 与 `server\tests\` 的命中都滤不掉（对抗审阅 2026-11-08 实测：滤后仍为 184；`\tests\` 反斜杠固定串模式才可滤，滤后 90），任务书把「含 tests 全量」误标为「不含 tests」；以 `--exclude-dir=tests` 校验得 90（local 35 + server 55）。94（tests）+ 90（真非 tests）= 184 恰为全量。
- 命中分布（tests 内 94 = local 90 + server 4）：test_session_persistence 37、test_retry_phone_policy 16、test_retry_policy 11、test_signup_plan 11、test_login_relay_service 5、test_application_services 2、test_runtime_bundle 2、test_ui_contract 2、test_business_clock 1、test_business_clock_wiring 1、fixtures/business_clock 2；server：test_dedup 1、test_login_resilience 2、test_watchlist_safety 1。脚本式 server 测试 test_endpoints.py / test_notify.py 均为 0 处。

### 判定口径

- 安全：同一时钟求差（超时阈值/预算/相对时长）、日志或本机元数据戳（写读同源）、字符串字面量、epoch 毫秒签名；不落盘造学校时间字段。
- 风险：拿本机 naive 时间（本地时区）造「学校时间字段」（北京时间，time_contract / docs 口径），或把它当业务时刻与学校字段比较。

### tests 范围逐处判定表【已复现枚举 / 静态推断判定】

共 94 处：**风险 3，安全 91**。判定均经上下文人工核对。

#### local/tests（90 处：安全 87，风险 2）

| 文件:行号 | 关键代码 | 判定 | 依据 |
|---|---|---|---|
| test_business_clock.py:89 | `"业务时刻必须等于假服务器时间，而非本机 time.time()")` | 安全 | 断言消息里的字符串字面量，非调用 |
| test_business_clock_wiring.py:99 | `forward = time.time() + 8 * 3600`（随后 `mock.patch("time.time", return_value=forward)`） | 安全 | 人为制造 OS 墙钟前跳作扰动输入，验证业务预算不受墙钟影响（95-102 行注释明示） |
| test_application_services.py:1351 | `deadline = time.time() + timeout` | 安全 | 同钟超时阈值 |
| test_application_services.py:1352 | `while time.time() < deadline:` | 安全 | 同上 |
| test_login_relay_service.py:112 | `on_success=lambda: self.success_calls.append(time.time())` | 安全 | 记录回调时刻求时长 |
| test_login_relay_service.py:113 | `on_finish=lambda: self.finish_calls.append(time.time())` | 安全 | 同上 |
| test_login_relay_service.py:352 | `deadline = time.time() + 2` | 安全 | 超时阈值 |
| test_login_relay_service.py:353 | `while time.time() < deadline and self.service.state().get("live"):` | 安全 | 同上 |
| test_login_relay_service.py:404 | `on_finish=lambda: self.finish_calls.append(time.time())` | 安全 | 记录时长 |
| test_retry_policy.py:254 | `budget = time.time() + 10` | 安全 | 超时预算 |
| test_retry_policy.py:255 | `while time.time() < budget and not any(...)` | 安全 | 同上 |
| test_retry_policy.py:569 | `f.write("%d %d %.6f" % (1 if ok else 0, inside.value, time.time()))` | 安全 | 测试自用 mark 文件（子进程存活探测），epoch 相对比较 |
| test_retry_policy.py:654 | `retry_started_at=time.time() - offset` | 安全 | TaskSpec 重试起点是 epoch 秒锚点、取相对偏移（645-654 行注释明示 offset 语义）；sign_start 为写死字符串 |
| test_retry_policy.py:707 | `started = time.time()` | 安全 | 计时起点 |
| test_retry_policy.py:727 | `return api, result, events, time.time() - started, ...` | 安全 | 相对时长 |
| test_retry_policy.py:759 | `deadline = time.time() + 2.0` | 安全 | 超时阈值 |
| test_retry_policy.py:760 | `while time.time() < deadline and _pid_alive(grandchild):` | 安全 | 同上 |
| test_retry_policy.py:805 | `deadline = time.time() + 1 + self.GRACE + 2.0` | 安全 | 超时阈值 |
| test_retry_policy.py:806 | `while time.time() < deadline and not any(...)` | 安全 | 同上 |
| test_retry_policy.py:868 | `stamp["at"] = time.time()` | 安全 | 记录 Job 赋权时刻，用于相对顺序断言 |
| test_retry_phone_policy.py:134 | `retry_started_at=time.time() - anchor_offset` | 安全 | 同 retry_policy:654；129 行 docstring 明示 anchor_offset 是「当前时刻−冻结起点」的相对量 |
| test_retry_phone_policy.py:161 | `started = time.time()` | 安全 | 计时起点 |
| test_retry_phone_policy.py:188 | `return result, time.time() - started, events, captured` | 安全 | 相对时长 |
| test_retry_phone_policy.py:373 | `now = time.time()` | 安全 | epoch 锚点算术（anchor = now − 常数），同钟相对差 |
| test_retry_phone_policy.py:389 | `started = time.time()` | 安全 | 计时起点 |
| test_retry_phone_policy.py:395 | `elapsed = time.time() - started` | 安全 | 相对时长 |
| test_retry_phone_policy.py:405 | `now = time.time()` | 安全 | epoch 锚点算术 |
| test_retry_phone_policy.py:421 | `started = time.time()` | 安全 | 计时起点 |
| test_retry_phone_policy.py:427 | `elapsed = time.time() - started` | 安全 | 相对时长 |
| test_retry_phone_policy.py:434 | `now = time.time()` | 安全 | epoch 锚点算术 |
| test_retry_phone_policy.py:450 | `started = time.time()` | 安全 | 计时起点 |
| test_retry_phone_policy.py:456 | `elapsed = time.time() - started` | 安全 | 相对时长 |
| test_retry_phone_policy.py:462 | `now = time.time()` | 安全 | epoch 锚点算术 |
| test_retry_phone_policy.py:478 | `started = time.time()` | 安全 | 计时起点 |
| test_retry_phone_policy.py:484 | `elapsed = time.time() - started` | 安全 | 相对时长 |
| test_retry_phone_policy.py:499 | `now = time.time()` | 安全 | epoch 锚点算术 |
| test_session_persistence.py:185 | `{"saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}` | 安全 | session.json saved_at 是本机元数据；login_state 不据其判失效（196-198 行注释，决策 012） |
| test_session_persistence.py:191 | `{"token": "t", "saved_at": datetime.now().strftime(...)}` | 安全 | 同上 |
| test_session_persistence.py:199 | `stale = (datetime.now() - timedelta(hours=25)).strftime(...)` | 安全 | 同上；陈旧样例也不判失效 |
| test_session_persistence.py:334 | `past_end = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")` → 喂 `sign_end` | **风险** | 本机 naive 时间造学校字段 sign_end（335-341 行进 start_plan 活动缓存，按 time_contract 北京时间口径解析判「已截止」）；本机 UTC+8 恰好自洽。对抗审阅 2026-11-08 复核：断言方向「已截止」使 x<17 时区恒绿、标签仍对，仅在特定时区窗口错位——措辞减轻，风险标签维持 |
| test_session_persistence.py:438 | `at = (datetime.now() - timedelta(seconds=5)).strftime(...)` → `sign_start` | **风险** | 本机时间造学校字段 sign_start（439-444 行进 TaskSpec.from_activity，模拟「刚开放」），同 :334（跨时区措辞减轻，风险标签维持） |
| test_session_persistence.py:505 | `closed = datetime.now() - timedelta(hours=1)` | 安全 | compute_lifecycle 生命周期戳，同钟写读 |
| test_session_persistence.py:508 | `life = app.compute_lifecycle(prev, datetime.now())` | 安全 | 参考点与戳同一本地 naive 时钟 |
| test_session_persistence.py:515 | `beat = datetime.now() - timedelta(hours=2)` | 安全 | 同上 |
| test_session_persistence.py:517 | `datetime.now())`（跨行调用续行） | 安全 | 同上 |
| test_session_persistence.py:521 | `closed = datetime.now() - timedelta(hours=3)` | 安全 | 同上 |
| test_session_persistence.py:525 | `datetime.now())` | 安全 | 同上 |
| test_session_persistence.py:531 | `life = app.compute_lifecycle({}, datetime.now())` | 安全 | 同上（空 prev 分支） |
| test_session_persistence.py:534 | `bad = app.compute_lifecycle({"last_closed_at": "not-a-time"}, datetime.now())` | 安全 | 坏值分支，时间仅作参考点 |
| test_session_persistence.py:540 | `future = datetime.now() + timedelta(hours=2)` | 安全 | 时钟回拨用例，两端同钟 |
| test_session_persistence.py:542 | `datetime.now())`（跨行调用续行） | 安全 | 同上 |
| test_session_persistence.py:594 | `life._write_merged({"last_heartbeat_at": self._stamp(datetime.now())})` | 安全 | ui.json 心跳戳，本机元数据 |
| test_session_persistence.py:642 | `past = datetime.now() - timedelta(hours=2)` | 安全 | 生命周期 prefs 戳 |
| test_session_persistence.py:672 | `closed_a = datetime.now() - timedelta(hours=3)` | 安全 | 同上 |
| test_session_persistence.py:673 | `started_b = datetime.now() - timedelta(minutes=10)` | 安全 | 同上 |
| test_session_persistence.py:678 | `life = app.compute_lifecycle(prev, datetime.now())` | 安全 | 同上 |
| test_session_persistence.py:687 | `started = datetime.now() - timedelta(minutes=5)` | 安全 | 同上 |
| test_session_persistence.py:691 | `datetime.now())`（跨行调用续行） | 安全 | 同上 |
| test_session_persistence.py:698 | `at = datetime.now() - timedelta(minutes=1)` | 安全 | 同上 |
| test_session_persistence.py:702 | `clean = app.compute_lifecycle(dict(base, run_open=False), datetime.now())` | 安全 | 同上 |
| test_session_persistence.py:704 | `crash = app.compute_lifecycle(dict(base, run_open=True), datetime.now())` | 安全 | 同上 |
| test_session_persistence.py:710 | `prev = {"last_closed_at": self._stamp(datetime.now() - timedelta(hours=3)), ...` | 安全 | 同上 |
| test_session_persistence.py:711 | `"last_started_at": self._stamp(datetime.now() - timedelta(minutes=10)),` | 安全 | 同上 |
| test_session_persistence.py:712 | `"last_heartbeat_at": self._stamp(datetime.now() - timedelta(minutes=11))}` | 安全 | 同上 |
| test_session_persistence.py:713 | `life = app.compute_lifecycle(prev, datetime.now())` | 安全 | 同上 |
| test_session_persistence.py:732 | `self._stamp(datetime.now() + timedelta(hours=1))`（未来心跳） | 安全 | 回拨场景，两端同钟 |
| test_session_persistence.py:769 | `old_saved = datetime.now() - timedelta(hours=12)` | 安全 | 锚点用例；779 行 `saved.timestamp()` 由同一 naive 值生成，自洽 |
| test_session_persistence.py:797 | `new_saved = datetime.now() - timedelta(minutes=1)` | 安全 | 同上 |
| test_session_persistence.py:822 | `app.compute_lifecycle({"last_closed_at": self._stamp(datetime.now() - timedelta(hours=10))}, ...` | 安全 | 关机间隔时长，同钟 |
| test_session_persistence.py:823 | `datetime.now())`（跨行调用续行） | 安全 | 同上 |
| test_session_persistence.py:839 | `saved = datetime.now() - timedelta(hours=10)` | 安全 | 锚点用例，同 769 |
| test_session_persistence.py:858 | `stale = datetime.now() - timedelta(hours=25)` | 安全 | 过期样例；hours_left 恒 None，不参与推算 |
| test_session_persistence.py:1274 | `now = datetime.now()` | 安全 | 旧格式生命周期 prefs 造数（1277-1279 行），同钟写读 |
| test_runtime_bundle.py:524 | `deadline = time.time() + 5` | 安全 | 子进程等待超时阈值 |
| test_runtime_bundle.py:526 | `while proc.poll() is None and time.time() < deadline:` | 安全 | 同上 |
| test_signup_plan.py:608 | `budget = time.time() + 10` | 安全 | 超时预算 |
| test_signup_plan.py:609 | `while time.time() < budget and (not api._plan_procs ...` | 安全 | 同上 |
| test_signup_plan.py:632 | `t0 = time.time()` | 安全 | 计时起点 |
| test_signup_plan.py:636 | `while proc.poll() is None and time.time() - t0 < 2.0:` | 安全 | 相对超时 |
| test_signup_plan.py:638 | `elapsed = time.time() - t0` | 安全 | 相对时长 |
| test_signup_plan.py:647 | `budget = time.time() + 3` | 安全 | 超时预算 |
| test_signup_plan.py:648 | `while time.time() < budget and self._pid_alive(grandchild_pid):` | 安全 | 同上 |
| test_signup_plan.py:670 | `budget = time.time() + 10` | 安全 | 超时预算 |
| test_signup_plan.py:671 | `while time.time() < budget and not any(...)` | 安全 | 同上 |
| test_signup_plan.py:1000 | `budget = time.time() + 5` | 安全 | 超时预算 |
| test_signup_plan.py:1001 | `while time.time() < budget and not launches:` | 安全 | 同上 |
| test_ui_contract.py:248 | `fresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")` | 安全 | 会话 fixture 文本；消费方不据 saved_at 判失效（267 行注释） |
| test_ui_contract.py:263 | `stale = (datetime.now() - timedelta(hours=25)).strftime(...)` | 安全 | 同上 |
| fixtures/business_clock.py:155 | `语义刻意保持简单：now 就是本机 time.time()，bounds 零误差，` | 安全（注释） | docstring |
| fixtures/business_clock.py:169 | `return time.time()` | 安全 | TestWallClock 显式注入的测试墙钟，152-157 行声明「不冒充北京时间」，使用方只做相对时长/同钟比较 |

#### server/tests（4 处：安全 3，风险 1）

| 文件:行号 | 关键代码 | 判定 | 依据 |
|---|---|---|---|
| test_dedup.py:138 | `print(f"[i] 已还原 state.json（{datetime.now():%H:%M:%S}）")` | 安全 | 仅控制台打印；该文件按纪律不运行 |
| test_login_resilience.py:132 | `base = base or datetime.now()` | 安全 | probe log 是本机运维元数据；生产写入（deploy/auto_login.py:132）与消费（:507,:540）同为 datetime.now()，写读同源自洽 |
| test_login_resilience.py:159 | `self._write(["fail"], base=datetime.now() - timedelta(hours=2))` | 安全 | 同上（陈旧阈值 3600s，两端同钟） |
| test_watchlist_safety.py:164 | `return (datetime.now() + timedelta(seconds=seconds)).strftime(wl.FMT)` | **风险** | `_soon()` 用本机 naive 时间造 watchlist `open_at`（学校格式/语义为北京时间）；被测 wl/runner 恰也用 datetime.now()（scripts/watchlist.py:44,126、watchlist_runner.py:137），测试闭环自洽不会误报，但按「本机时间造学校时间字段」口径命中，跨时区语义错位；生产侧同源问题见下 Top-4 |

### 非 tests 范围（90 处）计数与分布【已复现】

严格口径（`--exclude-dir=tests`）：local 35（grab.py 12、app.py 10、gui.py 4、time_contract.py 3、infrastructure/phone_session_store 2、infrastructure/lifecycle_store 2、signup_plan.py 1、business_clock.py 1）；server 55（deploy/auto_login.py 11、scripts/selfcheck.py 7、scripts/run.py 7、deploy/grab_signup.py 5、scripts/activity_watch.py 4、scripts/notify.py 3、scripts/grab_card.py 3、scripts/watchlist.py 2、scripts/token_probe.py 2、scripts/login.py 2，另 9 个文件各 1：watchlist_runner / trigger_server / token_report / remind / regress / query / net_probe / dev-push_card / common）。

排除的「看着像但不是」：scripts/common.py:140 是**注释**（正是在讲为什么不能用 datetime.now() 分类、Asia/Shanghai 会错位几小时）；time_contract.py 3 处是「墙钟仅诊断」的快照字段（决策 012 设计内）；business_clock.py:859 是 os_offset_s 诊断值；grab.py:504/:528 的 `time.time()*1000` 是签名协议 epoch 毫秒（无时区语义）。

**风险最可疑 Top 4（文件:行号）**【静态推断】（原 Top 5；#5 经对抗审阅 2026-11-08 改判安全/低风险并移出名单，4 对 1 改判）：

1. server/scripts/watchlist.py:126 — `if datetime.now() > start + timedelta(seconds=float(window)):` 本机 naive now 与学校字段 start 比较判过期（:44 的 `now()` 同源）
2. server/scripts/watchlist_runner.py:137 — `now = datetime.now()`，runner 用本机 now 判 started/missed 窗口
3. server/scripts/remind.py:40 — `now = datetime.now(); today = now.date()`，用本机日界挑「今天」活动（`start.date() == today`），跨时区日界错位
4. server/scripts/query.py:115 — `now = datetime.now()` 传给 classify/mine_items，按本机 now 对学校字段分类

（原 #5 server/scripts/run.py:62-63 改判安全/低风险：`today` / 120 天 cutoff 只作用于 `announced`，该集合仅由 `_mark_announced` 自写自读（:73 保留裁剪、:256 `is_new` 成员判断），同钟写读、不与学校日期比较，按本报告「同钟写读=安全」口径不构成风险。）

（备选：server/scripts/grab_card.py:64,:108 卡片构造 `now = now or datetime.now()`，同样拿本机 now 对学校字段取舍。）

## ③ 本机全量 unittest【已复现】

- 命令：`python -X utf8 -m unittest discover -s local/tests -p "test_*.py" -v`（仓库根；加 `-v` 为捕获逐个 skipped 原因）；2026-11-07 执行，耗时 134.055s，退出码 **1**。日志：`<过程留证>/l7-unittest.log`（末行 `EXIT=1`）。
- 结果：**Ran 1911 tests，FAILED (failures=1, skipped=4)** → 通过（ok）= 1911 − 1 − 4 = **1906**。任务书「约 1700 例」已过时：共享树含他人未提交的新测试文件（test_cancel_signup.py、test_list_signed.py、test_phone_conflict.py、test_ui_conflict_cancel.py）。
- 对抗审阅复跑完全复现（2026-11-08）：`Ran 1911 tests in 135.527s`、`FAILED (failures=1, skipped=4)`、`EXIT=1`（<过程留证>/l7-rerun.log，2588 行）；skip 4 与失败 1 逐条一致。
- skipped 4 个（与任务书一致）：
  1. test_lifecycle_release.RealGitFixtureTests.test_annotated_tag_peeled_resolved_from_real_git — skipped：真实 Git fixture（临时仓库 init/commit/tag/push/ls-remote）需单独授权：确认后设 `CAMPUS_GIT_FIXTURE_AUTH=1` 再运行；本轮只定义不执行
  2. test_lifecycle_release.RealGitFixtureTests.test_lightweight_tag_resolved_from_real_git — 同上
  3. test_lifecycle_release.RealGitFixtureTests.test_missing_tag_is_empty_from_real_git — 同上
  4. test_signup_signing.NativeFailureTests.test_non_windows_raises_signer_unavailable — skipped：本机即 Windows，非 Windows 分支无从触发
- **失败 1 个（非 skip，如实上报）**：`test_phone_ui.LayoutStaticTests.test_mobile_layout_statics`（断言在 local/tests/test_phone_ui.py:2210）— `assertNotIn("display: grid", css, "单栏布局不引入多列网格")` 失败：工作区未提交的 conflict-cancel 改动给 `local/ui/m/styles.css` 新增了 `.why-r { display: grid; ... }`（今日复核在 styles.css:180）。该文件在素材记录当时的 24 个他人改动文件之列，今日 `git status` 仍显示 `M local/ui/m/styles.css`；按共享工作区纪律只记录，不回滚、不修改。

## 补丁判定专节：L7 可出补丁 = 0 条（2026-11-08 对抗审阅重写）

- **候选唯一一处**：local/tests/test_component_builder.py:25（一行 2 个字面量）。它是**被测的非法输入样本**（传入 `builder.output_root()` 断言 `assertRaises(ValueError)`），不是夹具路径。
- **机制复核（对抗审阅推翻原依据）**：实现 `output_root`（local/build/build_advanced.py:27-33）只拒绝三类输入——非绝对路径、root==temp、不在 temp 之下——**从不检查 `<>` 字符**。两个 `<tmp>` 字面量都经 `not is_absolute()` 分支抛 ValueError，与样本 `"relative"` 的拒绝分支重复、零独占覆盖；换成 `tempfile.gettempdir()` 后两样本分别经 root==temp、`not is_relative_to` 分支**仍抛 ValueError**，测试仍绿，且补上当前未覆盖的 root==temp 边界分支。原「改了会把非法输入变合法、断言崩坏」的机制主张不成立（原作者先前基于「`<>` 非法字符」直觉的复核不成立，如实记录）。
- **「不出补丁」结论维持，理由改写**：`<tmp>` 在该行是**被测输入样本**而非夹具路径；AGENTS.md「夹具里出现 `<tmp>` 字面量就是缺陷，改成 `tempfile.gettempdir()` 不算改测试路径凑绿」（用户 2026-11-06 定）规则的适用对象是**夹具路径**，对本处被测输入不适用——机械替换不属于该条豁免情形；而是否替换（补 root==temp 边界覆盖）已超出机械替换、属改测试语义，需用户定，见 DEFERRED-L7-1。
- **其余 4 处**（test_retry_policy.py:5、test_updater.py:51、server/tests/test_activity_watch.py:4、server/tests/test_runtime_safety.py:8）均为 docstring/注释，不执行，不构成「会执行的夹具」缺陷。
- **DEFERRED-L7-1（改写，待人定）**：
  - 问题：该行两个 `<tmp>` 字面量是否要替换为 `tempfile.gettempdir()` 以补边界覆盖——机械上可行（替换后两样本仍分别经 root==temp、not is_relative_to 分支抛 ValueError，测试仍绿），但属改测试语义而非机械卫生替换。
  - 倾向：不出补丁但替换可行且测试仍绿，是否补覆盖需用户定。
  - 待人定：若用户裁定要补覆盖，按 `gettempdir()` 与 `gettempdir()+"/../elsewhere"` 替换两个字面量（保留 `"relative"`、`"<样例盘符路径>"` 样本），可补 root==temp 与 not is_relative_to 两个边界分支；若裁定不改，本条关闭。

## 抽查复核（2026-11-08，搬运后由主流程执行）

1. `grep -rn '<tmp>' local/tests server/tests` → 5 行，逐行与判定表 #1-#6 的原文一致；`grep -o '<tmp>' … | wc -l` = 6。【已复现】
2. `grep -rn -E 'time\.time\(\)|datetime\.now\(\)' local/tests server/tests | wc -l` = 94。【已复现】
3. 同式 `--include='*.py'` 对 local、server → 184；加 `--exclude-dir=tests` → 90（local 35、server 55）。【已复现】
4. `sed -n '334p;438p' local/tests/test_session_persistence.py` 与 `sed -n '164p' server/tests/test_watchlist_safety.py` → :334 与 :164 逐字一致；:438 引文含 `...` 缩写，为截引（片段逐字）。【已复现；2026-11-08 修订措辞】
5. `sed -n '22,28p' local/tests/test_component_builder.py` → 确认 ：25 字面量处于 `assertRaises(ValueError)` 循环体内（被测非法输入）。【已复现】
6. `grep -o '<button' local/ui/index.html | wc -l` = 110、m/index.html = 19（供 L8 报告交叉验证，见 a11y-names.md）。【已复现】
7. 全量日志：第 2542 行 `Ran 1911 tests in 134.055s`、第 2544 行 `FAILED (failures=1, skipped=4)`、第 2588 行 `EXIT=1`；skip 原因逐条与上文 4 项一致（日志 522/524/526/1482 行）；失败断言文本见日志 2538-2539 行。【已复现】
8. `grep -n 'def test_mobile_layout_statics' local/tests/test_phone_ui.py` → :2202，断言在 :2210。【已复现】
9. `git status --porcelain` 含 `M local/ui/m/styles.css`；`grep -n 'why-r' local/ui/m/styles.css` → :180 `.why-r { display: grid; … }`。【已复现】

## 修订记录（对抗审阅 2026-11-08）

对抗审阅合并与定档见同目录 ADVERSARIAL-L7.md（A 实质反证 + B 机械核验；B 为 L7 原分析者，只承担机械项，实质判定由未参与 L7 的审阅者承担）。修订各项（前 → 后）：

1. 补丁判定节与判定表 #1/#2 依据列：机制依据「改 gettempdir() 会变合法输入、assertRaises(ValueError) 崩坏」→ 推翻改写（output_root 只拒「非绝对 / root==temp / 不在 temp 下」三类、从不查 `<>` 字符；替换后两样本仍抛 ValueError、测试仍绿且补边界覆盖）；「L7 可出补丁 = 0」结论维持，理由改写为「被测输入样本、夹具规则适用对象不适用」；DEFERRED-L7-1 由「口径确认」改为「是否补 root==temp 边界覆盖需用户定」。
2. ② 计数节成因：「grep -v '/tests/' 滤不掉 local/tests 的命中（server/tests 能被过滤掉）」→「正斜杠模式滤 0 行，local 与 server 皆滤不掉；`\tests\` 反斜杠固定串才可滤，滤后 90」。94/184/90 数字不变。
3. 非 tests server 分布：「另 10 个文件各 1」→「另 9 个文件各 1」（实列 9 名；总和 55 = 46+9 校准）。
4. Top-5 → Top-4：原 #5 run.py:62-63 改判安全/低风险（announced 仅自写自读：:73 保留裁剪、:256 成员判断，同钟无学校日期比较），4 对 1 改判。
5. :334 依据措辞：「跨时区机器错位」→「x<17 时区恒绿、标签仍对，仅在特定时区窗口错位」；:334/:438 风险标签维持。
6. 判定表 4 处折行引文（:517/:542/:691/:823）：`..., datetime.now())` → `datetime.now())`（跨行调用续行）；抽查复核 #4「逐字一致」→「:334/:164 逐字、:438 含缩写为截引」。
7. ③ 全量段补「对抗审阅复跑完全复现（Ran 1911, failures=1, skipped=4, EXIT=1）」。
8. 红牌 4 张（server/tests 过滤表述、10→9 计数、补丁机制依据、Top-5 #5 双重标准）处置与逐条判定（总 14 条：站得住 8、部分站不住 3、推翻 2、机械层轻微瑕疵 1）见 ADVERSARIAL-L7.md；除上述外，判定标签均不变。
