# 对抗审计：补充轮材料

- **执行模型**：WorkBuddy，底层模型 DeepSeek-V4.1-Flash
- **基线**：`7e2d31c`（`git archive` 导出副本；补充轮自述「`state-trace.md`/`ui-states.md` 在基线里不存在，A 任务实际读了工作区」，这两份我按工作区当前内容核对，其余按基线代码核对）
- **被审文件**：`supplement/README.md`、`desktop-recheck.md`、`phone.md`、`grab-protocol.md`、`refactor-prereq.md`，以及 `supplement/scripts/` 两个脚本的产物口径
- **方法**：同第一轮——先自己列，再比对；`grab.py` 的输出与退出码用 `ast` 与全文 grep 重算；`esc` 用法逐处看生成出来的 HTML 到底是什么引号；每条意见给被审材料与基线代码两处行号
- **严重度**：阻断 / 重要 / 次要，定义同第一轮

## 结论

| 严重度 | 条数 | 编号 |
|---|---|---|
| 阻断 | 3 | B1–B3 |
| 重要 | 10 | C1–C10 |
| 次要 | 6 | D1–D6 |

补充轮把第一轮的三条推测（U6/U11/U12）落地得很扎实：U6 的调用链、U11 的事件链、U12 的 `api()` 无 timeout，我按基线重走一遍全部成立（见第五节抽查）。问题集中在两处：**S1（`esc` 单引号）整条是误判**，**S2（`save_retry_policy` 死路径）与 `grab-protocol` 的 `list` 退出码 1 是凭印象写的**；另外 `phone.md` 是未完成的草稿。

---

## 一、阻断

### B1　S1「`esc` 有 30+ 处单引号属性注入风险」整条不成立：HTML 属性全是双引号

**原文说什么**：`supplement/README.md:52` 把 S1 记为「esc() 约 30+ 处用在 HTML 属性值里、被单引号包裹，但 esc 不转义单引号」；`refactor-prereq.md:341-355` 用一张表给 `state/filters.js` 判「中」、`views/conflict-tip.js` 判「中」、`views/list.js` 判「**高**」、`views/plan-panel.js` 判「中高」，结论是「这些属性普遍用单引号包裹（共约 30+ 处）……就可以闭合属性注入」，并把「esc 补上单引号转义」列为重构前置动作。

**代码实际是什么**：被举的四处，生成出来的 HTML 属性**都是双引号**，源码里的单引号只是 JS 字符串定界符：

| 位置 | 源码 | 生成的 HTML |
|---|---|---|
| `local/ui/views/list.js:190` | `"<div class=\"" + … + "\" data-id=\"" + esc(id) + "\" aria-label=\"" + esc(item.name) + "\">"` | `data-id="…" aria-label="…"` |
| `local/ui/state/filters.js:86` | `'<span class="rw" title="' + esc(rw.title) + '">'` | `title="…"` |
| `local/ui/views/plan-panel.js:215` | `' title="' + esc("完整地点：" + placeText + "（Enter 展开/收起）") + '">'` | `title="…"` |
| `local/ui/views/conflict-tip.js:10` | `'<div class="tl" role="img" aria-label="' + esc(model.aria) + '">'` | `aria-label="…"` |

`esc`（`local/ui/state/time.js:123-125`）转义 `& < > "` 四个字符，双引号属性已被覆盖。要构造单引号闭合，得先有单引号定界的属性——全仓 `grep -rn "='" local/ui/` 只命中一处 `local/ui/app.js:237` 的 CSS 选择器 `[data-act='cx-go']`，**没有一处生成 HTML 属性**；转义形式 `=\'` 零命中。

**文件:行号**：被审材料 `supplement/README.md:52`、`refactor-prereq.md:335-359`（表 343-353、结论 355-359）；代码 `local/ui/views/list.js:190-194`、`local/ui/state/filters.js:86,89`、`local/ui/views/plan-panel.js:215,479,483`、`local/ui/views/conflict-tip.js:10`、`local/ui/state/time.js:123-125`、`local/ui/app.js:237`

**类别**：R1 事实错（把 JS 字符串定界符当成 HTML 属性定界符）+ R3 判断站不住（风险等级全部要撤）

**影响**：这是补充轮最大的假阳性。按它排，步骤 0 之前会先做一次「esc 补单引号」的改动，理由是防注入；实际没有这个注入面。第一轮 R10 本来把它标成「推测，没有逐处检查」，补充轮的任务就是把它查清，结果查反了。`supplement/README.md:106` 的提交分组第 5 条「`fix(ui): esc 补单引号`」应当撤销；`refactor-prereq.md` 第三节应整节改写为「115 处调用，属性均为双引号，`esc` 已转义 `"`，无属性闭合风险；唯一残留是文本节点里 `&<>"` 之外的字符无需转义」。

### B2　S2「`save_retry_policy` 是死路径」不成立：它在手机服务里被特判

**原文说什么**：`supplement/README.md:53`：「ACTION_PARAMS 白名单有 `save_retry_policy` 但 Api 无同名公开方法，手机调这个 key 会得 `not_available`」；`refactor-prereq.md:450`、`456` 重复同一结论，并建议「拆分时要么实现要么从白名单删掉」。

**代码实际是什么**：`local/application/phone_service.py:428-431` 在 `getattr` 之前就把这个 key 拦下并改写成 `save_prefs`：

```python
if name == "save_retry_policy":
    # 手机只许改重试策略：terms/路径/任意键一律不进偏好
    return self._call("save_prefs",
                      {"prefs": {"retry_policy": clean.get("retry_policy", {})}})
```

它**不是**靠 `getattr(self._api, "save_retry_policy")` 找方法，所以「Api 上没有同名方法」是对的，但结论反了。`local/tests/test_phone_service.py:492-502` 的 `test_save_retry_policy_only_allows_policy_keys` 正在守这条路径：合法键通过、夹带 `terms_version` 被 `args_not_allowed` 拒。

**文件:行号**：被审材料 `supplement/README.md:53`、`refactor-prereq.md:450,456`；代码 `local/application/phone_service.py:428-431`、`local/domain/phone_rules.py:163`、`local/tests/test_phone_service.py:492-502`

**类别**：R1 事实错（引用的代码不是那个意思）

**影响**：若按「从白名单删掉」执行，手机端改重试策略会直接变成 `action_not_allowed`，功能回退；若按「实现一个同名方法」执行，则与 `save_prefs` 的受限入口重复，等于放开 `terms`/路径键。两条都不能做。S2 应整条删除。

### B3　`grab-protocol.md` 给 `list` 编了一个不存在的退出码 1

**原文说什么**：`grab-protocol.md:100` 的退出码表：「**list** | 1 | 未来活动筛选时（非错误，只是 CLI 交互提示） | L1408, L1410, L1412, L1619, L1621」。

**代码实际是什么**：`cmd_list` 的函数体是 `local/grab.py:1333-1475`，其中的 `return` 只有：

- `2`：`1361`（登录失效）、`1373`（PermissionError）、`1376`（拉取异常）；
- `0`：`1419`（空列表非 JSON）、`1422`（空列表 JSON）、`1467`（JSON 输出）、`1475`（文本输出）。

**没有 `return 1`**。被引的 `1408`、`1410`、`1412` 是 `cmd_list` 内部嵌套函数 `rank(a)` 的返回值（`1407` `if a["signed"]: return 2`、`1409` `if filter_now is None: return 1`、`1411-1412` `return 0 if … else 1`）——它们是**排序档位**，不是退出码。`1619`、`1621` 同理，是 `candidates()` 里另一个 `rank()` 的返回值（`candidates` 定义在 `1612` 一带）。

**文件:行号**：被审材料 `grab-protocol.md:99-101`；代码 `local/grab.py:1333-1475`（`return` 分布）、`1404-1412`（`rank`）、`1612-1622`（`candidates` 的 `rank`）

**类别**：R1 事实错（行号对不上，引用的不是那个意思）

**影响**：步骤 3 的核心是「同样输入得到同样 stdout 行和退出码」的对照测试（`code-issues.md:451`）。照这张表写，`list` 的用例会断言一个永远不会出现的 `1`，红一次之后要么改测试、要么「修」`grab.py` 让它返回 1——后者会改掉 CLI 契约。这张表在写 T-1/T-6 之前必须修正。

---

## 二、重要

### C1　U17「三端 stop_reason 映射差距大」站不住：后端对 7 种原因全量下发 `outcome_label`，两端都在用

**原文说什么**：`supplement/README.md:43` 与 `phone.md:331-341`：后端 7 种、桌面只覆盖 3 种、手机只覆盖 2 种，「closed/conflict/… 在桌面/手机上都会退化成『报名未成功』」，并据此建议一条修复提交（`supplement/README.md:104`）。

**代码实际是什么**：

1. `local/domain/retry_rules.py:110-115`：`stop_reason_label()` 有值就写进 `payload["outcome_label"]`；`test_signup_reply.py:72-79` 守着「只给新原因加、旧终态不加」。
2. `local/domain/plan_rules.py:179-228`：单场终态的每一条分支都用 `retry_payload(...)`，所以 7 种原因的 `outcome_label` 都会随计划事件下发。
3. 桌面：`local/ui/views/plan-panel.js:1153` 是 `String(task.outcome_label || "") || stopReasonText(task.stop_reason)`——优先用后端 label；即使没有，`stopReasonText`（`1058-1078`）也把 7 种全映射了。
4. 手机：`local/ui/m/app.js:423` 是 `"报名未成功" + (t.outcome_label ? "：" + t.outcome_label : …)`——同样优先用 label。

所以「closed/conflict/no_activity/clock_skew/unknown_reply/page_unavailable 退化成一句没原因的话」不成立。真正的差异只有两处：

- `auth_unavailable`（不在 `STOP_REASON_LABELS` 里，没有 `outcome_label`）：桌面 `task-display.js:63` 给「未提交」，手机没有分支，落到「报名未成功」；
- 任务卡的**短标签**（`taskDisplayLabel`）只对 full/unconfirmed/auth_unavailable 特判，其余用通用标签——这是标签设计，不是映射缺失。

**文件:行号**：被审材料 `supplement/README.md:43,104`、`phone.md:237-255,331-341`；代码 `local/domain/retry_rules.py:110-115`、`local/domain/plan_rules.py:179-228`、`local/ui/views/plan-panel.js:1058-1078,1153`、`local/ui/m/app.js:423`、`local/ui/state/task-display.js:62-65`

**类别**：R3 判断站不住 + R1（只看了标签函数，没看兜底映射与 `outcome_label` 的下发）

**影响**：`supplement/README.md:104` 的提交第 2 条「`fix(signup): stop_reason 三端覆盖补全`」应缩成「手机补 `auth_unavailable` 一句」，严重度从「中」降到「低」。按原结论做，会在三个文件里加一堆永远走不到的分支，还会让人以为显示正确性依赖「后端记得填 outcome_label」——实际已经由 `retry_payload` 统一保证。

### C2　U15 的严重度在四处互相矛盾，且「永久锁死」不可达

**原文说什么**：

- `phone.md:303`：「严重度：🔴 高」；
- `phone.md:171`：「这是一个潜在的永久锁死缺陷。严重度高。」；
- 同一节 `phone.md:313`：「实际风险评估：中等偏低——api/postAction 两层都 try-catch 了，throw 几乎不可能漏出」；
- `supplement/README.md:41`：「低 | 否（代码对比）」。

**代码实际是什么**：`beginRelogin`（`local/ui/m/app.js:3061-3100`）确实没有 `try…finally`，`model.reloginStarting = false` 在 `await` 之后（`3091-3092`）；但 `postAction`（`2316-2325`）把 `api` 整个包在 `try/catch` 里、失败返回同形对象，`api`（`2275-2311`）只有 `finally` 没有 `catch`，异常只会落到 `postAction` 的 catch。也就是说，`await postAction(...)` 在正常实现下不会抛，`reloginStarting` 不会被永久置真。这和 `pair`（`2396-2428` 用 `finally`）的差别是**写法不统一**，不是「永久锁死」。

**文件:行号**：被审材料 `phone.md:167-171,300-313`、`supplement/README.md:41`；代码 `local/ui/m/app.js:3061-3100,2316-2325,2275-2311,2396-2428`

**类别**：R4 自相矛盾（同一缺陷 高/中低/低 三说）+ R3（结论超出证据）

**影响**：U15 与 U20 说的是同一件事（散落的手动清锁），一个判「高」一个判「低」。按「高」排，会挤进先修队列；按「低」排，只值一次写法统一。建议合并成一条「低」：`beginRelogin` 改成 `try…finally`，与 `pair` 对齐，不改行为。

### C3　对第一轮的改动表只记了 13 行，实际改了 26 行，且其中一条记录的目标值与文件不符

**原文说什么**：`supplement/README.md:11-33` 的「对第一轮的改动表」列了 13 行（12 行实改 + 1 行「未改」），表下写「共改 `state-trace.md` 14 处、`ui-states.md` 4 处，都在允许范围内」。

**实际是什么**：`desktop-recheck.md:261-292` 的附录「state-trace.md 最终修改清单」自己列了 **26 行**（L28、L54、L72、L79、L82、L88、L90、L91、L113、L117、L129、L137、L141、L142、L146、L166、L184、L185、L205、L237、L244、L245、L292、L303、L345、L347），且当前 `state-trace.md` 里「子」标记已为 0——说明这 26 行都动过。汇总表漏了 14 行（约一半），「共改 14 处」与它自己的 13 行、附录的 26 行三个数互不相同。

同一张表还有一条方向错的记录：`supplement/README.md:31` 说 `ui-states.md` 的合计句被改成「高 1 / 中 5 / 低 8」，而文件实际是 `ui-states.md:30`「高 1，中 4（U6 降级），低 9」——文件是对的（14 条里 U2/U3/U4/U5 为「中」、其余 9 条为「低」），改动表的目标值写错了。

**文件:行号**：被审材料 `supplement/README.md:11-33`、`desktop-recheck.md:261-292`、`ui-states.md:30`；代码侧无需代码，纯文档对账

**类别**：R4 自相矛盾（改动表与改动清单、与实际文件三处不一致）

**影响**：本计划给 review-supplement 的验收判据就是「补充轮改第一轮的每一处都核对过改动表」。现在改动表不是全量，无法据它确认「都在允许范围内」——26 行里哪几行是改内容、哪几行只是改来源标记，只能去读附录和正文反推。建议把 `desktop-recheck.md` 的附录直接并进 `supplement/README.md` 的表，并把「14 处」改成实数。

### C4　`phone.md` 是未完成的草稿：第 7 类进行中状态没有表，正文留着「让我看完整代码」

**原文说什么**：`phone.md:72` 的标题是「7 类进行中状态 × 八条退出路径」；`supplement/README.md:73` 把它的内容记为「55 字段完整追踪、7 类进行中 × 八条退出路径」。

**实际是什么**：七类里前六类（flying、pairing、pending、reconciling、cancelingStart、reloginStarting）有表，**第七类 `reloginSubmitting` 没有表**，只有一句「让我看 submitRelogin 完整代码」（`phone.md:181`）。同一节还留着三处未收敛的思考过程：

- `phone.md:154`：「L3092 `finally: model.reloginStarting = false`？让我看完整代码」；
- `phone.md:161`：「让我确认 beginRelogin 的 finally 是否存在」；
- `phone.md:138`：「等一下——让我看：L2757 是在 `try {` 内的……好的，所有 return 都在 try/finally 包裹里」；
- `phone.md:183`：「另外还有 7 类进行中状态之外的 challenge……在某些 ingestRelogin 分支可能被遗漏」——没有结论。

我按基线把 `submitRelogin`（`local/ui/m/app.js:3113-3157`）读完：置真在 `3123`，正常失败在 `3148` 清，网络异常与 `duplicate_submit` 是**故意不清**（注释写明「结果未知……等快照给结论」），由 `ingestRelogin` 的终态分支收。也就是说这一类没有漏，但没有写进交付物。

**文件:行号**：被审材料 `phone.md:72-183`；代码 `local/ui/m/app.js:3113-3157`

**类别**：R2 漏项（交付物不完整）+ 未标「推测/草稿」

**影响**：B 任务的验收判据是「model 的可变字段逐个列，不按功能挑」——55 字段那部分做到了；但「7 类进行中 × 八条退出路径」的承诺只兑现了 6/7，且正文夹着草稿句，读者无法判断哪些结论已经落地。若后续计划引用 `phone.md` 的「无遗漏」结论，会以为七类都查过。

### C5　`stop_reason` 的计数 16/4/12 与实际 17/5/12 不符

**原文说什么**：`grab-protocol.md:344`「stop_reason → exit code 组合 | 16 种」、`:281`「terminal() 全部 16 个 stop_reason」、`:254`「现有 fake worker 只发 success / max_attempts / retry_duration / login_invalid 四种……其余 12 种（already_signed / auth_unavailable / clock_unavailable / unconfirmed / sign_end / process_error / full / closed / conflict / no_activity / clock_skew / unknown_reply / page_unavailable）」。

**代码实际是什么**：

- `terminal()`（`local/grab.py:2553-2646`）处理 **17** 个值：`success`、`already_signed`、`login_invalid`、`auth_unavailable`、`max_attempts`、`unconfirmed`、`clock_unavailable`、`REPLY_STOP_HINTS` 的 7 个键（`full/closed/conflict/no_activity/clock_skew/unknown_reply/page_unavailable`）、`process_error`，以及兜底的 `sign_end`/`retry_duration`。文档自己的 2.3 表也列了 17 行。
- fake worker 覆盖 **5** 种：`local/tests/test_retry_policy.py` 里 `stop_reason=` 的取值有 `success`、`already_signed`、`login_invalid`、`max_attempts`、`retry_duration`——`already_signed` 是有的。

所以正确的一组是 **17 总 / 5 已覆盖 / 12 未覆盖**。文档写的「12」碰巧对，但「16」和「4」各错一位，且 `:254` 的清单把已覆盖的 `already_signed` 又列进「未覆盖」的 13 项里。

**文件:行号**：被审材料 `grab-protocol.md:238,254,281,344`；代码 `local/grab.py:2553-2646,2491-2499`、`local/tests/test_retry_policy.py`（`stop_reason=` 取值）

**类别**：R1 数字算错

**影响**：T-1 的写法是「terminal() 全部 16 个 stop_reason → exit code + done 行」。按 16 写，会少一条用例；按清单里的 13 项「未覆盖」补，会重复补 `already_signed`。

### C6　`refactor-prereq.md` 的缺口统计 22/5/17 与自己的表 17 行对不上

**原文说什么**：`refactor-prereq.md:33`：「22 条要补，现有覆盖能部分沾到边的 5 条（U1 修改中、U2 后台刷新、计划结束刷新、步骤 1B 事件竞态、步骤 3 对照），完全缺的 17 条。」

**实际是什么**：第一节的表一共 **17 行**（U1 三行、U2/U3 四行、U4 一行、U7 一行、U9 一行、1A 三行、1B 两行、步骤 2 一行、步骤 3 一行）。17 行里 5 行有部分覆盖、12 行全缺。22 = 5 + 17 这个算式只在「总数 22」成立时成立，而表里没有 22 行。

**文件:行号**：被审材料 `refactor-prereq.md:13-33`；无需代码

**类别**：R1 数字算错（小结与表不符）

**影响**：补测试的工作量按 22 条估会高估 5 条（约 29%）。建议改成「17 条要补，其中 5 条有部分覆盖、12 条全缺」。

### C7　块 1「更新」的公开方法表里混进了三个全局方法

**原文说什么**：`refactor-prereq.md:43-53` 的「块 1：更新」公开方法表列了 `check_update`、`update_download`、`update_cancel`、`update_launch`、`front_ready`、`bootstrap`、`help`。

**代码实际是什么**：`bootstrap`（`local/app.py:1149`）组装的是整份初始快照（登录、列表、计划、更新、条款、手机、偏好全在里面），`help`（`1245`）打开帮助，`front_ready`（`2052`）是界面就绪信号。三者都不属于更新，也不只更新在用。按这张表做步骤 2 的第一刀，会把三个全局方法搬进更新服务，`Api.bootstrap` 的组装职责随之被拆散。

**文件:行号**：被审材料 `refactor-prereq.md:43-53`；代码 `local/app.py:1149,1245,2052`

**类别**：R1（归类错，引用的方法不是那个意思）

**影响**：步骤 2 第一刀的范围会多出三个方法；`bootstrap` 一旦搬走，`app.X` 的测试补丁面（X1 的 42 个名字里有 6 个与 bootstrap 的组装有关）会跟着动。建议把这三个移到「其他：全局」一节。

### C8　`STOP_REASON_LABELS` 的行号写错，且对应的 spot check 仍打勾

**原文说什么**：`phone.md:237` 的 R4 表把后端映射表标成「`local/domain/signup_reply.py` **L86-93**」；`phone.md:396` 的 spot check 第 8 条「`signup_reply.py:86-93` STOP_REASON_LABELS 7 条全量 | ✅ 后端全集」。

**代码实际是什么**：`STOP_REASON_LABELS` 在 `local/domain/signup_reply.py:63-72`（`63` 是 `STOP_REASON_LABELS = {`，`72` 是 `}`）。`86-93` 是 `classify_reply` 的尾部——`if code_text == "1": return SignupReply("success", …)` 到 `return SignupReply("unknown", …)`，与映射表无关。

**文件:行号**：被审材料 `phone.md:237,396`；代码 `local/domain/signup_reply.py:63-72,86-93`

**类别**：R1 行号对不上 + 「标核对却没读到底」

**影响**：单看结论（7 条全量）是对的，行号错不影响结论；但这条 spot check 被记为「通过」，说明核对时没有真的定位到那段代码。同类 spot check 的可信度要打折。

### C9　spot check「test_update_check.py 有 84 个测试」实际 68 个

**原文说什么**：`refactor-prereq.md:487`：「第一节 test_update_check.py 方法数：grep 到 84 个 ✓」。

**实际是什么**：`local/tests/test_update_check.py` 里 `def test_` 共 **68** 个（`grep -c "def test_"` 与 `grep -c "def test"` 都是 68）。同文件 858 行。

**文件:行号**：被审材料 `refactor-prereq.md:487`；代码 `local/tests/test_update_check.py`

**类别**：R1 数字算错（标「✓」但未复算）

**影响**：这个数字本身不进任何结论，但它是一条「抽查通过」的记录。抽查记录是这套材料唯一的自证机制，出现两处（C8、C9）未真正核对的 ✅，其余 40 多条 spot check 的可信度需要按比例打折。

### C10　`esc` 的调用数 116 与第一轮/清单的 115 不一致，多算的是定义行

**原文说什么**：`refactor-prereq.md:339`：「脚本 `string_access.mjs` 精确计数：**12 个文件共 116 次调用**（原任务描述『115 次』差 1）」；`supplement/README.md:52` 也写 116。

**实际是什么**：`grep -o "esc(" local/ui/**` 共 116 次出现，其中 1 次是 `local/ui/state/time.js:124` 的 `function esc(value) {` 定义本身；**调用 115 次，分布在 11 个文件**（含定义的文件共 12 个）。`inventory.md:755` 与 `code-issues.md:100` 的 115 是对的。

**文件:行号**：被审材料 `refactor-prereq.md:339`、`supplement/README.md:52`；代码 `local/ui/state/time.js:124`、`inventory.md:755`

**类别**：R1 数字算错（把定义当调用）+ R4（与第一轮 115 冲突）

**影响**：数字差 1 不影响结论，但「12 个文件」也被带错（调用发生在 11 个文件）。与 B1 一起改时顺手改掉。

---

## 三、次要

### D1　同一份文件里 `ACTION_PARAMS` 一会儿 11 个 key、一会儿 12 个

`refactor-prereq.md:178` 写「白名单共 11 个 key」，`:195` 的注写「读到 11 个（不含 `save_retry_policy`——刚才 grep 输出里它可能被截断了）」，`:439` 又写「**12 个 key**」，`:458` 写「这 11 个方法」。实际 `local/domain/phone_rules.py:155-171` 是 12 个（含 `save_retry_policy`）。同一份交付物里 11/12 混用，读者无法判断哪个是结论。

### D2　块 3 把私有方法 `_stop_phone_access` 写成「`stop_phone_access()` 再定义一次？」

`refactor-prereq.md:150-155` 的表列了 `stop_phone_access()` 两次（4017、4024），第二行写「（再定义一次？）」。实际 `local/app.py:4024` 是 `def _stop_phone_access(self)`（私有实现），4017 是公开入口，不是重名。

### D3　「`cancel_start_request` 桌面端也调」不成立

`refactor-prereq.md:447` 写「（桌面端也调，但 grep 结果里没显式 `api("cancel_start_request")`）」。实际全前端只有手机页 `local/ui/m/app.js:2785` 通过 `postAction({action:"cancel_start_request", …})` 调它；桌面端零调用（`grep -rn "cancel_start_request" local/ui/` 只命中这一处）。这句话应删掉或改成「只有手机页调」。

### D4　`desktop-recheck.md` 的小结计数与自己的表不符

`desktop-recheck.md:69-75` 写「26 处子行：属实 18、有条件属实 2、推测转实/不成立 3、概念混淆 1」= 24。按表逐行数：属实 21、有条件属实 2、推测转实 1（L292）、概念混淆 1（L142）、结论「偏简化」1（L146）= 26；另 L82 的 U6 在第二节单列。建议改成「26 处：属实 21、有条件属实 2、偏简化 1、概念混淆 1、推测转实 1」。

### D5　§4.4/§4.5 的命令没跑通，结论按抽样写成事实

`refactor-prereq.md:462-465` 说 `git grep "window\["` 在 PowerShell 下转义失败、「从代码抽样」得出「没有用字符串键访问」；`:469-473` 同样。结论本身我复核成立：`grep -rn "window\[" local/ui/` 为 0，`eval(`/`new Function` 为 0，`setTimeout("` 为 0。但写法上是「命令失败 + 抽样 → 结论」，按本计划「推测要标」的要求，应写明「抽样核对，未全仓扫描」，或改用能跑通的命令重跑。

### D6　`grab-protocol.md` 的「改动文件清单」漏了同目录的 `scripts/grab_outputs.py` 来源说明

`grab-protocol.md:317-322` 说两个文件都是本轮新建，但 `supplement/README.md:113` 说 `grab_outputs.py` 是「上一轮 2026-11-11 下午遗留文件，本轮确认功能完整后直接用」。两处对同一文件的来源说法不同。不影响结论，但审计材料的「改动文件清单」应只列本轮实际新建/修改的文件。

---

## 四、改动表逐处核对（对第一轮文件）

以 `desktop-recheck.md:261-292` 的 26 行为准，逐行对照当前 `state-trace.md`：

| 范围 | 结论 |
|---|---|
| 第一节 L28、L54、L72、L79、L88、L90、L91 | 该节 12 行状态表与 4 张退出路径表里已无「子」标记；L82 的竞态段已改成「已核：没有竞态」 |
| 第二节 L113、L117、L129、L137、L141、L142、L146 | 已无「子」；L146 的四段比对已改为指向 `desktop-recheck.md` 第三节 |
| 第三节 L166、L184、L185 | 已无「子」 |
| 第四节 L205、L237、L244、L245 | 已无「子」；L237 保留「桥接本身挂住的情形是推测」——与 U12 的结论一致 |
| 第五节 L292、L303 | L292 已写事件链完整；L303 已无「子」 |
| 第六节 L345、L347 | 已无「子」 |
| `ui-states.md` U6/U11/U12 + 合计句 | 三行已按 `desktop-recheck.md:230-235` 改；合计句实际是「高 1 / 中 4 / 低 9」，与附录一致、与 `supplement/README.md:31` 的记录不一致（见 C3） |

26 行里没有发现「改了但完全没留痕迹」的；问题只是汇总表少记（C3）。

---

## 五、`grab-protocol.md` 的解析方复核（独立全仓搜）

按计划要求「grab-protocol.md 要独立全仓搜一遍 worker 输出的解析方再比对」。我不用它的 grep，而是按前缀在 `local/` 全仓搜：

| 输出前缀 | 我找到的解析方 | 与文档一致？ |
|---|---|---|
| `[checkpoint] ` | `local/domain/worker_lines.py`（`parse_checkpoint_line`）← `local/application/plan_service.py:25` | 一致 |
| `[clock] ` | `worker_lines.parse_clock_line` ← `plan_service` 不 import、`login_service.py:12` import | 一致（文档说「grab 子命令 plan_service 不解析」，成立） |
| `[retry] `（进度与 done） | `domain/retry_rules.parse_retry_line` ← `plan_service.py:20`；`app.py:4643` 的 `_parse_retry_line` 只给旧路径 | 一致 |
| `[i] 第 N 次提交` | `retry_rules.ATTEMPT_RE` ← `plan_service` | 一致 |
| `[timing] list ` | `local/app.py:2713` 从 stderr 取；`_stderr_note` 写入 | 一致（文档标了 ⚠️ stderr） |
| list 纯 JSON | `app.py:2702` `json.loads` | 一致 |
| cancel 纯 JSON | `app.py:2607` `_cancel_rules.normalize_worker_result` | 一致 |
| `[OK]/[X]/[!]/[?]/[i]/====/表头` | 无人解析（人话行） | 一致 |

补一条文档没列的：`local/app.py:4636` 的 `_attempts_of` 与 `4639` 的 `_retry_payload` 是**领域函数再导出**，不解析 stdout，但如果按「谁读 worker 输出」搜会误命中——文档的 grep 清单里有这两个名字，但没有说明它们是再导出而非解析方。属说明不足，不单列意见。

---

## 六、抽查记录

| 文件 | 抽了哪些 | 条数 | 对 | 错 |
|---|---|---|---|---|
| `supplement/README.md` | 改动表 13 行与附录 26 行、U15–U20 六条、S1–S3 三条、spot checks 52 条的说法、plan_amendments 5 条 | 12 | 9 | 3（U15 严重度、U17 结论、S1/S2；改动表记在 C3） |
| `desktop-recheck.md` | L28/L54/L72/L79/L82/L88/L90/L91/L113/L117/L129/L137/L141/L142/L146/L166/L184/L185/L205/L237/L244/L245/L292/L303/L345/L347 的结论与证据；U6 的 `login_relay_service.cancel` 锁内清 `_proc`；U11 的 `presentPlanDone` 首句；U12 的 `bridge.js api()`；第三节四段比对的 5 个选择器与条件 | 31 | 30 | 1（小结计数，D4） |
| `phone.md` | 55 字段表的 12 行（items/selected/busy/login/lastOkAt/flow/challenge/reloginSubmitting/reloginStarting/pending/plan/tickMark）；7 类进行中的 6 张表；R1/R8/R6/R4/R5/R9/R7 七条规则比对的行号；U15–U20 六条；12 条 spot check 的 4 条 | 29 | 25 | 4（U15 严重度 C2、reloginSubmitting 缺表 C4、STOP_REASON_LABELS 行号 C8、U17 C1） |
| `grab-protocol.md` | terminal() 17 个分支；`REPLY_STOP_HINTS` 7 键；`sys.exit` 唯一；8 处 `open` 写入；1 处 `os.environ`；cmd_grab 入口 4 个 return；cmd_list 全部 return；`[timing]` stderr；`_stdout_to_stderr` 两处；5 个环境变量；DATA_DIR 三个分支 | 24 | 20 | 4（list 退出码 B3、16/4/12 C5、`[i]` 与 `[retry]` 的解析方说明基本对） |
| `refactor-prereq.md` | 第一节 17 行；块 1–5 的方法行号各抽 3 个；块 3 的 ACTION_PARAMS 表；§3 的四处引号；§4.2 的 api 名单抽 8 个；§4.3 的 12 key；§4.4/4.5；10 条 spot check 的 4 条 | 27 | 17 | 10（S1 B1、S2 B2、11/12 D1、4024 D2、cancel_start_request D3、缺口统计 C6、块 1 方法 C7、84 vs 68 C9、esc 116 C10、§4.4 方法 D5） |

**未达到每份 20 条**：无（五份都过 20）。`supplement/scripts/` 两个脚本只做只读审阅（`grab_outputs.py` 的 87/1/1/8 四个数与我的独立计数一致），没有单独计入。

---

## 七、无法判定

1. `desktop-recheck.md` 说 A 任务因基线没有 `state-trace.md` 而读了工作区文件（`supplement/README.md:112`）。这意味着 A 的 26 行行号可能与工作区当时的版本对应，而不是基线；但 `state-trace.md` 是 untracked，无法用 git 复原。我按当前内容核对，结论自洽，行号偏差无法证伪。
2. `string_access.mjs` 的 `api_calls` 正则误匹配手机页 `/api/action`（`supplement/README.md:115`）——我未运行该脚本，只按源码抽读，无法确认误匹配是否影响了 §4.2 的名单。
3. `grab_outputs.py` 的「87 个输出调用」：我用 `grep -c` 粗算 `print(`/`log(`/`sys.stderr.write` 的总行数接近但不等于 87（口径含 `log()` 定义与注释），未逐处归类，无法判定 87 的准确性。
4. `refactor-prereq.md` 块 2/4/5 的「被测试改写的 Api 成员」次数是否与 `inventory.md` 第三节 C 逐项一致：抽了 12 个名字，全对；未逐项核对全部 66 个。
