# 登录块搬成模块：把三个普通脚本按层拆进 `features/login`

这一批只搬不改。三个普通脚本（`state/login.js`、`views/login.js`、`views/relogin.js`，共 869 行）按层拆进 `local/ui/features/login/` 的六个模块，函数体、常量与注释逐字照搬；另外把三个跟登录无关的通用名字挪进普通脚本，把 `app.js` 加载期那两行接线挪进 `main.js`。

## 一、搬了什么

| 原位置 | 去处 | 内容 |
|---|---|---|
| `state/login.js` | `features/login/state.js`、`view.js`、`actions.js` | 登录三态还原与剩余估算（状态层）、顶栏胶囊绘制（视图层）、统一重画与自动登录收回（编排层） |
| `views/login.js` | `features/login/view.js` + `views/result.js` + `views/log.js` | `paintLogin` 进视图层；`setBusy`、`setResult`、`resultTimer` 进新普通脚本；`addLog` 并进日志视图文件末尾 |
| `views/relogin.js` | `state-relogin.js`、`view-relogin.js`、`actions-relogin.js` | 对话框的纯推导、DOM 呈现、桥接请求与接线分三层 |
| `app.js` 顶层两行 | `main.js` | 登录按钮绑定与 `wireRelogin()`，放到 `installLegacyGlobals()` 之后 |

`index.html` 删掉三行旧 `<script>`，在原来第一行的位置加 `views/result.js`。

每个名字去了哪个文件、按哪条规则归层，逐条写在 `move-map.md`。

## 二、怎么保证「没改」

- **逐字核对**：`scripts/move_check.py` 从开工 HEAD `fb3e035` 取三个旧文件，按顶层声明切成 57 段（注释随段走），逐段到新位置找一字不差的一段——**57 段全部找到且相同**；反过来把新文件里不属于原文的行分类，**分不进任何一类的是 0 行**（多出来的只有 import、`export { }` 续行、`main.js` 接线、注释、空行与原文件本来就有的行）。
- **行为没变**：现有测试断言一个字没改（详见第五节的对账），全量本机版通过。
- **缺陷仍然测得出来**：见 `net-after-move.md`，同一份 112 行清单在搬之前与搬之后逐行对照。

## 三、结论数字

| 项 | 数字 |
|---|---|
| 顶层声明段 | 57 段，逐字找到 57 段，找不到 0 段 |
| 新文件里无法归类的行 | 0 行 |
| 接线变异（搬之前 / 搬之后） | 21 处 / 21 处，两次都是全部变红、存活 0 |
| 真加载冒烟（搬之前 / 搬之后） | 通过 / 通过 |
| 把 `main.js` 两行接线删掉 | 真加载登录按钮那条立刻变红（副本里做） |
| 安全网 112 行（搬之前 vs 搬之后） | 结论 112 / 112 相同，没有一行从「变红」变「等价」或反过来 |
| 模块图守卫 | 五类问题都为空 |
| 代码形状 | `check.py` 通过；`views/relogin.js` 那条 555 行文件项删除，两条函数键改到新路径、记录值不变 |
| 全量本机版 | 见第六节，与上一批对数后只多出本批新增用例 |

## 四、搬之前先把接线测起来

搬文件之前先给重新登录对话框的每一处接线补了测试，并在**还没搬的代码**上跑绿、做完变异（21 处全部变红），然后才动手搬。理由很直白：搬完再补测试，就分不清「红」是搬坏的还是本来就没有测试。结论表在 `wiring.md`。

## 五、现有测试的对账

- 现有界面测试的用例数：搬之前 739 例（`test_ui_*.py` 两份登录相关文件在内），搬之后一致的用例没有增减；新增的只有本批新文件 `local/tests/test_ui_relogin_wiring.py`（24 条）。
- 现有测试的断言：零改动。搬动过程中动过两处「读法」而不是断言——`test_relogin_busy_order.py` 的文档字符串里提到旧路径的一句改成新位置、`docs/UI_SPEC.md` 里一处说明文字同样改路径。两处都不参与断言语义。
- `test_ui_modules.py`、`test_ui_layers.py`、`test_code_shape.py`、`tools/code_shape/check.py` 全通过；`node --check` 对六个新模块与两个新普通脚本逐个通过。

## 六、复跑命令

```bash
# 代码结构三件套
python -B tools/code_shape/check.py
python -B -m unittest discover -s local/tests -p test_code_shape.py
python -B -m unittest discover -s local/tests -p test_ui_layers.py
python -B -m unittest discover -s local/tests -p test_ui_modules.py

# 接线测试（含真加载）与搬前搬后的安全网
python -B -m unittest discover -s local/tests -p test_ui_relogin_wiring.py
python -B design/evidence/2026-11-15/login-move/scripts/mutate_wiring.py --phase post
python -B design/evidence/2026-11-15/login-move/scripts/net_after_move.py --shard-index 0 --shard-count 8 --out <输出目录>/shard-0.json

# 逐字核对
python -B design/evidence/2026-11-15/login-move/scripts/move_check.py

# 全量本机版
python -B -m unittest discover -s local/tests -p "test_*.py"
```

## 七、这一批没做的事

- **`controllers/refresh.js` 一个字没动**：它写 `S.login` 的那四个函数属于活动列表与登录检查共用的编排，搬计划栏那一块时再一起处理。
- **通用名字仍是普通脚本**：`setBusy`、`setResult`、`addLog` 块外有十几个普通脚本在用，做成模块就要全部挂回 `window`；留在视图层，过渡名单一项都不用加。
- **没有重命名、没有调语句顺序、没有合并重复、没修缺陷**：包括函数里的 `typeof` 判断都照原样留着。
