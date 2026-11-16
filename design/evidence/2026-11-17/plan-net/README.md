# 计划栏安全网：分支与进行中标志的逐条变异

## 这一轮做了什么

把计划栏五个源码文件里决定「显示哪种结论、给哪个按钮、读哪个进行中标志」的分支与读取点逐条列出来，
一共 690 条候选，在仓库副本里一条一条改坏，看现有测试能不能当场变红。改坏只在临时副本里做，
仓库本体的产品代码、已提交的测试、夹具、工具一个字没动；新增用例只进两个计划栏行为测试文件。

- **候选怎么来的**：`scripts/mutate_plan.py` 按函数枚举 `if` / `else if` 的条件、三元的两支、
  挑文字或按钮的 `&&` 与 `||`，以及读 `S.busy`、`S.starting`、`S.stopping`、`S.editing`、
  `S.startRequest` 及其字段、`S.verifyAsked` 的每一处（赋值不算）。
- **定位**：文件、函数、那一行的文字、第几次出现；不用行号。生成后先在副本上逐条自检，690 条都恰好命中一次。
- **范围**：`views/plan-panel.js` 只取 26 个计划栏函数，`controllers/tick.js` 只取 `tick()` 里读忙态与编辑态的三处；
  其余函数（倒计时点阵、路线、横幅、底栏、检查清单、场次票、策略行、窗口分档等）不在本轮范围，
  删掉 232 + 48 = 280 条。不分范围本可生成 970 条。
- **怎么跑**：每条只改一处，改完先过 `node --check`，再按 `plan_flow` → `plan_board` → `exit_paths_plan`
  → `main_window_plan` → `contract_plan` 的顺序跑五个测试文件；第一个变红就停跑这一条，记下第一个失败的用例。
  单个测试文件 120 秒，超时算这一条要复跑，复跑仍超时就停下报告（本轮没有超时）。四进程并行，
  每个进程各复制一次仓库、改完跑完就还原。

## 结果

| 项 | 数量 |
|---|---:|
| 候选 | 690 |
| 补测前变红 | 242 |
| 补测前没变红 | 434 |
| 补测后变红（有跑 node 的行为用例守着） | 354 |
| 补测后判等价（入口清单见 `after.md` 的 §1、§2） | 10 |
| 补测后仍没人守 | 312 |
| 变异不成立（赋值点被当成读取） | 14 |

补测后新增 27 条行为用例（`test_ui_plan_board.py` 20 条、`test_ui_plan_flow.py` 7 条），
变红的 354 条全部落在跑 node 的行为断言上；只有字面断言守的为 0。

`before.md` 是补测前的逐条结论（一行一条），`after.md` 是补测后重跑的逐条结论，
末尾按函数列出还没人守的分布。**这一轮没有做到「没人守为零」**，剩下的 312 条要接着补，
逐条编号在 `after.md` 里。

## 复跑命令

```text
python -B design/evidence/2026-11-17/plan-net/scripts/mutate_plan.py --workers 4
python -B design/evidence/2026-11-17/plan-net/scripts/rerun_plan.py --function paintSelected
python -B design/evidence/2026-11-17/plan-net/scripts/rerun_plan.py --ids M001,M002 --tests test_ui_plan_board.py
python -B design/evidence/2026-11-17/plan-net/scripts/probe_plan.py M001 --snippet 片段.js
python -B -m unittest discover -s local/tests -p test_ui_plan_board.py
python -B -m unittest discover -s local/tests -p test_ui_plan_flow.py
python -B tools/code_shape/check.py
```

`mutate_plan.py` 一条命令跑完全部候选，`--workers` 是并行进程数（默认 4）。
`rerun_plan.py` 按文件、函数、种类或编号挑一部分候选复跑，补完一条用例后用它看这一组有没有变红。
`probe_plan.py` 在同一段界面片段上比较「未变异」与「这一条变异」的输出，用来判等价。

## 已知限制

- **沙箱缺计时能力**：夹具的 `setTimeout` 只记账不调度，开始请求的 15 秒对账、5 秒查询超时这几条
  写不出用例（要补得先给夹具加可手动触发的定时器，本轮不改夹具）。
- **14 条变异不成立**：`S.startRequest.state`、`.gen`、`.timer`、`.queryTimer`、`.reconcile` 的赋值点
  被生成器当成了读取，替到等号左边后语法不成立；它们不计入红，也不计入没变红。
- **本轮没有提交**：`auto_commit: false`，改动留在工作区。
