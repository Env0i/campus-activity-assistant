# 手机面板搬成模块（只搬）的证据

- **基线提交**：`15dde9b`（分支 refactor/step1，开工时工作区干净）。执行日期：2026-11-14。
- **搬了什么**：`local/ui/views/phone.js`（1252 行）整文件拆进 `local/ui/features` 下三个
  功能目录——`phone-access/`（state、view、actions、actions-panel 四个文件）、
  `components/`（state、view、actions）、`login/`（state-recovery、view-recovery、
  actions-recovery）。方法体、函数体、它们前面紧挨着的注释逐字照搬，缩进不变；声明行
  只加 `export`；其余方法按层分装进七个「方法包」，由编排层的 actions-panel.js 用一句
  Object.assign 一次装回 PhonePanel。PhonePanel 本体（全部字段与四个只读推导方法）在
  phone-access/state.js。**没搬的**：views/settings.js 里验证码识别那一半（OcrPanel 与
  它的绘制、启用、打开目录）仍是普通脚本，本批只改 wireSettings 里那两处绑定；
  views/phone.js 已删除。
- **归层规则**：不碰 DOM、不发桥接请求、不用定时器的纯推导归状态层；只读写 DOM 和面板
  字段的归视图层；发桥接请求、用定时器或剪贴板、绑定事件、打开关闭弹窗的归编排层。
  按这条规则改了归属的名字与没点到名的成员怎么落的，逐条见 `move-map.md`。
- **设置页那两处为什么改**：wireSettings 在普通脚本阶段执行，那时模块还没跑、
  `window.PhonePanel` 不存在；原来「绑定之前先判断在不在」会让「下载并安装」「取消下载」
  两颗按钮永远绑不上。把判断挪进点击处理里（写法同同一函数里导入按钮那处现成的样子），
  这是本批除搬以外唯一的产品改动。接线测试用「把设置页两处改回原样」的变异证明了这
  一点：改回原样后识别行那两条接线断言变红，其余 33 例仍绿
  （复跑命令见下，`revert_settings_check.py`，只在临时目录下的仓库副本里做）。
- **接线测试**：新文件 `local/tests/test_ui_panel_wiring.py`，35 处事件绑定（面板 wire 里
  29 处、设置页验证码识别 6 处）每处一条用例，先于搬家编写、在基线代码上全绿（35 例）；
  每处绑定的动作行换成空语句的变异全部红在它自己那句断言上，搬之前与搬之后逐条结论
  相同，见 `wiring.md`（行清单与执行器在 `scripts/mutate_wiring.py`）。
- **逐字核对**：`scripts/move_check.py` 从基线提交取出原文件机械切段（含段前紧挨着的
  注释），逐段在十个新位置找一字不差的一段——87 段全部找到且相同（声明行可多一个
  export）；反向列出九个新文件里多出来的 74 个非空行，全部归入文件头注释、import、
  导出的包装、方法包与导出的包装、装配、启动函数六类，分不出类的为 0。
  文件尾两段的去向：判断 readyState 调 wire 的那段包进导出的启动函数 startPhonePanel
  （main.js 在放出排队的后端事件之后调用）；挂回 window 的那段搬进 legacy-globals.js，
  另挂回 maskAccount 与 downloadFailText。
- **安全网重跑**：认阶段 17 行、读进行中标志 18 行、使用点 46 行、检查中探针 2 行
  （共 83 行）加出口那一批组件的 9 个出口，在搬走后的新位置各做一次同样的变异，
  复用 2026-11-14 组件安全网的执行器（行清单在 `scripts/rows_after_move.py`，只换
  文件路径，函数名与该行原文一个字不改）。逐行对照见 `net-after-move.md`：
  83 行逐行相同（83/83）、9 个出口相同（9/9）；搬之后结论分布 行为测试已守 89、
  等价 1（installing-failText-ocr，同一行同一理由）、页面里没有这个元素 2
  （busy-paint 与 busy-paint-remove），与搬之前完全一致；未变异基线相关集合 451 例全绿。
- **守卫与名单**：模块图守卫五类问题（顶层循环、缺 import、普通脚本引用了没挂回的
  模块名字、违反层规则、挂出去没人用）全部为空；`ui_modules_expect.json` 用
  `--expect` 重新生成。「模块用到的普通脚本全局名字」为 `$`、`OcrPanel`、`S`、`api`、
  `openSettings`、`paintCountdown`、`paintOcrDownload`、`paintStatusCards`、`refresh`——
  取元素、桥接、设置页与状态卡的名字都在预期内；其中 refresh 与 paintCountdown 是扫描
  把方法简写的名字当成了对同名全局函数的引用，属于工具精度问题，这一批不改工具。
  挂回 window 的名字：PhonePanel、maskAccount、downloadFailText 加原有的
  termsAccepted、termsLocked。三份名单的 diff：`baseline.json` 删掉 views/phone.js 的
  文件项并把 paintPhoneAccess（262）、paintRelogin（88）、wire（65）三条的键改到新路径，
  记录值与理由不变；`ui_layer_allow.json` 只删 views/phone.js 那一组。
- **真加载**：真加载冒烟那条断言从「挂回 window 的每个名字都是函数」放宽为「有定义」
  （PhonePanel 是对象）——这是本批唯一被放宽的现有断言，其余断言零改动
  （`test_ui_modules.py` 的 NativeLoadSmokeTests）。同一处夹具加了可选的 after 片段参数，
  用它加三类真加载断言（成员名排序后与搬之前逐个相等、识别行下载与取消各发一次请求、
  手机行开启发请求），四例全过。
- **现有测试跟着搬家**：约四十处按路径加载换成装配文件的路径常量，读源码的几处改读
  这组模块的原文拼接，桌面入口的加载路径断言随脚本搬家改到页面脚本清单；加载路径与
  读取路径之外，现有测试的断言零改动（diff 见结果目录 existing-tests-diff.patch 的
  逐行清单）。用例数：test_phone_ui 210→210、test_reason_maps 2→2、
  test_ui_contract_components 15→15、test_ui_contract_settings 45→45；
  test_ui_modules 7→10，多出的三条是本批按要求新增的真加载断言；其余多出的用例全部
  来自新文件 test_ui_panel_wiring.py（35 条）。
- **打包口径（只读确认）**：`local/build/build_exe.py` 把整个 `local/ui` 目录作为资源
  根打包（`--add-data <local/ui> ui`），新子目录不需要另外登记。
- **出口脚本的行号失效**：`design/evidence/2026-11-13/exit-path-tests/scripts/mutate_exits.py`
  按 dddc179 的行号定位 views/phone.js，本批搬走后这些行号对这个文件已经失效；新位置的
  重跑走本目录 `scripts/run_after_move.py`（按「文件、函数、那一行的文字」定位）。
- **复跑命令**（仓库根，Python 一律带 `-B`；变异只在 tempfile.gettempdir() 之下的仓库
  副本里做，仓库本体不动）：

  ```bash
  # 逐字核对（87 段 + 反向归类，退出码非零即不通过）
  python -B design/evidence/2026-11-14/phone-panel-move/scripts/move_check.py
  # 接线变异（--stage 搬之前 / 搬之后）
  python -B design/evidence/2026-11-14/phone-panel-move/scripts/mutate_wiring.py --stage 搬之后
  # 安全网 83 行 + 9 个出口在新位置重跑（可加 --shard i --shards 4 并行）
  python -B design/evidence/2026-11-14/phone-panel-move/scripts/run_after_move.py --verify
  python -B design/evidence/2026-11-14/phone-panel-move/scripts/run_after_move.py --baseline
  python -B design/evidence/2026-11-14/phone-panel-move/scripts/run_after_move.py
  # 把设置页两处改回原样的验证（副本里做，识别行两条接线断言必须变红）
  python -B design/evidence/2026-11-14/phone-panel-move/scripts/revert_settings_check.py
  # 真加载四例
  python -B -m unittest discover -s local/tests -p "test_ui_modules.py" -v -k NativeLoadSmokeTests
  # 守卫
  python -B -X utf8 tools/code_shape/check.py
  node tools/code_shape/ui_modules.mjs
  ```
