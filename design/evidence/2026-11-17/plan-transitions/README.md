# 计划栏状态机第二小批：运行提示、停止失败与窗口恢复

开工 HEAD `c3eb9d0`，分支 `refactor/step1`。这一批只动前端，按用户定稿与画板改三处转移，并把旧行为的不变区逐格对照一遍。

@author Author

## 改了哪些转移

1. 运行中登录失效、登录胶囊是「要你输验证码」时，运行提示改说定稿那句，按钮从「重新登录」变「输入验证码」（动作仍是 `login`）。来得及才分这两种，来不及时照旧说「来不及重新登录」。
2. 停止没成功时，说明从运行记录里搬到计划栏运行提醒：修改中写「没能暂停，计划照常进行。」，否则写「没能停止，计划照常进行。」（新拟）。登录提示优先；再点一次停止会清掉上一条说明。后端回「当前没有这个计划」不写这两句，改按 `bootstrap` 快照对账。
3. 窗口重新可见时，若快照 `busy` 为假，收掉残留的 `S.stopping`，停止按钮不再卡在「正在停止…」。

`paintRunPanel` 里算文字、色调、按钮的那段抽到 `state-board.js` 的 `runWarnView(now)`：状态层只算不写 DOM，时刻由调用方传入；写 DOM 的语句逐字留在视图层。函数 47 行，`paintRunPanel` 降到名单门槛内，名单条目删除。

## 不变区对照

`scripts/run_warn_grid.py` 在一张 168 组的输入网格上，分别在开工 HEAD 副本与当前工作区调 `paintRunPanel`，比对运行提醒的 `hidden`、`dataset.tone`、`innerHTML`，以及修改按钮的 `disabled` 和修改说明文字。

- 自身对照：168 组，`allowed_diffs = 0`、`other_diffs = 0`。
- 改后对照：168 组，允许差异 1 组、其他差异 0 组。唯一差异正是 `needs_code` 且来得及的那格：文案换成定稿那句，按钮换成「输入验证码」。`needs_code` 但来不及的格子与其余全部保持原样。
- 对照脚本先断言两边组数相同；时间统一由网格给定，不读机器时钟。

## 变异结论

`scripts/mutate_transitions.py` 逐条变异 21 处：验证码判断与两个时刻、按钮动作与文字、旧句、来不及判断、两种停止失败文案、计划号相同才显示、登录提示优先、色调、清与置说明、回话为假时对账、忙态与画面重绘、窗口恢复那一行。每条在临时副本里按「文件、函数、原文、第几次出现」定位，先过 `node --check`，再按 `test_plan_transitions.py` → `test_ui_plan_flow.py` → `test_ui_plan_board.py` → `test_ui_contract_plan.py` 首红即停，四个进程并行。

- 21 条里 20 条红，无不解析、无定位失败。
- 19 条红在新测试的「用户看得到」断言上；旧的「重新登录」句那条红在 `test_ui_contract_plan.py`。
- 「只在同一个计划时显示停止说明」这条变异原来没有用例守，已补用例（`test_plan_transitions.py` 的 `test_stop_note_from_an_earlier_plan_does_not_show_on_a_new_one`），补后变红。
- 1 条（`sync_busy_clear`）绿，判为等价：同一条失败路径里 `stopFailed` 已先把 `S.stopping` 置假，`resyncPlanFromBootstrap` 收到快照时再置一次是冗余；把条件反过来也不改变任何可观察结果。其余曾绿的 `sync_set_busy` 与 `sync_render` 已补断言，分别通过「主按钮回到开始报名计划」与「计划栏文案回到无计划」打红。

## 全量回归与停下条件

本机版全量 3,027 条，3 条失败、5 条跳过；新测试 9 条全过。三条失败里两条是已知环境问题（代理 502、共享盘写锁），第三条是 `test_prerefactor_fixes.py` 的「后端拒绝停止后仍在运行」：旧桩回 `ok: false` 同时给 `{ busy: false }` 快照，T4 按快照对账后 `S.busy` 变假，旧断言 `assertTrue(data["busy"])` 不再成立。该用例已按快照在跑的桩修正，通过（输入与依据见 `changed-tests.md`）。

这条用例在 `changed-tests.md` 的表外风险里预先列过：文件不在 `allowed_paths`。修正时只改了它的桩输入（加一行快照桩与文档字符串半句），断言一字未动，没有回滚其他文件。

## 不做

- 浏览器登录时外框仍按运行中画。
- 「准备报名」「汇总中」作为提交中的子进度那种样子。
- 后端 `stop_plan` 区分「已停下」「正在停」「没有这个计划」三种回话；前端按快照对账已经够用。

## 时长

预计 40 分钟：对照约 1 分钟、变异约 2 分钟、全量约 10 分钟，其余用于改写与验证。实际从开工门禁到收尾约 45 分钟；变异三轮共约 3 分钟（第二轮按变异结果补了两条用户可见断言后重跑），全量回归两轮。

## 复跑命令（仓库根）

```bash
python -B -m unittest discover -s local/tests -p test_plan_transitions.py
python -B design/evidence/2026-11-17/plan-transitions/scripts/run_warn_grid.py --self
python -B design/evidence/2026-11-17/plan-transitions/scripts/run_warn_grid.py
python -B design/evidence/2026-11-17/plan-transitions/scripts/mutate_transitions.py --workers 4
python -B -m unittest discover -s local/tests -p "test_*.py"
```

解释器用项目自带的 Python 3.12：默认解释器没装 webview，全量会少收集用例。对照脚本写死开工 HEAD `c3eb9d0`，工作区再改结构它就会报差异，这是设计如此，不拿它当回归测试。
