# 计划栏标题区状态机的结构重构证据

开工 HEAD `02c8760`（`refactor/step1`），只换结构，不改行为。

## 换了什么

- 新增 `local/ui/features/plan/state-machine.js`：冻结的 `BOARD_PHASES` 列出十九个阶段，`boardPhase(facts)` 只看调用方抄好的事实，按原分支的先后返回其中一个。在跑的三支与没选活动的六支各收成一个小函数，判断条件逐字照抄原分支。状态层不碰 DOM、不读 window、不读时钟、不调别的函数。
- `features/plan/view.js` 新增 `BOARD_STYLE`：一个阶段一项，写标签字、色调、圆点、标题、副行（或副行 HTML）、地点时间。要看别的事实的（结果页、运行中的标签与说明、条款未知与否、已选场次数）写成小函数，函数体就是原分支里的表达式。
- `paintSelected` 从 124 行的 if 长龙改成「抄事实 → 调 `boardPhase` → 查表 → 写 DOM」的 36 行。写 DOM 的方式逐字保留：`className` 置为 `b-title`、清空 `#selected-meta` 的 innerHTML、`#board-text` 先 `textContent = ""`、`setBoardTag` 的三个参数、只有「时间待校准」那一支用 innerHTML、只有「下一场 / 开放中」两支写地点时间。原分支里的注释原样挪到表里对应那一项旁边。
- `features/plan/actions-run.js` 只改一句过时注释（`editPausedLine` 现在在本文件、由 `features/plan/actions-events.js` 的计划结束处理调用）。
- `docs/UI_SPEC.md` 的 5.19 里加「计划栏标题区状态机」一段：十九个阶段各一句、先后关系、代码位置，并写明一处现状（浏览器登录时外框仍按运行中画，标题区写登录中）与下一批要接的新转移。
- 大小名单删掉 `features/plan/view.js::paintSelected`（124 → 36 行，已到 60 行以内）。模块图期望值用 `node tools/code_shape/ui_modules.mjs --expect` 重新生成，内容没有变化；五类问题全空。

## 为什么行为不变

标题区的每一段文字都来自同一批表达式：表项里的定值是原分支的字符串原文，小函数体是原分支的表达式原文（`resultView()` 的四个字段、`runTagText`、`runCaption`、`view.item`、`selectionSummary`、`S.terms.unknown` 的三元、`boardMetaHtml`）。先后顺序由 `boardPhase` 的 return 次序原样保住，写 DOM 的语句没有换写法。

## 对照结论

`scripts/board_grid.py` 用整页沙箱，在同一张网格上分别跑开工 HEAD 的副本与当前工作区，逐组比较 `#board-tag` 的 `dataset.tone` 与 `dataset.dot`、`#board-tag-text`、`#selected` 的 `className` 与标题、`#selected-meta` 的 innerHTML、`#board-text` 的 textContent 与 innerHTML。

| 运行 | 组数 | 不同 | 结论 |
|---|---:|---:|---|
| 自身对照（HEAD 对 HEAD） | 23,221 | 0 | 沙箱本身稳定，两边组数相等 |
| 改前对改后 | 23,221 | 0 | 标题区逐元素一致 |

每个阶段命中的组数（都至少命中一组）：

| 阶段 | 命中 | 阶段 | 命中 |
|---|---:|---|---:|
| `first_use` | 3,841 | `next_open` | 115 |
| `logging_in` | 9,681 | `next_upcoming` | 115 |
| `result` | 2,401 | `school_empty` | 133 |
| `terms_hold` | 770 | `clock_pending` | 64 |
| `broken` | 2,953 | `none_eligible` | 202 |
| `list_error` | 49 | `none_upcoming` | 241 |
| `list_loading` | 193 | `selected_paused` | 721 |
| `run_target` | 49 | `editing` | 1,105 |
| `run_settling` | 17 | `selected` | 554 |
| `run_preparing` | 17 | | |

网格铺开的是：在跑与否、登录窗口开着与否、修改中与否、演示与否各取真假；`present` 取真、假、未给；组件坏没坏；列表态取 ready / loading / error / 其它；条款已同意、未同意、未知；活动列表取空、全已报名、有一场正在开放、只有将来开放；已选取 0 / 1 / 2 场；可信现在有与没有；结果页开与没开；运行中的执行阶段取等开放、准备提交、提交中、汇总中与没有任务。

## 测试自带网格

`local/tests/test_plan_machine.py` 原来用 `importlib` 加载这里的 `scripts/board_grid.py`，还得先把整个仓库（连未跟踪的运行时目录一起）复制到临时目录再跑：单文件 38 秒，另有两处隐患——证据目录改名或挪走，产品测试就断；测试会连带复制别的工具的目录。

现在网格原文搬进测试文件（`GRID` 常量），直接用 `fixtures.ui_harness.run_js` 在测试自己的沙箱里跑，不读证据目录、不复制仓库，断言一条没改。两边输出核对过：23,221 组，每组的八个字段、阶段命中数、21 条具名行全部相同（0 不同），单文件 38 秒降到 13 秒。

## 变异结论

`scripts/mutate_board.py` 在各自独立的临时副本里按「文件、函数或样子表项、目标行文字」定位，四个进程并行，改完立刻还原、副本复用。

- 共 115 条变异：20 条状态机判断与阶段清单、95 条样子表项（标签字、色调、圆点、标题、副行或副行 HTML、地点时间，每个阶段逐项算）。
- **全部打红，没有不红的，也没有改完解析不了的**。
- 113 条由 `test_plan_machine.py` 打红；2 条由 `test_ui_plan_board.py` 打红（条款那一条判断里「没在跑」「登录过」两个条件各一条），后四个文件一次都没用上。

两条落在第二个文件上的变异做过单独复核：在开工 HEAD 的副本里对原分支 `paintSelected` 做同样的变异，也是 `test_ui_plan_board.py` 打红——说明这个条件本来就有测试守着，不是这一批新引入的缺口，也没有补测试。

## 时长

- 预计：对照网格每次约一分钟（实际一次约 40 秒到 1 分钟）；变异 115 条、每条先跑三个快文件、四个进程并行约 5 分钟（这一条估得不准，见下）；合计留 40 分钟余量。
- 实际：约 36 分钟（09:24 开工，10:00 收工）。变异一轮约 13 分钟——每条变异都要跑 `test_plan_machine.py`，而它里面的整页网格一次约 15 秒，比预估的「三个快文件共 4 秒」贵得多；115 条按四个进程摊下来就是十几分钟。中间还重跑过一轮：第一轮的副本里没有 `.git`，网格取文件清单时 `git ls-files` 直接报错，115 条全部「红」得没有意义——把取清单改成「有 git 用 git、没有就按目录走一遍」之后重跑，才有上面这份结果。

## 全量回归

`python -B -m unittest discover -s local/tests -p "test_*.py"`（项目解释器）跑 3,018 条：比上一批多出本批的五条，**没有新增失败**，三条失败都是已知环境问题——`test_grab_log` 与 `test_session_writer` 的跨进程锁在共享盘上偶发、`test_phone_http` 走代理拿到 502。5 条跳过是缺可选依赖（`ddddocr`、`ruff`）。

## 计划外的一处

`local/tests/test_ui_contract_feedback.py` 的第一条契约测试按文字切「大屏组件分支」那一段源码找锚点（`S.runtime.error && S.listState !== "ready"` 到 `if (!S.busy && S.listState === "error"`）。这两个分支按计划搬进了状态机与样子表，锚点文字跟着改了名，旧写法直接抛 `ValueError: substring not found`。

改法只换「从哪一段里取」：从 `boardPhase` 的组件分支取到「列表失败」分支，再从 `BOARD_STYLE` 的 `broken` 取到 `list_error`；断言与消息一个字没改，切出来的两段也确有内容（组件分支 77 字符、短状态 177 字符）。但这个文件不在本计划的 `allowed_paths` 里，所以 `allowed_only` 会报一项失败——计划漏了它（上一批的修订项里已经提过一次同样的事）。

## 复跑命令

```bash
python -B design/evidence/2026-11-17/plan-machine/scripts/board_grid.py --self
python -B design/evidence/2026-11-17/plan-machine/scripts/board_grid.py
python -B -m unittest discover -s local/tests -p test_plan_machine.py
python -B design/evidence/2026-11-17/plan-machine/scripts/mutate_board.py --workers 4
```

对照脚本固定拿 `02c8760` 当开工 HEAD；变异脚本拿当前工作区，跑完不留痕迹。
