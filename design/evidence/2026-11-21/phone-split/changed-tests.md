# 测试装载改动与新增守卫说明

本批对手机页相关测试只调整脚本装载方式与新增拆分守卫，不修改任何原有业务断言，不新增 `test_*.py` 文件。

## 1. 脚本装载方式改动清单

所有手机页脚本清单的唯一来源统一为 `local/ui/m/index.html` 中 `<script src="...">` 标签的出现次序（共 12 份：`model.js` 至 `ui-shell.js`）。

| 测试文件 | 位置 | 改前 | 改后 | 原因 |
|---|---|---|---|---|
| `local/tests/test_phone_ui.py` | `_phone_scripts()`、`_read_phone_scripts_text()` | 无 | 新增读取 `index.html` 脚本清单与按清单拼接全文的帮助函数 | 避免在测试里硬编码 12 份文件名，保持与页面唯一真源一致 |
| `local/tests/test_phone_ui.py` | `PHONE_JS_HARNESS`（`getElementById`） | `getElementById: (id) => el2("#" + id)` | `getElementById: (id) => el2("#" + String(id).replace(/^#/, ""))` | 拆出 `if (typeof document !== "undefined")` 后，手机页顶层 `const $` 会遮住沙箱全局 `$`；测试里有片段按 `$("#...")` 取元素，需去掉开头的 `#` 统一落到同一假元素实例 |
| `local/tests/test_phone_ui.py` | `PHONE_JS_HARNESS`、`LOAD_PHONE_SCRIPTS_LINE`、`run_phone_js(files=...)` | 单行读取并执行 `m/app.js` | 按 `index.html` 清单依次读取并执行全部手机脚本；`files=` 视图模式同步以 `LOAD_PHONE_SCRIPTS_LINE` 为替换锚点 | `app.js` 已拆分为 12 份普通脚本，沙箱须按页面顺序装载全部脚本，视图模式替换逻辑保持不变 |
| `local/tests/test_phone_ui.py` | `_get_phone_worker()` | 只编译 1 个 `vm.Script(m/app.js)` | 按 `_phone_scripts()` 为每份脚本各编译一次 `vm.Script`，每个用例按顺序依次在 `sandbox` 中执行 | 维持常驻 worker 的预编译加速与多脚本顺序隔离 |
| `local/tests/test_phone_ui.py` | `test_cancel_task_posts_the_tapped_card_task_id`、`test_review_lists_the_plan_and_the_same_reminders` | `(PHONE_DIR / "app.js").read_text(...)` | `_read_phone_scripts_text()` | `app.js` 已删除，源码文本契约改读按清单拼接的全文 |
| `local/tests/test_phone_ui.py` | `PhoneHttpEnd2EndTests.setUp`、`test_html_entry_resources_are_really_served` | 只复制与请求 `app.js` | 复制 `index.html`、`styles.css` 与 `_phone_scripts()` 全部脚本，并逐一验证静态路由返回 `200` 与 `javascript` 类型 | 端到端临时目录与页面资源检查须覆盖拆分后的全部脚本 |
| `local/tests/test_phone_infra.py` | `PhoneHttpBase.setUp`、`RoundTripTests.test_static_pages_are_served_from_fixed_table`、`PublicHostSwitchTests.setUp`、`BackupHostTests.setUp` | 写入假 `app.js` 并请求 `/app.js` | 写入与请求清单首份脚本 `_phone_scripts()[0]`（即 `model.js`） | `/app.js` 已从 `PHONE_STATIC` 移除，静态表基础连通性改用清单内有效脚本路径 |
| `local/tests/test_retry_policy.py` | `IntegrationBase.setUp` | 只复制 `index.html`、`styles.css`、`app.js` | 从 `PHONE_DIR / "index.html"` 解析 `<script src="...">` 清单并复制全部脚本 | 集成服务临时目录须具备完整手机页静态脚本 |

## 2. 新增守卫与临时副本变红反证

新增守卫分别加在已有测试文件 `local/tests/test_phone_infra.py` 与 `local/tests/test_phone_ui.py` 中，全部先在基于 `git archive HEAD` 叠加工作区改动的临时副本里做变红反证（运行后清理临时目录）。

### 2.1 `test_phone_infra.py::RoundTripTests.test_phone_static_matches_index_html_and_disk`

守卫规则：
1. `PHONE_STATIC` 中不含 `/app.js`；
2. `index.html` 引用的每个脚本都在 `PHONE_STATIC` 中、MIME 类型包含 `javascript`、且磁盘文件存在；
3. `PHONE_STATIC` 中的每个 `.js` 都被 `index.html` 引用；
4. `local/ui/m/` 下的每个 `.js` 都在 `PHONE_STATIC` 中。

临时副本反证记录：

| 反证编号 | 临时副本篡改方式 | 触发规则 | 实际结果 |
|---|---|---|---|
| G1 | 从 `PHONE_STATIC` 删去 `/ui-plan.js` 条目 | `index.html` 脚本必须在 `PHONE_STATIC` 中 | FAIL（`AssertionError: '/ui-plan.js' not found in ... : ui-plan.js 必须在 PHONE_STATIC 里`） |
| G1b | 将 `PHONE_STATIC["/ui-plan.js"]` 类型改为 `text/plain; charset=utf-8` | MIME 类型须含 `javascript` | FAIL（`AssertionError: 'javascript' not found in 'text/plain; charset=utf-8'`） |
| G1c | 删除临时副本磁盘上的 `local/ui/m/ui-plan.js` | `index.html` 引用的文件必须存在 | FAIL（`AssertionError: False is not true : 缺少脚本文件 ui-plan.js`） |
| G2 | 向 `PHONE_STATIC` 追加未被 `index.html` 引用的 `"/extra.js"` | `PHONE_STATIC` 中每个 `.js` 须被 `index.html` 引用 | FAIL（`AssertionError: 'extra.js' not found in [...] : PHONE_STATIC 里的 extra.js 未被 index.html 引用`） |
| G3 | 在临时副本 `local/ui/m/` 新建未登记的 `extra.js` | 磁盘每个 `.js` 须在 `PHONE_STATIC` 中 | FAIL（`AssertionError: '/extra.js' not found in {...} : 磁盘脚本 extra.js 必须在 PHONE_STATIC 里`） |
| G4 | 向 `PHONE_STATIC` 重新加回 `"/app.js"` | 表中不得再有 `/app.js` | FAIL（`AssertionError: '/app.js' unexpectedly found in {...}`） |

### 2.2 `test_phone_ui.py::PhoneScriptSplitGuardTests`

守卫规则：
1. `test_manifest_scripts_have_unique_top_level_declarations`：清单内所有脚本顶格 `function`、`const`、`let`、`class` 声明名字互不重复；
2. `test_manifest_scripts_strict_order_and_single_boot`：每份第一行为 `"use strict";`；`model` 开头的文件全部排在 `ui` 开头的文件之前；`if (document.readyState !== "loading") wire();` 与 `else document.addEventListener("DOMContentLoaded", wire);` 两行只出现在最后一份脚本中。

临时副本反证记录：

| 反证编号 | 临时副本篡改方式 | 触发规则 | 实际结果 |
|---|---|---|---|
| G5 | 在 `ui-shell.js` 末尾追加顶格 `function renderPair() {}` | 顶格声明名字互不重复 | FAIL（`AssertionError: 'renderPair' unexpectedly found in {...} : 顶格声明 renderPair 重复：ui-session.js:117 与 ui-shell.js:281`） |
| G6 | 删去 `model.js` 第一行的 `"use strict";` | 每份第一行须为 `"use strict";` | FAIL（`AssertionError: False is not true : model.js 第一行必须是 "use strict";`） |
| G7 | 在 `index.html` 中把 `model-conflict.js` 移到 `ui-session.js` 之后 | `model` 开头的文件必须排在所有 `ui` 开头的文件之前 | FAIL（`AssertionError: True is not false : model-conflict.js 必须排在所有 ui 开头的文件之前`） |
| G8 | 把两行启动代码复制到 `ui-session.js` 末尾 | 启动两行只能出现在最后一份脚本 | FAIL（`AssertionError: 'if (document.readyState !== "loading") wire();' unexpectedly found in [...] : 非最后一份脚本 ui-session.js 不得包含启动行`） |
