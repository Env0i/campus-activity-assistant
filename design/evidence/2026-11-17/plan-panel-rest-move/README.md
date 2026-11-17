# 计划栏剩余段搬成模块（只搬）

@author Author

开工 HEAD `580c1c4`，分支 `refactor/step1`，执行日期 2026-11-17。`views/plan-panel.js`（748 行）整段搬空后只从磁盘删，暂存区一步没碰。只搬不改——函数体、常量、注释一字不差，只加 `export`、单行具名 `import` 与一行文件头注释。

## 搬了什么

28 个顶层函数按层落进 9 个新模块：

| 新文件 | 放什么 |
|---|---|
| `features/plan/state-draft.js` | `autoLoginCredential`、`latestSelectedOpen`、`preStartWarnings` |
| `features/plan/view-draft.js` | `togglePlace`、`paintChecks`、`paintPrewarn`、`planCheckList`、`startBlocker`、`paintWhy`、`paintTickets`、`paintPolicyLine` |
| `features/plan/actions-draft.js` | `bindPlaceToggle` |
| `features/plan/state-led.js` | `routeDeadline`、`routeTime`、`routeTarget`、`ledSet`、`fmtLed` |
| `features/plan/view-led.js` | `paintRoute`、`paintCountdown`、`paintLedLabel`、`paintLedBox`、`paintLed` |
| `features/plan/view-controls.js` | `updateControls` |
| `features/plan/view-dock.js` | `paintDock` |
| `features/shell/view-band.js` | `bandOf`、`applyBand`、`setPlanOpen` |
| `features/shell/view-banners.js` | `paintBanners` |

`controllers/refresh.js` 里的 `RUNTIME_ERRORS`（含注释）与 `runtimeErrorCopy` 两段逐字搬进 `features/shell/state-runtime.js`；refresh.js 只少这两段。

配套改动：`app.js` 只少顶层 `bindPlaceToggle();` 一行；`main.js` 加两行 import、一句为什么挪的注释与那一行调用；`index.html` 少 `views/plan-panel.js` 那一个 script 行；`legacy-globals.js` 按模块图守卫新挂回 11 个名字、撤掉 8 个已无人用的旧挂回、横幅/分档/组件文案另起 `attachShellGlobals`（`installLegacyGlobals` 不超 60 行）；8 个已有模块各只加需要的单行 import。详细逐个名字的去处、理由、引用图、加载期引用、挂回谁在用，见 `move-map.md`。

两处落点与原预分不同，都在 `move-map.md` 写了理由：`planCheckList`、`startBlocker` 因用 `views/terms.js` 的 `termsUpdateMode`，从预分的 `state-draft.js` 改归 `view-draft.js`（否则报 state→views 跨层），函数体一字未动。

## 口径

- **逐字核对**：段 = 一个顶层函数或常量 + 紧挨着上方的注释；每段去掉 `export ` 后必须在某个新文件里找到一字不差的一段；反过来新文件里多出来的行只能是文件头注释、import、`export` 关键字与挂回。
- **搬后安全网**：只重跑 plan-net 那一批里「已守」且落在本批 28 个函数里的行，函数名、行文字、第几次、变异写法一字不改，只换路径；等价行照旧应不红。
- **真加载冒烟**：按 index.html 顺序跑普通脚本，再真实动态 import 加载 main.js，宽/窄/中档各跑；删掉 main.js 里挪过来的那一行后地点开关那条必须红。

## 结论数字

| 项 | 结果 |
|---|---|
| 逐字核对 | 28 段全部找到且一字不差；0 段缺失、0 段不同；新文件多余行 0；`app.js` 只少 1 行、`main.js` 只多 5 行（2 import + 2 注释 + 1 调用）、`refresh.js` 只少 2 段 |
| 模块图守卫 | 五类问题全空（循环、缺 import、层违规、未挂回、挂了没人用） |
| 分层 / 结构 | `test_ui_layers.py`、`test_code_shape.py`、`test_ui_modules.py` 全过；`check.py` 通过 |
| 真加载冒烟 | 搬前 10/10、搬后 10/10；删掉 main.js 那一行后地点开关宽窄两档都红 |
| 搬后安全网 | 57 条（已守 56、等价 1）：已守全部仍红、等价仍绿、0 定位失败、0 语法错 |
| 六个计划出口 | 函数体本批一字未改，上一批「全部仍红」的结论继续成立 |
| 名单 | 大小名单删 1 个文件项、改 3 条函数键、refresh.js 记录值改小；分层白名单删 1 组；无新增；模块图期望值重新生成 |
| 现有测试读法 | 4 个 allowed_paths 内文件只改读法与路径，断言一字不动 |

## 计划缺陷（plan_defect，交规划方）

`test_ui_contract_login.py` 有两条按文字切源码的用例在搬后变红：`test_start_button_requires_valid_or_demo`（切 `updateControls → paintBanners`）与 `test_login_expiry_check_present`（切 `planCheckList → autoLoginCredential`）。两对锚点搬到不同模块、顺序由依赖图强制，必须改读法。R7 要求改「所有按文字切源码的测试」读法，但 `scope.allowed_paths` 与 move 任务 `allowed_paths` 都漏列了该文件。按 R11「allowed_paths 以外的文件变了就停下」，本执行未改它，两条用例如实报红，交规划方裁决。详见 `move-map.md` 第十一节。

另：`test_ui_contract_settings.py` 两条同类切片用不带 start 的 `index`，搬家后切出空串，但断言是 `assertNotIn`，空串恰好仍过（测试未红）。这不是本批引入的行为回归，是既有测试写法对新模块顺序不敏感；该文件同样不在 allowed_paths，未改。

## 时长

- 预计 **90 分钟**（开工前写）：prep 25、move 35、verify-move 30（安全网与全量可重叠）。
- 实际约 **80 分钟**：开工 12:55，收工 14:15 前后。未超预计一倍。

## 复跑命令（仓库根）

```bash
python -B design/evidence/2026-11-17/plan-panel-rest-move/scripts/move_check.py
python -B design/evidence/2026-11-17/plan-panel-rest-move/scripts/net_after_move.py --workers 4 --out <file>
python -B -m unittest discover -s local/tests -p test_ui_plan_move_smoke.py
python -B -m unittest discover -s local/tests -p "test_*.py"
node tools/code_shape/ui_modules.mjs
python -B tools/code_shape/check.py
```

解释器用项目自带的 Python 3.12。临时副本只放在系统临时目录，复制时跳过数据根、配置与工作区元数据。结果目录不入库，收工按项目规范跑 scrub-share。
