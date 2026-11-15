# 登录块：补行为测试之前与之后的变异结论

这一批只加测试与证据，产品代码、现有测试、夹具、工具、文档一个字没动。要回答的问题是：登录块里「认结论与认步骤」的每一行、以及「读进行中标志」的每一行，今天有没有用户可见的行为测试守着。

## 量什么

两份清单都来自登录块三份界面脚本（`local/ui/state/login.js`、`local/ui/views/login.js`、`local/ui/views/relogin.js`）：

- **表甲**：认结论与认步骤的行——胶囊文字与色调、登录按钮文案与实心/描边、详情卡说明、重新登录对话框的标题、副句、当前哪一步、底栏按钮、红字。
- **表乙**：读进行中标志的行——`S.busy`、`S.autoLogin`、`S.login.checking`、`S.login.loginPending`、`S.relogin.open`、`S.relogin.flowId` 这些标志被读来决定「画什么」或「做不做」的地方。

两表合计 118 行，其中 6 行与别处是同一处判断（表乙里标「复用」的），实测 112 行。

## 口径

`scripts/mutate_login.py` 在 `tempfile.mkdtemp()` 的副本里逐行改一处（带条件的那一行整行换成空语句、条件取反、返回值换掉），按「文件 + 函数 + 那一行的原文」定位，不按行号；改完跑登录相关的界面测试，记下变红的用例与第一条失败的断言，然后还原。

四种结论：

- **行为测试已守**：变红的用例里至少有一条是跑 node 的行为用例（在整页沙箱里摆状态、看用户可见结果）；
- **只有字面断言守**：变红的全是读源码文本的契约用例；
- **没人守**：一条都没红；
- **等价**：换掉以后用户看到的东西和发出的请求都不变，理由写在那一行里。

## 结论数字

| 时点 | 行为测试已守 | 等价 | 没人守 | 只有字面断言守 |
|---|---|---|---|---|
| 补测试前（`before.md`） | 53 | 0 | 64 | 1 |
| 补测试后（`after.md`） | 109 | 3 | 0 | 0 |

补完以后剩下的 3 条等价：`reconcileAutoLogin` 的早退（余下分支只把同一个标志再置一次 false）、`loginEstimateShort` 的「时钟不可用」分支（落到兜底拼出来的字面完全相同）、`setLogin` 里「已转人工就不点亮自动登录」那一行（紧接着的 `reconcileAutoLogin` 会把它收回，最终状态不变）。`expiryText` 的有锚点分支本来是第 4 条「等价」，本批补了胶囊「预计约到 …」的用例以后它已经能被抓住。

## 补出来的用例

- `local/tests/test_ui_login_capsule.py`（21 条）：胶囊按登录结论挑文字与色调、副句只报事实、有锚点时写明「预计约到 …」、忙碌时仍报结论、转人工后收回「自动登录中…」、登录窗口开着时不自动刷新列表、详情卡「检查」按钮在忙碌与检查中禁用。
- `local/tests/test_ui_relogin_dialog.py`（41 条）：按「有没有保存账号 × 保存的密码有没有被拒绝」落到不同入口；自动登录与浏览器登录两条路的标题、副句、等待行、底栏；关闭时取消 / 不取消这一场的两种情况；验证码认错留在输验证码那步并给红字；对话框关着时后台回来的结果不推进流程。

D6 要求的五个场景分别由谁守：

| 场景 | 用例 |
|---|---|
| 启动第一次检查不显示成已登录或失效 | `test_ui_login_capsule.py::test_checking_without_a_saved_session_says_checking` |
| 自动登录中不先闪红 | `test_ui_login_capsule.py::test_busy_plan_says_auto_login` |
| 条款没同意时写等同意条款、按钮不可用 | `test_ui_login_capsule.py::test_waiting_terms_says_so` + `test_ui_contract_shell.py::test_terms_unaccepted_disables_the_school_actions` |
| 自动登录进行中关掉对话框不取消这一场 | `test_ui_relogin_dialog.py::test_closing_keeps_the_computers_own_auto_login` |
| 用户自己手输验证码认错（后端换了一张图）后留在输验证码那一步 | `test_ui_relogin_dialog.py::test_typed_wrong_code_stays_on_code_step_with_grey_tries_note` |
| 电脑认不出验证码、转人工时给出红字 | `test_ui_relogin_dialog.py::test_wrong_captcha_keeps_the_code_step_with_a_red_hint` |

现码手输认错不出红字（只给灰字次数说明），与 D6 原文「给出红字」不一致，留给状态机那一步处理。

## 搬家用的事实

`move-facts.md` 五张表由 `scripts/move_facts.py` 出：块内名字被谁引用（含加载期，加载期引用有两处，都在 `app.js` 顶层（L251 取值、L252 调用），搬 `relogin` 之前要先挪进 `main.js`）、状态字段的写点与读点、反向调用（块内调用了哪些别的层）、`controllers/refresh.js` 每个函数该归哪条链路（只有 `checkRoundOpen` 属于登录检查）、三个通用名字（`addLog` / `setBusy` / `setResult`）现在寄住在 `views/login.js`，搬之前得先挪到公共层。

## 复跑

```bash
# 全量变异，按 8 片并行；结果写 JSON，再汇总成 after.md 的表
python -B design/evidence/2026-11-15/login-net/scripts/mutate_login.py --shard-index 0 --shard-count 8 --out out-0.json
# 只重跑指定的几条
python -B design/evidence/2026-11-15/login-net/scripts/mutate_login.py --ids J15,J21,J23,Y12
# 两个新增测试文件
python -B -m unittest discover -s local/tests -p test_ui_login_capsule.py -v
python -B -m unittest discover -s local/tests -p test_ui_relogin_dialog.py -v
# 搬家事实
python -B design/evidence/2026-11-15/login-net/scripts/move_facts.py
```

`mutate_login.py` 的 `--verify` 用来确认每条定位串在源码里唯一存在；`--baseline` 只跑原始副本，用来确认测试本身是绿的。
