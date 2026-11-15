# 两行组件在「共有部分」上的差别表（动手前逐项列出）

- 基准：开工提交 `86db720` 里的 `features/phone-access/view.js`（paintPhoneAccess）
  与 `features/components/view-ocr.js`（paintOcrDownload）；认阶段为
  `features/phone-access/state.js` 的 phonePhase 与 `features/components/state-ocr.js`
  的 ocrPhase。只读代码得出，未改任何产品文件。执行日期：2026-11-15。
- **共有部分**（两边都画、判断逻辑逐项相同，收进 features/components/view-row.js
  的 paintComponentRow）：标题行主按钮（hidden = 非 missing 且非 outdated；disabled =
  busy ∥ installing；文案 = outdated「更新组件」/ failed「重新下载」/ 其余「下载并安装」）、
  取消按钮（hidden = ¬downloading；disabled = busy ∥ verifying；文案 verifying「校验中…」
  其余「取消下载」）、「没装」块显隐（missing ∧ ¬installing）、导入兜底行显隐
  ((missing ∥ outdated) ∧ failed ∧ ¬installing)、进度块显隐（loading）、进度文字四态
  （installing「正在安装组件…」/ checking「正在检查组件…」/ verifying「下载完成，正在校验
  组件…」/ 其余各行自己的下载文案）、MB 数（state = downloading ∧ total > 0）、
  aria-valuenow 与填充宽度（verifying 100%，其余 total > 0 时按比例夹到 0–100，否则 0）、
  红条与取消句的「有字才显示」机制、「会装到 / 装在」两行的显隐（missing ↔ 其余且 ¬loading）、
  位置框 title 与路径 code、「打开所在文件夹」的 disabled = busy。
- **逐项差别**与改完后由谁保留：

| # | 差别 | 改前现状（元素、条件、文字） | 改完后由谁保留 |
|---|---|---|---|
| 1 | busy 的来源 | 手机行只读 `PhonePanel.busy`；识别行读 `OcrPanel.busy ∥ PhonePanel.busy` | 调用方算好放进 `componentState` 的 ctx.busy，抄进 facts；共有绘制只消费 facts |
| 2 | installing 的来源 | `PhonePanel.installing.phone_control` vs `.relogin_ocr` | 同上，调用方放进 ctx.installing |
| 3 | 「打开所在文件夹」禁用的写法 | 手机行包在 `if (after)` 里、识别行总是设——但 `phoneShow` 找到元素就返回（`#phone-loc-after` 在页面里总在），所以两边**行为相同**：每次绘制都设 `disabled = busy`。差别只在代码形状，不在用户看得到的结果 | 共有绘制统一为「总是设 disabled = busy」；`row_dom_grid.py` 在 busy × 位置有无的全部交叉格上证明改前改后逐项相同 |
| 4 | 下载中的进度文案 | 「正在下载手机控制组件」vs「正在下载验证码识别组件」 | spec.downloadText——两行各一份 spec 常量，放在各自的视图文件里 |
| 5 | 红条的内容与条件 | 手机 `#phone-component-error`：(missing ∥ outdated) ∧ ¬installing 才写，内容 `notes.missing ∥ downloadFailText`；识别 `#ocr-download-error`：任何阶段都写 `OcrPanel.error`（installing 时整条清空），failText 只在 (missing ∥ outdated) ∧ failed ∧ ¬installing 拼进 | texts.componentError 由调用方算好（各自的优先级与清空条件原样保留），共有绘制只负责写入 spec.errorId 的「有字才显示」 |
| 6 | 取消后那句话 | 手机 `#phone-component-state`：missing ∧ ¬missingErr ∧ cancelled 才说「下载已取消，没有装任何东西。」；识别 `#ocr-note`：`OcrPanel.note ∥`（missing ∧ cancelled ∧ ¬error ∧ ¬failText 才说同一句）——识别行同一元素要先让位给「刚装好那句」 | texts.cancelledNote 由调用方算好，共有绘制写入 spec.cancelledNoteId。手机行 off 态还有第二句「下载已取消，现有组件没有改动。」写在 `#phone-off-note`（识别行没有）→ 手机调用方自己画 |
| 7 | 进度块里的加载错误行 | `#phone-loading-error`（loading ? notes.loading : ""）只有手机行有；识别行的进度块里没有错误行 | 手机调用方自己画，留在 paintPhoneAccess |
| 8 | 手机行 phase 先看 running | phonePhase 开头 `if (st && st.running) return "on"`；识别行没有这一档 | phonePhase 适配层保留该分支；componentState 不管 running |
| 9 | 「刚装好」那句 | 手机：下载 → 校验 → installed 时把一句写进 notes.off（「手机控制组件已安装，选一条通道就能开启。」）；识别：同一转移把一句写进 OcrPanel.note（「验证码识别组件已安装并启用。」）——文字、落点、后续优先级都不同 | 各自调用方保留（面板字段的读写原样留在 paintPhoneAccess / paintOcrDownload） |
| 10 | 手机行特有的行内件 | 状态 chip（off/on/outdated/broken/disabled 五态 + linked 色调）、lead、feature-error、featureBtn（重新导入组件包 / 启用手机控制 / 安装·更换组件包 + dataset.action）、通道卡、开启/关闭、配对、二维码、地址…… | 留在 paintPhoneAccess，不进共有绘制 |
| 11 | 识别行特有的行内件 | title-chip（off 时显「未启用」）、「启用」按钮、「重新导入组件包」按钮、带版本号的 lead、`#ocr-off-note` 块显隐 | 留在 paintOcrDownload，不进共有绘制 |
| 12 | 识别状态映射的返回值 | phonePhase：ready→off、available→disabled；ocrPhase：ready→on、available→off | 两个适配函数按 enabled→（手机 off / 识别 on）、disabled→（手机 disabled / 识别 off）、其余同名映射；名字、参数、返回值不变 |

- 认阶段的判断顺序（下载中 → 校验中 → 检查中 → 需要更新 → 坏了 → 已启用 → 已装没启用 →
  没装）两份除「手机访问开着为 on」一档外逐行相同，收进 componentState 后由两个适配
  函数各自映射回去（第 8、12 条）。
- 改完后这张表逐项对得上：第 1、2 条看两个调用方传的 ctx；第 3 条看共有绘制的统一写法
  加对照脚本；第 4 条看两份 spec 常量；第 5、6 条看两个调用方算的 texts；第 7 条看
  paintPhoneAccess 里保留的那一行；第 8、12 条看两个适配函数；第 9、10、11 条看两个
  调用函数各自留下的段落。
