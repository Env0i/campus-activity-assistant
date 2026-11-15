# 组件状态机落地（行为不变）的证据

- **基线提交**：`86db720`（分支 refactor/step1；开工时工作区里另有一处本会话之外的
  AGENTS.md 改动，未触碰）。执行日期：2026-11-15。开工前提：后端补字段那一批
  （`5999381` 快照字段 + `86db720` 证据）已入库，`local/domain/component_rules.py`
  与本目录上一级前提的 README 都在版本管理里。
- **换了什么结构**：两个组件行（手机控制、验证码识别）共用一台纯函数状态机与一个
  行绘制函数——
  - `features/components/state-machine.js`（新文件，状态层）：`componentState(row, ctx)`
    返回这一行的状态（missing / downloading / verifying / checking / outdated / broken /
    enabled / disabled，判断顺序与改前两份认阶段逐行相同）加画面要用的派生事实
    （下载事务、失败、刚取消、在下载或校验、在加载、安装中、忙碌、位置、下载快照）。
  - `features/components/view-row.js`（新文件，视图层）：`paintComponentRow(spec, facts,
    texts)` 画两行共有的主按钮、取消按钮、没装块、导入兜底、进度块、位置两行、
    红条与取消句；行与行的差别由两份 spec 常量（`PHONE_ROW_SPEC` 在
    phone-access/view.js、`OCR_ROW_SPEC` 在 view-ocr.js）与调用方算好的 texts 保留。
  - `phonePhase` / `ocrPhase` 改成薄适配：手机行开着就是 on，识别行把 enabled 当
    已启用、disabled 也当未启用，其余同名映射；名字、参数、返回值不变，`PhonePanel`
    成员清单没动。
  - `paintPhoneAccess`（262 行 → 224 行）与 `paintOcrDownload`（119 行 → 74 行）只留
    各行特有的部分；两个新文件的函数都在 60 行以内（`paintComponentRow` 50 行、
    `componentState` 32 行）。大小名单两条：paintPhoneAccess 记录值 262 → 224
    （理由不变），paintOcrDownload 从函数甲档换到乙档（119 → 74），名单没有加项；
    模块图期望值用 `--expect` 重新生成，与改前内容一致（新文件没有引入新的跨层
    引用，挂回名单与「模块用到的普通脚本全局名字」两份清单逐项没变）。
- **为什么行为不变**：动手前先在 `differences.md` 逐项列出两行在共有部分上的差别
  （12 条），每一条写明改完后由谁保留——其中一条（「打开所在文件夹」的禁用时机）
  经代码核实两边行为本来就相同（`phoneShow` 找到元素就返回，`#phone-loc-after`
  在页面里总在），差别只在代码形状，共有绘制统一为「总是设 disabled=busy」并由
  下面的 DOM 对照证明。改完后这张表逐项对得上：第 1、2 条看两个调用方传的 ctx；
  第 3 条看共有绘制的统一写法加对照；第 4 条看两份 spec；第 5、6 条看调用方算的
  texts；第 7 条看 paintPhoneAccess 保留的加载错误行；第 8、12 条看两个适配函数；
  第 9、10、11 条看两个调用函数各自留下的段落。
- **两份改前改后的对照（最重要的证据）**，脚本都在本目录 `scripts/`，只读：
  - `phase_grid.mjs`（纯函数层）：网格 download.state 六档 × status 五档 ×
    ready/available/running 各两档 = **240 组**，旧 `phonePhase`/`ocrPhase`（git show
    从 `86db720` 取原文）对新适配逐一求值：**phonePhase 不同 0 组、ocrPhase 不同
    0 组**。开工提交对开工提交自检也是 0（脚本自身没毛病的证明）。
  - `row_dom_grid.py`（整页沙箱层）：同一张网格再叠 installing、busy、面板 notes 与
    OcrPanel.note/error 有无、组件位置有无、下载进度数字有无（各两档）= **7680 格**，
    在 `86db720` 导出副本与当前工作区各画一遍两行，76 个元素 × 7 类属性
    （hidden、disabled、textContent、className、dataset.state、style.width、
    aria-valuenow）逐项比对 = **4,085,760 条比对，不同 0 条**。开工提交对开工提交
    自检也是 0。限制：面板 notes 与 OcrPanel.note/error 在网格里是同一档开关，识别行「有错误、没备注」这种组合不在网格里。
- **变异结论**（`scripts/mutate_machine.py`，量的单位是用户看得到的每一个结果）：
  状态机判断链八条加派生事实八条、行绘制写元素语句二十条，共 **36 条**，在 mkdtemp
  副本里逐条做（定位按「文件、函数、那一行的文字」，跑组件相关的十个测试文件、
  按开销从小到大遇到第一个变红就停；node 沙箱偶发崩溃重跑一次不计）。**36/36 全部
  红在自己那条用例上，老缺口 0（改前同型变异与定位都核对过、无需补测试），
  新引入失守 0**，执行器退出 0。代表性结论：判断链各条的错位被
  `test_component_state_covers_every_state_in_order` 抓住（新文件 test_component_machine.py
  的逐状态断言）；派生事实被同一文件的派生断言与 `test_ui_component_rows.py` 的
  行为用例抓住；行绘制的每一处写元素语句各有一条用户看得到的断言变红
  （进度块 32.0 / 100.0 MB、aria-valuenow 32、填充宽度 32%、失败红条、取消句、
  「会装到」行、位置框 title 与路径文本、打开位置按钮禁用等）。
  执行方的 36 条里没有覆盖手机行开着时改写状态的那三行和识别行取消句的「没有面板错误」条件；审计另做的变异在这两处都没有用例变红，核实是改前就有的老缺口，于是在 test_ui_component_rows.py 补了两条用例（ComponentRowLeftoverTests）。
- **现有测试跟着换了什么**：只新增 `local/tests/test_component_machine.py`
  （5 条：状态逐个断言、派生事实、安装中叠在没装与需要更新上、两个适配函数的
  映射各一条，走 fixtures.ui_harness 的 run_js）。现有用例零改动；数「下载已取消，
  没有装任何东西。」出现次数的那两条读取范围不用扩——新模块里没有这句，它在
  手机行调用方保留的那份 texts 里，装配文件引用图（跳过识别两文件后）恰好一次。
- **复跑命令**（仓库根；对照与变异都只在临时目录的副本里做，仓库本体不动）：

  ```bash
  # 纯函数层对照（新代码读工作区；旧函数从开工提交取；末尾可再给一个提交引用作新方）
  node design/evidence/2026-11-15/component-machine/scripts/phase_grid.mjs 86db720
  # 整页沙箱对照（--new-ref 不给读工作区）
  python -B design/evidence/2026-11-15/component-machine/scripts/row_dom_grid.py --base-ref 86db720
  # 三十六条变异（36/36 红退出 0；有老缺口退出 2；有新引入失守退出 1）
  python -B design/evidence/2026-11-15/component-machine/scripts/mutate_machine.py --base-ref 86db720
  # 新测试与组件相关的既有测试
  python -B -m unittest discover -s local/tests -p test_component_machine.py
  python -B -m unittest discover -s local/tests -p test_ui_component_rows.py
  python -B -m unittest discover -s local/tests -p test_phone_ui.py
  # 大小与分层
  python -B -X utf8 tools/code_shape/check.py
  node tools/code_shape/ui_modules.mjs
  python -B -m unittest discover -s local/tests -p test_ui_layers.py
  ```
