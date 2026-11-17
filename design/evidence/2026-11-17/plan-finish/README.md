# 计划栏收尾小修：外框随登录、停止记录按快照写、琥珀色例外

@author Author

开工 HEAD `6a8ac06`，分支 `refactor/step1`。这一批只动前端三处与规格，按用户 2026-11-16 的两处决定和 2026-11-12 的琥珀色例外收尾；计划栏标题区状态机与样子表一字没动。

## 改了什么、为什么

1. `state-board.js` 的 `boardPlanState` 第一行：在跑且**不是在浏览器登录**才返回 `running`。浏览器登录窗口开着时 `S.busy` 也为真，但那时没有计划在跑（`doLogin` 一开头就在 busy 时返回），外框按没在跑画，和标题区的「登录中」一致。其余各行不动。
2. `actions-run.js`：后端回「当前没有这个计划」时，原来由 `stopFailed` 写「停止没成功，计划继续运行」，改为 `resyncPlanFromBootstrap(wasEditing)` 拿到快照后再写——快照说还在跑写原句，快照说已不在写「计划已经结束，修改作废」（新拟），拿不到快照保守写原句，不替后端下结论。`wasEditing` 由停止分支在进入 `stopFailed` 前记下带过来；桥接异常那一支照旧写原句，原有的第一条失败记录（后端说明）照旧。
3. `docs/UI_SPEC.md` §5.19：把「浏览器登录时外框仍按运行中画」的现状句换成新规则，并从「下一批接」清单里删掉「外框随登录」；停止没成功那段补快照说已不在时的「计划已经结束，修改作废」；在 §5.17 讲整屏边框颜色的那一节补琥珀色例外——点阵倒计时的琥珀只表示时间，不表示警告，其余「要你留意」照用琥珀。

注意：`styles.css` 里 `running` 与没在跑（`idle`）都没有专门的边框规则，两种外框在画面上看不出颜色差别。改的是 `data-plan-state` 这个属性的含义：读它的测试和 QA 脚本会看到不同，用户肉眼看不到差别。样式表按要求没动。

## 旧用例与新增用例

动手前写 `changed-tests.md`，按文字与属性全量 grep，并在临时副本里试改产品、跑 6 个相关文件：全部 6 个文件 rc 为 0、表外变红 0 条，**无需改任何旧用例**。新增 6 条只追加在 `test_plan_transitions.py` 末尾，已有 9 条一字不动。

在开工 HEAD 副本上，两条新转移（登录外框、快照说已不在）红，四条照旧守卫绿；在当前工作区（产品已改）16 条全绿。

## 变异结论

`scripts/mutate_finish.py` 按「文件、函数、那一行的文字、第几次出现」定位，逐条变异 9 处：外框条件的去掉与取反、快照两句话对调、`wasEditing` 判断去掉、catch 那句去掉、改由 `stopFailed` 继续写原句、桥接异常那支去掉、原有第一条说明去掉、`wasEditing` 没带进对账分支。每条在临时副本里先过 `node --check`，再按 `test_plan_transitions.py` → `test_ui_plan_flow.py` → `test_ui_plan_board.py` → `test_ui_contract_plan.py` → `test_prerefactor_fixes.py` 首红即停，四个进程并行。

- 9 条里 9 条红，无一绿、无定位失败与解析失败。
- 7 条红在新测试「用户看得到」的外框或运行记录断言上；「桥接异常那支不再写」红在上一批已有的「修改中停止没成功」用例上（该支本就该不变）。
- 没有等价变异，无需补断言。

## 全量回归与守卫

本机版全量结果见结果文件；`test_ui_modules.py` 与 `tools/code_shape/check.py` 通过，模块图期望值用 `node tools/code_shape/ui_modules.mjs --expect` 重新生成后文件无变化（内容没变就不改）。大小名单、分层白名单、ruff 例外都没加项。

## 复跑命令（仓库根）

```bash
python -B -m unittest discover -s local/tests -p test_plan_transitions.py
python -B design/evidence/2026-11-17/plan-finish/scripts/mutate_finish.py --workers 4
python -B -m unittest discover -s local/tests -p "test_*.py"
node tools/code_shape/ui_modules.mjs --expect
python -B tools/code_shape/check.py
```

解释器用项目自带的 Python 3.12：默认解释器没装 webview，全量会少收集用例。临时副本只放在系统临时目录，复制时跳过数据根、配置与工作区元数据。
