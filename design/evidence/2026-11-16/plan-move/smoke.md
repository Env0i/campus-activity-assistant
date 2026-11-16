# 真加载冒烟：搬之前、搬之后

真加载 = 按 `index.html` 的普通脚本顺序逐个执行，再用真实的动态 `import` 加载 `main.js`。拼接夹具把所有脚本放进同一个作用域，模块里的名字恰好是全局的；真加载下模块名不进全局，普通脚本阶段引用模块名字才会暴露成 ReferenceError。所以搬之前先跑一次，搬完再跑一次。

## 三条用例

`local/tests/test_ui_plan_move_smoke.py`：

| 用例 | 撑的是哪一段 |
|---|---|
| `test_wide_load_draws_the_running_plan_board` | 宽档（默认 1120×800）：两场等开放的运行中快照下，大屏标签「等开放」、标题「活动甲」、两张任务卡、停止按钮可点 |
| `test_narrow_load_draws_the_plan_dock_and_board` | 窄档 430×820：`S.band` 落 narrow，计划条没藏起来、标题写着「运行中」，大屏标题照样是当前场次 |
| `test_result_page_draws_stats_and_reselect` | 结果页（一场成功一场失败）：统计里有「已报名」与「报名未成功」，「重新选择」按钮放出来，标签「部分完成」 |

三条都不改产品代码，只摆状态再调 `render()`；时间用 2099 年，避免随日历过期。

## 搬之前（开工 HEAD `abd2a6a`）

```text
$ python -B -m unittest discover -s local/tests -p test_ui_plan_move_smoke.py -v
test_narrow_load_draws_the_plan_dock_and_board ... ok
test_result_page_draws_stats_and_reselect ... ok
test_wide_load_draws_the_running_plan_board ... ok

Ran 3 tests in 1.905s
OK
```

## 搬之后

```text
$ python -B -m unittest discover -s local/tests -p test_ui_plan_move_smoke.py -v
test_narrow_load_draws_the_plan_dock_and_board ... ok
test_result_page_draws_stats_and_reselect ... ok
test_wide_load_draws_the_running_plan_board ... ok

Ran 3 tests in 2.280s
OK
```

## 「删掉 main.js 一行接线」这一步不适用

计划要求「在副本里把 M4 挪进 `main.js` 的某一行删掉，确认真加载那一条变红」。这一批的 M4 核对结果是 **0 行**：55 个搬走的名字在其余普通脚本里没有一处是加载期（文件顶层）用到的——顶层调用、顶层把函数名当回调传出去、顶层 `const` 初始化、加载期会执行的调用链，四类都没有命中。所以 `main.js` 这一批没有新增任何行，也就没有可删的那一行。

真加载本身仍然被上面三条用例守着：如果哪个普通脚本在加载期引用了模块名，普通脚本阶段就会抛错，`run_native_smoke` 直接崩溃，三条用例全红。
