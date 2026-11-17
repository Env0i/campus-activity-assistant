# 搬完重跑安全网：56 条已守与 1 条等价在新位置各做一次

@author Author

## 行清单怎么来的

`rows.json` 一条一行。来自 `design/evidence/2026-11-17/plan-net/after.md`（基线提交 `3091a3a`，339 条 plan-panel 候选）里**结论是「已守」或「等价」**、且函数落在本批搬走的 28 个名字里的行。候选的函数、那一行的文字、第几次出现、变异写法都由 `mutate_plan.py --list --json` 在基线 `3091a3a` 的源码上枚举（690 条，与 after.md 同一基线、编号一致），只把 `path` 换成搬后的新位置。剥注释、跨行表格与转义管道都按原文解析，没有手抄。

本批 28 个函数的候选判定分布：**已守 56、等价 1、没人守 33**（共 90 条）。只跑已守与等价的 57 条——没人守的那 33 条搬前就没人守，缺口仍在 after.md 里，本批不补。

## 怎么跑的

`scripts/net_after_move.py`：每条在自己的临时仓库副本里改一处（按新位置的函数、行文字、第几次定位），先过 `node --check`，再跑 after.md 记录的那个测试文件，没变红再跑其余四个；四进程并行。已守行必须仍红，等价行应仍绿。

## 结论

| 项 | 结果 |
|---|---|
| 行清单 | 57 条（已守 56、等价 1） |
| 状态计数 | red 56、green 1 |
| 已守但仍绿 | 0 |
| 等价却变红 | 0 |
| 定位失败 / 语法错 | 0 / 0 |

## 落点对照

| 搬前 | 搬后 | 已守行 |
|---|---|---|
| `views/plan-panel.js` · `startBlocker` | `features/plan/view-draft.js` · `startBlocker` | 红 |
| `views/plan-panel.js` · `paintWhy` | `features/plan/view-draft.js` · `paintWhy` | 红（另 1 条等价仍绿，M148） |
| `views/plan-panel.js` · `updateControls` | `features/plan/view-controls.js` · `updateControls` | 红（大头） |

其余落在 28 个函数里的候选搬前就是「没人守」或「不成立」，没有已守行可重跑。

## 计划相关六个出口

P03（`reconcileStart`）、P05（`presentPlanDone`）、P07（`startPlan`）、P08（`adoptPlan`）、P13（`clearSelection`）、P14（`handlePlan`）六个出口的函数体**本批一字未改**：逐字比对 `HEAD` 与工作区，四个函数体全部相同；`actions-start.js` 只多了三行 import。因此上一批 `plan-actions-move/net-after-move.md` 里「六个出口全部仍红」的结论继续成立，本批不再重复跑——本批没有动这些出口所在的逻辑，只加了 import 与搬走文件中与本批 28 个函数无关的部分。

## 一个落点调整的记录

`planCheckList` 与 `startBlocker` 原预分进 `state-draft.js`，但两者用 `views/terms.js` 的 `termsUpdateMode`，搬进状态层会触发跨层。按 R1 执行时核对改归 `view-draft.js`，函数体一字未动；`view-dock.js` 对 `startBlocker` 的 import 相应改从 `view-draft.js`。理由详见 `move-map.md` 第十一节。落点调整后安全网仍全部成立（含 `startBlocker`、`paintWhy` 的已守行）。
