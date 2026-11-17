# 真加载冒烟：搬前、搬后与删行验证

## 跑什么

`local/tests/test_ui_plan_move_smoke.py`。真加载＝按 `index.html` 的普通脚本顺序逐个执行，再用真实的动态 import 加载 `main.js`，不走拼接夹具。拼接以后模块里的名字恰好是全局的，只有真加载才暴露「普通脚本拿不到模块名字」这类缺陷。

七条用例：

| 用例 | 守什么 |
|---|---|
| 宽档画运行中的计划栏 | 普通脚本阶段不抛错；标题、两张任务卡、停止按钮都画出来 |
| 430 宽窄档摆计划条 | 窄档下计划条与计划栏照样画出来 |
| 结果页画统计与「重新选择」 | 结果页的大数字、页脚按钮、部分完成的标签 |
| 点「开始报名计划」发出 `start_plan` | 宽窄两档各一次；带上选中的场次，接纳后置忙 |
| 点「停止计划」先弹确认 | 宽窄两档各一次；弹层焦点落「继续计划」，确认后才发 `stop_plan` |
| 结果页点「完成」回到空草稿 | 宽窄两档各一次；结果页收起、选择清空 |
| 已失效时点「登录」改走浏览器登录 | 宽窄两档各一次；先开重新登录对话框，再发出 `login` |

## 搬之前（开工代码 `35229af`）

```
Ran 7 tests in 6.811s
OK
```

新加的四条在开工代码上就是绿的——这一点先立住，搬完才有对照。

## 搬之后

```
Ran 7 tests in 6.958s
OK
```

## 删掉 main.js 挪进来的那一行

在临时副本里把下面这行从 `main.js` 删掉（其余一律不动），跑同一个测试文件：

```js
$("#btn-stop-yes").addEventListener("click", confirmStopPlan);
```

```
退出码 1
变红的用例：
   FAIL: test_stop_button_asks_before_stopping (...) (band='wide')
   FAIL: test_stop_button_asks_before_stopping (...) (band='narrow')
FAILED (failures=2)
```

只有对应的那一条红，其余六条仍绿——说明这 8 行确实被冒烟守住了，不是搬过去就算完。

## 一处摆设方式的调整

第三条原来用 `openResultPage()` 打开结果页。这个名字搬完后没有任何普通脚本在用，按 A6 不再挂回 `window`，冒烟里也就拿不到；改成直接摆 `S.resultOpen`，再用仍挂回的 `syncResultSelection()` 补齐选择签名（`resultPageOpen()` 会对不上签名就把结果页又关上）。**断言一行没改。**
