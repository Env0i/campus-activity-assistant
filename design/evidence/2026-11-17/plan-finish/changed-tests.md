# 旧用例排查表（动手改产品之前列）

@author Author

开工 HEAD `6a8ac06`，分支 `refactor/step1`。本表在改产品之前先写：按两处决定把相关文字与属性全量 grep 一遍，
再在临时副本里试改产品、跑相关文件，确认哪些旧用例会变红。结论是**没有旧用例需要改**——表为空。

## grep 口径

检索词：`boardPlanState`、`loginPending`、`停止没成功，计划继续运行`、`计划继续运行`、`data-plan-state` / `dataset.planState`。
执行前先跑，命中逐条过一遍，不按文件名猜。

## 命中与判定

| 文件 | 命中行 | 读的是 | 判定 |
|---|---|---|---|
| local/tests/test_prerefactor_fixes.py | 126 / 145 / 161 | 运行记录里的「计划继续运行」 | 保留。126 的桩明确给 `bootstrap {busy:true}`（后端拿到旧计划号、快照仍说在跑），新口径下仍写这句；145 是桥接异常那一支，照旧写；161 断言非修改时不写，新口径下仍不写 |
| local/tests/test_ui_plan_flow.py | 121 | 运行记录里的「停止没成功，计划继续运行」 | 保留。该用例无 `bootstrap` 桩（`res.ok:false` 后对账分支拿快照失败），新口径的 catch 分支仍写这句 |
| local/tests/test_plan_transitions.py | 106 | 桥接异常那支的运行记录 | 保留。桥接异常那一支不变 |
| local/tests/test_ui_plan_board.py | 200 / 464 | 200 是登录时的标题三句（不读外框）；464 是结果页外框 | 保留。都不读 `loginPending` 时的 `data-plan-state` |
| local/tests/test_ui_contract_plan.py | 522 / 586 / 591 / 608 / 612 / 1185 | `dataset.planState`，运行/结果各态 | 保留。这些用例 `busy` 为真时 `loginPending` 均为假，不碰「登录中」那一格 |
| local/tests/test_ui_main_window_plan.py | 306 / 328 | `dataset.planState`，结果页各结论 | 保留。结果页 `busy` 为假，不碰第一行的 `running` |
| local/tests/test_ui_reliability.py | 1091 / 1178 / 1270 / 1273 | `boardPlanState()` / `dataset.planState`，终态与晚到事件 | 保留。都不在登录窗口开着的状态下读外框 |

## 副本试改结论

临时副本（排除 `local/data`、`server/data`、`config.json`、`.env`、`.workbuddy/`）里按两处用户决定试改产品代码，跑下列 6 个文件：

```
test_plan_transitions.py        test_ui_plan_flow.py           test_ui_plan_board.py
test_ui_contract_plan.py        test_ui_main_window_plan.py    test_prerefactor_fixes.py
```

6 个文件 rc 均为 0、无失败。**表外变红 0 条**，无需改任何旧用例的断言或输入。

新增用例只在 `test_plan_transitions.py` 末尾追加（已有 9 条一字不动）。在开工 HEAD 副本上，
「登录窗口开着外框按没在跑画」与「快照说已不在时写计划已经结束」两条会红，其余四条（等开放仍 running、
快照仍在跑写停止没成功、拿快照失败、非修改时不写）是照旧行为的守卫，在开工 HEAD 上绿。

## 表外变红时的停下理由

若上面 6 个文件之外再有变红，按停下条件处理：不改断言、不改口径，把现象与命中行写进结果，等裁决。
