# T10 重构前置：四类接缝清单（seams）

- 基线：`7e2d31c`（与 plan/ 五份交付同基线）。行号一律基线口径；产品代码只按 `git show 7e2d31c:<路径>` 与只读基线树核对。
- 事实底座：尽量引 plan/ 结论不重算——Api 清点与补丁面见 `plan/prereq.md` §2（q-033 至 q-059）、esc 见 §3、桥接名与字符串访问见 §4；行为面见 `plan/desktop.md`。
- 判据：**不改被测源码即可替换行为**。做不到的写「不成立」并说明缺什么机制。
- 本件只读分析；下列命令全部只列出、未执行（git grep 类已在基线提交上跑过取证，python/node 测试命令未跑）。

## 接缝 1：Api 方法（local/app.py:813 `class Api`）

**判定：成立。** 现状「逐方法/逐字段替换」已可用（基线测试大量现成写法）；拆五块后要升级成「整块替身」，缺的机制是五块尚无独立构造入口（`Api.__init__(self, clock=None)` 只注时钟，app.py:814，其余依赖全部自建）。

### 替换点在哪
- 类定义 local/app.py:813；构造 `__init__(self, clock=None)`（app.py:814-817，仅 `_clock` 可注入，未注入显式 `_UnavailableClock`）。
- 现成替换写法（基线 local/tests，全部不改被测源码）：
  1. 实例属性遮蔽类方法：`self.api.check = lambda request_id="": fired.set()`（test_application_services.py:1473）、`self.api._terms_gate = lambda *a, **k: None`（:1478）、`self.api._do_check_inner = inner`（:1489）、`self.api.stop_phone_access = mock.Mock()`（test_release_audit.py:104，prereq q-057）、MethodType 绑定 `api.accept_terms = types.MethodType(namespace["accept_terms"], api)`（test_terms_consent.py:437-438，prereq q-058）。
  2. 类级补丁：`mock.patch.object(app.Api, "_run"/"_spawn"/"_run_plan_task")`（test_runtime_bundle.py:397/441/443，prereq q-046 至 q-050）。
  3. 依赖替身按字段塞入：`self.api._phone = FakePhoneService()`（test_application_services.py:283-289，prereq q-054）。
  4. 模块级补丁：`app.sys.frozen`、`app.subprocess.Popen`、`app.AppLifecycle.INTERVAL_S`、`app.threading.Thread`（test_runtime_bundle.py:1893-1930、test_session_persistence.py:1333、test_update_check.py:563-597）。
- 补丁面体量（基线复算）：app 模块一级属性上的 patch 调用点 70 处（app.Api×6、app.subprocess×5、app.sys×5、local_app.updater×14、local_app.threading×6 等）；`patch("app.X")` 字符串形态 0 处，全走 patch.object。提案 §4 口径「42 个名字」（reconcile.md §3.3 判成立）。
- 成员改写面（基线复算）：`(self.api|api).X =` 272 行，去重 64 名；提案 §4 口径「66 个成员」（差异为 setattr 形态如 `setattr(api, "_cancelling", …)` 与个别别名变体，prereq §2.2 分块列全）。

### 怎么替换
- 逐方法替换：现状即成立，直接照上面四类写法。
- 整块替换（拆五块的验收手段）：五块先抽成服务对象（更新/组件/手机访问/登录恢复/计划，方法归属底稿 prereq §2.1），经 app.py 组合根注入；测试用假服务整块换入（FakePhoneService 是现成样板）。跨块 24 方法安置后，`_window/_emit/_lock/_clock/_phone/_plan` 等共享面收进显式上下文对象，测试替换该上下文而不是逐字段打补丁。
- 约束：凡构造 `app.Api` 的测试必须经 `local/tests/fixtures/api_threads.py` 的 `stop_auto_relogin_on_cleanup`——Api 一构造就启动自动重登线程（AGENTS.md 测试注意、grab.md T5 夹具清单）。拆分后每个块服务也要能被夹具收掉。

### 替换后如何验证行为不变
- `python -m unittest discover -s local/tests -p "test_application_services.py" -v`（实例替换与整块替身路径）
- `python -m unittest discover -s local/tests -p "test_runtime_bundle.py" -v`（_run/_spawn/_run_plan_task 与模块级补丁路径）
- `python -m unittest discover -s local/tests -p "test_*.py" -v`（全量，约 1700 例）
- 期望全绿，且补丁目标与新模块路径一一对应：patch.object 落在已不存在的旧属性上会 AttributeError，而实例属性改写迁移后会静默失效——提案 §4 原话「拆的时候这些补丁会悄悄落空而不报错」，所以迁移以命令清单逐条对账，不只看绿。

### 最小验证命令
```bash
git grep -nE "(mock\.)?patch(\.object)?\(\s*(app|local_app|self\.app|self\.local_app)\." 7e2d31c -- local/tests
git grep -nE "(self\.api|api)\.[A-Za-z_0-9]+ ?=" 7e2d31c -- local/tests
python -m unittest discover -s local/tests -p "test_application_services.py" -v
```
（前两条：基线分别给 70 处补丁点、272 行成员改写；改造后去掉 `7e2d31c` 复跑，期望 0 或全部指向拆分后的新路径。）

## 接缝 2：js_api 桥接名

**判定：替换传输层成立（不动 Api 类，测试现成两种写法）；桥接名改名不成立**——44 名硬编码在前端调用点、Api 方法名（60 公开方法）与手机白名单三处，prereq §4.2 已证一一对应，改名必动两端；要成立需补「单一桥接名注册表 + 契约测试比对」机制（现缺）。

### 替换点在哪
- 前端→后端唯一漏斗：local/ui/controllers/bridge.js:6 `function api(name, ...args)` → 第 8 行 `window.pywebview.api[name]` 按名取方法；api() 无 timeout 参数（desktop.md U12：bridge.js:6-11）。44 个名字字面量分布 local/ui（除 m/，手机页走 HTTP postAction；复算 = 44）。其中 24 处直接从视图层发出：views/phone.js 15、views/relogin.js 4、views/settings.js 4（提案 §4「三个视图文件直接发桥接请求 24 处」，复算一致）。
- 后端→前端唯一注入点：local/app.py:1119 `_emit` 拼 `"window.onBackend && window.onBackend.%s(%s)"` 后 `evaluate_js`；12 个 kind（直发 10 + 闭包转发 plan/task）与 local/ui/app.js:90 `window.onBackend = {...}` 的 12 键一一对应（prereq §4.3）。
- 手机动作派发：local/application/phone_service.py `getattr(self._api, name)`；白名单 12 键（local/domain/phone_rules.py:155 起），`save_retry_policy` 特判改道 `save_prefs`、`start_plan` 注入 source=phone（prereq §4.4-4.5）。

### 怎么替换
- 替换传输层（前端→后端）：不动 Api 类即可。现成写法两种：
  1. QA 全替身：`local/tests/fixtures/runtime_bridge.js:752` `window.pywebview = { api: api }`；
  2. 行为测试按测注桩：test_ui_main_window_plan.py:393 `window.pywebview = { api: { stop_plan: () => new Promise(() => {}) } }`（prereq q-002）、test_clock_tail.py:165 `window.pywebview={api:{sync_clock:...}}`。
  桥的本质是「按名字从 js_api 对象取属性」，Api 类不参与取名这一步，替 window.pywebview 即整体换掉桥。
- 替换某个事件方向处理器：node 沙箱/契约测试直接覆写 `window.onBackend.check = ...`；契约测试已有按 `window[name]`/eval 动态替换全局函数的先例（test_ui_contract.py:2383-2385，prereq §4.1）。
- window.onBackend 拆注册函数（app.js:90 对象字面量 + 内联闭包 → 逐 kind 注册函数）：属于前端重构动作而非测试接缝；runtime_bridge.js 按名直调 `window.onBackend.<kind>`（:370/:406/:429 等）证明 12 键名是与测试替身共享的事实契约，拆注册不得改键名。
- 桥接名改名：不成立（见判定）。缺的机制：前后端共用的桥接名清单（一张表）+ 契约测试比对两侧；在它存在之前，任何改名都要同时手改三处并靠全量测试兜底。

### 替换后如何验证行为不变
- `python -m unittest discover -s local/tests -p "test_ui_contract.py" -v`（桥名、onBackend 键、加载顺序断言 `test_script_load_order_puts_views_before_dependents`，test_ui_contract.py:463-471）
- `python -m unittest discover -s local/tests -p "test_clock_tail.py" -v`（window.pywebview 按测注入的行为回放）
- `python -m unittest discover -s local/tests -p "test_ui_reliability.py" -v`（runtime_bridge 驱动的行为回放）
- 期望：44 名清单不变；12 kind → 12 键对应不变；`api()` 仍无 timeout（若顺手给 api() 加超时是行为变更，须按 desktop.md U12 口径另立验收）。

### 最小验证命令
```bash
git grep -hoE 'api\("[a-z_0-9]+"' 7e2d31c -- local/ui ':!local/ui/m' | sort -u | wc -l   # 期望 44
git grep -n "onBackend" 7e2d31c -- local/app.py local/ui/app.js   # 注入 app.py:1119；处理器表 app.js:90
python -m unittest discover -s local/tests -p "test_ui_contract.py" -k load_order -v
```

## 接缝 3：state/ 越层

**判定：成立。** 事件（store.js 通知口）与反向注入两条路都能替掉全部直接调用；机制前提是 store.js 承载注册口并保持同步派发（store.js 是唯一状态仓库且在 index.html:562 最先加载）。

### 替换点在哪
- state/*.js 直接调用 views/controllers 顶层函数的调用点。本任务复算：**53 行 / 58 次调用、24 个函数名**；分布 state/clock.js 15、state/login.js 12、state/plan.js 10、state/filters.js 8、state/task-display.js 6、state/conflict.js 1、state/labels.js 1（rounds.js/store.js/time.js 为 0）。提案 §4 口径 62 处（reconcile.md §3.3 判与提案无冲突）；差异来自函数名提取范围，**完成判据按复算命令归零**，不依赖口径。
- 具体落点（基线行号）：
  - clock.js 78-81、114-116、134-137、159-162：`paintClockStatus()`、`if (clockPopOpenNow()) renderClockPop()`、`updateControls()`、`render()`
  - login.js 29、33、61、70、72-76、137-140：`typeof reloginAutoLive !== "function"` 防御（:29，reloginAutoLive 定义在 views/relogin.js——提案 §目标 5 点名的例子）、`numOrNull`、`paintLogin()/paintRail()/paintSelected()/paintBoardActions()/refreshLoginEmptyState()`、`paintClockStatus()`、`render()`
  - plan.js 51、62、78、80、103、104、106、114、123、128：`setBusy()`、`noteStartedFromPhone()`、`render()`、`noteSignedTasks()+scheduleSignedRefresh()`（controllers/refresh.js）、`showTaskResult(task)`、`selectionSignature()`
  - filters.js 307、343、362、372、381、382、391、392：`verifiedSigned` 防御、`termsLocked()`、`render()`、`setResult()`
  - task-display.js 58、100、101、104、148、150：`verifiedSigned` 防御、`hmsDay()`、`submittingDetail(task)`、`effectiveRetryDeadline()`
  - conflict.js:147 `termsLocked()`；labels.js:61 `verifiedSigned` 防御
- 佐证：四处 `typeof X === "function" && X(...)` 防御（login.js:29、filters.js:307、task-display.js:58、labels.js:61）说明越层已在靠运行期探测兜底加载序——调用全部发生在事件回调里，没有脚本求值期调用，「先注册后消费」时序天然成立。

### 怎么替换（具体写法，事件口方案）
第 1 步，state/store.js 增加通知口（不 import、不硬引用任何 views/controllers 名字）：
```js
/* store.js：状态仓库的绘制通知口。注册表为空时静默——启动早期没有渲染方。 */
const paintListeners = [];
function onStatePainted(fn) { paintListeners.push(fn); }
function notifyStatePainted() { paintListeners.forEach((fn) => fn()); }
```
第 2 步，state/login.js 原 70-76 五连改为：
```js
notifyStatePainted();   /* 替掉 paintLogin/paintRail/paintSelected/paintBoardActions/refreshLoginEmptyState */
```
第 3 步，controllers（或 app.js 启动段，须在视图加载后）注册：
```js
onStatePainted(() => { paintLogin(); paintRail(); paintSelected(); paintBoardActions(); refreshLoginEmptyState(); });
```
等价性论证：paint* 全是从 S 现算现画的全量重画（desktop.md 对 views/login.js 的逐行结论），回调同步派发保持「改完状态立刻画完」的现有语义，不引入 setTimeout；注册一次、多处 notify，最终 DOM 与逐点调用一致。带参调用（`showTaskResult(task)`、`renderClockPop()`）同构：notify 带payload 或注册回调按 kind 分流。反向注入（state 暴露 `setLoginPainter(fn)`、controllers 注入）同样可行，测试更直白：注入假 painter 断言被调次数与顺序。
不能省的护栏：新注册点若放新文件要动 index.html 并同步加载顺序断言（test_ui_contract.py:463）；放现有 controllers 文件或 app.js 可不动 index.html。

### 替换后如何验证行为不变
- 契约：`python -m unittest discover -s local/tests -p "test_ui_contract.py" -v`（read_ui_scripts() 按 index.html 加载序拼接全部业务脚本、不含 led.js，test_ui_contract.py:35）
- 行为：`python -m unittest discover -s local/tests -p "test_clock_tail.py" -v`（clock 链路）、`python -m unittest discover -s local/tests -p "test_ui_reliability.py" -v`（登录/计划）、`python -m unittest discover -s local/tests -p "test_signup_plan.py" -v`（node 沙箱回放 plan-events）、`python -m unittest discover -s local/tests -p "test_ui_conflict_cancel.py" -v`（filters/conflict 链路）
- 新增守卫：把复算命令固化成契约用例（state/*.js 不含 views/controllers 顶层函数调用），并入 test_layer_boundaries 的前端扩展（提案 §原则「依赖单向，用测试守住」）。

### 最小验证命令
```bash
git grep -hoE "^(async )?function [A-Za-z0-9_$]+" 7e2d31c -- local/ui/views local/ui/controllers | awk '{print $NF}' | sort -u > /tmp/vc_names.txt
git grep -hoE "^(async )?function [A-Za-z0-9_$]+" 7e2d31c -- local/ui/state | awk '{print $NF}' | sort -u > /tmp/st_names.txt
git grep -hoE "[A-Za-z_$][A-Za-z0-9_$]*\(" 7e2d31c -- local/ui/state | sed "s/($//;s/(//" | sort -u | comm -12 - /tmp/vc_names.txt | comm -23 - /tmp/st_names.txt | wc -l
python -m unittest discover -s local/tests -p "test_ui_contract.py" -k load_order -v
```
（第三条基线输出 24；改造后去掉 `7e2d31c` 复跑，期望 0。）

## 接缝 4：esc 注入点（state/time.js 的 esc 全局）

**判定：成立（单点替换，115 个调用点不挡路）。** 挡路项两个：views/terms.js:46 的同名局部遮蔽（改名或重构语义时必须先处理）；转义集无契约测试（换转义集前必须先补，否则「行为不变」无法验收）。

### 替换点在哪
- 定义唯一点：local/ui/state/time.js:123 `function esc(value)`——只转义 `& < > "`，**不转义 `'`**；同文件 `cssEscape` 是选择器专用（prereq §3，q-060/q-061）。
- 调用点 115 处（按调用次数计；grep 按行 88 行）：plan-panel.js 38、list.js 28、clock-pop.js 12、terms.js 8、filters.js 7、conflict-tip.js 6、selection.js 6、help.js 3、login.js 3、status-cards.js 2、controllers/window.js 2（prereq §3）。落点人工复核：文本节点 91 + 双引号属性 24，单引号属性/事件处理器字符串/URL 为 0（prereq §3.1/§3.2）——「不转义单引号」当前不构成注入路径。
- 会挡路的点：
  1. views/terms.js:46 `const esc = dialog.querySelector(".help-esc")` 在 applyTermsFooter 内遮蔽全局 esc（:82/:85 用的是局部 DOM 元素，prereq 特例 2）——换实现不影响这两行；但给 esc 改名/挪走定义时这是同名冲突点。另有一处无关同名：test_ui_conflict_cancel.py:269 `const esc = { key: "Escape", ... }` 是键盘事件对象。
  2. 加载序：esc 定义在 state/time.js（index.html:596 加载，倒数第二），调用方 plan-panel.js/list.js/filters.js 等都在它之前加载。现状不挡——全局函数声明 + 运行期按名解析；**会挡的改动**：改 ES Module import、或把声明改成 const 箭头（不提升、模块词法作用域，先加载的调用方解析不到）。ESM 迁移（提案已定采用）必须把 esc 一并搬层。
  3. terms.js:347-350 是唯一「esc 后再 .replace 换固定按钮」的加工链（prereq 特例 1）——换转义集后这条链的输出会变，须单独核对。
  4. 无契约测试：基线 local/tests 没有断言 esc 转义集的用例（检索 esc/&amp;/quot 无命中；prereq §3.2 已标「需测试定」）；115 处落点形态也没有自动化守护，改动后只能人工重扫。

### 怎么替换
- 换实现、不动调用方：只动 time.js:123 一行（115 个调用点运行期按名解析，零改动）；或测试沙箱在 read_ui_scripts() 拼装后覆写 `esc = ...`（全局声明可被后加载赋值覆盖）。
- 换转义集（如补 `'` 转义）：先补两件事——(a) esc 转义集契约测试（现缺）；(b) `scripts/esc_sites.mjs` 复扫确认落点形态仍只有文本节点与双引号属性（当前 0 处单引号属性，补 `'` 对现有 115 处行为等价，风险只在未来新增单引号属性落点）。
- 手机页（local/ui/m/）有独立转义实现，不在本接缝范围（prereq 未尽事项 2）。

### 替换后如何验证行为不变
- `python -m unittest discover -s local/tests -p "test_ui_contract.py" -v`（文案逐字断言不受影响）
- `node design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/esc_sites.mjs`（调用点与落点形态全量复扫，期望 115/91/24 计数不变或按新契约记录变化）
- 新增：esc 转义集契约用例（先补后换，作为「行为不变」的判据本体）。

### 最小验证命令
```bash
git grep -n "function esc" 7e2d31c -- local/ui/state/time.js   # 唯一定义点 :123
node design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/esc_sites.mjs   # prereq §3 清点工具，从仓库根复跑
python -m unittest discover -s local/tests -p "test_ui_contract.py" -v
```

## 附：两目标与本清单的关系
- 「Api 拆五块」主要消费接缝 1、2（方法替换面与桥接面）；「state/ 越层清零」消费接缝 3、4。依赖树见同目录 mikado.md。
- 接缝 2 的「24 处视图直发桥接」与接缝 3 的 53/58 处越层是两回事：前者是视图层越权发请求（views/phone.js、views/relogin.js、views/settings.js），不阻塞越层清零，但同属前端分层松动，建议同一计划批次处理。


## T7 修正补记（2026-11-12，依 AA3-01/02/03 对抗结论与作者攻防辩认错修正，主执行方代录）

- **AA3-01（判法自相矛盾）**：接缝 2「桥接名改名不成立」与接缝 3「成立」用了不同判法。统一判法后接缝 3 按形态分流（见下），「成立」仅对绘制类子集成立。
- **AA3-02/03（查询型调用罩不住）**：21/58 次越层调用（10/25 名）返回值参与 state 决策，通知口罩不住。接缝 3 改为按形态分流：①绘制类调用走 notifyStatePainted（原方案不变）；②带返回值门槛的整组（如 state/plan.js:103 `if (noteSignedTasks([task])) scheduleSignedRefresh();`，noteSignedTasks 定义于 controllers/refresh.js:398）原样搬进 controllers 注册回调，state 只发终态事件，noteSignedTasks→scheduleSignedRefresh→showTaskResult→render 的顺序与同步语义不变。
- **前置条件（AA3-03 的验收网要求）**：搬迁前先补行为测试钉住「任务到终态后 scheduleSignedRefresh 恰调一次、非终态不调」（node 沙箱回放）——该链基线零测试引用（prereq q-010），不补测试则等价性无从验收。
- **AA3-04（接缝 1 漏项）**：接缝 1 的替换点清单只计「写」面；私有成员读/断言触点实测 667 处命中、约 395 处无人计账。处置记入 plan/fix-round.md（需人裁决：清点成本与工期）。
