# 搬家对照表（views/phone.js → features 下三个功能目录）

- 基线提交：15dde9b（views/phone.js，1252 行）。执行日期：2026-11-14。
- 每行 = 逐字核对脚本（scripts/move_check.py）机械切出的一个段：原文件行号范围、段的开头一句、按归层规则搬到的文件与新文件里的行号范围（声明行可多一个 export 关键字，其余逐字相同且连续；段前紧挨着的注释随段一起搬）。
- 归层规则：不碰 DOM、不发桥接请求、不用定时器的纯推导归状态层；只读写 DOM 和面板字段的归视图层；发桥接请求、用定时器或剪贴板、绑定事件、打开关闭弹窗的归编排层。
- 复跑命令：`python -B design/evidence/2026-11-14/phone-panel-move/scripts/move_check.py`（逐段核对，退出码非零即有段没找到或分不出类；--json 可出逐段落点）。

| 原文行号 | 段的开头 | 层 | 落点 |
|---|---|---|---|
| 1-1 | "use strict"; | 状态层 | features/phone-access/state.js:6-6 |
| 9-25 | /* 手机访问状态机（settings-gap PH07，原型 phView，M | 状态层 | features/phone-access/state.js:18-34 |
| 27-33 | /* PH06 / PH23（审核决定 A4）：「手机已连接」= 开着，且本次兑 | 状态层 | features/phone-access/state.js:38-44 |
| 35-60 | /* PH17：两张通道卡的文案逐字照原型 phView（1270–1273 行 | 状态层 | features/phone-access/state.js:48-73 |
| 62-68 | /* IM03：导入自检的结论文案，字面照原型 impCheck（Main.dc | 状态层 | features/components/state.js:5-11 |
| 70-93 | function importCheckText(key, path, info | 视图层 | features/components/view.js:11-34 |
| 95-105 | /* PH11：下载失败照原型拼「下载没有完成：原因，可以重试。」。G2：限流、 | 状态层 | features/components/state.js:15-25 |
| 107-115 | function downloadFailText(download) { | 状态层 | features/components/state.js:29-37 |
| 117-121 | /* PH25：倒计时句改成原型的「m:ss 后失效，一码只能用一次」；点阵二维 | 状态层 | features/phone-access/state.js:77-81 |
| 123-129 | /* 「多久以前」的人话：秒/分/小时/天四档，超过一天不再精确到分钟。 */ | 状态层 | features/login/state-recovery.js:5-11 |
| 131-137 | function agoText(seconds) { | 状态层 | features/phone-access/state.js:85-91 |
| 139-143 | function phoneShow(selector, visible) { | 视图层 | features/phone-access/view.js:10-14 |
| 145-152 | function phoneText(selector, text) { | 视图层 | features/phone-access/view.js:18-25 |
| 155-160 | state: { | 状态层 | features/phone-access/state.js:97-102 |
| 161-161 | busy: false, | 状态层 | features/phone-access/state.js:103-103 |
| 162-164 | // 开启/关闭是有耗时的动作（Cloudflare 要等隧道出域名），单独记一 | 状态层 | features/phone-access/state.js:104-106 |
| 165-165 | pollTimer: null, | 状态层 | features/phone-access/state.js:107-107 |
| 166-166 | pollTicks: 0, | 状态层 | features/phone-access/state.js:108-108 |
| 167-167 | tickTimer: null, | 状态层 | features/phone-access/state.js:109-109 |
| 168-168 | lastCode: "", | 状态层 | features/phone-access/state.js:110-110 |
| 169-170 | // 用户在通道卡里点的那一条；没点过时用快照里记住的偏好 | 状态层 | features/phone-access/state.js:111-112 |
| 171-172 | // PH30：反馈就地显示在各块里，不再写抽屉最底部（用户在上面点，底部那行可 | 状态层 | features/phone-access/state.js:113-114 |
| 173-174 | // PH28 关闭确认开着；PH29 点了「再配对一台手机」（addPairA | 状态层 | features/phone-access/state.js:115-116 |
| 175-175 | addPair: false, | 状态层 | features/phone-access/state.js:117-117 |
| 176-176 | addPairAt: 0, | 状态层 | features/phone-access/state.js:118-118 |
| 177-177 | copied: false, | 状态层 | features/phone-access/state.js:119-119 |
| 178-178 | copyTimer: null, | 状态层 | features/phone-access/state.js:120-120 |
| 179-180 | // PH09：组件位置只走电脑端专用接口 B3，取不到就是 null，界面不显 | 状态层 | features/phone-access/state.js:121-122 |
| 181-181 | lastDownload: "", | 状态层 | features/phone-access/state.js:123-123 |
| 182-183 | // 配对码倒计时：快照给剩余秒数，两次刷新之间每秒自减，不读墙钟 | 状态层 | features/phone-access/state.js:124-125 |
| 184-184 | codeSync: null, | 状态层 | features/phone-access/state.js:126-126 |
| 185-186 | // 对话框里「选中的文件」与「自检通过的文件」分开记：自检不过时不能安装 | 状态层 | features/phone-access/state.js:127-128 |
| 187-187 | verified: { phone_control: "", relogin_o | 状态层 | features/phone-access/state.js:129-129 |
| 188-189 | // 清除账号要先确认：确认行开着时不能被轮询刷新顺手关掉 | 状态层 | features/phone-access/state.js:130-131 |
| 190-191 | // CR11：账号表单是否展开、行内反馈（CR19）；导入弹窗当前在导入哪个组 | 状态层 | features/phone-access/state.js:132-133 |
| 192-192 | credNote: "", | 状态层 | features/phone-access/state.js:134-134 |
| 193-193 | credNoteTone: "ok", | 状态层 | features/phone-access/state.js:135-135 |
| 194-194 | importKey: "phone_control", | 状态层 | features/phone-access/state.js:136-136 |
| 195-196 | // I1：点「安装这份」到 refresh 返回为止，按功能记「安装中」；这段 | 状态层 | features/phone-access/state.js:137-138 |
| 198-213 | async refresh() { | 编排层 | features/phone-access/actions.js:12-27 |
| 215-225 | /* PH09：位置只问一次就记住（数据目录这次运行里不会变）；没拿到就下次刷新 | 编排层 | features/components/actions.js:12-22 |
| 227-233 | downloadActive() { | 状态层 | features/phone-access/state.js:142-148 |
| 235-237 | needsPolling() { | 状态层 | features/phone-access/state.js:152-154 |
| 239-253 | /* 五秒一次只问本机内存里的状态。抽屉开着时每次都问：下载进度、配对码和「手机 | 编排层 | features/phone-access/actions.js:31-45 |
| 255-260 | stopPolling() { | 编排层 | features/phone-access/actions.js:49-54 |
| 262-270 | startTick() { | 编排层 | features/phone-access/actions.js:58-66 |
| 272-277 | stopTick() { | 编排层 | features/phone-access/actions.js:70-75 |
| 279-282 | feature(key) { | 状态层 | features/phone-access/state.js:158-161 |
| 284-296 | /* 正在跑的那条通道以快照的 active_channel 为准（服务端说了算 | 状态层 | features/phone-access/state.js:165-177 |
| 298-314 | paint() { | 视图层 | features/phone-access/view.js:31-47 |
| 316-408 | /* 登录恢复一组（settings-gap 三、CR01–CR22，原型 cr | 视图层 | features/login/view-recovery.js:13-105 |
| 410-433 | /* CR12 / CR14：保存按钮随勾选项改名，账号或密码为空时禁用。 | 视图层 | features/login/view-recovery.js:109-132 |
| 435-698 | /* 手机访问一组（settings-gap 一、PH01–PH32），按 ph | 视图层 | features/phone-access/view.js:51-314 |
| 700-707 | /* PH25：倒计时每秒走一格，两次刷新之间不必等后端 */ | 视图层 | features/phone-access/view.js:318-325 |
| 709-726 | /* 导入已下载的组件包（原型 impView，IM01）：一次只导入一个组件， | 编排层 | features/components/actions.js:26-43 |
| 728-741 | paintComponents() { | 视图层 | features/components/view.js:40-53 |
| 743-754 | async pickComponent(key) { | 编排层 | features/components/actions.js:47-58 |
| 756-774 | /* 选完文件立刻自检（IM01 没有单独的「自检」按钮）。.exe 不进后端： | 编排层 | features/components/actions.js:62-80 |
| 776-782 | showComponentNote(prefix, text, ok) { | 视图层 | features/components/view.js:57-63 |
| 784-826 | /* 装好后关掉弹窗，结论就地说在抽屉里对应的那一节（原型 impInstall | 编排层 | features/components/actions.js:84-126 |
| 828-833 | closeComponents() { | 编排层 | features/components/actions.js:130-135 |
| 835-843 | /* 标题行右侧那颗「原型没画」的按钮：启用位没开就走 B2 启用，其余（加载失 | 编排层 | features/phone-access/actions.js:79-87 |
| 845-861 | async enableFeature() { | 编排层 | features/phone-access/actions.js:91-107 |
| 863-886 | async toggleStart() { | 编排层 | features/phone-access/actions.js:111-134 |
| 888-909 | async toggleStop() { | 编排层 | features/phone-access/actions.js:138-159 |
| 911-915 | /* 关闭是破坏性的（手机立刻失去权限、要重新扫码），所以先问一句再动手（PH2 | 编排层 | features/phone-access/actions.js:163-167 |
| 917-920 | cancelStop() { | 编排层 | features/phone-access/actions.js:171-174 |
| 922-926 | async confirmStop() { | 编排层 | features/phone-access/actions.js:178-182 |
| 928-934 | /* PH29：已连接后再配一台，重新显示配对区；新手机配上（paired_co | 编排层 | features/phone-access/actions.js:186-192 |
| 936-950 | /* PH24「去保存」（CR22）：打开设置的登录组、展开账号密码表单并聚焦账 | 编排层 | features/login/actions-recovery.js:11-25 |
| 952-967 | async openComponentDir() { | 编排层 | features/components/actions.js:139-154 |
| 969-982 | /* 复制地址：优先 Clipboard API，被禁用时退回 textarea | 编排层 | features/phone-access/actions.js:196-209 |
| 984-1006 | /* PH26：复制后按钮 1.6 秒内显示「已复制」，失败才在本块红字说明 * | 编排层 | features/phone-access/actions.js:213-235 |
| 1008-1036 | /* 组件下载：一次点击就走完「取地址 → 下载 → 校验 → 安装」，用户不用 | 编排层 | features/components/actions.js:158-186 |
| 1038-1059 | async cancelComponent(key) { | 编排层 | features/components/actions.js:190-211 |
| 1061-1075 | /* 换通道只记偏好：不重启当前监听，也不偷偷帮用户把隧道切过去 */ | 编排层 | features/phone-access/actions.js:239-253 |
| 1077-1085 | /* PH30：重新检测的结论就地说；仍没连上时通道卡和提示行已经说清差哪一步  | 编排层 | features/phone-access/actions.js:257-265 |
| 1087-1122 | /* CR11 / CR12 / CR19：勾了「只在这次运行中用」或本机加密存 | 编排层 | features/login/actions-recovery.js:29-64 |
| 1124-1136 | /* CR05：标题行按钮展开表单——清掉旧反馈和上次的输入，勾选项回到默认（保 | 编排层 | features/login/actions-recovery.js:68-80 |
| 1138-1146 | /* CR15：取消——清空输入并收起表单 */ | 编排层 | features/login/actions-recovery.js:84-92 |
| 1148-1153 | /* 清除账号先展开确认行：这是不可撤销的动作，不能一点就删 */ | 编排层 | features/login/actions-recovery.js:96-101 |
| 1155-1158 | cancelClearCredentials() { | 编排层 | features/login/actions-recovery.js:105-108 |
| 1160-1164 | async confirmClearCredentials() { | 编排层 | features/login/actions-recovery.js:112-116 |
| 1166-1176 | async clearCredentials() { | 编排层 | features/login/actions-recovery.js:120-130 |
| 1178-1242 | wire() { | 编排层（装配） | features/phone-access/actions-panel.js:18-82 |
| 1245-1248 | if (typeof document !== "undefined") { | 编排层（装配） | features/phone-access/actions-panel.js:96-99 |
| 1250-1252 | /* app.js 的 check 事件要顺手刷新这张卡片（重新登录成功会走 c | 过渡名单（bridge） | legacy-globals.js:13-15 |

## 按归层规则改了归属的名字（逐个写理由）

- **importCheckText → features/components/view.js（视图层）**：归属清单里把这个名字列在 components/state.js，但它读 `$("#help-version")` 的版本文字来拼「不配套」那句话——碰了 DOM，按归层规则不进状态层，落到同一功能目录的视图层文件里。
- **「多久以前」的注释（原文 123 行）与 agoText 本体分开**：原文里这条注释紧跟 maskAccount的注释（agoText 的函数被 maskAccount 隔开），逐字核对把它们连成一段照搬进features/login/state-recovery.js；agoText 本体按归属清单留在 features/phone-access/state.js。
- **IM03 注释（原文 62–67 行）与 IMPORT_TITLE 整段进 features/components/state.js**：原文里注释紧跟 IMPORT_TITLE，机械切段把它们连成一段；importCheckText 本体在视图层。

## 归属清单里没点到名的成员，按归层规则落的位置

- PhonePanel 的方法全部按归属清单归位；方法包包装与装配语句在features/phone-access/actions-panel.js（编排层）：七个方法包（手机访问的绘制与动作、组件的绘制与动作、登录恢复的绘制与动作、wire）用一句 Object.assign 一次装回 PhonePanel。
- 文件尾两段：判断 readyState 后调用 wire 的那段（原文 1245–1248）包进actions-panel.js 导出的启动函数 startPhonePanel，由 main.js 在放出排队的后端事件之后调用；挂回 window 的那段（原文 1250–1252，两行注释加一行挂载）搬进 legacy-globals.js，另挂回 maskAccount 与 downloadFailText（它们被计划面板与设置页这两个普通脚本用到）。
- 手机访问的四个只读推导方法（feature、selectedChannel、downloadActive、needsPolling）留在 PhonePanel 本体里，与全部字段一起在 features/phone-access/state.js。
