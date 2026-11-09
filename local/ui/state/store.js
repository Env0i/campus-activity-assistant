/* 状态仓库：常量、引导文案、全局状态 S（唯一状态持有者）。 */
const $ = (selector) => document.querySelector(selector);

const DEFAULT_HELP = {
  title: "使用帮助",
  subtitle: "三步完成一次报名",
  /* 文案逐字照抄原型 Main.dc.html:745（1:1 基准）。原型帮助里没有适用范围说明，
   * 那两句在首次使用的条款摘要里（:750），不在这里重复。 */
  steps: [
    { no: 1, title: "确认登录", text: "顶部显示“已登录”就可以继续。只有提示失效时才需要重新登录。" },
    { no: 2, title: "选活动并开始", text: "在时刻表勾选活动，核对右边的计划，再点“开始报名计划”。勾选不会自动开始。" },
    { no: 3, title: "看结果", text: "每场结果单独显示。看到“待核对”时，到学校活动页确认。" },
  ],
};

/* 与 grab.py / app.py 对齐的常量 */
const RETRY_WINDOW_S = 120;  // grab.py --window：开放后最多再试 120 秒
const SLEEP_GAP_MS = 120e3;  // 两次心跳间隔超过 2 分钟：多半是电脑睡过去了
const WEEK = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

/* 引导内容版本：与软件版本（VERSION 文件）独立，内容有实质变化时 +1，
 * 完成或跳过过旧版的用户会在新版再自动弹一次；同版绝不重复自动弹。
 * 3：新工作台（决策 009 修订）由六步改为五步，启动时机改为登录成功且列表加载后。 */
const TOUR_VERSION = 3;
/* GitHub 最新版本页：只有用户点按钮时才由后端用系统浏览器打开，启动时不联网检查 */
const RELEASES_LATEST_URL = "https://github.com/Env0i/campus-activity-assistant/releases/latest";
/* 五步主线（设计文档第 7 节）：时刻表 → 动手勾选 → 核对计划 → 开始以后 → 顶部状态。
 * target 对应 index.html 的 data-tour-target；「row」由 views/tour.js 现找一行可勾选的活动。
 * 只有勾选那一步可以真的点一行（interactive），其余步骤背景不可点；引导从不代替用户点任何东西。 */
const TOUR_STEPS = [
  { target: "list", title: "这是活动时刻表",
    text: "活动按开放时间排好。“预报名”等开放后自动提交，“立即报名”点开始后马上提交。上面可以搜索和筛选。" },
  { target: "row", interactive: true, title: "勾选想报的活动",
    text: "点这一行试试。勾选只是加入计划，不会开始报名；举办时间重叠的活动不能同时选。" },
  { target: "select", title: "核对计划，再点开始",
    text: "选好的活动都列在这里，可以逐场移除，也能修改尝试时长。开始不了时，按钮下面会写还差什么。" },
  { target: "run", title: "开始以后看这里",
    text: "这里显示倒计时，下面是每场进度。可以最小化窗口，但不要关闭工具或让电脑睡眠。看到“待核对”时，到学校活动页确认。" },
  { target: "login", title: "出问题先看顶部",
    text: "登录和北京时间的状态都在这里，有问题会写下一步。想再看一遍引导，点“帮助”。" },
];

/* FU02 首次说明框六条要点（原型 FirstUse 画板 Main:799-807，版式与标题逐条照原型；
 * 说明句按 r5 正文改写——原型句子与 r5 有出入处以 r5 为准（plan decisions 第 2 条），
 * 正文真源是 index.html 内嵌全文）。
 * 第六条是入口行：link 标记让 views/terms.js 渲染「现在就看」链接钮（Main:806），
 * 点它先收起首次说明框再开全文阅读器；末句照原型指路设置入口。 */
const FIRST_USE_POINTS = [
  { title: "非官方工具",
    text: "只适用于一所目标学校，与学校、学校系统运营方及飞书均无隶属、合作或授权关系，不承诺报名成功。" },
  { title: "工具会直接调用学校接口",
    text: "活动列表、活动详情与报名结果核对都直接调用学校接口，不经过学校页面。报名开放时程序直接向学校报名接口提交，报名前会向学校获取一个只在本次运行内存里的运行时密钥，不落盘、不写日志；开抢时会在短时间内多次提交，页面点击只在直接提交不可用时兜底。只提交你在计划里选好的场次。" },
  { title: "保存账号后会自动登录",
    text: "保存账号密码后，登录失效且具备自动登录条件时，工具会自动登录。程序用浏览器填表登录时会替你勾选学校登录页的《隐私协议》；直接调用登录接口时，完全不经过学校登录页。不保存就不会自动登录。" },
  { title: "风险由你判断",
    text: "学校登录页的《隐私协议》里没有关于脚本或自动化的条款，工具不声称合规，以你账号名义提交的一切由你本人负责。用本工具登录会让同一账号在其他地方的登录失效，包括手机上的学校页面与服务器版。只用本人账号，不提供多账号、批量占位或代他人报名。" },
  { title: "数据只在这台电脑",
    text: "登录凭据、活动缓存与设置只保存在这台电脑的数据目录，没有云端备份。平时只连学校系统、网络授时服务；你点检查更新或下载时会访问 GitHub；开了手机访问时，手机和电脑之间的往来经你选的 Cloudflare 或 Tailscale 通道。" },
  { title: "完整条款", link: true,
    text: "用户协议、隐私政策和开源许可的全文，现在就看。以后也能在“设置 → 条款与隐私”里看。" },
];

const S = {
  items: [],
  byId: new Map(),
  rowEls: new Map(),
  rowStates: new Map(),
  selected: new Set(),
  selectionNotice: "",
  filter: { q: "", status: "all", time: "all", sort: "open", checkin: "all", checkout: "all" },
  listState: "idle",
  /* 最近一次列表失败的原话：完整失败说明只归列表空态，结果框不再复读 */
  listError: "",
  /* preLoginSnapshot：一次重新登录前的完整登录结论快照。取消/超时/失败时整份
   * 回滚，避免异步尝试的中途状态把仍有效的旧凭证画成「登录已失效」。 */
  /* estimateReason：预计有效的来源（E2：ok / no_anchor / clock_unavailable），
   * 只决定详情卡写哪种提示，不参与任何放行或过期判断 */
  login: { hours: null, ok: null, expireAt: null, savedAt: null, present: null, checking: false, loginPending: false, result: null, estimateReason: null, preLoginSnapshot: null },
  /* 程序组件自检结论（worker_missing/worker_permission/spawn_failed）：非空时组件
   * 问题优先于登录/网络文案，登录与开始禁用。check/list 两分支按「刷新轮次」
   * 协同恢复：任一分支报组件故障立即挂横幅，另一分支成功/普通 unknown 不得撤；
   * 本轮两分支都完成且无故障才撤旧横幅（FB4 的两到达顺序一致语义） */
  runtime: { error: null, checkPending: false, listPending: false, roundError: null },
  /* 更新只读GitHub，单独记录结果；不能借用报名/组件错误通道。 */
  update: { state: "idle", requestId: "", result: null, timer: null },
  /* FB1 轻量「开始提交中」标志：成功/拒绝/reject 均释放，只做即时按钮反馈，
   * 后端最终接纳点的原子重检仍是最终权威 */
  starting: false,
  clock: { state: "unknown", offset: null, uncertainty: null, checkedAt: null, detail: "" },
  online: navigator.onLine !== false,
  sleepGap: 0,
  /* GL01 又打开了一次（second_open 事件）：横幅挂着直到点「知道了」 */
  secondOpen: false,
  /* MG01/MG02 迁移结果（bootstrap.migration）：{moved, login_failed, other_failed} 或 null（没迁移）。
   * migrationDismissed 记本次运行内点过 MG01「知道了」——只存内存，不写偏好。 */
  migration: null,
  migrationDismissed: false,
  /* LS06 更多筛选面板是否展开；记在偏好 filter_open 里，applyPrefs 读回 */
  filterOpen: false,
  busy: false,
  stopping: false,
  /* 后端 bootstrap 的 demo 标记：演示模式不要求登录校验 valid 即可开始计划 */
  demo: false,
  /* 计划事件归属（P1）：后端每次最终接纳新计划递增 plan_generation，
   * 事件/快照据此判定归属；这里记录已见过的最大代次，旧代次事件不得改写当前计划 */
  maxPlanGen: 0,
  plan: { id: null, gen: 0, status: "idle", tasks: new Map() },
  /* 本进程已确认的报名成功（activity_id → {source, atMs}）。学校列表短暂滞后时
   * 仍把这场留在「已报名」并禁止再次选择；超过窗口后以学校列表为最终权威。 */
  confirmed: new Map(),
  /* 独立北京时间锚点：ingestBusinessClock 维护，businessNowMs 消费（决策 012）。
   * anchorEpochMs 对应 perfAt 那一刻；sampleAgeMs 是快照原地的授时年龄。 */
  businessClock: { anchorEpochMs: 0, perfAt: 0, sampleAgeMs: 0, uncertaintyMs: 0,
                   bridgeMs: 0, gen: -1, owner: "", state: "unavailable",
                   source: "", reason: "",
                   syncState: "idle", syncError: "", attempted: false },
  /* 上一帧的运行阶段：跨过开放时刻/进入真正提交时要重画一次大屏摘要 */
  lastRunPhase: null,
  prefs: {},
  /* 使用条款同意状态（决策 013）：version 是后端 bootstrap 带来的当前条款
   * 版本；acceptedVersion 是本机 ui.json 里已同意的版本；declined 记「这一版
   * 已经拒绝过」（重启时由 prefs.terms_declined_version 恢复）；unknown 记
   * 「条款状态没读到」，是 fail-closed 的第二种形态——拒绝不退出、不再强弹，
   * 但登录/列表/报名计划保持停用。 */
  terms: { version: "", acceptedVersion: "", acceptedAt: "", declined: false,
           prompted: false, unknown: false,
           /* 交互收口的会话态（只存内存，不新增 prefs 键）：saving=正在保存；
            * requestSeq=请求代号，超时/关闭时自增使迟到回执失效；unconfirmed=
            * 10 秒没拿到可确认结果（既非成功也非失败）；viewOnly=已同意同版的
            * 只读查看；source/focusBack=打开来源与要还回去的焦点；closeHandled=
            * 程序性关闭自己处理焦点与引导，close 监听不再重复处理；tourYield=
            * 打开条款时让位的引导；deferredIntro=boot 时被条款推迟的首次欢迎/引导 */
           saving: false, requestSeq: 0, unconfirmed: false, viewOnly: false,
           source: "", focusBack: null, closeHandled: false, tourYield: false,
           /* box=正在等待返回的条款小框（FU01/TM08，decisions 第 1 条）：
            * "intro"=首次说明框、"update"=条款更新框、""=没有小框在等。
            * 全文阅读器由小框打开时保留该值，×/Esc 关全文据此回到原小框；
            * 同意成功或拒绝后清空（两框都关，不再回小框）。 */
           deferredIntro: null, box: "" },
  /* MIT 许可证页签的懒加载缓存：null=还没取过；{state:"loading"}=在途；
   * {state:"ok",text}=随包 LICENSE 原文；{state:"error",text}=就地可重试的失败。
   * 只缓存成功结果，失败留 error 态等「重新读取」，不自动轮询。 */
  licenseText: null,
  /* 后端 bootstrap 的 lifecycle 快照：上次关闭时长/质量 + 登录估算（只提示，不参与门禁） */
  lifecycle: null,
  /* 五步引导运行态：open=遮罩在场；paused=计划运行中暂停；restoreFocus=结束后要还的焦点 */
  tour: { open: false, step: 0, paused: false, restoreFocus: null },
  /* 计划级重试策略：-1=自动延长（最多 25 分钟）；时长 0=直到报名截止（缺截止回退 120 秒）；次数 0=不限 */
  retryPolicy: { retry_for_s: 120, max_attempts: 0 },
  /* 三种重试模式的权威选项与默认值（bootstrap.retry_options 同源覆盖）：
   * 桌面白名单与手机设置都按这份口径，不各自维护第二套清单 */
  retryOptions: {
    default: 120,
    fallback_seconds: 120,
    adaptive_cap_seconds: 1500,
    choices: [
      { value: 120, label: "2 分钟" },
      { value: 600, label: "10 分钟" },
      { value: 1800, label: "30 分钟" },
      { value: 3600, label: "1 小时" },
      { value: -1, label: "自动延长（最多 25 分钟）" },
      { value: 0, label: "直到报名截止" },
    ],
  },
  /* 取消报名（20261107-conflict-cancel X3/X4）：askId=确认块开在哪一场；busyId=正在取消哪一场；
   * res=结果句（{id, kind, say?, reason?}），到下一次手动刷新或下一次点取消为止 */
  cancel: { askId: "", busyId: "", res: null },
  /* 「不可加入」原因气泡：id=当前打开的那一行；flashId=「去已报名那场」后短暂高亮的行 */
  tip: { id: "", timer: null, openTimer: null, flashTimer: null },
  flashId: "",
  logOpen: false,
  /* 最近 40 条运行记录：成功结论只写一次，重复事件不刷第二遍（RC-06） */
  recentLogs: [],
  recheckPending: false,
  savePending: {},
  saveTimer: null,
  /* 每一轮 check/list 的请求 ID：迟到事件按 ID 丢弃，不能覆盖新轮（R11） */
  round: { check: "", list: "", checkTimer: null, listTimer: null,
           /* gen 是「刷新消费代次」：每次 refresh 递增，同轮重复只生效一次，
            * 新一轮允许用同一个 owner 结果收口（FR04）。applied 只按
            * branch:gen:request 记账，不再跨轮永久拦截。 */
           gen: { check: 0, list: 0 }, cache: [], applied: {},
           /* 一次性副作用（日志/提示）按请求幂等：跨轮重放同一 owner 时
            * 状态要恢复，但同一句话不能刷两遍。 */
           notified: {} },
  /* 开始请求的对账状态：submitting / reconciling / accepted / rejected / unknown。
   * gen 是查询代次：只有同一请求、同一代次的回复才能落地。 */
  startRequest: { id: "", state: "idle", timer: null, queryTimer: null,
                  reconcile: 0, gen: 0 },
};

/* 轮次 ID：同一轮的所有事件共享，旧轮迟到消息不得改写新轮 */
