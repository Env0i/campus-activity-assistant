# 登录状态机结构重构证据

## 换了什么

- 新增 `local/ui/features/login/state-machine.js`，冻结 `LOGIN_PHASES`、`LOGIN_VIEW_STATES`，用 `loginPhase` 和 `loginViewState` 承接原来的判断顺序与八个 `S.login.view.state` 取值。
- `features/login/view.js` 把胶囊的阶段判断与样子取值拆开，`LOGIN_APPEARANCES` 保存每个阶段的 class、胶囊字、副句和详情说明。DOM 写入、按钮文字、实心描边和状态卡调用沿用原语句。
- `features/login/state-relogin.js` 增加冻结的 `RELOGIN_STEPS` 与 `RELOGIN_CASES`，重新登录函数和文字没有改动。
- `docs/UI_SPEC.md` 增加状态机小节，大小名单删除已降到 60 行以内的 `paintLogin` 项。模块图期望报告仍为五类问题全空。

## 对照结论

`capsule_grid.py` 在开工 HEAD 副本与当前工作区各运行同一张网格，共 24,576 组，逐组比较 class、dataset.state、aria-label、胶囊字、副句、详情说明、按钮文字、按钮 class 和 `S.login.view` 四个字段，差异组数为 0。

当前工作区每个阶段命中数如下，所有阶段至少命中一组：

| 阶段 | 命中数 |
|---|---:|
| `plan_running` | 1,408 |
| `demo` | 10,880 |
| `auto` | 6,144 |
| `logging_in` | 3,072 |
| `checking` | 452 |
| `never` | 128 |
| `unknown` | 8 |
| `expired` | 64 |
| `valid` | 72 |
| `unset` | 108 |
| `terms` | 2,240 |

开工 HEAD 没有阶段机，脚本将其阶段统计记为旧分支 `legacy` 24,576 组，输出行仍逐组与改后结果相等。

## 变异结论

`mutate_machine.py` 在独立临时副本中按文件、函数或样子表项和目标行文字定位，共执行 67 条变异，全部由新增测试打红：

- 10 条阶段判断与默认阶段变异。
- 3 条条款覆盖例外变异。
- 10 条 `loginViewState` 映射变异。
- 44 条样子表变异，覆盖 11 个阶段的 class、胶囊字、副句和详情说明。

每条变异的第一条失败用例由脚本在运行时输出，阶段判断与清单变异落在 `test_login_machine.py`，样子表变异落在 `test_each_phase_keeps_its_visible_appearance`。

最终本机版全量运行 2,934 条，5 条跳过，只有既有发布守卫测试因 Windows/Node 非 UTF-8 诊断输出触发自身的 `None` 拼接错误，未修改该测试。登录状态机新增测试、登录胶囊、重新登录对话框、模块图、分层和代码结构检查均通过。

## 复跑命令

```text
python -B design/evidence/2026-11-16/login-machine/scripts/capsule_grid.py
python -B design/evidence/2026-11-16/login-machine/scripts/mutate_machine.py
python -B -m unittest discover -s local/tests -p test_login_machine.py
python -B -m unittest discover -s local/tests -p test_ui_login_capsule.py
python -B -m unittest discover -s local/tests -p test_ui_relogin_dialog.py
python -B -m unittest discover -s local/tests -p test_ui_modules.py
python -B -m unittest discover -s local/tests -p test_ui_layers.py
python -B tools/code_shape/check.py
node tools/code_shape/ui_modules.mjs --expect
```
