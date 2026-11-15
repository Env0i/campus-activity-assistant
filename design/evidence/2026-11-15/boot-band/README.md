# 窄窗口下界面起不来（顶层 `applyBand()` 早于模块名挂回）

日期：2026-11-15。

## 症状

窗口拉窄（中档 900 左右、窄档 430 左右）后开着设置抽屉截图，整个界面空白、控制台一条
`pageerror`：`termsLocked is not defined`。宽窗口（默认 1120）不出现。

## 复现

```bash
python -B -m unittest discover -s local/tests -p "test_ui_modules.py" \
  -k medium_and_narrow
```

修之前跑，两个宽度都红，报的是同一句：

```
FAIL: test_real_load_at_medium_and_narrow_widths_keeps_the_tail_bindings (width=900)
AssertionError: 原生加载冒烟崩溃：views/plan-panel.js:416
ReferenceError: termsLocked is not defined
FAIL: test_real_load_at_medium_and_narrow_widths_keeps_the_tail_bindings (width=430)
AssertionError: 原生加载冒烟崩溃：views/plan-panel.js:416
ReferenceError: termsLocked is not defined
```

## 根因

- `local/ui/app.js` 原来在顶层调 `applyBand()`。它按窗口宽度分档；中、窄档会把计划栏
  画出来，于是走到 `paintDock()` → `startBlocker()` → `termsLocked()`。
- 而 `termsLocked` 是模块里的名字（`local/ui/features/terms/state.js`），要等
  `local/ui/main.js` 里的 `installLegacyGlobals()` 才挂回 `window`。普通脚本阶段调用
  就是 `ReferenceError`。
- 抛在 `app.js` 顶层，于是它**后面那 40 余处 `addEventListener` 一处都没执行**——
  界面看着像是空白页，实际是整段绑定被这一次异常带走了。宽档不画计划栏，所以默认
  宽度 1120 一直是绿的；「真实加载」冒烟用例把宽度写死成 1120，也就一直抓不到。

## 修法

只挪一句，不换办法：

- `local/ui/app.js`：删掉顶层那句 `applyBand();`（`window.addEventListener("resize", …)`
  原样留着）。
- `local/ui/main.js`：在 `installLegacyGlobals();` 之后、`boot()` 之前调 `applyBand()`，
  注释写明「先挂回名字再按档绘制」，以及宽档行为不变。

## 验证

```bash
python -B -m unittest discover -s local/tests -p "test_ui_modules.py"   # 15 条 OK
python -B -m unittest discover -s local/tests -p "test_ui_layers.py"    # 4 条 OK
node tools/code_shape/ui_modules.mjs                                    # 五类为空
```

新用例 `test_real_load_at_medium_and_narrow_widths_keeps_the_tail_bindings` 在两种宽度下
各真加载一次，断言就绪标记为真、且末尾那条「打开数据目录」的绑定真的点得动（发出一次
`open_data`）。修之前红、修之后绿。

## 已知未验证

- 真窗口（WebView2）里没有单独重跑一遍；`local/ui/m/`（手机页）不走这套分档绘制，
  未在窄窗口的真机上核对。
