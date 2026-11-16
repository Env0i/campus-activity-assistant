# 计划栏搬成模块：把两个状态脚本与计划栏本体按层拆进 `features/plan`

这一批只搬不改。`state/plan.js`、`state/task-display.js` 两个普通脚本整个搬走，`views/plan-panel.js` 里画计划栏本体的 28 个函数与两个常量搬进新目录，函数体、常量与注释逐字照搬；控制器、检查清单、开始前门禁、倒计时点阵、路线、横幅、底栏与按钮门禁这一批不动，留在 `plan-panel.js`（它从 1358 行降到 748 行）。

## 一、搬了什么

| 原位置 | 去处 | 内容 |
|---|---|---|
| `state/task-display.js`（248 行） | `features/plan/state-task.js`（246 行） | 任务展示纯模型：状态归类、阶段/文案/细节投影 |
| `state/plan.js`（175 行） | `features/plan/state.js`（110 行）+ `features/plan/actions.js`（72 行前段） | 事件归属、代次合并、计划结论统计（状态层）；写状态后重画的三个函数（编排层） |
| `views/plan-panel.js` 的 28 个函数与 2 个常量 | `features/plan/state-board.js`（232 行）、`view.js`（383 行）、`actions.js` | 纯推导 15 个、画 DOM 11 个、会调 `refresh` 的 1 个 |
| `index.html` 两行 `<script>` | 删掉 | `state/task-display.js`、`state/plan.js` 不再存在 |
| `features/login/actions.js` | 加一行 import | 它的 `setLogin` 直接调 `paintSelected()` / `paintBoardActions()`，模块之间要显式导入 |

`main.js` 与 `app.js` 这一批**没有新增或删除任何行**：加载期引用核对结果是 0 行（见 `move-map.md` 第五节）。每个名字去了哪个文件、按哪条规则归层，逐条写在 `move-map.md`。

## 二、怎么保证「没改」

- **逐字核对**：`scripts/move_check.py` 从开工 HEAD `abd2a6a` 取三个原文件，按「紧挨着的注释 + 顶层声明」切成 **58 段**，逐段到新位置找一字不差的一段——**58 段全部找到且相同**，找不到 0 段、找到但不同 0 段。反过来把新文件里不属于原文的行分类，**分不进任何一类的是 0 行**。`plan-panel.js` 与开工 HEAD 相比**只少了搬走的段**。
- **行为没变**：现有测试的断言一个字没改（第六节对账），本机版全量通过。
- **缺陷仍然测得出来**：`net-after-move.md`，同一份 365 行清单在搬之前与搬之后逐行对照。

## 三、结论数字

| 项 | 数字 |
|---|---|
| 顶层声明段 | 58 段，逐字找到 58 段，找不到 0 段 |
| 新文件里无法归类的行 | 0 行 |
| `plan-panel.js` | 1358 行 → 748 行，只少了搬走的段 |
| 新文件行数 | 110 / 72 / 246 / 232 / 383，都没有超过 500 |
| 真加载冒烟（搬之前 / 搬之后） | 通过 / 通过（宽档、430 宽窄档、结果页三条） |
| 搬后重跑安全网 | 已守 354 条**全部仍红**；等价 10 条**全部仍不红**；出口 P14 仍红；变异不成立 0 条 |
| 模块图守卫 | 五类问题（顶层循环、缺 import、跨层引用、没挂回的模块名字、挂了没人用）都为空 |
| 代码形状 | `check.py` 通过；`plan-panel.js` 从名单甲换档到名单乙（748），两条函数键改到 `features/plan/view.js`，没有新增项 |
| 分层白名单 | 删掉 `state/plan.js` 一整组与 `views/plan-panel.js` 的 `refresh`，没有新增项 |
| 本机版全量 | 3008 条，2 条失败都不在本轮改动范围（见第六节） |

## 四、预计与实际时长

- **预计**：约三小时（冒烟 40 分钟、搬家与接线 70 分钟、逐字核对与搬后重跑安全网 40 分钟、全量回归与文档 40 分钟）。
- **实际**：约两小时。搬家与接线本身约 40 分钟；逐字核对调试了一会儿口径（`export` 前缀、文件头注释怎么算）；搬后重跑安全网 365 行前后跑了四遍——前两遍的行清单位置与替换值来自一份过期的中间产物（条件变异丢了 `if` 关键字、出现次数把注释里的同名字样算进去了），换成「从开工 HEAD 用同一份生成器重新生成」之后才拿到干净结果，最后一遍约 12 分钟。

## 五、复跑命令

```bash
# 代码结构三件套与代码形状
python -B tools/code_shape/check.py
python -B -m unittest discover -s local/tests -p test_code_shape.py
python -B -m unittest discover -s local/tests -p test_ui_layers.py
python -B -m unittest discover -s local/tests -p test_ui_modules.py

# 真加载冒烟
python -B -m unittest discover -s local/tests -p test_ui_plan_move_smoke.py

# 逐字核对
python -B design/evidence/2026-11-16/plan-move/scripts/move_check.py

# 搬后重跑安全网（365 行，四进程）
python -B design/evidence/2026-11-16/plan-move/scripts/net_after_move.py --workers 4 --out <输出目录>/net-after.json

# 计划栏相关测试与全量
python -B -m unittest discover -s local/tests -p test_ui_plan_board.py
python -B -m unittest discover -s local/tests -p test_ui_plan_flow.py
python -B -m unittest discover -s local/tests -p test_ui_contract_plan.py
python -B -m unittest discover -s local/tests -p "test_*.py"
```

## 六、现有测试的对账

| 文件 | 改动 |
|---|---|
| `local/tests/test_ui_contract_list.py` | 一处读法：空态文案改读 `ui/features/plan/view.js`；同一条用例的切片终点从 `updateControls` 改成读到文件末尾（`taskHtml` 与 `updateControls` 搬到了两个文件）。断言零改动 |
| `local/tests/test_ui_contract_shell.py` | 一处读法：`LATE_WINDOW_S` 改读拼接文本 `ui/app.js`（读单文件会带上 `export ` 前缀，原正则匹配不上）。断言零改动 |
| `local/tests/test_prerefactor_fixes.py` | 两处文档字符串 + 副本变异目标改到 `features/plan/actions.js`。断言与变异点文字零改动 |
| `local/tests/test_ui_main_window_plan.py` | 一处注释里的路径 |
| `docs/UI_SPEC.md` | 5.19 开头那句的文案来源 |
| 其余测试 | 一个字没动 |

`test_retry_phone_policy.py` 与 `tools/qa_runtime_reliability.py` 计划里点了名，实际不需要改：前者没有 `state/plan.js` 字样，后者那一处写的是 `plan-panel.js loginReady`，而 `updateControls` 这一批留在原处。

**全量**：`python -B -m unittest discover -s local/tests -p "test_*.py"` 跑 3008 条（比上一批多出本批新增的三条真加载冒烟），2 条失败：

- `test_grab_log.LogLockTests.test_two_processes_append_and_rotate_without_losing_lines`：两个进程往同一个日志里写 160 行，共享盘上偶发丢一行（159 != 160），单独复跑通过；
- `test_phone_http.RejectionTests.test_cookies_after_stop_are_rejected`：本机 HTTP 请求走代理拿到 502。

两条都与本批改动无关（都不读界面脚本），是已知环境问题；5 条跳过是缺可选依赖。

## 七、这一批没做的事

- **控制器没搬**：`controllers/plan.js`、`controllers/plan-events.js`、`controllers/tick.js` 一个字没动，下一批再说。
- **`plan-panel.js` 剩下的几段没拆**：检查清单与开始前提醒、开始前门禁与策略、路线与倒计时点阵、LED、`updateControls`、底栏分档与横幅仍在原处。
- **没有重命名、没有调语句顺序、没有合并重复、没修缺陷**：包括只被搬走代码用到的 `retryDeadline` 这种旧入口也照原样搬了过去。
- **一处计划外的动作**：为了让 `check.py` 能跑，把两个已删文件记进了 git 索引（`git update-index --force-remove`），没有 `git add` 任何内容、没有提交。见 `move-map.md` 第九节。
