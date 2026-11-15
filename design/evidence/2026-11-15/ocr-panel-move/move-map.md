# 搬家对照表（views/settings.js 验证码识别一节 → features/components 两个文件）

- 基准：整理那一笔提交里的 views/settings.js（403 行）；执行日期：2026-11-15。
- 每行 = 逐字核对脚本（scripts/move_check_ocr.py）按名字切出的一个段：基准行号范围、
  段的开头一句、按归层规则搬到的文件与新文件里的行号范围（声明行可多一个 export
  关键字，其余逐字相同且连续；段前紧挨着的注释随段一起搬；面板字段那段注释按路径
  注释规则只改一处——「本文件的动作」改指 views/settings.js）。
- 归层规则同上一批：不碰 DOM、不发桥接请求、不用定时器的纯推导归状态层；只读写 DOM
  和面板字段的归视图层；发桥接请求、绑定事件、打开关闭弹窗的归编排层。
- 复跑命令（仓库根）：
  `python -B design/evidence/2026-11-15/ocr-panel-move/scripts/move_check_ocr.py --tidy-ref 02454cb --move-ref 699e909`
  （六段逐字核对、settings.js 只剩两处连续删除、反向归类、三个模块文件 diff，退出码非零即不通过。）

| 基准行号 | 段的开头 | 层 | 落点 |
|---|---|---|---|
| 130-137 | function ocrFeature() { | 状态层 | features/components/state-ocr.js:5-12 |
| 139-148 | /* 验证码识别（settings-gap 二、OC01–OC15，原型 ocrView，Main.dc.html 1399–1411）。 | 状态层 | features/components/state-ocr.js:16-25 |
| 150-162 | /* 状态机：downloading / verifying 下载中 / broken 已装但加载失败（原型没画，保留，OC14）/ | 状态层 | features/components/state-ocr.js:29-41 |
| 164-168 | function ocrShow(selector, visible) { | 视图层 | features/components/view-ocr.js:10-14 |
| 170-177 | function ocrText(selector, text) { | 视图层 | features/components/view-ocr.js:18-25 |
| 191-311 | /* 标题行右侧二选一：没装放「下载并安装」（失败后「重新下载」）、已装没启用放「启用」、下载中放「取消下载 / 校验中…」、 | 视图层 | features/components/view-ocr.js:29-149 |

## 没搬的部分（留在 views/settings.js，仍是普通脚本）

- ocrLoadLocation、enableOcr、openOcrDir 三个发请求的函数与 paintSettings、wireSettings：
  它们的调用方都还在视图层普通脚本里——paintSettings 调 ocrLoadLocation，wireSettings
  的点击处理调 enableOcr 与 openOcrDir；搬过去会变成「视图层引用编排层」，要过只能往
  分层白名单加项，所以等设置页剩下的部分整体迁成模块时再一起搬。
- 搬完后的 views/settings.js 是 232 行，等于基准减去两整块（130-178 与 191-312，各含
  块后的一个分隔空行），逐行相等由逐字核对脚本验证。

## settings.js 剩下的普通脚本在哪些行、什么时机用到挂回的名字

挂回名单本批改为：OcrPanel、PhonePanel、maskAccount、paintOcrDownload、termsAccepted、
termsLocked（downloadFailText 搬走后不再有普通脚本在用，从名单删掉）。settings.js 里：

- `paintOcrDownload`（features/components/view-ocr.js）：paintSettings 第 54、55 行
  （打开抽屉时重画；55 行是位置查询回包后的补画）、enableOcr 第 148、160 行与
  openOcrDir 第 173 行（请求回包后重画）——都在函数被调用时才查名字，不在加载期。
- `OcrPanel`（features/components/state-ocr.js）：paintSettings 第 55 行、ocrLoadLocation
  第 132、135、138 行、enableOcr 第 144-147、155、157、158 行、openOcrDir 第 172 行
  ——同样是打开抽屉、点按钮、请求回包这些时机。
- `ocrLoadLocation`（131 行）、`enableOcr`（143 行）、`openOcrDir`（164 行）、
  `paintSettings`（51 行）定义在 settings.js 自己身上：paintSettings 由 openSettings
  第 22 行调用，enableOcr/openOcrDir 由 wireSettings 第 222、231 行的点击处理调用。
- ocrFeature、ocrPhase、ocrShow、ocrText 搬走后不再有普通脚本引用（模块图守卫的
  「普通脚本引用了只在模块里定义的名字」一类为空）。

## import 与挂回（显式写明，防拼接假绿）

- view-ocr.js 引 OcrPanel、ocrFeature、ocrPhase（来自 state-ocr.js）与 downloadFailText
  （来自同目录 state.js）；components/actions.js 引 OcrPanel；phone-access/view.js 引
  paintOcrDownload——这三处原本靠「typeof 名字」兜底引用，拼接测试里模块名字恰好是
  全局的，缺了 import 照样全绿，真窗口里却是 undefined；模块图守卫的「缺 import」
  一类能抓到，真加载断言再补看得见的那条。
- legacy-globals.js 加挂 OcrPanel 与 paintOcrDownload（settings.js 还在用），删掉
  downloadFailText（连同它的 import）。
