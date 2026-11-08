# L3 对抗审阅合并：phone-page-gap.md（2026-11-08）

被审对象：`design/evidence/2026-11-08/phone-page-gap.md`（对账表 52 行）。本文件合并两名反证方的结论，作为该报告修订的依据；修订内容记录在报告尾部「修订记录（对抗审阅 2026-11-08）」。合并人未读报告作者的推理过程，未动 `<过程留证>/` 与任何代码；全部争议点按素材所引 file:line 复核后定档。

## 1. 方法与输入

- **对抗 A（机械核验，后端架构师）**：`<过程留证>/adv-L3-a.md`。输入为被审报告＋工作区 Phone.dc.html（950 行）＋Main.dc.html（2498 行）＋Phone 名薄壳＋local/ui/m/{index.html,app.js,styles.css}＋local/infrastructure/phone_http.py。覆盖口径：
  - **217 处引用（192 个不同）全量提取、逐条对照磁盘行核验语义**：0 越界、全部成立；六个文件行数声明全部属实（Phone 950／Main 2498／index.html 156／app.js 1309／styles.css 199／phone_http.py 389，合并人 wc -l 复测同值）；
  - **280 条 CJK 反引号串逐字脚本比对**：207 逐字命中、2 条为报告第 14 行已声明的 U+2060 按可见字转录、63 未逐字分诊后 **55 条属记法类**（{占位}模板、示意合成值、斜杠枚举、省略号缩写）、**8 条真错**（全角弯引号错抄直引号，见 §4）；
  - 差异统计 52 行/77 计次脚本重算全等；28 板分母复算成立；外围事实核验（git status 43 项、PhoneConflict untracked、a85209e 的 Main=2283/Phone=842、index.html 与 phone_http.py 干净）全部吻合；工具 `<过程留证>/l3-audit.py`、`l3-audit2.py`（明细 out.txt 556 行）。
- **对抗 B（实质反证，测试自动化工程师）**：`<过程留证>/adv-L3-b.md`。输入为被审报告＋Phone.dc.html 950 行全读＋Main.dc.html 抽读＋m/index.html、app.js 1309 行、styles.css 199 行、phone_http.py 389 行全读＋phone_service.py、phone_rules.py、app.py、grab.py、business_clock.py、login_relay_service.py 定位复核。覆盖口径：
  - **28/28 画板逐板核验，每板 ≥3 行 文件:行 证据**（含 PhoneApp 无 frozen＝可交互、Main 4 板 tier="wide"）；
  - **已一致 3 行 100% 重验**（PA05、SH02 按钮切换、G06），G06 有两处偏差（见 §3）；
  - **12 个缺实现逐项反证**：「无对应实现」主张均有 m/ 全文与 grep 支撑，未发现报告漏提的近似实现；唯 PhAddPair 板未入册（记法类，见 §6）；
  - **后端信号列 grep 反证**：RL04 的 `relogin_setup` 四字段已在、EX06 的 `unavailable` 档已在、EX03 的 /pair 锁定回包结构已核、EX05 的 `pc_list_error` 全仓无；
  - 元信息（报告第 7-14 行）逐项复核；建议列自洽复核（RL04/EX06 两条「需后端先补」与后端现状矛盾）。
- 双方**互不知晓对方结论**（各自声明审阅范围互不重叠于对方产物）。合并规则：以报告 52 行对账为基准；同一行判定不一致取更严格档；行号/归属/记法类修正不计三档，单列 §6；「无法验证可关闭」记 §5。合并人对全部争议行、红牌 10 张的处置证据与 §5/§6 的 file:line 逐一 `sed -n`/`grep -n` 实测（Phone.dc.html、Main.dc.html、local/ui/m/**、local/app.py、local/business_clock.py、local/application/phone_service.py、local/application/login_relay_service.py、local/ui/views/relogin.js、`git diff --numstat`、薄壳 scene 机器比对）；站得住行的证据标注转自素材，以 A 的 217 处全量核验背书。

## 2. 三档汇总（52 行对账表）

| 口径 | 站得住 | 部分站不住 | 推翻 | 红牌 |
|---|---|---|---|---|
| A（机械核验，217 引用＋280 span 全口径） | 52 行行级全部成立（例外均为行号/记法级，移 §6） | 0 行级 | 0 | 10（红牌① 2＋红牌② 8） |
| B（实质反证，28 板×≥3 行） | 47 | 5（G06、LD01、SH01、RL04、EX06） | 0 | 0（1 处轻微②＋3 处引用不精确，记附注） |
| **合并（同行取更严格）** | **47** | **5（G06、LD01、SH01、RL04、EX06）** | **0** | **10＝2 轻微无行号（PA05、MN04 现状格）＋8 条弯引号错抄直引号（G10/G11/PA03/RW03/RL06/SH02/RS02/MN02，源行 Phone:276/343/910/879/889/913/564、Main:1385）** |

- 分歧行裁定（均经合并人按素材复核）：
  - **G06**：A 记「aria 同文不成立」为轻微语义瑕疵（不计失败），B 升为部分站不住并另证代码侧稀疏化——**取 B**；行判定档依 B。
  - **scene 枚举 relbad**：A §5 报「实列 22 个、漏 relbad」，B §二报「与报告逐一相同」——机器比对**取 B**：报告第 8 行枚举 23 项与磁盘 23 壳 scene 逐一相同、relbad 在列（diff 为空）；A 记报告 143 行、B 记 142 行（wc -l 142），A 所阅疑为提交前草稿，该项对当前文本不成立，详见 §6。
  - **红牌数**：A 10 对 B 0——**取 A**：B 未做全语料引号比对（其②为 G06 aria，归行内修正），0 张不构成对 8 张引号错的反证。
  - **RL05**：A 判「无法验证合格」、B 复核后亦判保留——一致。
  - **MN04 paired_count**：B 记待核——合并人实测 phone_service.py:118 确有 `paired_count` 属性，服务层「已需补」不成立；是否进电脑端 UI 状态归 settings-gap B1 口径，本审不改该格（§5 附注）。
- 「推翻 0」双向确认：A 全量核验无推翻、B 无推翻项；A 的负向主张（「无锁定 UI」「无对应实现」「无确认步骤」「无自定义 sheet」）经 A§4 与 B 板核双向 grep 复现为真。

## 3. 逐条判定表

证据缩写：**A§1/§2/§4**＝A 引用核验／逐字比对／红牌扫描；**B 板 X**＝B 逐画板核验（X 为画板名）；判定档非「站得住」与红牌处置的行号均经合并人实测。

| 编号（报告行号） | 原结论（摘） | 反证证据 | 判定档 | 报告已改 |
|---|---|---|---|---|
| G01（21） | 顶栏与品牌差 | A§1（Phone:236/239-240/923、index.html:33-39）；B 板 Phone 本体【站】 | 站得住 | 否 |
| G02（22） | 底部按钮条结构差 | A§1（Phone:155-158/294、index.html:49-56）；B 板 Phone 本体【站】 | 站得住 | 否 |
| G03（23） | 无自定义 sheet/modal | A§4 grep 复现（确认路径仅 window.confirm，app.js:948/967/987）；B 板 Phone 本体【站】 | 站得住 | 否 |
| G04（24） | 无 LED 计划板 | A§1（Phone:788、app.js:681-692）；B 板 Phone 本体【站】 | 站得住 | 否 |
| G05（25） | 列表行要素差 | A§1（Phone:744-747/752-753、app.js:170-176/482-561）；B 板 Phone 本体【站】 | 站得住 | 否 |
| G06（26） | 冲突 why「已一致（在途）」 | B 板 Phone 本体：Phone:288 的 aria-label 实为 `和已报名的活动时间重叠的原因`（多『的原因』尾缀，A§1 同证），并非同文；代码侧 aria=标题逐字（app.js:569），两端并不一致；代码 whyView 比原型多 `days.length > 7` 稀疏化（app.js:326/332，只留首末日），原型 whyOf（Phone:470）全量渲染日标签——「已一致」两处偏差。其余断言（dt 两行、图例、四态解除路径、goSigned 643-659）双方实测成立 | 部分站不住 | 是（aria 改述＋稀疏化差异） |
| G07（27） | 分组三区对七组 | A§1（Phone:413-423/728、app.js:57-66）；B 板 Phone 本体【站】 | 站得住 | 否 |
| G08（28） | 筛选条结构差 | A§1（Phone:931/282-283、index.html:77-88）；B 板 Phone 本体【站】 | 站得住 | 否 |
| G09（29） | 空态文案差 | A§1（Phone:290、index.html:48/62）；B 板 Phone 本体【站】 | 站得住 | 否 |
| G10（30） | 运行提示无任务卡 | A§2 红牌②：`点"修改计划"` 应作 点“修改计划”（Phone:276）；卡状态/明细/卡钮断言 A§1＋B 板 PhoneRun【站】 | 站得住（红牌②改正文） | 是（引号） |
| G11（31） | 重登表单文案差 | A§2 红牌②：`"我已阅读并同意《隐私协议》"` 应作弯引号（Phone:343）；其余 A§1＋B 板 PhoneCaptcha【站】 | 站得住（红牌②改正文） | 是（引号） |
| G12（32） | 无点阵/琥珀体系 | A§1（Phone:155-158/246-253、styles.css:85-87/153）；B 板 Phone 本体【站】 | 站得住 | 否 |
| G13（33） | stale 样式不可达 | A§1（styles.css:120、app.js:460）；B 板 Phone 本体【站】（静态推断已在无法验证清单声明） | 站得住 | 否 |
| PA01（39） | pair 外框结构差 | A§1（Phone:244-255/921、index.html:15-29、app.js:771-772）；B 板 Phone 本体【站】 | 站得住 | 否 |
| PA02（40） | 配对说明文案差 | A§1（Phone:253、index.html:17-22）；B 板 Phone 本体【站】 | 站得住 | 否 |
| PA03（41） | 点阵屏输入缺失 | A§2 红牌②：`点"配对"` 应作 点“配对”（Phone:910）；其余 A§1＋B 板 Phone 本体【站】 | 站得住（红牌②改正文） | 是（引号） |
| PA04（42） | 配对错误文案＋缺结构化字段 | B §五：服务端 /pair 锁定回包实为 `{ok:false,error:"locked",text:"尝试次数过多，请稍后再试"}`（phone_service.py:241-242）、错码 `error:"bad_code"`（:252-253）——服务端实际句与原型（Phone:632/633）各少一句，报告漏列此文案差；「需补 `{remaining_attempts, lock_seconds}`」成立（A§4 同：回包无结构化字段） | 站得住（现状补服务端实际句） | 是（补实际句） |
| PA05（43） | PhoneApp 已一致 | B 板 PhoneApp【站】（name="Phone" scene="pair" 无 frozen、renderVals yes:true、canvas.json is_interactive:true）；A 红牌①：现状格无 file:line | 站得住（红牌①补行号） | 是（补行号） |
| LD01（49） | 无独立详情确认页 | B 板 PhonePick：现状/缺失成立（无 `已选 N 场` 计数 grep 证实）；但「`立即/预报名` 区分需 retry_policy」不成立——原型 Phone:778 即按 stOf（开放状态）区分（`stOf(i,s)==='open'` 计 nInstant），m/ 用 open_ts/sign_start＋businessNowS 即可算 | 部分站不住 | 是（后端信号改述） |
| LD02（50） | 无活动详情卡 | A§1（Phone:789-793/268）；B 板 PhonePick【站】（字段核实保留） | 站得住 | 否 |
| LD03（51） | 无整页搜索视图 | A§1（Phone:521/737、app.js:1257/18-39）；B 板 PhoneSearch【站】 | 站得住 | 否 |
| LD04（52） | 勾选冲突静默禁用 | A§1（app.js:178-184）；B 板 PhonePick【站】 | 站得住 | 否 |
| RW01（58） | running 无 LED/四站/任务卡 | A§1（Phone:815-817/820-825/868/930）；B 板 PhoneRun【站】 | 站得住 | 否 |
| RW02（59） | pending 文案差＋缺板卡 | A§1（Phone:800-802/867、app.js:914-918/931-932/939）；B 板 PhoneCheck【站】 | 站得住 | 否 |
| RW03（60） | 取消等待确认文案差 | A§2 红牌②：`还要再点"停止计划"` 应作弯引号（Phone:879）；B 板 PhoneCheck【站】 | 站得住（红牌②改正文） | 是（引号） |
| RL01（66） | captcha 外框差 | A§1（Phone:884/898/900/347、index.html:116-126）；B 板 PhoneCaptcha【站】 | 站得住 | 否 |
| RL02（67） | 提交过程文案差 | A§1；B 板 PhoneCaptcha【站】 | 站得住 | 否 |
| RL03（68） | auto 无独立画面 | A§1（Phone:888、app.js:1046-1050/1052/1166）；B 板 PhoneAuto【站】 | 站得住 | 否 |
| RL04（69） | relall/relacct 两态不区分；「需后端先补」 | B §五：现状成立（app.js:475 显隐式对上，B 板 PhoneRelAcct/RelAll）；「需补 needAcct/needCap/ocrOn 结构化」不成立——`relogin_setup` 已含 `{saved, account_hint, ocr_ready, paused}`（app.py:3042-3055，docstring 明写手机重新登录用途），m 侧 app.js:863 已接收、:370 已消费 ocr_ready；lead 四态是纯前端缺口 | 部分站不住 | 是（降档「纯前端可做」） |
| RL05（70） | 无 lead；safe_error 取值无法验证 | B §五：保留——桌面端有同源文案（views/relogin.js:148 bad_password、login_relay_service.py:43 注释），但手机侧 safe_error 取 worker reason/error（login_relay_service.py:432/447/503），静态断不了取值；其余 A§1＋B 板 PhoneRelConfirm【站】 | 站得住 | 否 |
| RL06（71） | 无确认步骤 | A§2 红牌②：`"我已阅读并同意…"` 应作弯引号（Phone:889）；缺实现 grep 复现（beginRelogin 直发 POST，app.js:1132-1174）；B 板 PhoneRelConfirm【站】 | 站得住（红牌②改正文） | 是（引号） |
| RL07（72） | relbad 无专门分支 | A§1 轻微＋B 板 PhoneRelBad：引 Phone:885 是赋值/渲染行（`sh.err = s.capErr`），字面串在 Phone:519/666/690（实测三行逐字在）；缺实现成立（仅经 setup.paused 显隐，app.js:475）；引用组修正记 §6，报告不改 | 站得住（§6 记法） | 否 |
| RL08（73） | 完成态文案差 | A§1（Phone:892-894/882、app.js:1108/1113）；B 板 PhoneRelConfirm【站】 | 站得住 | 否 |
| SH01（79） | review 面板结构差；「label 无法验证」 | B §五：现状成立；「选项 label 值后端下发，无法验证」错——label 在 app.py:249-264 可验证（`2 分钟/10 分钟/30 分钟/1 小时/自动延长（最多25分钟）/直到报名截止`），且 `自动延长（最多25分钟）` 与原型 `自动延长`（Phone:306）有差，报告漏列此文案差；B 板 PhoneReview 其余断言【站】 | 部分站不住 | 是（后端信号＋现状＋差距类型） |
| SH02（80） | reviewwarn 提醒句式差 | A§2 红牌②：`"直到报名截止"` 应作弯引号（Phone:913）；按钮切换已一致经 B 100% 重验通过（Phone:941 对 app.js:1027 同构）；其余提醒句 A§1＋B 板 PhoneReviewWarn【站】 | 站得住（红牌②改正文） | 是（引号） |
| SH03（81） | stopsheet 缺 sheet 确认 | A§1（Phone:874/313、app.js:967-970）；B 板 PhoneStop【站】 | 站得住 | 否 |
| SH04（82） | cancelsheet 同上 | A§1（Phone:877、app.js:987-992）；B 板 PhoneCancel【站】 | 站得住 | 否 |
| SH05（83） | 更多 sheet 节序差 | A§1（Phone:873/936-937/320、index.html:72-151）；B 板 Phone 本体【站】 | 站得住 | 否 |
| SH06（84） | 操作失败红条缺失 | A§1（Phone:870、app.js:972/994）；B 板 PhoneStop【站】 | 站得住 | 否 |
| RS01（90） | 无独立结果页 | A§1；B 板 PhoneResult【站】（三处替代与 NEEDS-HUMAN 2 支撑成立） | 站得住 | 否 |
| RS02（91） | 任务卡原因文案差 | A§2 红牌②：`学校回"操作成功"` 应作 学校回“操作成功”（Phone:564）；taskText 对上（app.js:344-358）；B 板 PhoneResult【站】 | 站得住（红牌②改正文） | 是（引号） |
| TM01（97） | terms 无整页态 | A§1（Phone:853/798/742/863、app.js:880/467/471 行不禁用属实）；B 板 PhoneTerms【站】 | 站得住 | 否 |
| EX01（103） | offline 文案差＋缺重试钮 | A§1（Phone:852/826、app.js:452-453/444-447）；B 板 PhoneOffline【站】 | 站得住 | 否 |
| EX02（104） | expired 横幅静态 | A§1（index.html:43、app.js:886-890）；B 板 PhoneExpired【站】 | 站得住 | 否 |
| EX03（105） | 无锁定 UI；「锁定文案无法验证」 | B §五：无锁定 UI 成立（A§4 同）；「锁定文案无法验证」销案——服务端实际句已核（phone_service.py:241-242），与原型（Phone:501）有差，漏列文案差补进现状格；B 板 PhoneLock【站】 | 站得住（销案＋现状补句） | 是（改可验证） |
| EX04（106） | pairfail 剩余次数缺 | A§1（Phone:525/909、app.js:766）；B 板 PhonePairFail【站】 | 站得住 | 否 |
| EX05（107） | pclisterr 无对应实现 | B §五 grep：`pc_list_error`/`activities_stale` 全 local/（排 tests）无，缺失成立；A§4 同；B 板 PhonePcList【站】（Phone:855/860 对上） | 站得住 | 否 |
| EX06（108） | pcclock 无横幅；「需补 down 档」 | B §五：现状成立（canStart 不看时钟，app.js:112-116；holdover 提醒在 366）；「需补 `down`（完全不可用）档」不成立——后端词汇即 `syncing/ready/holdover/unavailable`（business_clock.py:254），clock_snapshot 异常兜底亦回 `state:"unavailable"`（app.py:816）；缺的是前端消费（app.js:248-249 只认 ready\|holdover 进 model.clock）→ 纯前端可做；B 板 PhonePcClock 其余【站】 | 部分站不住 | 是（降档「纯前端可做」） |
| MN01（114） | phonesetup 对 m/ 合理缺失 | B 板 PhoneSetup【站】（name="Main" scene="phonesetup" 无 frozen、canvas.json is_interactive:true、Main:1362-1372/701-708 对上） | 站得住 | 否 |
| MN02（115） | phonets 同上 | A§2 红牌②：`点"重新检测"` 应作 点“重新检测”（Main:1385）；其余 A§1（phone_http.py:45-59/223-233）＋B 板 PhoneTs【站】 | 站得住（红牌②改正文） | 是（引号） |
| MN03（116） | phonewait 同上 | A§1（Main:2453/1391-1411）；B 板 PhoneWait【站】（phCodes()[0]='482 913' 实测） | 站得住 | 否 |
| MN04（117） | phonelinked 同上 | B 板 PhoneLinked【站】；A 红牌①：现状格无 file:line（补 index.html:33-39＋app.js:380-383）；paired_count 待核见 §5 | 站得住（红牌①补行号） | 是（补行号） |

## 4. 红牌节（10 张，处置全落报告）

- **①结论无 文件:行（2 张，轻微）**：PA05（现状「m/ 的 #pair 即可交互实现」无引用）、MN04（现状「无『手机已连接』专门态」无 m/ 侧引用）——A 逐行扫描（其余 50 行现状格均有引用）；B 独立扫描记 0 张（其口径以双端有行号为准）。**处置**：PA05 补 `index.html:15-29`＋`app.js:771-772`、MN04 补 `index.html:33-39`＋`app.js:380-383`（合并人实测四处内容在位）。
- **②原型原文非逐字（8 张）**：全为把原文全角弯引号 “ ” 错抄成直引号，违反报告自称「字符串一律反引号逐字抄录」——G10 Phone:276 点“修改计划”、G11 Phone:343 “我已阅读并同意《隐私协议》”、PA03 Phone:910 点“配对”、RW03 Phone:879 “停止计划”、RL06 Phone:889 “我已阅读并同意《隐私协议》”、SH02 Phone:913 “直到报名截止”、RS02 Phone:564 学校回“操作成功”、MN02 Main:1385 点“重新检测”。A 以 280 条全语料脚本比对唯一系统性错类；B 未做该比对。**处置**：8 条全部改正文（逐字改回弯引号，合并人对八处源行逐一实测弯引号在位）。
- **③「无法验证」写成「未实现」（0 张，双方一致）**：7 条无法验证全部写明所缺；「无锁定 UI／无对应实现／无确认步骤／无自定义 sheet」均有 grep 证据为真（A§4、B §四）。
- G06「aria 同文」作为非逐字主张由 B 记轻微②，因属行内断言（不是引文抄录），归 G06 行修正，不计入红牌计数。

## 5. 销案/降档节

| 项 | 原判定 | 销案/降档结论 | 证据（合并人实测） |
|---|---|---|---|
| RL04 | 「需后端先补（lead 四态的字段依据）」 | **降为「纯前端可做」**：四字段已下发且已被 m/ 消费，lead 四态只剩前端分支 | `relogin_setup` 返回 `{saved, account_hint, ocr_ready, paused}`（app.py:3042-3055，docstring 明写手机用途）；app.js:863 ingest、app.js:370 读 `setup.ocr_ready` |
| EX06 | 「需后端先补（down 档＋前端横幅）」 | **降为「纯前端可做」**：`unavailable` 档即「完全不可用」档，后端已下发，缺前端识别与横幅 | 时钟词汇注释 `# syncing/ready/holdover/unavailable`（business_clock.py:254）；clock_snapshot 异常兜底 `state:"unavailable"`（app.py:816）；前端只认 `ready\|holdover`（app.js:248-249）。NEEDS-HUMAN 6 的提问保留 |
| 无法验证 #3 前半：pair 锁定 text | 无法验证 | **销案（可验证且有差）**：服务端实际句 `尝试次数过多，请稍后再试`（locked）／`配对码不对，请核对后重试`（bad_code），均较原型少次句（`换一台设备也一样要等`／`再错 N 次要等 60 秒`）——报告漏列的文案差，补进 PA04/EX03 现状格 | phone_service.py:241-242（locked）、:252-253（bad_code）；原型 Phone:632/633/501 |
| 无法验证 #3 后半：retry_options label | 无法验证 | **销案（可验证且有差）**：label 取值 `2 分钟/10 分钟/30 分钟/1 小时/自动延长（最多25分钟）/直到报名截止`；`自动延长（最多25分钟）` 对原型 `自动延长`（Phone:306）有差——补进 SH01 | app.py:249-265；Phone:306 |
| RL05：safe_error 取值 | 无法验证 | **保留**：桌面端有同源文案，但手机侧取值经 worker reason/error 透传，静态不可断 | views/relogin.js:148、login_relay_service.py:43（同源）；:432/447/503（safe_error ← reason/error） |

- 随降档联动：RL04/EX06 建议列与 NEEDS-HUMAN 3 同步改「纯前端」；差异统计的「需后端先补」落点 4 行收敛为 2 行（EX03、EX05）。
- **附注（B 提出，不改报告）**：MN04 后端信号「电脑端已需补 paired_count（settings-gap B1）」——phone_service.py:118 已有 `paired_count` 属性，「需补」至少对服务层不成立；是否进电脑端 UI 状态归 settings-gap 口径，本审不动该格。

## 6. 行号与记法修正节（均不计三档）

1. **app.js 在途增量**：报告写 `+322/−4`，`git diff --numstat` 实测 **+318/−4**（A 判读：322 是 `--stat` 柱数总和 318+4，把柱数当成插入数）；styles.css +34 属实。已改。
2. **RL07 引 Phone:885**：该行是赋值/渲染处（`sh.hasErr = !!s.capErr; sh.err = s.capErr;`），字面串在 Phone:519/666/690（三行实测逐字在）。引渲染行不算错，报告不改。
3. **G06 引 Phone:142**：该行是图例色点 CSS（`.tl-k .k-a::before{…}`），图例文本 `已报名/这一场/重叠` 实在 Phone:288 同行（B 判定，合并人实测）。引用不精确但图例实存，报告本次不改（后续修订可改引 288）。任务书转写作「Main:142」系笔误，Main:142 为无关 CSS（`.tipb-r`）。
4. **「23 薄壳 scene 枚举漏 relbad」（A §5）——对当前文本不成立**：机器比对报告第 8 行枚举与磁盘 23 壳 scene（Phone 名、扣 untracked 的 PhoneConflict）**逐一相同（diff 为空），relbad 在列**；计数 23 与文件数一致。B「逐一相同」正确。A 记报告 143 行、B 记 142 行（wc -l 142），A 所阅疑为提交前草稿（报告由 c72ee93 提交后未再改）。报告不改。
5. **示意合成值约 15 处**（`已选 3 场`、`1 场立即报名，2 场预报名`、`这一批 2 场同时提交…`、`1 已报名｜1 名额已满｜1 待核对`、`4:32 后失效…` 等）：属报告第 14 行已声明的推算类记法，成分字面全部核实存在，B 复算两例成立（PhoneRun gap=593→`00:09:53`；PhoneWait phLeft=272→`4:32`，Main:1314/1113 实测）。A 建议把无法验证清单的例举扩为类级说明，留待后续修订，本次不改。
6. **PhAddPair.dc.html**（name="Main" scene="phaddpair"、tier="wide"、frozen——合并人实测）：同为手机相关画板，不在 28 板分母亦未在排除清单点名（B 记轻微覆盖缺口）；属任务书口径（只对账 Phone 侧 24 板＋Main 手机侧 4 板），报告已在排除条补一句点名。
7. **记法说明（不改文）**：PA04 现状格内 `||` 曾干扰 A 初版统计解析器，改反引号感知切分后 52 行/77 计次全等——统计可信度的过程记录。

## 7. 修改清单（报告原句→改后句，详见报告尾部修订记录）

1. 第 9 行 排除条尾补：`另 PhAddPair.dc.html（name="Main" scene="phaddpair"，frozen）同为手机相关画板，不在本表分母（任务书口径只对账 Phone 侧 24 板＋Main 手机侧 4 板），点名备查。`
2. 第 11 行：`` `app.js` +322/−4 `` → `` `app.js` +318/−4 ``。
3. G06 原型列：`（aria 同文，Phone:288）` → `（原型 aria 带『的原因』尾缀：` `和已报名的活动时间重叠的原因` `，Phone:288；代码侧 aria=标题逐字，app.js:569）`。
4. G06 现状列尾补：`；较原型多 days.length > 7 稀疏化（app.js:326-332，只留首末日），原型 whyOf（Phone:470）全量渲染日标签`。
5. G10 原型列：`回电脑点"修改计划"` → `回电脑点“修改计划”`。
6. G11 原型列：`勾选学校登录页上的"我已阅读并同意《隐私协议》"。` → 弯引号。
7. PA03 原型列：`输完了，点"配对"` → `输完了，点“配对”`。
8. PA04 现状列尾补：`；服务端实际句：bad_code 配对码不对，请核对后重试（phone_service.py:252-253）、锁定 尝试次数过多，请稍后再试（:241-242），均较原型（Phone:633/632）少次句（再错 N 次要等 60 秒／换一台设备也一样要等）`。
9. PA05 现状列：`m/ 的 #pair 即可交互实现，无冻结概念` → `m/ 的 #pair 即可交互实现（index.html:15-29、app.js:771-772），无冻结概念`。
10. LD01 后端信号列：`` `立即/预报名` 区分需 retry_policy `` → `` `立即/预报名` 区分按开放时刻即可算（原型 Phone:778 按 stOf 开放状态区分，无需 retry_policy） ``。
11. RW03 原型列：`还要再点"停止计划"。` → `还要再点“停止计划”。`。
12. RL04 后端信号列：`（saved/paused）；需补：needAcct/needCap/ocrOn 结构化（如 relogin_setup.ocr_ready 透传）` → `（saved/account_hint/ocr_ready/paused 四字段已在，app.py:3042-3056；m 侧 app.js:863 已接收、:370 已消费 ocr_ready）——字段已存在，纯前端可做`；建议列 `需后端先补（lead 四态的字段依据）；文案照原型` → `纯前端可做（lead 四态字段已就绪，原「需后端先补」撤销）；文案照原型`。
13. RL06 原型列：`勾选学校登录页上的"我已阅读并同意《隐私协议》"。` → 弯引号。
14. SH01 后端信号列：`（app.js:869-872；选项 label 值后端下发，无法验证）` → `（app.js:869-872；label 后端下发且可验证：app.py:249-264 取值 2 分钟/10 分钟/30 分钟/1 小时/自动延长（最多25分钟）/直到报名截止）`；现状列尾补 `；#retry-for 选项 label 由服务端下发（app.py:249-264），其中 自动延长（最多25分钟） 较原型 自动延长（Phone:306）多「（最多25分钟）」括注`；差距类型 `结构` → `结构＋文案`。
15. SH02 原型列：`"直到报名截止"对它只会尝试 2 分钟` → `“直到报名截止”对它只会尝试 2 分钟`。
16. RS02 原型列：`学校回"操作成功"` → `学校回“操作成功”`。
17. EX03 现状列：`；具体锁定文案无法验证` → `；服务端实际句 尝试次数过多，请稍后再试（phone_service.py:241-242），较原型（Phone:501）少 换一台设备也一样要等 尾句（文案差计在 PA04）`。
18. EX06 后端信号列：`（ready/holdover）；需补：down（完全不可用）档` → `（后端词汇 syncing/ready/holdover/unavailable，business_clock.py:254；快照异常兜底亦回 unavailable，app.py:816）——down 档已存在，缺前端消费（app.js:247-249 只认 ready/holdover），纯前端可做`；建议列 `需后端先补（down 档＋前端横幅）…` → `纯前端可做（unavailable 档后端已下发，前端补识别与横幅；原「需后端先补」撤销）…`。
19. MN02 原型列：`后点"重新检测"` → `后点“重新检测”`。
20. MN04 现状列：`m/ 对应物 #conn pill 已连接＋#last-sync；无「手机已连接」专门态` → `m/ 对应物 #conn pill 已连接＋#last-sync（index.html:33-39、app.js:380-383）；无「手机已连接」专门态`。
21. NEEDS-HUMAN 3：`（RL04-RL07，RL04 需后端）` → `（RL04-RL07，纯前端）`；`（EX05/EX06，需后端）` → `（EX05 需后端、EX06 纯前端）`。
22. 无法验证清单：`服务端下发文案的实际取值：pair 锁定 text、relogin safe_error、state.retry_options.choices 的 label（如 直到报名截止）。` → `服务端下发文案的实际取值：relogin safe_error（对抗审阅复核：手机侧取值经 worker reason，静态不可断，保留）。〔pair 锁定 text、retry_options label 已销案 2026-11-08：phone_service.py:241-242/252-253、app.py:249-264，见 PA04/EX03/SH01 行〕`。
23. 差异统计：`文案 27` → `文案 28`、`77 个类型计次` → `78 个类型计次`；已一致行补 G06 两处偏差注；「需后端先补」行改 `落在 2 行：EX03、EX05 …；RL04/EX06 已降为纯前端可做`。
24. 报告尾部新增「修订记录（对抗审阅 2026-11-08）」小节。
