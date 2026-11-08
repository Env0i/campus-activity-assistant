# 夜班八层台账（2026-11-08）

本文件汇总 2026-11-08 夜班产出的 8 份只读对账/盘点报告（含 PATCHES/README.md）。逐层给分母（复算结果）、产出文件、提交哈希、差异统计（照报告）、关键结论与未处理项。NEEDS-HUMAN 逐条搬运见 `DEFERRED.md`，交接与回传见 `HANDOFF.md`。

## 总表

| 层 | 名称 | 分母（复算） | 差异数（照报告） | NEEDS-HUMAN | 补丁数 | 提交 |
|---|---|---|---|---|---|---|
| L1 | C2 登录与详情卡对账 | 19 画板；86 行（79 行计入） | 109 项（缺失 28／文案 34／结构 7／状态 5／多出 5／样式 5／已一致 25） | 9 条 | 0 | ae981f6 |
| L2 | 对话框与横幅对账 | 23 画板；54 行 | 76 计次（文案 26／结构 13／缺失 8／多出 4／状态 10／样式 4／已一致 11） | 8 条 | 0 | 5959569 |
| L3 | 手机页对账 | 28 画板（Phone 24 板＋Main 4 板）；52 行 | 77 计次（缺失 23／文案 27／结构 14／状态 8／已一致 3／样式 1／多出 1） | 6 条 | 0 | c72ee93 |
| L4 | 主窗口对账 | 24 薄壳＋Main 本体；52 行（勘误附行 LS23/PB17 不计） | 64 计次（已一致 34／文案 10／缺失 8／多出 8／状态 3／结构 1／样式 0） | 7 条 | 0 | 5a05f65 |
| L5 | 文案真源比对 | 462 条唯一用户可见字符串 | 不一致 22＋代码没有 4（其余：一致 402、禁止示例/已废止 28、元描述 5、分发词表 1） | 4 议题（9 条） | 0 | 41e86aa |
| L6 | 文档路径引用核验 | 40 篇文档；194 条唯一路径 | 死链 39（全部为迁移对照表旧路径列）＋有意 12＋存在 143 | 0 条 | 0 | 41e86aa |
| L7 | 测试卫生 | `<tmp>` 6 处（5 行）；tests 内时钟 94 处；非 tests 时钟 90 处；全量 1911 例 | 时钟风险 3（tests）＋生产侧可疑 Top 5；unittest 失败 1／skip 4 | 1 条（DEFERRED-L7-1） | 0 | 7e2f3c2 |
| L8 | 无障碍名称静态审计 | 129 button＋30 input/select＋11 对话框＝170 控件 | 无名称 button 0/129；缺名称输入 0/30；aria-labelledby 无效 1；缺 aria-modal 8/11 | 0 条（问题清单 10 条供排期） | 0 | 7e2f3c2 |

八层 NEEDS-HUMAN 合计：L1–L4 共 30 条＋L5 4 议题（9 条）＋L7 1 条＝35 个条目、41 条计数（L5 按议题归并，议题四含 6 条规格字符串）。逐条见 `DEFERRED.md`。八层补丁合计 0（见 `PATCHES/README.md`）。

---

## L1 C2 登录与详情卡：原型与现行代码对账表

- **产出**：`c2-login-gap.md`　**提交**：ae981f6（`docs(evidence): L1 登录与详情卡对账表`）
- **分母（复算）**：原型 19 画板（登录 family 1–7、重登 family 8–12、顶栏详情卡 family 13–17、时钟 family 18–19）；对账表 86 行，其中 79 行计入统计（「（同上，不计）」引用行与「—」演示行不计）。
- **差异统计（照报告）**：109 项——缺失 28、文案 34、结构 7、状态 5、多出 5、样式 5、已一致 25。
- **关键结论**：
  1. 缺失集中在登录弹窗 family：画板 1/2/3/6/7 的宿主容器与内件整体缺失（20 项），宿主取舍牵动 NEEDS-HUMAN 1。
  2. 文案差最多的是隐私句「我已阅读并同意」缺半句与按钮叫法（`重新校准`/`刷新`/`打开学校登录页`）。
  3. 已一致 25 行集中在计划栏提醒、blocker/why 行、顶栏状态词与弹窗开合（Esc/取消）。
  4. 原型行号基准更正：素材自注 a85209e，实测对应工作区版 Main.dc.html（2498 行，偏移 +32～+215）；本表保留工作区行号，a85209e 换算列入无法验证。
  5. 复核修正 2 处：行号基准；时钟 blocker 素材写 plan-panel.js:439，a85209e 实为 :437。
  6. 详情卡 family 主要是键值行缺失：`电脑时钟` 行、登录卡的 `有效多久/别处登录/失效以后/手机重新登录`、手机卡的 `手机最近访问`。
- **未处理项与理由**：无法验证清单 9 类（DC 画板连线、`.clock.cal.hold` 视觉、窄档弹窗实测像素、断行与字体渲染、后端回包/事件载荷真实结构与打码账号字段、面板与列表部分画板元素未逐字对照、a85209e 版原型行号换算、`手机最近访问` 后端字段是否存在、busy 态 Esc 门控）——本层为静态对账，未运行浏览器与后端；「原型演示：」控件不进产品，相关行差距类型写「—」；本层不出补丁，修单按表派工。

## L2 对话框与横幅：原型与现行代码的逐项差距

- **产出**：`c3-dialogs-gap.md`　**提交**：5959569（`docs(evidence): L2 对话框对账表`）
- **分母（复算）**：原型 23 画板（关窗 5、更新 5、引导 3、FirstUse 1、条款 6、HelpKeys 1、迁移 2；任务书「条款 7」为误，以素材 6 块、合计 23 为准）；对账表 54 行。
- **差异统计（照报告）**：76 计次（一行可含多型）——文案 26、结构 13、缺失 8、多出 4、状态 10、样式 4、已一致 11。
- **关键结论**：
  1. 关窗组文案整组与标题随计划状态切换需照原型改；三张选择卡顺序（原型：最小化→隐藏→退出）与代码相反。
  2. 整块缺失四类：CloseHidden 隐藏态 UI、更新进度条与新版本块、FirstUse 独立首启模态、Migrated/MigrateFail 迁移横幅——多数需后端先补信号（隐藏态事件、体积字段、迁移结果进运行记录）。
  3. 引导组主要是引号口径（`「」` vs `“”`）与 `第 1/6 步` 静态残留；引导行为链（暂停/恢复/Esc/落盘）只登记不判定。
  4. 条款组结构取舍（全屏＋章节导航 vs 现对话框内嵌；TermsUpdate 独立模态 vs 内嵌区块）需用户定。
  5. 抽查 36 处修正 1 处：迁移 stderr 实带 `[i] `/`[!] ` 前缀，MG01/MG02 已按实测抄录。
  6. `views/terms.js:349` 死引用（`#btn-help-terms-view` 已不存在）属功能搬移遗留，本表只记不改（NEEDS-HUMAN 7）。
- **未处理项与理由**：无法验证清单 8 项（引导第 3 步原型全文、TourPick 换卡态、更新 launching 兜底文案与 closeWhy、更新回包体积字段、条款未知态日志行、CloseLive 计划面板文案、样式细节未逐全 styles.css、行号随在途改动漂移）——素材未覆盖或未运行；CloseHidden 模拟桌面「是演示形态还是产品形态」随 NEEDS-HUMAN 5 留给用户。

## L3 手机页（local/ui/m/）：原型与现行代码的逐项差距

- **产出**：`phone-page-gap.md`　**提交**：c72ee93（`docs(evidence): L3 手机页对账表`）
- **分母（复算）**：28 画板＝Phone 侧 24 板（Phone.dc.html 本体＋23 个 `name="Phone"` 薄壳）＋Main 侧 4 板（phonesetup/phonets/phonewait/phonelinked）；`PhoneConflict.dc.html` 未入库在途新增，不在分母；对账表 52 行。
- **差异统计（照报告）**：77 个类型计次——缺失 23、文案 27、结构 14、状态 8、已一致 3、样式 1、多出 1。
- **关键结论**：
  1. 共用件缺口最大：sheet 外壳、LED 计划板、任务卡、独立结果页在 m/ 均无对应结构，缺失 23 计次居首。
  2. 「需后端先补」明确落 4 行：RL04（relogin lead 四态字段）、EX03（pair 锁定结构化回包）、EX05（`pc_list_error`）、EX06（business_clock `down` 档）；PA04/EX04/RL05/RL07 依赖同批字段，LD02 需字段核实。
  3. EX06 发现 canStart 只看 stale/busy（app.js:112-116），时钟完全不可用不拦开始，与决策 012 有缺口（NEEDS-HUMAN 6，可能超出 m/ UI 范围）。
  4. 在途 conflict-cancel 块（buildWhy、goSigned、styles 162-199）与原型 G06 已一致，随在途提交；冲突规则在 PhoneModel 内联复制、不 import 电脑端 conflict.js。
  5. 行号抽查 22 处修正 1 处（whyView 标题 app.js:330→329）；冲突相关行号属在途段，回退会失效。
  6. 三处原生 confirm 与 PhoneResult 形态需用户定；sheet 化是 m/ 纯前端工程量最大的一项。
- **未处理项与理由**：无法验证清单 7 项（像素级排版/断行/动画需 Edge/WebView2 实测、冻结薄壳动态过程、服务端下发文案实际取值、原型合成数值、Main 四板 phoneCard 可见性、`state.activities` 字段全集、stale 样式不可达为静态推断）——静态审计不运行浏览器；12 个缺实现的取舍顺序列 NEEDS-HUMAN 3，不擅自排序定案。

## L4 主窗口：原型 24 画板与现行代码对账表

- **产出**：`main-window-gap.md`　**提交**：5a05f65（`docs(evidence): L4 主窗口对账表`）
- **分母（复算）**：24 张 `dc-import name="Main"` 薄壳（清单已勘误：磁盘另有 Running/PreWarn 薄壳与画板 15/19 同 scene；素材乙把 Main 本体计为画板、漏 Attention）＋Main 本体（归第一组）；对账表 52 行（TF 7＋LS 22＋PB 16＋GL 7），勘误附行 LS23/PB17 不计。
- **差异统计（照报告）**：64 计次——已一致 34、文案 10、缺失 8、多出 8、状态 3、结构 1、样式 0。
- **关键结论**：
  1. 34 行已一致：三档宽度等价实现、计划栏运行态（Waiting/MediumRun/RunClick/RunAuto/RunPhone）、via 行、NarrowResult 副文等核心链路与原型逐字同。
  2. 整块缺失 4 处：SecondRun 单实例（需后端事件）、Slept 的 `错过了` 统计/结论/任务卡、dock 修改中与结果态（TF05/PB16 同一处补）、Filters 折叠抽屉；另有 RunPhone 开始日志句与窗口内 toast。
  3. 素材修正 4 处（dock 行号漂移 3 处就地标注「勘误」；secondrun grep 复核维持全无命中）。
  4. `ToastMin.dc.html:11` 缺 `frozen="{{yes}}"`（其余 23 张都有），原型内部问题，列 NEEDS-HUMAN 1。
  5. LS12 列表失败按钮照原型改 `刷新`、正文语序对齐——与 settings-gap.md「列表加载失败的按钮叫刷新」返修项同一条。
  6. Slept 横幅现状 `刚才有 N 界面没动静…` 系笔误级文案（原型写 `约 N 分钟` 并点名场次），sleepWindow 内场次前端可得名。
- **未处理项与理由**：无法验证清单 7 项（LED 渲染/桌面层叠/断行/动画、未运行 `--demo` 与 pywebview 桥、回包真实结构按消费侧记录、运行时行为、Running/PreWarn 两薄壳细节未逐行核对、在途 conflict 三件套归专项切片、素材甲【静态推断】进入路径沿用标注）——纯源码推演，未开浏览器未连后端。

## L5 文案真源比对：design/specs/copywriting.md ↔ local/ui/

- **产出**：`copy-audit.md`　**提交**：41e86aa（`docs(evidence): L5 L6 文案与死链盘点`）
- **分母（复算）**：规格全部带引号用户可见字符串去重 462 条，逐条 grep 四步匹配 `local/ui/**`（12,825 行）；462 条全量收录于报告表格，无增删。
- **差异统计（照报告）**：一致 402（含模板归一/拼接/两参渲染）、不一致 22、代码没有 4、规格禁止示例/已废止（代码未出现＝符合）28、规格元描述 5、分发词表 1。
- **关键结论**：
  1. 一致率 86%（402/462）；不一致 22 条集中在引导改版余波、按钮/动作名（`检查计划状态`→`重新确认`）、占位词与分隔符（`·`）、`已开放，准备提交` 变体等。
  2. NEEDS-HUMAN 9 条归并 4 议题：时间线占位词三方不一致（spec:195）、spec:262 与 b-amendment-007 冲突、spec:340 规格自相矛盾（§10 未同步 §3 红线）、§11 六步引导已被五步取代未回改（spec:370-375 六条）。
  3. 规格 28 条禁止示例/已废止句在代码零出现（红线全部守住）；分发词表 1 条不在 local/ui 范围。
  4. 行号三点观察：login.js 素材行号差 1、list.js/store.js 随在途改动漂移——一律保留素材原行号，复核以内容为准。
  5. 抽样复核 13 条（另含 L6 共 17 处），内容全部与素材一致，未改素材任何条目。
- **未处理项与理由**：4 议题的「改规格还是改代码」是规格归属裁决，不在盘点层处理；本层不出补丁；无独立无法验证节（漂移风险已在观察 4 声明）。

## L6 文档反引号路径引用核验

- **产出**：`doc-refs.md`　**提交**：41e86aa（`docs(evidence): L5 L6 文案与死链盘点`）
- **分母（复算）**：git ls-files 的 docs（不含 archive）、design/specs、design/decisions、README.md、AGENTS.md 共 40 篇（34 篇含引用），反引号内仓库路径唯一引用 194 条（39＋12＋143，搬运后抽样 8 处复核一致）。
- **差异统计（照报告）**：存在 143、死链 39、有意 12；改名建议 39、删除建议 0、NEEDS-HUMAN 0。
- **关键结论**：
  1. 39 条死链全部集中在 docs/README.md:58-96「旧路径 → 新路径」迁移对照表旧路径列；同表右列即改名目标，39 个目标逐一 test -e 为真。
  2. 补丁判定 0 条：删改旧路径列会破坏对照功能，该表属记录性质文档（「旧记录不追改」的精神延伸）。
  3. 若今后要消灭这批死链，正确做法是在对照表所在节补一句说明，而不是改路径。
  4. `server/config.json`、`local/data` 等 12 条判「有意」：gitignore 运行文件/占位符/glob 示意，文档口径引用，非死链。
  5. 存在 143 条中 6 条带行号且行号有效、2 条带命令参数；出处分布 docs=151／specs=18／decisions=44／README=11／AGENTS=29（一篇引用可计多组）。
- **未处理项与理由**：死链按上列理由有意保留，不建 PATCHES 文件；本层无无法验证事项（全量 test -e 覆盖，死链另做 git ls-files 同名复核）。

## L7 测试卫生正式报告

- **产出**：`test-hygiene.md`　**提交**：7e2f3c2（`docs(evidence): L7 L8 测试卫生与无障碍`）
- **分母（复算）**：三节——① `<tmp>` 字面量：grep 复算 5 行命中、6 次出现（local 4＋server 2，按出现次数口径任务书成立；component_builder.py:25 一行双命中）；② `time.time()/datetime.now()`：tests 内 94、全量含 tests 184、严格非 tests 90（local 35＋server 55，口径勘误见结论 5）；③ 本机全量 unittest 1911 例。
- **差异统计（照报告）**：`<tmp>` 6 处中唯一会执行的 2 处（同一行）为被测非法输入样本，不出补丁，其余 4 处为 docstring/注释；tests 内时钟 94 处＝风险 3＋安全 91；非 tests 90 处含风险最可疑 Top 5（全在 server/scripts：watchlist.py:126、watchlist_runner.py:137、remind.py:40、query.py:115、run.py:62-63）；unittest FAILED (failures=1, skipped=4)，通过 1906。
- **关键结论**：
  1. 唯一会执行的 `<tmp>`（local/tests/test_component_builder.py:25 一行 2 处）是被测非法输入（传入 `builder.output_root()` 断言 `assertRaises(ValueError)`），替换成 tempfile.gettempdir() 会破坏断言——不出补丁；口径张力记 DEFERRED-L7-1。
  2. tests 内时钟风险 3 处：test_session_persistence.py:334/438（本机 naive 时间造学校字段 sign_end/sign_start）、server/tests/test_watchlist_safety.py:164（同口径造 watchlist open_at）——本机 UTC+8 自洽，跨时区机器错位。
  3. 全量 1911 例（任务书「约 1700」已过时，共享树含他人未提交的新测试文件）；失败 1 个＝test_phone_ui.LayoutStaticTests.test_mobile_layout_statics（:2210），由他人在途 conflict-cancel 给 m/styles.css 新增 `.why-r { display: grid; }` 所致——按共享工作区纪律只记录、不回滚、不修改。
  4. skipped 4 个：真实 Git fixture 3 例（需 `CAMPUS_GIT_FIXTURE_AUTH=1` 单独授权）＋非 Windows 分支 1 例（本机即 Windows）。
  5. 口径勘误：任务书把 184 标为「不含 tests」，实测 184＝含 tests 全量（94＋90），严格不含 tests 为 90；成因是 Windows grep 路径反斜杠让 `grep -v '/tests/'` 滤不掉 local/tests。
  6. 排除的「看着像但不是」：common.py:140 是注释、time_contract 3 处是决策 012 设计内诊断快照、grab.py 签名 epoch 毫秒无时区语义。
- **未处理项与理由**：风险判定为【静态推断】（枚举已复现、判定经上下文人工核对）；未跑 server 全量、不跑 `test_dedup.py`（纪律）；生产侧 Top 5 仅静态排查不动代码；test_retry_policy.py:5 死链 docstring 属「旧记录不追改」，是否回改由用户定。补丁 0。

## L8 无障碍名称静态审计正式报告

- **产出**：`a11y-names.md`　**提交**：7e2f3c2（`docs(evidence): L7 L8 测试卫生与无障碍`）
- **分母（复算）**：129 button（110＋19，grep 交叉验证对上）、30 input/select/textarea（22＋8）、11 对话框（5 原生 dialog＋6 role="dialog"）＝170 控件；静态 HTML 与任务书分母完全一致，无差额。
- **差异统计（照报告）**：无名称 button 0/129、缺 type 的 button 0/129、缺有效名称输入 0/30、缺 aria-modal 8/11、aria-labelledby 无效 1（#tour-card）；hidden 标注：button 93/129、输入 21/30、对话框 6/11。
- **关键结论**：
  1. 名称覆盖全绿：129 个 button 全有名称（aria-label 9＋文本 120），30 个输入全有有效名称（placeholder 无一例单独撑名称）。
  2. 唯一实质问题 P1：`div#tour-card`（index.html:336）的 aria-labelledby 指向静态为空的 `h3#tour-title`（JS 填充），运行时可能变成无名对话框——修法：先填标题再显示，或预置第一步标题。
  3. 增强项：三张 `.pop` 状态弹层（#clock-pop/#login-pop/#phone-pop）建议显式补 aria-modal="false"（非模态语义写明）。
  4. 信息项：5 个原生 `<dialog>` 经 showModal 打开时 UA 隐式 modal，缺显式 aria-modal 不构成 WCAG 违规。
  5. 全部判定【已复现】：grep 正向计数＋独立 html.parser 解析双向交叉复核，分母与 hidden 逐行一致。
- **未处理项与理由**：问题清单 10 条（P1 实质＋P2-P4 增强＋P5 动态核验＋P6-P10 信息项）供后续排期，本轮不改 UI（收录轮性质，见 PATCHES/README.md）；JS 运行时填充/改名（#tour-title、#btn-login-text 等）与焦点边界动态行为超出静态审计范围——动态核验需 WebView2（Edge）。

## 对抗审阅（2026-11-08）

八层对抗审阅收束（对抗提交 ff45306→3b2707a，总表与逐层要点见 `ADVERSARIAL.md`），每层三档（站得住／部分站不住／推翻）与红牌：
- L1：78／6／2，红牌 6（全关闭）
- L2：46／8／0，红牌 0（销案 5）
- L3：47／5／0，红牌 10（全处置）
- L4：44／6／2，红牌 ≈13（全处置）
- L5：444／15／3，红牌 0（补漏 1 条，462→463）
- L6：193／1／0，红牌 0
- L7：8／3／2，红牌 4（全处置）
- L8：170 全部站得住，红牌 0
合计：站得住 1030、部分站不住 44、推翻 9、红牌 33；报告已改 138＋补漏 1；L5–L8 技术文档工程师为原分析者、限机械项，实质判定由前端开发者独立承担（身份披露见 ADVERSARIAL.md）；DEFERRED-L7-1 已按对抗结论改写。
