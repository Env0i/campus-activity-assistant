# 登录块搬家：搬了之后仍然是什么行为

这一批只搬不改，所以「搬之后」意味着两件事同时成立：一是**原来能测出来的缺陷仍然测得出来**（可检出性没变），二是**原来的行为一个没变**（用户看到的东西没动）。这份文件按这两条给证据。

## 一、量具与口径

- 用的是上一批（登录安全网）留下的量具 `design/evidence/2026-11-15/login-net/scripts/mutate_login.py`：112 行「每一行改坏一处」的清单，每行单独在仓库副本里改一处，跑对应测试，看有没有用例变红。
- 搬之后每行的「文件」由函数名映射到新位置（函数名与那一行的文字一个字不改）；脚本是 `scripts/net_after_move.py`，映射表就在里面。
- 结论分四种：**变红**（有行为测试守住）、**等价**（改坏了也看不出差别，要写理由）、**没人守**、**只有字面断言守**。

## 二、跟上一批记录的对照

上一批的记录在 `design/evidence/2026-11-15/login-net/after.md`：112 行实测，**109 行变红、3 行等价**。

搬之后逐行对照：

| 对照结果 | 行数 | 说明 |
|---|---|---|
| 结论相同、变红用例名相同 | 109 | 一字不差 |
| 结论相同、变红用例名不同 | 3 | 见下一节 |
| 结论不同（变红↔等价） | 0 | — |

3 行是 Y20、Y23、J50。上一批记录里这三行写的「出处」是 `test_a_pending_login_window_blocks_the_auto_refresh`、`test_auto_once_result_after_closing_does_not_move_the_step`、`test_error_line_only_shows_when_it_has_text`；搬之后这三条不再变红，变红的是另外几条。

查证的做法与结论：把**开工 HEAD `fb3e035` 导出成临时树**（也就是搬之前的那份代码），用同一份量具**一个进程跑三行**，变红的用例与搬之后完全一样——

| 行 | 开工 HEAD 单进程跑出来的变红用例 | 搬之后单进程跑出来的变红用例 |
|---|---|---|
| Y20 | `test_relay_without_a_challenge_does_not_open_the_code_step` | 同左 |
| Y23 | `test_relay_auto_mode_says_the_computer_is_recognizing` | 同左 |
| J50 | `test_typed_wrong_code_stays_on_code_step_with_grey_tries_note`、`test_error_line_only_shows_when_it_has_text` | 同左（两条都红） |

也就是说：这三格在上一批记录里点错了用例名（当时 8 个分片并行跑，多报了几条与该行无关的失败），不是搬家改变了可检出性。**这三行在搬之前的代码上本来也是靠现在这几次用例变红的。**

补充一条现场数据：把与这三行相关的两个测试文件在 6 路并行下各跑 3 轮（共 18 次，无变异），一次都没有失败——所以这不是「这些用例本身不稳」，而更像当时那轮并行测量里混进了与这一行无关的失败。这一点我没有归因清楚，如实记在这里；不影响本批的结论，因为「搬之前」与「搬之后」都用同一份单进程量具重跑过，逐行一致。

## 三、搬之前与搬之后逐行对照（同一份量具、同一份清单）

做法：拿开工 HEAD 的导出树当「搬之前」，把它和搬之后的工作区各跑一遍同样的 112 行（都是 8 分片并行，避免一边单进程一边并行的口径差），逐行比「结论」与「变红的用例集合」。

| 对照结果 | 行数 |
|---|---|
| 结论相同 | 112 / 112 |
| 结论不同 | 0 |
| 变红用例集合完全相同 | 103 / 112 |
| 变红用例集合不同 | 9 |

那 9 行的差别都长一个样：**同一行在两边都变红，只是其中一边多报了几条别的用例**，多出来的永远是这 7 条之一——

- `test_anchor_with_a_future_time_says_roughly_when`
- `test_a_pending_login_window_blocks_the_auto_refresh`
- `test_typed_wrong_code_stays_on_code_step_with_grey_tries_note`
- `test_auto_once_result_after_closing_does_not_move_the_step`
- `test_begin_result_after_closing_does_not_move_the_step`
- `test_a_failed_code_answer_after_closing_does_not_show_a_message_step`

这 7 条里既有「时钟」「多久以前」这类跟时间有关的，也有「关闭之后的结果不要推进步骤」这类跟对话框状态有关的。它们多报只出现在 8 分片并行的测量里，单进程重跑同样几行就没有多报（上面第二节那张表就是单进程的）。

**所以要看的数字是这两行：结论 112 / 112 相同、没有任何一行从「变红」变成「等价」或者反过来。** 变红用例集合的 9 处差异全部是「多报」，没有「少报」。

## 四、搬之后的两条硬证据

1. **真加载冒烟**：搬之后 `local/tests/test_ui_relogin_wiring.py` 的两条真加载用例（打开→取消、430 宽窄窗口）都通过；同一份测试在搬之前的那份代码上也通过（那条记录在 `wiring.md`）。
2. **把接线删掉就红**：在副本里删掉 `main.js` 里那两行接线（登录按钮绑定与 `wireRelogin()`），真加载冒烟里「点登录要打开对话框」那条立刻变红，报 `False is not true : 真加载下点「登录」要打开对话框`。说明这条冒烟确实守住了「接线被搬走」这件事，不是空跑。

## 五、复跑命令

```bash
# 搬之后：112 行按新位置跑，八分片
python -B design/evidence/2026-11-15/login-move/scripts/net_after_move.py \
  --shard-index 0 --shard-count 8 --out <输出目录>/shard-0.json
# 与上一批记录逐行对照
python -B design/evidence/2026-11-15/login-move/scripts/net_after_move.py --compare <输出目录>
# 拿开工 HEAD 的导出树当「搬之前」重跑同一批行
python -B design/evidence/2026-11-15/login-move/scripts/net_after_move.py --tree <导出树> \
  --shard-index 0 --shard-count 8 --out <输出目录>/shard-0.json
```

仓库里不留临时目录与分片原始输出，只留这份对照结论。
