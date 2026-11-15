# 验证码识别一节的状态与绘制搬成模块（只搬）的证据

- **基线提交**：`9c3fd44`（分支 refactor/step1；开工时工作区里另有一处本会话之外的
  AGENTS.md 改动，未触碰）。执行日期：2026-11-15。分两步做：先落一个只动注释与缩进的
  整理补丁（可单独提交），再搬家。
- **搬了什么**：views/settings.js 里验证码识别一节的六个顶层名字——状态层
  ocrFeature、OcrPanel、ocrPhase 进 `features/components/state-ocr.js`，视图层
  ocrShow、ocrText、paintOcrDownload 进 `features/components/view-ocr.js`。函数体、
  对象字面量、段前紧挨着的注释逐字照搬（缩进不变），声明行只加 `export`；ocrShow 与
  ocrText 不合并、window.PhonePanel 写法照留。settings.js 从 403 行减到 232 行，等于
  基准减去两整块（130-178 与 191-312，各含块后一个分隔空行），逐行相等由核对脚本验证。
- **为什么那三个函数不搬**：ocrLoadLocation、enableOcr、openOcrDir 的调用方都还在
  视图层普通脚本里——paintSettings 调 ocrLoadLocation，wireSettings 的点击处理调
  enableOcr 与 openOcrDir；搬进编排层文件就成「视图层引用编排层」，要过只能往分层
  白名单加项，那是不允许的。它们与 paintSettings、wireSettings 一起留在 settings.js，
  等设置页剩下的部分整体迁成模块时再搬。settings.js 因此仍是普通脚本。
- **归层规则**：同上一批——不碰 DOM、不发桥接请求、不用定时器的纯推导归状态层；
  只读写 DOM 和面板字段的归视图层。视图层文件里没有发桥接请求、没有调编排层函数。
- **为什么要显式 import**：上一批搬好的模块里有三处用「typeof 名字」兜底引用识别一节
  或下载失败文案——components/actions.js 的 OcrPanel（三处）、phone-access/view.js 的
  paintOcrDownload、识别一节自己用的 downloadFailText。搬完以后这些名字都定义在模块里，
  不写 import 的话拼接测试照样全绿（拼接后模块名字恰好是全局的），真窗口里却是
  undefined，识别一节的提示、红条文案和重画会悄悄失效。本批按规则全部写成单行具名
  import：view-ocr.js 引 OcrPanel、ocrFeature、ocrPhase、downloadFailText；
  components/actions.js 引 OcrPanel；phone-access/view.js 引 paintOcrDownload。
  五条变异（删三条 import、去两个挂回）证明了拼接类用例对缺 import 免疫、只有模块图
  守卫与真加载断言能抓，见 `wiring.md`。
- **挂回名单**：legacy-globals.js 加挂 OcrPanel 与 paintOcrDownload（settings.js 还在
  用，都在函数被调用时才查名字），删掉 downloadFailText（连同它的 import）——搬走后
  不再有普通脚本用它。守卫报告：挂回名单 OcrPanel、PhonePanel、maskAccount、
  paintOcrDownload、termsAccepted、termsLocked；「模块用到的普通脚本全局名字」少了
  OcrPanel 与 paintOcrDownload，剩 $、S、api、openSettings、paintCountdown、
  paintStatusCards、refresh。
- **逐字核对**：`scripts/move_check_ocr.py` 以整理那一笔提交里的 settings.js（403 行）
  为准，按名字切六段（连同段前注释），逐段在两个新
  文件里找一字不差的一段——6/6 全部找到且相同（声明行只多一个 export；面板字段那段
  注释只差「本文件的动作」改指 views/settings.js 这一处）；settings.js 只剩两处连续
  删除；两个新文件多出的非空行 4 行全部归类（两条文件头注释、两条 import），分不出类
  为 0；上一批的三个模块文件相对基线的 diff 只有加的 import 行、路径注释替换，以及
  整理那一步挪「多久以前」注释的那一处。逐段落点见 `move-map.md`。
- **整理补丁（可单独提交）**：只动注释与空白——过渡名单里挂 PhonePanel 那三行缩进
  进函数体；startPhonePanel 函数体缩进并去掉首尾空行；组件状态层文件头的「组件组件」
  改「组件」；「多久以前」那条注释从登录恢复的打码函数上面挪到 phone-access/state.js
  里 agoText 声明正上方，两边多出的空行各收成一行；settings.js 里两行注释指向
  phone.js 的旧路径改成新位置。六个文件改前改后的记号序列（tools/code_shape/jslex.mjs
  的 tokenize，注释不进记号）完全相同；补丁能干净套用到基线提交。
- **安全网重跑**：83 行加组件 9 个出口，其中 ocrPhase 的 8 行与 paintOcrDownload 的
  18 行换到两个新文件（其余 66 行原样），逐行重跑：未变异基线 451 例全绿（与上一批
  同数），92/92 逐行结论、变红用例集合、先红断言与上一批搬完后的对照全部相同；
  结论分布 行为测试已守 89、等价 1（installing-failText-ocr，同一行同一理由）、
  页面里没有这个元素 2（busy-paint 与 busy-paint-remove），与上一批一致。
  见 `net-after-move.md`。
- **接线变异重跑**：35 处绑定（全在本批没动的文件里）逐处变异重跑，与上一批搬完后
  的结论 35/35 逐条相同（含变红用例与先红断言原文），见 `wiring.md`。
- **真加载**：新增四条真加载断言（打开抽屉发一次查组件位置的请求、点「启用」发请求
  且识别行说明出现启用成功那句、点「打开所在文件夹」发请求、下载失败后红条先看得见
  再核对文字），连同上一批的四条共 8 例全过。删 view-ocr.js 引 downloadFailText 的
  import 之后，真加载第四条真的变红（红条退回兜底文案），模块图守卫缺 import 一类
  非空；同样的副本里拼接类用例照常绿。见 `real-load-output.md`。
- **守卫与名单**：模块图守卫五类问题（顶层循环、缺 import、普通脚本引用了没挂回的
  模块名字、违反层规则、挂出去没人用）全部为空；期望值用 `--expect` 重新生成。
  三份名单的 diff：`baseline.json` 只把 views/settings.js::paintOcrDownload 一条的键
  改到 features/components/view-ocr.js（记录值 119 与理由不变）；`ui_layer_allow.json`
  未动（守卫不要求删项）；`ui_modules_expect.json` 由工具生成。
- **现有测试跟着搬家**：夹具 `module_group_raw_src` 加可选的跳过清单参数（不给时行为
  不变）；test_phone_ui.py 里两处数手机面板文案出现次数的用例把读取范围改成跳过
  features/components/state-ocr.js 与 view-ocr.js（新增一个常量），断言一个字不动——
  识别的视图文件经新 import 进了装配文件的引用组，同一句「下载已取消，没有装任何
  东西。」会被多数一次。test_ui_modules.py 新增真加载四条。除此之外现有测试零改动。
  用例数：test_phone_ui 210→210、test_ui_component_rows 12→12、test_ui_panel_wiring
  35→35、test_reason_maps 2→2、test_ui_contract_* 365→365、test_ui_layers 4→4、
  test_code_shape 14→14；test_ui_modules 10→14，多出的四条是本批新增的真加载断言。
- **夹具不认异步导出（留给下一批）**：测试夹具剥壳的两份实现（Python 拼接一份、
  node 沙箱一份）只认 `export function/const/let/var/class`，不认 `export async
  function`。本批没搬异步函数（ocrLoadLocation、enableOcr、openOcrDir 三个异步函数
  留在 settings.js），所以碰不到；设置页整体迁移那一批搬异步函数前要先补夹具。
- **打包口径（只读确认）**：`local/build/build_exe.py` 把整个 `local/ui` 目录作为资源
  根打包，新文件不需要另外登记。
- **复跑命令**（仓库根，Python 一律带 `-B`；变异只在临时目录下的仓库副本里做，
  仓库本体不动）：

  ```bash
  # 整理补丁的记号序列比对（6 个文件）
  node design/evidence/2026-11-15/ocr-panel-move/scripts/tidy_tokens.mjs 9c3fd44 02454cb
  # 逐字核对（六段 + settings 只剩两处连续删除 + 反向归类 + 三个模块文件 diff）
  python -B design/evidence/2026-11-15/ocr-panel-move/scripts/move_check_ocr.py --tidy-ref 02454cb --move-ref 699e909
  # 安全网 92 行（可加 --shard i --shards 4 并行；--baseline 未变异基线）
  python -B design/evidence/2026-11-15/ocr-panel-move/scripts/run_after_ocr_move.py --baseline
  python -B design/evidence/2026-11-15/ocr-panel-move/scripts/run_after_ocr_move.py
  # 接线变异重跑
  python -B design/evidence/2026-11-14/phone-panel-move/scripts/mutate_wiring.py --stage 搬之后
  # 五条 import 与挂回变异
  python -B design/evidence/2026-11-15/ocr-panel-move/scripts/mutate_imports.py
  # 真加载八例 + 删 import 变异
  python -B -m unittest discover -s local/tests -p "test_ui_modules.py" -v -k NativeLoadSmokeTests
  python -B design/evidence/2026-11-15/ocr-panel-move/scripts/real_load_import_mutation.py
  # 守卫
  python -B -X utf8 tools/code_shape/check.py
  node tools/code_shape/ui_modules.mjs
  ```
