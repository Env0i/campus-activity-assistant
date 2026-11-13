# 三级抽检（第四位独立专家）：五条争议点

- 基线：7e2d31c（HEAD，工作区即此基线加 design/ 下未提交文档）
- 方法：只凭任务书给定的证据起点自己重跑命令，不读任何一方论证文章；不联网、不跑测试构建、不改源文件。
- 评估日期：2026-11-13

---

## 争议点 1：refresh.js 清空三行的行号

**争议点陈述**
- 甲方（第一轮对抗审计 A4）：local/ui/controllers/refresh.js 的「清空 items/byId/selected」三行在 480-482。
- 乙方（重做条目 d-248）：三行在 479-481。

**证据（自己重跑命令的输出，逐字）**

`git show 7e2d31c:local/ui/controllers/refresh.js | awk 'NR>=476 && NR<=484 {printf "%d\t%s\n", NR, $0}'`：

```
476	      settleRefreshBranch("list");
477	      return;
478	    }
479	    S.items = [];
480	    S.byId = new Map();
481	    S.selected.clear();
482	    syncResultSelection();   /* 列表失败清掉选择不是用户改勾选，不关结果页 */
483	    S.listState = "error";
484	    /* FB4：先消费后端的 runtime_error 再渲染——check 成功而 list 起不来时
```

乙方 excerpt 在全文的定位：`git show 7e2d31c:local/ui/controllers/refresh.js | grep -n "S.items = \[\];"`：

```
479:    S.items = [];
```

（全文件仅此一处命中，excerpt 定位唯一，三行即 479/480/481。）

**判定**：乙方站得住，甲方站不住。

**依据**：三行原文在 479-481，且乙方 excerpt 在全文唯一命中于 479，甲方 480-482 整体偏一行（480-482 实为 byId/selected/syncResultSelection）。

---

## 争议点 2：Mikado 树 A1/A2/A3 第一批是否死锁

**争议点陈述**
- 甲方（AA3-21，阻断级）：原树把 A1/A2/A3 列为无依赖叶子放进「第一批可并行」，而三者完成判据是拆分终态、依赖 C1..C5 产出物，按树执行第一批即死锁。
- 乙方（mikado 原树）：A1/A2/A3 可并行。

**证据（工作区文件 design/evidence/2026-11-12/refactor-audit/redo/zcode/extra/mikado.md 原文，逐字）**

A1 节点（:26-27）：

```
26	- 完成判据：`git grep -nE "(mock\.)?patch(\.object)?\(\s*(app|local_app|self\.app|self\.local_app)\." -- local/tests` 清单为空或每处指向新模块路径；`python -m unittest discover -s local/tests -p "test_*.py" -v` 全绿。
27	- 依赖：无（叶子）
```

A2 节点（:31-32）：

```
31	- 完成判据：`git grep -nE "(self\.api|api)\.[A-Za-z_0-9]+ ?=" -- local/tests` 计数 0（已改为替身服务或显式端口）；`python -m unittest discover -s local/tests -p "test_application_services.py" -v` 全绿。
32	- 依赖：无（叶子）
```

A3 节点（:36-38）：

```
36	- 要补的机制：五块服务对象同样持有线程/进程（更新下载线程、手机访问监听、计划 worker），夹具扩成「构造即登记、cleanup 即收」。
37	- 完成判据：`git grep -n "stop_auto_relogin_on_cleanup" -- local/tests/fixtures/api_threads.py` 命中且注释覆盖块服务；`python -m unittest discover -s local/tests -p "test_application_services.py" -v` 与 `-p "test_silent_relogin.py" -v` 全绿。
38	- 依赖：无（叶子）
```

「第一批可并行的叶子节点」清单（:156-160）：

```
156	## 第一批可并行的叶子节点
158	1. A1 app 模块补丁点改造（G1）
159	2. A2 Api 实例成员改写改造（G1）
160	3. A3 构造与清理夹具贯通（G1）
```

树的另一处自证（:58，C1 的依赖声明）：

```
58	- 依赖：B3（另需 A1/A2 已迁移对应补丁与改写）
```

**判定**：甲方站得住，乙方站不住。

**依据**：三节点文本均自标「依赖：无（叶子）」且列入第一批清单，但 A1 判据「每处指向新模块路径」、A2 判据「已改为替身服务或显式端口」、A3 判据「覆盖（五）块服务」全是 C1..C5 抽出后才存在的新模块/服务产出物——完成判据依赖 C 块产出物而依赖声明为零，第一批按树不可闭合，死锁成立（该文件 :182 已写有 AA3-21 修正条目，与本判读一致）。

---

## 争议点 3：接缝 3 三步换法是否丢 800ms 有界刷新链

**争议点陈述**
- 甲方（AA3-03）：按 seams.md 接缝 3 的三步换法，state/plan.js:103 的 `if (noteSignedTasks([task])) scheduleSignedRefresh();` 的「成功后 800ms 有界刷新」会丢，且该链基线零测试引用。

**证据（自己重跑命令的输出，逐字）**

`git show 7e2d31c:local/ui/state/plan.js`（:100-107）：

```
100	  S.plan.tasks.set(String(data.task_id), task);
101	  if (["success", "failed", "already_signed", "canceled"].indexOf(task.status) >= 0) {
102	    /* 报名成功是已确认事实：任务卡、列表、计数、选择门禁和冲突基线同一时刻更新 */
103	    if (noteSignedTasks([task])) scheduleSignedRefresh();
104	    showTaskResult(task);
105	  }
106	  render();
107	}
```

`git show 7e2d31c:local/ui/controllers/refresh.js | grep -n "noteSignedTasks\|scheduleSignedRefresh"`：

```
398:function noteSignedTasks(tasks) {
451:function scheduleSignedRefresh() {
```

`scheduleSignedRefresh` 定义体（refresh.js :449-458）：

```
449	/* 计划收尾后安排一次有界列表刷新：只补权威列表，不重发、不改结论。
450	 * 刷新失败时后端仍保留已确认成功，界面下一轮成功刷新会重新合并。 */
451	function scheduleSignedRefresh() {
452	  if (confirmedRefreshTimer) clearTimeout(confirmedRefreshTimer);
453	  confirmedRefreshTimer = setTimeout(() => {
454	    confirmedRefreshTimer = null;
455	    if (S.busy || S.starting || S.demo) return;
456	    refresh(true);
457	  }, 800);
458	}
```

`git grep -n "scheduleSignedRefresh" 7e2d31c -- local/tests`：零命中（exit=1）。

seams.md 接缝 3 的三步换法（extra/seams.md :87-103）：第 1 步 store.js 加 onStatePainted/notifyStatePainted，第 2 步 state 层原调用改 notifyStatePainted()，第 3 步 controllers 注册 paint 回调；等价性论证原文：

```
103	等价性论证：paint* 全是从 S 现算现画的全量重画（desktop.md 对 views/login.js 的逐行结论），回调同步派发保持「改完状态立刻画完」的现有语义，不引入 setTimeout；注册一次、多处 notify，最终 DOM 与逐点调用一致。
```

（接缝 3 的替换写法只覆盖 paint* 与带参绘制调用，scheduleSignedRefresh 只出现在 :81 的落点清单里，替换写法一节未给任何承载方式。旁路：local/ui/controllers/plan-events.js:34 另有 `if (signedChanged && autoRefresh !== false) scheduleSignedRefresh();`，但触发条件是 plan-events 事件且受 autoRefresh 开关约束，与 plan.js:103 的逐任务终态触发不是同一路。）

**判定**：甲方站得住。

**依据**：接缝 3 给出的替换机制只有同步 paint 通知并明文「不引入 setTimeout」，800ms 延迟刷新按该三步换法在 plan.js:103 触发点上无处落地，且 scheduleSignedRefresh 在基线 local/tests 零引用，丢失不会打红任何测试。

---

## 争议点 4：rules.md 规则 7 是否缺「重试截止倒计时」块

**争议点陈述**
- 甲方（AA2 意见 1）：重做 rules.md 的规则 7「时间与倒计时」缺「重试截止倒计时」整块（后端 retry_window.py 算式与两端消费）。
- 乙方（rules.md 作者）初版：已被他节覆盖。

**证据（自己重跑命令的输出，逐字）**

`git show 7e2d31c:local/domain/retry_window.py | head -40`（节选，模块与三模式算式存在）：

```
2	"""重试窗口纯算式：worker / 父监督 / 桌面投影共用同一口径。
5	三种模式由 retry_for_s 区分：
6	  - 正数：用户选的显式时长，sign_end 更早时被截断，不扩窗；
7	  - 0：直到报名截止，缺截止回退 DEFAULT_RETRY_SECONDS，不扩窗；
8	  - ADAPTIVE_RETRY(-1)：自动延长，初始 DEFAULT_RETRY_SECONDS，之后由本场
9	    合法 window_extended 事件按 extension_delta 逐次增长，上限
10	    anchor + ADAPTIVE_SECONDS 且受 sign_end 硬截。
14	关键算式（父监督扩窗）：new_hard_stop = hard_stop + (candidate - accepted)。
23	DEFAULT_RETRY_SECONDS = 120.0
25	ADAPTIVE_SECONDS = 1500.0
27	ADAPTIVE_RETRY = -1
```

grep 命中数（redo/zcode/plan/ 下）：

```
rules.md:          0   （grep -c "retry_window\|effectiveRetryDeadline\|taskDeadline"）
rules.cites.jsonl: 9   （r-085..r-094，覆盖 retry_window.py 四条 + plan-panel.js effectiveRetryDeadline/submittingDetail/routeDeadline 三条 + m/app.js taskDeadline 两条）
```

`grep -n "r-08[5-9]\|r-09[0-4]" rules.md`：零命中（exit=1）——九条引文收集了但规则正文一条都没引用。

`grep -n "重试\|倒计时" rules.md`：全文「重试」零命中；所有「倒计时」命中均在规则 7（:173-196）与汇总表 :254，内容全部是距开放/格式文案（「HH:MM:SS」「N天 HH:MM」「N 小时后」等），无一涉及重试截止。规则 7 汇总行原文（:254）：

```
254	| 7 | 北京时间与倒计时 | UTC+8 契约+业务时钟 [[r-056]][[r-057]][[r-058]] | Asia/Shanghai+逐字段回验 [[r-059]][[r-060]][[r-061]][[r-062]] | businessNowS+900 秒上限 [[r-063]][[r-064]][[r-065]] | 一致；文案不同 | 倒计时措辞两套（都照各自原型） |
```

（「未尽事项」:281-288 六条也无一条提及重试截止倒计时。）

**判定**：甲方站得住，乙方站不住。

**依据**：retry_window.py 三模式算式与两端消费（effectiveRetryDeadline/taskDeadline）在基线真实存在，rules.md 九节正文与汇总表对该主题零命中，作者引文库里 r-085..r-094 九条恰是这块材料却一条未进正文——不是「被他节覆盖」，是整块缺失且引文成孤儿。

---

## 争议点 5：PHONE_STATIC 白名单四名还是六名

**争议点陈述**
- 甲方（AA1 意见 1）：local/infrastructure/phone_http.py 的 PHONE_STATIC 有 6 个键。
- 乙方（重做条目 q-082 初版）：只放行四个名字。

**证据（自己重跑命令的输出，逐字）**

`git show 7e2d31c:local/infrastructure/phone_http.py`（:23-33）：

```
23	# 固定静态资源表：只认这几条路径，杜绝目录遍历/任意文件读取
24	PHONE_STATIC = {
25	    "/": ("index.html", "text/html; charset=utf-8"),
26	    "/index.html": ("index.html", "text/html; charset=utf-8"),
27	    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
28	    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
29	    # 品牌图标：head link rel="icon" 和 apple-touch-icon
30	    # 走同一个白名单映射，不新开路由、不放宽其他路径
31	    "/favicon.ico": ("favicon.ico", "image/x-icon"),
32	    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
33	}
```

键逐一计数："/"、" /index.html"、" /styles.css"、" /app.js"、" /favicon.ico"、" /apple-touch-icon.png" = **6 键**（映射到 5 个不同文件，"/" 与 "/index.html" 同指 index.html）。

**判定**：甲方站得住，乙方站不住。

**依据**：基线原文 24-33 行字典恰好 6 个键，乙方「四个名字」只数到图标注释块之前的 4 条，漏了 "/favicon.ico" 与 "/apple-touch-icon.png" 两键（即便按「不同文件」口径也是 5，任何口径都到不了 4）。

---

## 抽检汇总

| 条号 | 判定 | 一句依据 |
|---|---|---|
| 1 | 乙方站得住 | 三行原文 479-481 且 excerpt 全文唯一命中 479，甲方偏一行 |
| 2 | 甲方站得住 | A1/A2/A3 自标无依赖叶子进第一批，判据却引用 C 块新模块/服务产出物，第一批不可闭合 |
| 3 | 甲方站得住 | 接缝 3 换法只有同步 paint 通知且明文不引入 setTimeout，800ms 刷新无处落地、测试零引用 |
| 4 | 甲方站得住 | retry 算式与两端消费基线存在，rules.md 正文零覆盖，r-085..r-094 九条引文未进正文成孤儿 |
| 5 | 甲方站得住 | PHONE_STATIC 恰 6 键，原文 24-33 行逐键可数 |

Agent: TestingRealityChecker（三级抽检，第四位独立专家）
