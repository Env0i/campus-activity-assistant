# 登录样式对照与变异

## 这批改了什么

- 已登录后的确认中胶囊保持绿色，圆点改成绿色圆环并沿用 `advspin` 转动；自动登录中改成蓝色圆环并转动。
- 暂时无法确认改为琥珀色「登录待确认」。详情卡在确认中覆盖为绿色标签「登录有效」，要你输验证码的转人工和识别缺失两条路径覆盖为琥珀标签「要你输验证码」；稍后重试仍是红色「登录已失效」。
- 计划运行时，要你输验证码横幅使用用户定稿正文「报名计划还在等，开放前 100 秒以前输完就照常继续。」，计划不运行时保留电脑需要输入验证码的正文。
- 胶囊继续使用原来的单个 `<i>`，样式只把它变成圆环，没有新增页面元素。

## 预期差异对照

`looks_grid.py --self` 在开工 HEAD 的两份副本上比较 24,064 组，跳过 512 组确认中，差异为 0。

开工 HEAD 对当前工作区比较 24,064 组，跳过 512 组。允许差异如下，其他差异为 0：

- `auto` 阶段 6,016 组，胶囊多 `is-spin`。
- `unknown` 阶段 8 组，胶囊从 `pill is-none` 变为 `pill is-warn`。

单独构造的格子结果如下。

| 阶段 | 开工 HEAD | 当前工作区 |
|---|---|---|
| 确认中 | 胶囊 `pill is-ok`；详情卡无色标签「已登录」，大字「正在检查」 | 胶囊 `pill is-ok is-spin`；详情卡绿色标签「已登录」，大字「登录有效」 |
| 要你输验证码·转人工 | 胶囊 `pill is-warn`；详情卡红色标签「要你输验证码」，大字「登录已失效」 | 胶囊 `pill is-warn`；详情卡琥珀标签「要你输验证码」，大字「要你输验证码」 |
| 要你输验证码·识别缺失 | 胶囊 `pill is-warn`；详情卡红色标签「要你输验证码」，大字「登录已失效」 | 胶囊 `pill is-warn`；详情卡琥珀标签「要你输验证码」，大字「要你输验证码」 |
| 稍后重试 | 胶囊 `pill is-bad`；详情卡红色标签「登录已失效」，大字「登录已失效」 | 与开工 HEAD 相同 |

## 变异结论

`mutate_looks.py` 在临时副本中逐条运行 `test_login_looks.py`，10 条变异全部变红。覆盖内容包括确认中圆环、自动登录中圆环、待确认琥珀、圆环动画与规则顺序、详情卡两个阶段覆盖及错误色值、计划运行判断取反和两句横幅正文对调。第一条失败断言分别落在对应的胶囊、样式、详情卡或横幅测试中。

## 不在本批的内容

- 没登录过的胶囊是否改成「去登录」。
- 详情卡里的自动登录中是否使用蓝色标签。
- 窄档隐藏副句后「N 分钟后再试」的可见性，读屏仍从 `aria-label` 读取。
- 计划栏里的登录提醒句。

本批没有在真实窗口或 Edge 中检查圆环的实际转动、颜色和布局，交给用户验收。

## 回归结果

- 样式测试、登录状态机、登录转移、登录胶囊、登录契约、Shell 契约、UI 分层测试通过。
- 代码结构检查和模块图守卫通过，名单没有增加记录或项目。
- 本机版全量运行 2,959 条，5 条跳过，1 条错误。错误仍是 Windows/Node 语法错误输出的编码问题，发生在 `test_release_guards.WorkflowCommandTests.test_syntax_check_command_fails_on_bad_script` 的测试自身字符串拼接，当前改动没有新增失败。
- `test_signup_plan` 的停止计时用例单独复跑 3 次，全部通过。

## 复跑命令

```text
python -B design/evidence/2026-11-17/login-looks/scripts/looks_grid.py --self
python -B design/evidence/2026-11-17/login-looks/scripts/looks_grid.py
python -B design/evidence/2026-11-17/login-looks/scripts/mutate_looks.py
python -B -m unittest discover -s local/tests -p test_login_looks.py
python -B -m unittest discover -s local/tests -p test_login_machine.py
python -B -m unittest discover -s local/tests -p test_login_transitions.py
python -B -m unittest discover -s local/tests -p test_ui_login_capsule.py
python -B tools/code_shape/check.py
node tools/code_shape/ui_modules.mjs --expect
python -B -m unittest discover -s local/tests -p "test_*.py"
```
