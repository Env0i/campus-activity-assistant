# 高级功能「一项一行」：不变区对照与变异

对应计划：`plan-20261115-visual-v1-adv-rows`。开工点 `7eb601c`（原型与截图入库的那一笔）。

## 改了什么，为什么

设置抽屉里的「手机访问」和「验证码识别」原来各是一段标题行加一堆散落的段落、按钮、进度块。
原型把它们改成**一项一行**：一行里放图标、名称与一句状态、至多一个主按钮、一只展开箭头，
其余内容（说明、大小、位置、通道卡、配对码、地址、导入入口）收进展开区。

理由是抽屉里两块并排的说明越来越长，按钮又随状态在不同位置出现或消失，用户看不出「这一项现在是什么情况」。
一行一句话，配一个圆点颜色，就能回答。

落地的分法：

- 状态层 `local/ui/features/components/state-row.js`：`rowHead(kind, facts, extra)` 是纯函数，输入快照与上下文，
  输出这一行该写什么（圆点档位、状态句、唯一那只按钮、小字、进度条百分比、要不要慢闪）。它不碰 DOM、不发请求、不读时钟。
- 视图层 `local/ui/features/components/view-row.js`：`paintComponentRow()` 把那份结果落进 DOM——标题行、进度条、
  小字（`p` 正文小字，`adv-n`）、红条（`ph-err adv-e`）、展开区，以及箭头的 `aria-expanded`。
- `view-ocr.js` 与 `phone-access/view.js` 只负责算输入：读快照、算 facts 与 extra，然后调同一个 `paintComponentRow()`。
  两个文件因此都比以前短。

## 不变区：展开区里该一字不变的格子

`scripts/detail_grid.py` 沿用 `component-machine/row_dom_grid.py` 的网格与沙箱写法：

- 网格 7680 格 = 240 组 × installing / busy / notes / 位置 / 进度数字各两档；
- 只比**两边 index.html 都有**的元素，共 59 个，都是展开区里这一批不该变的（说明、导入兜底、位置、大小、
  通道卡、配对、地址、再配一台、确认块、状态行）；
- 每格比七类属性：`hidden` / `disabled` / `textContent` / `className` / `dataset.state` / `style.width` / `aria-valuenow`。

结果：

```
网格大小：7680 格
实际比对：7680 格（skip_cell 恒 False）
逐元素比对 59 个元素 × 7 类属性：3171840 条比对
不同的条数：0
```

自检（开工点比自己）：`--base-ref 7eb601c --new-ref 7eb601c` → 同样 7680 格、3171840 条、不同 0。

三处**故意不在** 59 个元素里，都是这一批含义变了的格子：

- `#phone-probe`、`#ocr-note`：从「阶段说明」变成「一行标题下的小字」；
- `#phone-off-error`：返修批把「开不起来的原因」从这条红条挪到标题行下的小字里，红条只剩「下载没完成」。

比对它们等于把变化当不变。这是有意排除，不是放宽口径。

## 变化区由谁守

- 新增 `local/tests/test_settings_adv_rows.py`（31 条）：逐档钉住状态句、圆点档位、唯一那只按钮的文案与实心/线框、
  进度条数字与满格、小字与红条的分工、默认开合的 `aria-expanded`、点箭头翻转、点「关闭手机访问」先把这一行展开，
  以及 `rowHead()` 在网格上只吐 `ROW_TONES` 里的档位。
- 改写过的旧断言见 `changed-tests.md`：`test_ui_component_rows.py`、`test_ui_phone_access_rows.py`、
  `test_component_transitions.py`、`test_phone_link.py`、`test_phone_ui.py`、`test_ui_panel_wiring.py`、
  `test_ui_exit_paths_components.py`、`test_ui_contract_components.py`、`test_ui_contract_settings.py`。

## 变异：45 条都要能红

`scripts/mutate_rows.py` 把 `local/` 复制到临时目录，逐条按「文件 + 那一行的原文」改坏，跑对应用例，再还原字节。
第一次跑有 6 条存活，说明用例没守住，于是补了 3 条、扩了 3 条，最后：

```
变异条数：43
存活：0
```

死掉的地方包括：各档状态句与颜色、按钮的实心/线框与文案、进度条数字与满格、等锁时「只把圆点变蓝」、
超时与读不到的句子和「重试」、慢闪、默认开合、箭头 `aria-expanded`、按钮位只亮一只、小字与红条的分工、
没装块与导入兜底的显隐、确认块自动展开。

## 截图对画板

`scripts/shots.py` 两边都用 Playwright 打开（原型是 127.0.0.1 静态服务 + `runtime_bridge` 注入），
共 24 个场景、44 张图（20 张画板各出画板与界面两张，另加 900 宽中档与「开启失败」两种来源、正在停止四张只有界面一侧）。

脚本除了抓图还在 Edge 里读每张卡的真实字色，查两件事：状态句与那行小字是不是原型规定的颜色
（绿 `#146c43`、琥珀 `#8f5600`、红 `#b63227`、灰 `#4e5964`，小字的红更深 `#8a2a20`），以及对底色算出来的对比度是否都不低于 4.5。
任何一项不对直接判失败。逐对结论见 `shots/pairs.md`（全目录只留这一份对照表）。

## 返修这一批（visual-v1-rework）

三处与「一项一行」本身无关、但用户看得到的问题，在这一批补上：

1. **窄窗口一打开就崩。** `local/ui/app.js` 顶层那句 `applyBand();` 在模块把 `termsLocked` 等名字挂回 window 之前就跑了，
   900 与 430 宽下按档绘制会调 `views/plan-panel.js` 的 `startBlocker` → `termsLocked()` 直接抛 `ReferenceError`。
   修法只是把这一句挪进 `main.js`、放在 `installLegacyGlobals()` 之后；夹具的 `run_native_smoke` 加了可选宽高，
   新增用例在两种宽度下真加载一次并点 `#btn-log-folder` 证明末尾那批绑定也装上了。红/绿输出与复现命令见
   `../boot-band/README.md`。
2. **字色不对。** 状态句原来直接用圆点的亮色（`#1f9d5c`、`#e0a100`、`#c0392b`），在浅底上对比度只有 2.3–3.5；
   现在字用原型的深色（`--ok`/`--warn`/`--bad`），圆点仍亮色。那行小字的深红/琥珀原来被 `.ph-sec p` 更具体的选择器压成灰色，
   现在提到 `.adv-sec p.adv-n` 这一档才真正生效。这三条都靠 `shots.py` 在 Edge 里读真实字色守着——测试环境没有样式表，
   颜色错了测试照样全绿。
3. **缺 Cloudflare 组件包时无处补装、开不起来的原因挤在展开区。** 标题行现在照常给「开启」，补装入口是展开区里那只
   `#btn-phone-package`（文案在页面里）；隧道自己断开或端口被占时按钮写「重新开启」。
   （这一条里「原因画在哪」当时写到了标题行下那行小字，下一节改回了红条。）

## 与计划的偏差

1. **说明位的 id 沿用旧名。** 识别行的说明位计划里叫 `#ocr-probe`，实际沿用 `#ocr-note`：`local/tests/test_ui_modules.py`
   的真加载用例读这个名字，而那份文件不在可写范围。手机行仍是 `#phone-probe`。没有 verify 口径依赖这两个名字。
2. **两处实现差**（MB 按 1024 换算、手机行多一只「重新检测」按钮）与**一处格式差**（配对码无分组空格）写在 `shots/pairs.md`，
   都没改：改的是显示口径，不属于这批。
3. **`#btn-phone-package` 的点击处理原来写成裸 `openComponents(...)`**，在真窗口与沙箱里都会 `ReferenceError`；
   补的用例当场抓到，改成 `PhonePanel.openComponents("phone_control")`。

## 怎么复跑

```bash
# 不变区：开工点与自己比应当 0 不同
python -B design/evidence/2026-11-15/adv-rows/scripts/detail_grid.py --base-ref 7eb601c --new-ref 7eb601c

# 不变区：工作区对开工点
python -B design/evidence/2026-11-15/adv-rows/scripts/detail_grid.py --base-ref 7eb601c

# 变异：逐条改坏，应当全部变红
python -B design/evidence/2026-11-15/adv-rows/scripts/mutate_rows.py

# 截图：两侧都出图（需要 Playwright 与 msedge）
python -B design/evidence/2026-11-15/adv-rows/scripts/shots.py --out design/evidence/2026-11-15/adv-rows/shots

# 变化区的用例
python -B -m unittest discover -s local/tests -p "test_settings_adv_rows.py"
```

## 返修二（visual-v1-rework2）

上一节第 3 条把「开不起来的原因」放到了标题行下那行小字里，与原型的 `PhStartFail.dc.html`（灰点 + 行内红条 + 「重新开启」）
和「红条只留给这次出错了」的规则相悖，这一批改回来：

- 原因走手机行标题行下那条红条（`#phone-component-error`，与「下载没完成」同一个元素、同一种粉底 + `role=alert` 的样式），
  标题行下那行小字在未开启时恢复为空；判定一字未改——`notes.offErr` 有字、或 Cloudflare 隧道是 `exited`/`tunnel_exited`，
  仍然决定按钮写「重新开启」。
- 因此 `local/tests/test_settings_adv_rows.py` 的开启失败用例与 `local/tests/test_phone_ui.py` 的隧道断开用例改成读红条
  （见 `changed-tests.md` 的「返修二」），并新增一条隧道断开时选中 Cloudflare 的用例。
- 变异新增三条（红条不写原因、原因又写回小字、未开启时条件写成开着才讲原因），另外删掉一条指向已删代码的旧变异，
  现在 45 条全部变红、存活 0。
- 两张「开启失败」截图重出（隧道那张场景改成选中 Cloudflare，与画板一致），并逐行复核了对照表里写的圆点颜色与截图一致；
  全目录只留 `shots/pairs.md` 一份对照表，旧的 `adv-rows/pairs.md` 已删。
