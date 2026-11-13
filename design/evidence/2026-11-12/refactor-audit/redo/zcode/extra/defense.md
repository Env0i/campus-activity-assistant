# 攻防辩（extra/，2026-11-12，T0+5.2h 前后）

从 AA1（11 条）、AA2（7 条）、AA3（23 条）里挑最狠的 5 条（优先「结论相反＋高严重度」），逐条回给**被攻内容作者侧的原专家**（攻防辩复用了 T2/T3/T5/T10 的原会话，均为真实 SendMessage 调用，台账见 .claude/results/20261113-zcode-full/agents.md）。要求每条 200 字内答「我为什么仍认为成立 / 我承认这条错」。**以下作者回复逐字照录，未替写、未删改**；其中两条略超 200 字（LSP 索引工程师的两条），如实保留并在此标注。

## 1. AA3-21（阻断）→ mikado 作者（LSP 索引工程师）

挑战：你的 mikado.md 把 A1/A2/A3 列为无依赖叶子并放进「第一批可并行」；AA3 论证 A1/A2/A3 的完成判据只能由 C1..C5 产出物满足——C 依赖 A、A 的完成又依赖 C，按树执行第一批就死锁，唯一满足路径是先删光 70 处补丁（先废测试覆盖）。

作者答（两条都回基线核过再答：plan.js:103-106 原文、noteSignedTasks 定义在 controllers/refresh.js:398）：

> **【1·AA3-21 阻断】「我承认这条错」。** A1/A2/A3 的完成判据（指向新路径、替身端口、夹具收块服务）都是拆分终态，写成无依赖叶子放进第一批必死锁。修正：A 不删，降级为随块迁移的对账清单——每个提交成对落地「抽 C_i＋迁移 i 块名下补丁与改写＋全量绿」，分账按 prereq §2.2 的补丁归属逐块对账（updater/_update_check 归 C1、_credential_store/_advanced_features 归 C4、_run_plan_task 归 C5、_run/_spawn 随跨块 D），A3 并入各 C_i 验收；第一批可并行叶子改为 B1/B2/F0/F1/F1b。「先删光 70 处补丁再拆」不是唯一路径也不采纳——那是先废测试覆盖，方向反了。

（约 240 字，超 200 字上限，如实保留。）

## 2. AA3-03（重要）→ seams 作者（同上）

挑战：你的 seams.md 接缝 3 三步换法在 state/plan.js:103 会丢「成功后 800ms 有界刷新」链，且该链基线测试零引用、test_signup_plan 照常全绿——接缝自带的验收网在最危险一行是空的。

作者答：

> **【2·AA3-03 重要】「我承认这条错」。** 统一 notify 口表达不了 plan.js:103 的「返回值门槛副作用」：noteSignedTasks（controllers/refresh.js:398）返回布尔，为真才排 800ms 有界刷新，机械套三步就丢链；scheduleSignedRefresh 基线零测试引用（prereq q-010），验收网确实空。修正：接缝按形态分两种——绘制类走 notifyStatePainted；带返回值门槛的整组原样搬进 controllers 注册回调，state 只发终态事件，noteSignedTasks→scheduleSignedRefresh→showTaskResult→render 顺序与同步语义不变；搬迁前先补行为测试钉「任务到终态后 scheduleSignedRefresh 恰调一次、非终态不调」（node 沙箱回放），否则等价性无从验收。

（约 260 字，超 200 字上限，如实保留。两处采纳修正已写进 extra/mikado.md 与 extra/seams.md 的 T7 修正补记。）

## 3. AA2 意见 1（重要·整块漏）→ rules.md 作者（后端架构师，T3）

挑战：你的 rules.md 规则 7 缺「重试截止倒计时」整块（retry_window.py 三模式算式与桌面 effectiveRetryDeadline、手机 taskDeadline 消费面在五份交付全无覆盖）。

作者答：

> 「我承认这条错」。我方规则 7 只覆盖了时钟语义（r-056..r-058）与距开放倒计时（r-061/r-062/r-064），「重试截止倒计时」整块确实缺失：retry_window.py 三模式算式（DEFAULT_RETRY_SECONDS=120、ADAPTIVE_RETRY=-1、ADAPTIVE_SECONDS=1500、sign_end 硬截，resolve_window）不在 81 条引用内；桌面 effectiveRetryDeadline（local/ui/views/plan-panel.js:1188，submittingDetail「重试到 HH:MM:SS」消费面）与手机 taskDeadline（local/ui/m/app.js:176，「本次尝试到/重试到」两处 LED）也均未引用。我的 r-052/r-055 只覆盖等待开放与提交次数，覆盖不了截止倒计时，「已被他节覆盖」不成立，属范围外的主张也不成立——倒计时显示本应含它。应补三端三小节：后端算式、桌面投影（telemetry 优先+兜底）、手机只读消费。本次不改文件，待授权后可作增补条目 r-082 起。

（处置：已授权补做，条目改从 r-085 起——r-082..r-084 已被 T6 对 U19 的裁定占用。）

## 4. AA1 意见 3/4（重要＋次要）→ phone.md 作者（代码库入职引导工程师，T2）

挑战：你的 phone.md 承诺 12 个等待操作各七出口，但编号从「6. 停止计划」跳「8. 重新登录开始」，「取消一场」无独立七出口；且第 6 节失败行把 cancelTask 的「没能取消这一场」错挂到 stopPlan 名下（基线该句属「没能停止计划」）。

作者答：

> 「我承认这条错」。成因是模板分块 heredoc 被截断在第 6 节「成功」行中间，我的续写按第 7 节断点接文：结果①「### 7. 取消一场（cancelTask）」标题与进入/成功两行整体缺失，编号从 6 跳 8；②第 6 节自己原有的失败/取消/超时/页面隐藏/配对失效五行丢失；③cancelTask 的失败句「没能取消这一场：…」（基线 2839）误挂到 stopPlan 名下，stopPlan 的失败句应为「没能停止计划：…」（2811）。jsonl 的 p-121/p-122 摘录与行号本身无误，错在 md 正文结构与归属；待授权后修模板重建并重跑 verify，不改基线引用数据。

（处置：已授权重建，已完成——第 6 节五行补回、新增第 7 节七出口、12 节连续，verify 0 失败。）

## 5. AA1 意见 1（重要）→ prereq.md 作者（总体规划架构师，T5）

挑战：你的 prereq.md ④ 引用 q-082 称 PHONE_STATIC「只放行四个名字」，基线实有 6 条（31-32 行还有两条图标映射），q-082 摘录区间止于 29 行恰好盖漏。

作者答：

> 「我承认这条错」。重读基线：local/infrastructure/phone_http.py:24-33 的 PHONE_STATIC 实有 6 个键——第 25-28 行四条页面资源，第 31-32 行还有 `/favicon.ico`、`/apple-touch-icon.png` 两条品牌图标（第 29-30 行注释明说走同一白名单）。q-082 摘录区间 24-29 恰好止于图标注释行，claim 却说「固定四文件映射」，md 4.5 的「只放行四个名字」同错，皆应改：区间扩到 24-33，计数改六。可辩护的只剩性质不变：仍是固定白名单、映射外 404，「页面端点与路由一一对应」的核对须补上两个图标请求；但这救不了「四个名字」这个断言本身。谢谢指正。

（处置：q-082 已重写为 24-32 区间六条、md 4.5 改「放行六条精确路径」，verify 0 失败。）

## 攻防辩小结

5 条挑战、5 条回复、5 条全部「我承认这条错」，无一条「仍认为成立」。作者侧修正方案全部落回产物（见 plan/fix-round.md 对应行的「已在本轮产物修正」）。首次派发 prereq 作者时遭遇一次模型流中断（自动重试达上限），按限流规则等待后重发成功，未换模型。
