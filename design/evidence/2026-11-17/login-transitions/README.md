# 登录状态机新转移证据

## 这批改了什么

- 前端只认后端 `auto_state`，`applyAutoState` 是唯一写 `S.autoLogin` 的位置，`receiveAutoState` 负责接收 `login_auto` 并重画。载荷没带自动登录字段时保持上一次，只有结论为 `valid` 或演示模式时收回成 `idle`。
- 状态机增加 `rechecking`、`needs_code`、`retry_later` 三阶段，分别映射为 `checking`、`bad`、`bad`，不增加 `S.login.view.state` 取值。`blocked` 只有原因是识别缺失时进 `needs_code`，其他原因仍是登录已失效。
- 样子表增加有效·确认中、要你输验证码、失效·稍后重试，剩余分钟数按单调时间向上取整。
- 登录横幅搬到 `loginBannerHtml`，增加「要你输验证码」入口。验证码步改用浏览器登录先显示「正在切换…」，等取消返回（成功或失败）再关对话框、只发一次登录。
- check 失败日志的条件仍是开工 HEAD 的 `recovering` 口径，本批没有改。

## 不变区对照

`unchanged_grid.py` 用上一批网格的完整维度：七个开关、`ok` 四个取值、`present` 三个取值、结论五个取值，结论为有效时估算到期时刻四个取值，上次校验时刻两个取值，共 24,576 组。会进入「有效·确认中」的 512 组跳过，比较其余 24,064 组。脚本先断言两边组数与跳过数相同再比。

- `--self`（开工 HEAD 的两份独立副本互比）：比 24,064 组，跳过 512 组，差异 0。
- 默认（开工 HEAD 对当前工作区）：比 24,064 组，跳过 512 组，差异 0。

变化区由 `test_login_transitions.py`、更新后的 `test_login_machine.py`、登录胶囊和重新登录对话框行为测试守住。开始报名按钮仍在确认结论回来前禁用。

## 旧用例

改过的旧用例逐条记在 `changed-tests.md`，一条用例一行，分「期望不变·喂字段」和「按画板改样子」两类。被上一批反过来的自动登录守卫已改回：给载荷补上真实后端那一刻会带的 `auto_state` 或 `login_auto`，断言回到开工 HEAD。只有前端自己判出的暂时无法确认（100 秒超时、桥接抛错、回绝）按「没带字段就保持上一次」停在自动登录中，这两条另加了「后端推 idle 就收回」的断言。

## 变异结论

`mutate_transitions.py` 在临时副本里逐条变异，每条只跑 `test_login_transitions.py`。34 条变异全部打红，覆盖：

- `applyAutoState` 的未知态、缺字段、running 镜像和接线重画；`setLogin` 在有效和演示模式下收回旧的 running。
- valid 收回、rechecking 三条件、needs_code 两种原因与 blocked 其他原因、backoff 剩余时间。
- 剩余秒数换算、分钟向上取整、三种样子的字与说明、三个 view.state 映射。
- 三条登录横幅、计划面板的横幅调用、`login_auto` 接线、legacy 挂回。
- 浏览器切换：「正在切换…」的字、等取消返回再关、取消失败也收口、只取消一次。

另有 2 条等价变异单独跑、不计入条数，结果都不红，符合预期：

- 去掉分钟数「最少 1」：只有剩余秒数大于 0 才进稍后重试，剩余秒数是整数，向上取整后本来就至少为 1。
- 去掉 `receiveAutoState` 里显式的横幅调用：前面的 `syncLoginDependentView` 里的 `render` 已经重画横幅。

计划面板那条变异原先的匹配串与现有代码对不上，脚本跑到那一条会报错退出；本次改成现有写法后重跑，全部 34 条打红。

## 复跑命令

```text
python -B design/evidence/2026-11-17/login-transitions/scripts/unchanged_grid.py --self
python -B design/evidence/2026-11-17/login-transitions/scripts/unchanged_grid.py
python -B design/evidence/2026-11-17/login-transitions/scripts/mutate_transitions.py
python -B -m unittest discover -s local/tests -p test_login_transitions.py
python -B -m unittest discover -s local/tests -p test_login_machine.py
python -B -m unittest discover -s local/tests -p test_ui_login_capsule.py
python -B -m unittest discover -s local/tests -p test_ui_relogin_dialog.py
python -B -m unittest discover -s local/tests -p test_ui_relogin_wiring.py
python -B -m unittest discover -s local/tests -p test_ui_reliability.py
python -B -m unittest discover -s local/tests -p test_ui_exit_paths_login.py
python -B tools/code_shape/check.py
node tools/code_shape/ui_modules.mjs --expect
```

2026-11-17 本机版全量（Python 3.12，控制台设 UTF-8）运行 2,949 条，6 条跳过，1 条失败、1 条错误，均与本批无关：`test_signup_plan` 的一秒计时用例在共享盘上偶发超时，单独复跑三次都通过；`test_component_builder` 的模型元数据用例因本机没装 `ddddocr` 报缺依赖。本机也没装 ruff，ruff 守卫整类跳过。发布守卫的 Node 语法检查用例在 UTF-8 控制台下通过。
