# 搬完重跑安全网：68 条已守与 6 个出口在新位置各做一次

## 口径

- **行清单**：`rows.json`，一条一行。来自计划栏安全网那一批里**结论是「已守」**、且落在两个控制器里的 68 行；函数名、那一行的文字、第几次出现、变异写法一字不改，只把文件路径换成搬完的新位置。另加 2026-11-13 出口那一批里计划相关的六个出口（P03、P05、P07、P08、P13、P14）。
- **怎么跑**：与那一批同一条执行路径——只在仓库副本里改一处，改完先过 `node --check`；先跑它在那一批里记录的那个测试文件，没变红再跑其余四个（`test_ui_plan_flow` / `test_ui_plan_board` / `test_ui_exit_paths_plan` / `test_ui_main_window_plan` / `test_ui_contract_plan`），首红即停。四进程并行。
- **为什么只有 68 条**：那两个文件在安全网那一批里共 209 条候选，其中 127 条当时就没变红（没人守）、14 条变异不成立；A10 只要求重跑已守的那些，所以这里是 68 条，不是 209 条。
- **等价**：那一批的 10 条等价全部落在 `plan-panel.js`，这一批没有涉及。

## 数字

| 项 | 条数 |
|---|---:|
| 安全网「已守」的行：仍然变红 | 68 |
| 出口六条：仍然变红 | 6 |
| 没变红 | 0 |
| 变异不成立（语法错） | 0 |
| 定位失败 | 0 |
| 合计 | 74 |

## 逐行对照

| 编号 | 原位置 | 新位置：文件 · 函数 | 搬前 | 搬后 | 首跑的那个测试文件 |
|---|---|---|---|---|---|
| M479 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M488 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M505 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M510 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M519 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M532 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_plan_flow.py` |
| M547 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_plan_flow.py` |
| M562 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_plan_flow.py` |
| M580 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_plan_flow.py` |
| M599 | `controllers/plan.js` | `actions-start.js` · `adoptPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M623 | `controllers/plan.js` | `actions-run.js` · `stopAskKey` | 已守 | 红 | `test_ui_contract_plan.py` |
| M629 | `controllers/plan.js` | `actions-run.js` · `stopAskKey` | 已守 | 红 | `test_ui_contract_plan.py` |
| M635 | `controllers/plan.js` | `actions-run.js` · `confirmStopPlan` | 已守 | 红 | `test_ui_contract_plan.py` |
| M641 | `controllers/plan.js` | `actions-run.js` · `noteStartedFromPhone` | 已守 | 红 | `test_ui_main_window_plan.py` |
| M651 | `controllers/plan.js` | `actions-start.js` · `restoreEditedPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M656 | `controllers/plan.js` | `actions-start.js` · `restoreEditedPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M670 | `controllers/plan.js` | `actions-browser.js` · `doLogin` | 已守 | 红 | `test_ui_plan_flow.py` |
| P03 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_exit_paths_plan.py` |
| P13 | `state/filters.js` | `filters.js` · `clearSelection` | 已守 | 红 | `test_ui_exit_paths_plan.py` |
| M481 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M489 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M507 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M511 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M521 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M533 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_plan_flow.py` |
| M558 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_plan_flow.py` |
| M568 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_exit_paths_plan.py` |
| M590 | `controllers/plan.js` | `actions-start.js` · `adoptPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M607 | `controllers/plan.js` | `actions-start.js` · `adoptPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M624 | `controllers/plan.js` | `actions-run.js` · `stopAskKey` | 已守 | 红 | `test_ui_contract_plan.py` |
| M632 | `controllers/plan.js` | `actions-run.js` · `stopPlan` | 已守 | 红 | `test_ui_contract_plan.py` |
| M636 | `controllers/plan.js` | `actions-run.js` · `confirmStopPlan` | 已守 | 红 | `test_ui_contract_plan.py` |
| M642 | `controllers/plan.js` | `actions-run.js` · `noteStartedFromPhone` | 已守 | 红 | `test_ui_main_window_plan.py` |
| M653 | `controllers/plan.js` | `actions-start.js` · `restoreEditedPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M661 | `controllers/plan.js` | `actions-run.js` · `doStopPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M672 | `controllers/plan.js` | `actions-browser.js` · `doLogin` | 已守 | 红 | `test_ui_plan_flow.py` |
| P05 | `controllers/plan-events.js` | `actions-events.js` · `presentPlanDone` | 已守 | 红 | `test_ui_exit_paths_plan.py` |
| P14 | `features/plan/actions.js` | `actions.js` · `handlePlan` | 已守 | 红 | `test_ui_exit_paths_plan.py` |
| M484 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M501 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M508 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M512 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M526 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M544 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_plan_flow.py` |
| M559 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_plan_flow.py` |
| M577 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_plan_flow.py` |
| M592 | `controllers/plan.js` | `actions-start.js` · `adoptPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M610 | `controllers/plan.js` | `actions-start.js` · `adoptPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M625 | `controllers/plan.js` | `actions-run.js` · `stopAskKey` | 已守 | 红 | `test_ui_contract_plan.py` |
| M633 | `controllers/plan.js` | `actions-run.js` · `confirmStopPlan` | 已守 | 红 | `test_ui_contract_plan.py` |
| M637 | `controllers/plan.js` | `actions-run.js` · `noteStartedFromPhone` | 已守 | 红 | `test_ui_main_window_plan.py` |
| M645 | `controllers/plan.js` | `actions-run.js` · `modifyPlan` | 已守 | 红 | `test_ui_main_window_plan.py` |
| M654 | `controllers/plan.js` | `actions-start.js` · `restoreEditedPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M662 | `controllers/plan.js` | `actions-run.js` · `doStopPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M673 | `controllers/plan.js` | `actions-browser.js` · `doLogin` | 已守 | 红 | `test_ui_plan_flow.py` |
| P07 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_exit_paths_plan.py` |
| M487 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M502 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M509 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M518 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M527 | `controllers/plan.js` | `actions-start.js` · `startPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M545 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_plan_flow.py` |
| M561 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_plan_flow.py` |
| M578 | `controllers/plan.js` | `actions-start.js` · `reconcileStart` | 已守 | 红 | `test_ui_plan_flow.py` |
| M598 | `controllers/plan.js` | `actions-start.js` · `adoptPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M621 | `controllers/plan.js` | `actions-run.js` · `closeStopAsk` | 已守 | 红 | `test_ui_contract_plan.py` |
| M628 | `controllers/plan.js` | `actions-run.js` · `stopAskKey` | 已守 | 红 | `test_ui_contract_plan.py` |
| M634 | `controllers/plan.js` | `actions-run.js` · `confirmStopPlan` | 已守 | 红 | `test_ui_contract_plan.py` |
| M640 | `controllers/plan.js` | `actions-run.js` · `noteStartedFromPhone` | 已守 | 红 | `test_ui_main_window_plan.py` |
| M649 | `controllers/plan.js` | `actions-run.js` · `modifyPlan` | 已守 | 红 | `test_ui_main_window_plan.py` |
| M655 | `controllers/plan.js` | `actions-start.js` · `restoreEditedPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M663 | `controllers/plan.js` | `actions-run.js` · `doStopPlan` | 已守 | 红 | `test_ui_plan_flow.py` |
| M675 | `controllers/plan.js` | `actions-browser.js` · `doLogin` | 已守 | 红 | `test_ui_plan_flow.py` |
| P08 | `controllers/plan.js` | `actions-start.js` · `adoptPlan` | 已守 | 红 | `test_ui_exit_paths_plan.py` |

