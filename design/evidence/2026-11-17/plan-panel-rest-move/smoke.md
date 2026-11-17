# 真加载冒烟：搬前、搬后与删行

@author Author

## 口径

真加载冒烟按 `index.html` 的普通脚本顺序逐个执行，再用真实动态 `import` 加载 `main.js`，不走拼接夹具。守的是「搬完以后真窗口还能起来、计划栏还画得出来、按钮还接得上」。宽档（默认 1120×800）与窄档（430×820）各跑一次；中档 900×820 另跑计划条开合。

本批在 `test_ui_plan_move_smoke.py` 末尾追加三条（已有七条不动）：地点开关翻转、中档计划条开合、组件错误横幅。每条不超 60 行。

## 搬前（开工代码 HEAD 6a8ac06）

追加后跑 `python -B -m unittest discover -s local/tests -p test_ui_plan_move_smoke.py -q`：

```
Ran 10 tests in 12.214s
OK
```

10 条全过——三条新冒烟在动手前就能在开工代码上跑通。

## 删行敏感（搬前副本）

在临时副本里删掉 `app.js` 顶层的 `bindPlaceToggle();`（命中 1 行），复跑同一文件：

```
rc: 1 失败: ['test_place_toggle_flips_expanded_after_native_load', 'test_place_toggle_flips_expanded_after_native_load']
```

宽窄两档的地点开关那条都变红，其余用例不受影响——这条冒烟确实依赖那一行绑定。

## 搬后（新模块落位后）

同一文件复跑：

```
Ran 10 tests in 17.012s
OK
```

10 条全过。三条新冒烟的结论：

1. `test_place_toggle_flips_expanded_after_native_load`：真加载后 `#selected-meta` 上有地点开关的 click 委托；给一个命中 `[data-place-toggle]` 的 target 连点两次，`aria-expanded` 依次变 `true`、`false`（宽窄两档）。
2. `test_medium_dock_opens_and_returns`：900×820 中点「查看计划」→ 计划条收起、露出「返回列表」、`#zd.dataset.planOpen=1`；点「返回列表」→ 计划条回来。
3. `test_runtime_error_shows_component_banner`：摆 `S.runtime.error="worker_missing"` 后重画，`#banners` 出现「程序组件缺失」与「重新检查」（宽窄两档）。

## 删行敏感（搬后副本）

`bindPlaceToggle();` 已从 `app.js` 挪到 `main.js` 的 `installLegacyGlobals()` 之后。在临时副本里删掉 `main.js` 里那一行（命中 1 行），复跑搬后冒烟：

```
main.js 删行命中: [18]
rc: 1 失败: ['test_place_toggle_flips_expanded_after_native_load', 'test_place_toggle_flips_expanded_after_native_load']
```

宽窄两档都红——搬完以后这条冒烟仍盯着那一行绑定，挪位置没有让它失效。
