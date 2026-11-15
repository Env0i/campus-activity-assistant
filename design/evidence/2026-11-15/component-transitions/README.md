# 组件状态机：读状态、重试、重新安装（2026-11-15）

上一批（`component-machine/`）把两个组件行收成了一台纯函数状态机加一个行绘制函数，行为一字不变。
这一批在同一个状态机上补画板上剩下的几条转移：等锁、超时、读不到、坏了的重新安装、取消不留痕。
下面写改了哪些、为什么、不变区怎么证明没动、变化区由谁守着。

## 改了哪些转移，为什么

| 转移 | 界面上现在长什么样 | 为什么这么改 |
|---|---|---|
| 等锁、还没有结论（checking，无缓存） | 进度块收起，读状态说明写「正在确认组件状态…」，主按钮与「启用」都收起 | 原来借用进度块说「正在检查组件…」，用户会以为在下载；也没有入口告诉用户还要等多久 |
| 等锁、有缓存结论 | 原来的字与 chip 一个字不变，只收按钮，说明不出现 | 已知的状态比「正在确认」有信息量，不该被一句话盖掉 |
| 等锁满 30 秒 | 写「另一个窗口正在安装或更新组件，已等 30 秒」，给「重试」 | 卡在别人的锁上没有任何提示，用户只会以为界面死了 |
| 读不到组件状态 | 写「暂时读不到组件状态」，给「重试」 | 原来这种情况直接显示成没装，会引导用户去重复安装 |
| 点了「重试」 | 记下这一刻的等锁秒数，从这一刻重新算 30 秒；读到结论后清掉 | 否则点完还是立刻超时，等于没点 |
| 坏了（status=failed） | 主按钮「重新安装」，走同一条在线下载；两行都写「组件文件不完整。重新安装不会动你的账号和设置。」 | 原来让用户去本机重新导入组件包，等于把「修好」这件事推回给用户；下载通道已经有了，重装直接用 |
| 坏了又下载失败 | 仍停在坏档，红条换成下载失败那句，导入兜底行出现 | 兜底入口只在真的失败过的时候出现，平时不占位置 |
| 没装时取消下载 | 回到「下载并安装」，任何地方都不留「已取消」这句话 | 取消不是结果，留一条记录只会让人以为装了一半 |
| 下载中同时等锁 | 「取消下载」照常可点，读状态说明不出现 | 进度块已经在说话了，再叠一句等于噪音 |

顺带删掉的东西：识别行标题行那个「重新导入组件包」按钮（连同 `index.html` 的元素、`views/settings.js` 的绑定、绘制段），
手机行 `#phone-component-state` 那个只用来写「取消」的段落；两行都不再写「下载已取消，没有装任何东西。」。
导入弹窗的入口只剩下载失败后那句里内联的链接。

## 不变区（这一步要证明「没改的东西真的没动」）

`scripts/unchanged_grid.py` 沿用上一批 `component-machine/scripts/row_dom_grid.py` 的网格与沙箱：
240 组快照 × 2（安装中、面板忙、备注、位置、进度数字各两档）= 7680 格，每格 7 类属性
（hidden / disabled / textContent / className / dataset.state / style.width / aria-valuenow）。

- 旧方：开工提交 `d5598bd`（`git archive` 导出），新方：工作区。
- 比两边都有的元素：74 个。删掉的 2 个（`#btn-ocr-feature-install`、`#phone-component-state`）与
  新增的 4 个（`#phone-probe`、`#btn-phone-component-retry`、`#ocr-probe`、`#btn-ocr-retry`）不在比对范围。
- 跳过本批按设计要变的格：`status ∈ {checking, failed}` 与 `download.state = cancelled`。
- 结果：跳过 3840 格，实际比对 3840 格，74 元素 × 7 类属性 = **1989120 条比对，不同 0 条**。
- 自检（旧方与旧方自己比，76 个元素）：2042880 条比对，不同 0 条——说明这套比对本身不会把差异吃掉。

复跑（仓库根）：

```
python -B design/evidence/2026-11-15/component-transitions/scripts/unchanged_grid.py --base-ref d5598bd
python -B design/evidence/2026-11-15/component-transitions/scripts/unchanged_grid.py --base-ref d5598bd --new-ref d5598bd
```

## 变化区由谁守着

- `local/tests/test_component_transitions.py`（新增，13 条）：一条转移一个用例，只看用户看得到的结果
  （按钮在不在、能不能点、说明写的是哪句、有没有再取一次快照）。两行都适用的转移，两行都断言。
  禁用类断言都先断言看得见，并带一格空闲可点的对照，避免「一直藏着」也能过。
- `local/tests/test_component_machine.py`（补 3 条）：`probe` 四种取值与「下载优先」、超时从重试起点算、`ctx.running` 下的状态与 `loading`。
- 改口径的旧断言 16 条见 `changed-tests.md`，逐条写了原断言、新断言与依据；表外没有变红的用例。

## 变异结论

`scripts/mutate_transitions.py` 在临时副本里一处一处改坏源码，再跑对应的用例：

- 共 29 条变异，**全部变红，存活 0 条**，没有一条是「红在语法或导入」。
- 审计另做变异发现：读状态没结论时收起识别行「启用」与手机行「启用手机控制」这两处原先没有用例守住（原用例从已启用出发，这两个按钮本来就收着），补了 test_lock_hides_the_row_enable_buttons_that_would_otherwise_show。
- 覆盖：`probe` 四档与判断先后、超时的两个条件与 30 秒这个数、`ctx.running`、`loading` 去掉检查中、
  主按钮的显隐与三种文字、导入兜底的坏档条件、两行红条的坏档说明、读状态三句话与 `data-probe`、
  「重试」的显隐与禁用、重试记起点与清起点、`needsPolling` 的等锁档、两个「重试」的接线。
- 有三条第一轮没红，处理方式写在脚本里：超时窗口那条补了一格「差 25 秒」，
  没有起点那条补了一格「后端说超时、等锁秒数却很小」，手机行坏档那句原来改出了语法错误，改成换文案后正常变红。
  也就是说，这三条不是等价变异，是当时用例没守住，补了用例之后才成立的。

复跑：

```
python -B design/evidence/2026-11-15/component-transitions/scripts/mutate_transitions.py
```

## 代码形状

- `paintPhoneAccess` 224 → 219 行、`paintOcrDownload` 74 → 70 行（`tools/code_shape/baseline.json` 的记录值跟着收紧，没有新增项）。
- 新增函数都在 60 行以内；没有新模块，`ui_modules_expect.json` 不用改；分层白名单没有加项。

## 与计划的偏差

- 计划原本打算把「重试起点」与相关方法挂成 `PhonePanel` 的成员。`local/tests/test_ui_modules.py` 用字面量快照
  守着 `PhonePanel` 的成员一名不多一名不少，而那个测试文件不在本批的可写范围里，所以改成模块作用域的
  `retryWaitBase` / `setRetryWaitBase` / `clearSettledRetryBase`，`PhonePanel` 成员清单一个字没动。
- `BROKEN_NOTE`（两行都写的那句坏档说明）放在 `features/components/view-row.js`：`features/components/state.js`
  不在本批可写范围里，而这句话是绘制层共用的文案，放绘制文件同样合适。
