# 计划栏控制器搬成模块

## 这一批做了什么

`local/ui/controllers/plan.js`（532 行）与 `local/ui/controllers/plan-events.js`（134 行）**整个搬走**，按「开始 / 运行中 / 事件 / 浏览器登录」四段落进模块：

| 新文件 | 行数 | 里面是什么 |
|---|---:|---|
| `local/ui/features/plan/actions-start.js` | 290 | `startPlan`、`START_QUERY_TIMEOUT_MS`、`reconcileStart`、`adoptPlan`、`restoreEditedPlan` |
| `local/ui/features/plan/actions-run.js` | 148 | 停止确认（`stopAskOpen` 一族、`stopPlan`、`confirmStopPlan`、`doStopPlan`）、`cancelTask`、`modifyPlan`、`noteStartedFromPhone`、`editPausedLine`、`reselectFailed`、`finishResult` |
| `local/ui/features/plan/actions-events.js` | 139 | `presentPlanDone`、`handlePlanDone`、`restartStoppedPlan`、`loggedConclusion`、`showTaskResult` |
| `local/ui/features/login/actions-browser.js` | 111 | `doLogin`、`handleDone`、`loginFailCopy` |

配套改动：`index.html` 少两行 `<script>`；`app.js` 顶层那 8 个「把函数名直接当回调」的绑定原样挪进 `main.js`（模块里 import，不经 `window`）；`legacy-globals.js` 按守卫报告新挂回 8 个名字、撤掉 11 个已无人用的名字、删掉 `attachPlanGlobals` 里重复的那段注释；`actions-relogin.js` 加一行 `doLogin` 的 import，`features/plan/actions.js` 加两行（`noteStartedFromPhone`、`showTaskResult`）。

逐个名字的去处与理由、8 行的监听器核对、挂回名单逐个谁在用、五处路径文字改动，见 `move-map.md`。

## 顺手修掉的：`check.py` 读已删文件就崩

`tools/code_shape/check.py` 的 `list_sources` 照着 `git ls-files --cached` 列文件，索引里还在、磁盘上已删的文件会去读一个不存在的路径然后崩。前两批搬家的执行方都只好先动 git 索引（这违反「不碰暂存区」）。这一批先修它：过滤条件加一条 `(ROOT / f).exists()`，别的一字未动；`test_code_shape.py` 末尾加一条用例——临时 git 仓库里放一个已跟踪文件、从磁盘删掉、不改索引，`list_sources` 不再列出它。

修好以后，这一批删两个控制器文件**只从磁盘删**，暂存区一步没碰（开工与收工的 `git status` 里那两条都是 ` D`，不是 `D `）。

## 口径

- **只搬不改**：函数体、常量、注释一字不差，只加 `export`、单行具名 `import` 与一行文件头注释。
- **逐字核对**：段 = 一个顶层函数或常量 + 紧挨着它上方的注释；文件末尾没有归属的注释跟着最后一个函数走。每段去掉 `export ` 前缀后，必须在四个新文件里找到一字不差的一段。
- **搬后重跑安全网**：只跑计划栏安全网那一批里**已守**、且落在这两个控制器里的行——函数名、那一行的文字、第几次出现、变异写法一字不改，只换文件路径；另加出口那一批的六个计划相关出口。
- **真加载冒烟**：按 `index.html` 的顺序跑普通脚本，再用真实动态 import 加载 `main.js`，宽档与 430×820 窄档各跑一遍。

## 结论数字

| 项 | 结果 |
|---|---|
| 逐字核对 | 26 段（`plan.js` 21、`plan-events.js` 5）**全部找到且一字不差**；0 段缺失、0 段不同 |
| 新文件里不属于原文的行 | 0 行（文件头 4 行、import 16 行、`export ` 前缀都归了类） |
| `app.js` 与开工相比 | 只少那 8 行；`main.js` 只多 2 行 import、2 行注释与这 8 行 |
| 搬后安全网 | 68 条已守**全部仍红**；六个出口**全部仍红**；0 语法错、0 定位失败 |
| 真加载冒烟 | 搬前 7/7 通过，搬后 7/7 通过；删掉 `main.js` 里 `#btn-stop-yes` 那行后，只有「停止先弹确认」那条变红（宽窄两档） |
| 模块图守卫 | 五类问题全空（循环、缺 import、层违规、未挂回、挂了没人用） |
| 代码形状 | `check.py` 通过；名单只有删项与三条键名改动，没有新增 |
| 本机版全量 | 3013 条：**没有新增失败**；3 条失败是已知环境问题（见下） |

## 全量回归

`python -B -m unittest discover -s local/tests -p "test_*.py"` 跑 3013 条（比上一批多出本批新增的四条冒烟与一条 check.py 用例），3 条失败，都不是这一批带来的：

- `test_grab_log.LogLockTests.test_two_processes_append_and_rotate_without_losing_lines`：两个进程往同一个日志里写，共享盘上偶发丢一行；
- `test_session_writer.SaveSessionTests.test_two_processes_saving_together_lose_nothing`：两个进程抢 `session.json.lock`，同一类共享盘偶发；单独复跑三次全过；
- `test_phone_http.RejectionTests.test_cookies_after_stop_are_rejected`：本机 HTTP 请求走代理拿到 502。

5 条跳过是缺可选依赖（`ddddocr`、`ruff`）。第一轮全量还红过两条 `test_ui_contract_feedback` 的用例——它们按位置切「联合源码」，模块顺序变了就切反；改完读法后复跑通过，见 `move-map.md` 第七节。

## 时长

- 预计 **60 分钟**（开工前写下：prep 20、move 20、verify-move 20，其中搬后安全网与全量可重叠）。
- 实际约 **30 分钟**：开工 01:05，收工 01:35（含两轮全量回归——第一轮红了两个契约测试，修完读法又跑了一遍）。
- 搬后安全网 74 行只用了 25 秒——大半行在记录的那个测试文件上首跑就红，不用跑满五个文件。

## 复跑命令

```bash
python -B design/evidence/2026-11-17/plan-actions-move/scripts/move_check.py
python -B design/evidence/2026-11-17/plan-actions-move/scripts/net_after_move.py --workers 4 --out /tmp/net.json
python -B -m unittest discover -s local/tests -p test_ui_plan_move_smoke.py
node tools/code_shape/ui_modules.mjs
python -B tools/code_shape/check.py
```

`net_after_move.py` 读同目录的 `rows.json`（一条一行：新位置、函数名、那一行的文字、第几次出现、变异写法、预期结论），在 `tempfile.gettempdir()` 下的仓库副本里改一处、`node --check` 通过后跑测试，仓库本体不动。

## 已知限制

- 两个控制器在安全网那一批里共 209 条候选，其中 127 条当时就没变红（没人守）、14 条变异不成立；这一批按 A10 只重跑**已守**的 68 条，那 127 条的缺口没有变化，仍在 `design/evidence/2026-11-17/plan-net/after.md` 里。
- `plan-events.js` 当时不在安全网范围内，所以它自己没有「已守」行可重跑；它的出口 `P05` 与逐字核对覆盖了它。
- `restoreEditedPlan` 的实际落点是 `actions-start.js` 而不是计划里写的 `actions-run.js`：照计划会形成 `run → start → events → run` 的顶层循环，改放之后依赖成一条直线。函数体一字未动，理由写在 `move-map.md` 第三节。
- 上一批提交的 `design/evidence/2026-11-16/plan-move/scripts/net_after_move.py` 里，`restore` 函数在最后一次改写时被误删（当时那一次运行用的是删改之前的版本，结果本身有效）。**提交前已补回**：还原清单从行清单里现算、基线副本里没有的文件跳过，行清单指向已删文件时记定位失败而不是抛异常。因此那份脚本对着今天的树也能跑完（68 行报「文件不在这次的树里」，其余照旧）。同一类问题在 `login-machine/scripts/capsule_grid.py` 的复制函数里也修了：跳过磁盘上已删的跟踪文件，并把未跟踪的新文件一并复制。
