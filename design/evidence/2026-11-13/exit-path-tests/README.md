# 步骤 1 出口行为测试的证据（计划 20261113-refactor-step1-exit-tests）

- **量的是什么**：桌面端 `local/ui` 每个进行中状态的 47 个出口语句（D2 变异表，
  行号以 dddc179 为准）在补测试之前有没有行为测试守着；补完之后，每个出口
  要么有行为测试守（变异变红），要么写不出行为用例的记「等价」。
- **基线提交**：`682463d`（分支 refactor/step1；`local/ui` 自 dddc179 以来零变动，
  脚本逐行核对通过）。执行日期：2026-11-14。
- **变异怎么做**：`scripts/mutate_exits.py` 把某一行的该状态赋值换成空语句
  （同一行的条件与 `return` 等其他语句原样保留）。只在 `tempfile.gettempdir()`
  下的仓库副本里做，仓库本体不动；副本按 `git ls-files`（已跟踪 + 未跟踪未忽略）
  复制，被忽略的文件一个都不带。每条变异做之前先核对该行仍是对该状态的赋值，
  做完先 `node --check`，再跑 D3 测试集合（`test_ui_*.py`、`test_prerefactor_fixes.py`、
  `test_phone_ui.py`，含本计划新建的四个文件）；可同时开最多四个副本并行
  （`--shard i --shards 4`）。
- **行为测试怎么认定（D1）**：脚本用 ast 解析测试文件——`test_` 函数体内
  （含经同类方法与同文件辅助函数传递）最终调到 `fixtures/ui_harness.py` 的
  `run_js`，或同文件里最终用 subprocess 跑 node 的辅助函数，才算行为测试；
  其余算字面断言。本轮 47 条变异的变红用例全部是行为测试，「只有字面断言守」
  始终为 0。
- **两张表的汇总数字**：
  - `before.md`（补之前）：没人守 25、行为测试已守 22、只有字面断言守 0（共 47 行）。
  - `after.md`（补之后）：行为测试已守 47、没人守 0、只有字面断言守 0、等价 0。
  - 「等价」清单为空：25 条没人守的出口全部补出了行为用例，没有需要按 D6 记等价的。
- **新补的用例**（每个出口一条，用例名带编号，只做行为断言）：
  - `local/tests/test_ui_exit_paths_login.py`（L01、L03、L04、L05、L07、L08、L09、L11、L12）
  - `local/tests/test_ui_exit_paths_plan.py`（P03、P05、P07、P08、P13、P14）
  - `local/tests/test_ui_exit_paths_list.py`（R03、R04、R05）
  - `local/tests/test_ui_exit_paths_components.py`（C01、C02、C03、C04、C06、C07、C09）
  - 每条新用例的两侧证据（未变异通过、对应变异变红）都可以用下面的复跑命令重做。
- **复跑命令**（仓库根，Python 一律带 `-B`；临时目录一律在
  `tempfile.gettempdir()` 之下，不写死盘符）：

  ```bash
  # 未变异基线（必须 0 失败）
  python -B design/evidence/2026-11-13/exit-path-tests/scripts/mutate_exits.py --baseline --save-output <结果目录>
  # 全部 47 条（补之前 / 补之后），可加 --shard i --shards 4 并行
  python -B design/evidence/2026-11-13/exit-path-tests/scripts/mutate_exits.py --phase 补之前 --out before.md
  python -B design/evidence/2026-11-13/exit-path-tests/scripts/mutate_exits.py --phase 补之后 --out after.md
  # 只跑指定编号（核对单条新用例的「变异变红」）
  python -B design/evidence/2026-11-13/exit-path-tests/scripts/mutate_exits.py --ids L01,R03,C09 --save-output <结果目录>
  ```
