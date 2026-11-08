# L8 对抗审阅合并：a11y-names.md 判定与处置（2026-11-08）

被审报告：`design/evidence/2026-11-08/a11y-names.md`（L8 无障碍名称静态审计：129 button + 30 input/select/textarea + 11 对话框 = 170 控件，汇总结论、问题清单 10 条、最严重 5 条）。本文件合并对抗双方结论。双方 0 红牌、全部条目站得住，故报告正文一字未改，仅按第五节结论在报告尾部补「对抗复核（2026-11-08）」小节。合并人未动 `<过程留证>/` 与任何代码、测试。

## 一、方法与输入

- **对抗 A（实质反证，前端开发者）**：`<过程留证>/adv-L8-a.md`（留证 `l8_audit_adv.py` 独立复算脚本、`l8-adv-out.txt` 逐控件输出、`l8_adv_diff.py` 报告表 vs 复算逐格比对、`l8_adv_text.py` 可见文本逐字比对；python -I 隔离运行，输入仅 index.html 两份与报告本体）。**覆盖**：
  1. **170 控件独立复算全量（不抽样）**：三类分母 129=110+19、30=22+8、11=11+0（原生 dialog 5 + role="dialog" 6、alertdialog 0）全对；逐格比对三张表（文件、行号、id、名称来源、type、form内、hidden；对话框另比 aria-modal 值、labelledby 目标 id/行号/文本、aria-label）——170 行全部对应、行号与 id 无一错位，**实质不一致 0 条**。
  2. **124 行文本逐字**：非省略号 124 行可见文本逐字比对**实质差异 0 条**；7 处脚本侧差异均为伪差（「(空)」是报告对空文本的标记、#clock 两 span 按渲染拼接无空格、行 312 因跳过省略号行造成的候选错位实际均一致）；省略号 5 行（80/102/103/106/107）为明确标注的截断，与源文一致；附录 4 条 label 引用核对成立（@71 为带 … 截断，方向正确）。
  3. **汇总结论逐项复算**：名称来源 aria-label 9 + 文本内容 120 = 129、无名称 0、title 兜底 0、labelledby 0、缺 type 0、submit 3；输入 19+2+9=30；placeholder 6 处全部另有 aria-label；缺 aria-modal 8/11（true 2/false 1）、labelledby 8 个目标 id 全存在、唯一静态空目标 #tour-title；hidden 93/129（self 7 + anc 65 + self+anc 21）、21/30（全部仅祖先）、6/11——全部与报告一致；报告「抽查复核」四条全部复现。
  4. **重点复核 6 项**（见三节）；红牌扫描 0。
- **对抗 B（机械核验，技术文档工程师）**：`<过程留证>/adv-L8-b.md`（复现脚本 l8-mech1..4.py、输出 out.txt）。结构完整性（三表 129/30/11 行、序号连续、必备要素齐备）、170 行「文件+行号+id+tag」与源精确一一对应且反向无遗漏、分母 grep -o 复算、属性逐字偏差 0（表1 type 129/129、表2 30/30 含 3 处「type缺省→text」、表3 aria-modal 与 labelledby 11/11、问题清单 10 条当前态属性、6 处 placeholder、4 条 label 引用）、统计重算 29 项全 OK（hidden 双口径一致）、红牌扫描 0。
- **身份安排（如实披露）**：B 即 L8 原分析者本人，与「审阅者未参与原分析」存在张力；处置沿用 L6/L7 口径——**B 只承担脚本可复算的机械项，全部实质/语义判定由未参与原分析的前端开发者（A）独立承担**。B 未触碰 <过程留证>/ 其余目录、design/evidence 其余目录与凭据。
- **合并口径**：实质判定以 A 为准、机械项以 B 为准；红牌双方 0，无需要合并人实测定档的争议项。

## 二、三档汇总（总 170 控件 + 汇总结论）

| 档 | 条数 | 条目 |
|---|---|---|
| 站得住 | 全部 | 170 控件（129+30+11）逐格比对 0 不一致；124 行文本逐字 0 实质差异；三类分母 129/30/11；全部汇总结论（名称来源 9+120、无名称 0、缺 type 0、输入 19+2+9、placeholder 6、缺 aria-modal 8/11、labelledby 无效 1、hidden 93/21/6）；重点复核 6 项 |
| 部分站不住 | 0 | — |
| 推翻 | 0 | — |

红牌 **0** 张：双方独立扫描三张红牌项（判定无 文件:行、属性/文本引用非逐字、「无法验证」写成「未实现/违规」）均为 0。A 补充旁证：5 个原生 dialog 的 showModal 调用全部落实（terms.js:265/348、relogin.js:62、window.js:74、phone.js:695），无 .show() 路径——「showModal 隐式 modal 不构成 WCAG 违规」的前提成立。

## 三、重点复核 6 项（A 实质复核，B 机械复算一致）

| # | 项 | 复核结果 |
|---|---|---|
| 1 | #tour-card 静态空标题（index.html:336→338） | aria-labelledby="tour-title" 指向 h3#tour-title 静态空；JS 填充在 views/tour.js:119（paintTour），startTour()（tour.js:60-61，先 hidden=false 后 paintTour）与 tourResumeNow()（107-110）取消隐藏与填标题在同一同步任务内，实际不存在「先开后填」的中间渲染帧。报告按自声明静态口径判「静态无效」、运行时影响用「若……」条件句并明示交动态核验——定性准确、未越界 |
| 2 | 三个 .pop 弹层（#clock-pop:349 / #login-pop:351 / #phone-pop:358） | role="dialog" + aria-label（逐字）+ hidden、无 aria-modal 复算一致；role=dialog 缺省即非模态，「建议补 aria-modal=false」是增强项而非违规，报告原话即「建议/低风险增强项」——判定与建议准确 |
| 3 | #settings aria-modal=false 定性（aside:207） | aria-modal="false" aria-labelledby="settings-title" hidden 逐字在源；不计入「缺 8/11」、定性「非模态抽屉正确语义（非缺陷）」、焦点边界交动态核验——准确且未越界 |
| 4 | 6 处 placeholder 并存 | q(36)/comp-phone-path(437)/comp-ocr-path(445)/pair-code(m:24)/m#q(78)/code(m:119) 全部与 aria-label 并存，无一例仅靠 placeholder 撑名称——报告成立 |
| 5 | 3 个 submit 在 form method=dialog | 行 112/191/203 均显式 type="submit" 且位于 `<form method="dialog">` 内——「对话框关闭/确认的正确用法」成立 |
| 6 | hidden 93/21/6 | 复算成立（button self 7 + anc 65 + self+anc 21 = 93；输入 21 全部仅祖先，与表内 hidden(祖先) 标注恰确；对话框 6），表内逐行标注、解析器、源 HTML 三方一致 |

## 四、观察项（非红牌，不改报告正文，仅记于此）

1. **A（views/tour.js 说明）**：任务书所写 controllers/tour.js 不存在，实为 views/tour.js；报告本身未指认 JS 文件路径，故不构成报告错误（报告引用本身正确）。
2. **B（P 编号引用说明）**：「最严重 5 条」第 4、5 条无自带 文件:行，以 P6-P10 / 问题1、问题3 编号指代，属汇总引用，未引入新判定。

## 五、结论

- 双方 0 红牌、无推翻项，**无需修改报告正文**；a11y-names.md 仅在尾部补「对抗复核（2026-11-08）」小节（5 行），原表、判定与汇总一字不动。
- 观察项 2 条按第四节记录在案，不触发修订。L8 审阅闭环，无 DEFERRED 项。
