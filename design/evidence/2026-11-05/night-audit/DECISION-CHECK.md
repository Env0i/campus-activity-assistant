# DECISION-CHECK — L4 决策记录核对(2026-11-05 夜审计)

核对原则:已作决定不重开,只核落地。工作区版本为准(含 27 项未提交改动)。核对人:代码审查员(L4 专项)。三态标记逐条附。

## 一、decision-agenda.md D1–D9(M=9,逐条有结论)

| 项 | 决定摘要 | 落地证据 | 判定 | 三态 |
|---|---|---|---|---|
| D1 撤销报名 | 做,延后;不做「我的活动」;依赖 D3 先修 | grep qxbm/撤销报名/rjyHdCyr·cancel 全仓 0 命中(未提前实现);D3 已先行;无「我的活动」视图 | 已落地(延后被遵守) | 静态比对 |
| D2 稿件查看 | 缓做,等方向 | grep rjyWgzj/listMine 0 命中 | 已落地(延后) | 静态比对 |
| D3 is_joined 判据 | 只认学校明确回执,缺字段保守判已报名 | local/grab.py:846-870 _join_state(口径逐条一致)、:886 接线;契约测试 test_school_contract.py:130-190(6 例);落地于未提交工作区 | 已落地(工作区) | 已复现(测试跑绿) |
| D4 组件安装落点 | 方案 A;数据同一目录;路径不进 state/手机快照 | component_packages.py:72-75 用 DATA_DIR;app.py advanced_features_state 内无路径;UI 无路径显示实现 | 已落地(显示部分按决定延后) | 静态比对 |
| D5 原型补齐顺序 | 按 prototype-missing-states.md 第六节顺序,困难计划 | 第六节存在且顺序一致;四画板未补(与延后一致) | 已落地(延后) | 静态比对 |
| D6 演示控件 | 不进产品 | local/ui grep「演示:」0 命中;test_ui_contract.py:2107-2108 禁用清单钉住 | 已落地 | 已复现(测试绿) |
| D7 99 处分批 | 按区域分批;61 处 1:1 直接改;纯文案进 desktop-copy;每批成对截图验收 | 未提交 diff 含 19 个唯一原型行号引用(Main:663/728/738/744/745/1261/1262/1702/1849/1922/1928/1944/1956/1988/1993/2006/2095/2096/2138),全部计划栏/主窗口纯文案类;结构类未动 | 部分落地(截图验收无法在仓库验证) | 部分已复现(diff)/部分无法验证(截图) |
| D8 运行时密钥同值 | 维持 013 L3 不改写历史;B9 升版时不另写 | 013-distribution-and-privacy.md:178;条款仍 r4 未动 | 已落地(维持现状) | 静态比对 |
| D9 N1/N2/N3+4001 观察 | N1/N2 本计划修;N3 归困难计划;4001 长期观察 | N1=relogin.js:155-163 reloginSucceeded+plan.js:404-405+ReloginRefreshTests(工作区);N2=refresh.js:127-132 断网早退+app.js:328-337 net-recheck+RefreshFeedbackTests(工作区);N3 diff 未触弹窗视觉(一致);埋点 log_events.py:18+grab.py:252 | 已落地(N1/N2 工作区;N3/观察延后) | 已复现(新测试跑绿) |

## 二、handoff 收据 B 组十条(M=10,逐条有结论)

| 项 | 决定 | 落地证据 | 判定 | 三态 |
|---|---|---|---|---|
| B1 | 010 缩进恢复 2 格 | 010-standalone-exe-and-settings.md:32 为 2 格;git status 该文件无改动 | 已落地 | 已复现(读文件+git) |
| B2 | 两个证据文件入库、交接说明不入库 | 74447a2 含 2026-11-02/README.md 与 live-check.md;handoff-to-claude.md 不存在未被跟踪 | 已落地 | 已复现 |
| B3 | 原始条目脱敏入库 | contracts/school-api/list-activity.raw-item.json 在库;README.md:35 注明;_map_activity 抽纯函数+契约测试落地工作区(grab.py:788、test_school_contract.py:96-113) | 已落地 | 已复现(测试绿) |
| B4 | 真实密码错回包(脱敏) | login_relay.py:78-81/:672 bad_password;test_login_relay.py:921/948;contracts README:35 | 已落地 | 已复现(测试绿) |
| B5 | 验证码大小写文案改+014 同步 | **local/ui/index.html:370 仍是旧文案「大小写照图里写」;014:55 仍「未确认」;redesign-design.md:322 待定项仍在**。回执标「已完成」与仓库现状**矛盾**(疑被收据自述的中途重做还原后未重做) | **未落地(回执标注失实)** | 已复现(读文件+grep) |
| B6 | 404/429/5xx/性别不符样本,遇到时留 | signup-replies.json 10 类,无真实 404/429/5xx;条件式决定,条件未触发 | 无法验证(等待真实回包) | 无法验证 |
| B7 | 删除 local/gui.py(连同测试引用) | **local/gui.py 仍存在且与 HEAD 一致**(无 D 标记;最后触碰为 d0be34c 修改);local/README.md:369 仍列。回执标「已删除(工作区)」与其自身重做记录(receipt:141「25 文件 checkout,gui.py 恢复」)自相矛盾 | **未落地(回执标注失实)** | 已复现 |
| B8 | 待核对「打开活动页」按钮不做 | 无该按钮;plan-events.js:142 属说明文字;21b6591 正文明确放弃 | 已落地(不做) | 静态比对 |
| B9 | 清条款「直发」+升版本(只记录、未执行、未排期) | USER_AGREEMENT.md 含「直发」5 行、index.html 内嵌 3 行;TERMS_VERSION="2026-11-03-r4" 未升 | 未落地(符合决定语义:待执行未排期,非违约) | 已复现(读文件) |
| B10 | 筛选空态标题以原型为准不改 | list.js:259 = 原型 Main:2097 | 已落地(维持) | 静态比对 |

## 三、两份 plan 落地核对

**找到的两份**:Plan-A=`.claude/handoff/2026-11-04-remaining-and-template.md`(收据 :377 引用的原清单);Plan-B=`docs/superpowers/specs/2026-11-03-architecture-revision-design.md`(收据通篇引用的架构方案)。决策清单点名的 "fix-is-joined"/"desktop-copy"/"困难计划" 批次无独立计划文档(全仓 grep 仅 decision-agenda.md 自身命中)——只能按决定内容核代码现状(已并入上表)。

### Plan-A(原清单,M=7)

| 项 | 承诺 | 证据 | 判定 |
|---|---|---|---|
| C1 | 登录入口文案改口径+规格三处同步 | 代码已落地(app.py:2254/2256、list.js/login.js);**但 copywriting.md:195 仍残留旧红线「登录剩余时间仅供参考」** | 部分落地(规格残留一处,疑同 B5 重做被剔除) |
| C2 | 「重登」→「重新登录/自动登录」 | 仅 login_relay_service.py:111 docstring 1 处(非用户可见) | 已落地 |
| C3 | 认「账号或密码错误!」报 bad_password | login_relay.py:81/672+test 921/948 | 已落地 |
| C4 | 手机页重排(决定不做) | m/ 未重排 | 已落地(按决定不做) |
| C5 | 7 条时区夹具改北京时间 | test_signup_plan.py:30/744-745、test_ui_contract.py:20/3301/3334 | 已落地 |
| C6 | 发版(决定不做) | VERSION/CHANGELOG 未动 | 已落地(按决定不做) |
| A 组 | 真机验证/构建/push | A6: origin/main=4ec0b3d 可验;A1/A5 结论入库(4ec0b3d);A3 的 5 资产在 dist/(不入库) | 已落地(A3 无法验证) |

### Plan-B(架构修订,第 11 节建议清单 M=17 + 第 12 节文档修订抽样)

| 项 | 判定 | 证据 |
|---|---|---|
| M1 直发改运行时密钥 | 已落地 | grab.py:2020/2026 |
| M2 回包分类表 | 已落地 | domain/signup_reply.py + contracts/signup-replies.json |
| M3 终态总核对 | 已落地 | grab.py:1508/:3197-3202 |
| M4 失效先复查/原地重登 | 已落地 | grab.py:1509+提交 6a46032/4a48acb/e16d268 |
| M5 修列表崩溃 | 已落地 | d0be34c |
| M6 条款 r4 重新同意 | 已落地 | app.py:207+3f1d74b |
| M7 文档修订 | 已落地 | 3e81dcb/536f89a/038c48f |
| M8 站点构建注入+发版可追溯 | 已落地 | local/site_target.py+6ee013c |
| M9 证据入库脱敏 | 已落地 | 8458d24+工作区 school-frontend-analysis.md 脱敏 |
| S1 开抢前预检 | 已落地 | grab.py:1510 PRECHECK_AHEAD_S=45.0+b0e4448 |
| S2 结构化日志/轮转 | 已落地 | grab.py:182 LOG_MAX_BYTES+log_events.py:18 |
| S3 去剩余时间改上次校验时刻 | 已落地 | d0be34c+test_ui_contract.py:1587 |
| S4 共享契约样例 | 已落地 | contracts/school-api 5 文件(1ce0d51/cff153f) |
| S5 登录态单写入口加锁 | 已落地 | grab.py:337/:367(00e1bce;全库无绕锁残留) |
| S6 Api 方法数按实际写 | 已落地 | ARCHITECTURE.md:177「49 个公开方法」 |
| L1 server 同步 | 已落地 | 23b3dfc |
| L2/L6/L7 等样本/排最后 | 已落地(条件式延后) | 无落地对象 |
| L3 历史不改写 | 已落地 | 013:178 |
| L4 核实登录网关签名头 | 无法验证 | 需真实网络 |
| L5 拆 cmd_grab | 已落地(条件式延后) | 未触发条件 |
| 第 12 节文档修订抽样 | 已落地 | RETRY_POLICY_GUIDE:150/156 ✓、UI_SPEC:674/732 ✓、ARCHITECTURE:177 ✓ 且旧句 0 命中、grab.py:2506 ✓ |

## 四、汇总与需人定项

- **D1–D9**:8 已落地、1 部分落地(D7,截图验收无法验证)。无重开。
- **B 组**:6 已落地、3 未落地(B5/B7 为**回执标注与仓库现状矛盾**;B9 符合"待执行"语义)、1 无法验证(B6)。
- **Plan-A**:C1 部分落地(copywriting.md:195 残留);其余落地。
- **Plan-B**:M1-M9/S1-S6/L1/L3/L5 全落地;L4 无法验证。
- **需人定(见 DEFERRED.md)**:B5/B7/C1 三处"回执说做了、仓库里没有"高度疑似同一根因——收据 :139-142 自述的中途清空重做还原了这批文件后未重做;处理方式(重做改动 vs 修订回执)属交接流程,留人定。

---

## 五、第二轮追加:STANDARD.md 判据与仓库设计的冲突登记(2026-11-05)

知识优先级:reports/STANDARD.md > 仓库设计文档 > 判断。冲突按 STANDARD 处理,但 STANDARD 本身在制定时吸收了仓库设计,以下为显式登记:

| # | 冲突 | 裁定 | 依据 |
|---|---|---|---|
| C1 | §3「一律走 business_clock」vs 架构 4.5 生命周期用"本机经过时长"与日志/展示戳用本地时区惯例 | STANDARD §3 J3.2 列允许清单(时间源实现/日志展示戳/lifecycle 经过时长/构建元数据/测试夹具);业务判定链除外 | 第一轮静态扫描 R7 分诊 46 处生产命中全部落在允许清单或已记 F-09 |
| C2 | §6「一律 with」vs 文件锁句柄跨临界区生命周期(grab.py:310、prefs_store.py:111、common.py:221/263) | J6.2 允许非 with,但必须 try/finally 收口,逐处核对 | 锁语义要求句柄活到锁释放,with 反而改变生命周期 |
| C3 | §2 命名 vs pywebview Api 公开方法名=前后端契约、部署脚本引用文件名 | 契约名不改(J2.3 允许清单) | test_ui_contract/launchers 钉住;改名=破契约 |
| C4 | §8 历史不追改 vs specs 与实现同步 | decisions/evidence/CHANGELOG 已发布段不追改;活规格(specs/docs/README)按 J8.4 修 | AGENTS.md「旧记录不追改」只约束过程记录 |

三态:以上均为静态裁定(有文档依据),C1 的允许清单覆盖面经静态扫描复核。

| C5 | 第一轮 R1 except-pass 扫描用单行正则,漏检多行形态(application 7 处、infrastructure 20 处含 noqa 变体) | 后续批次一律用多行正则 canonical 命令;STANDARD §4 J4.1 已补「行尾 noqa 注释变体」形态说明 | 批2/批3 扫描员双向确认 |
| C6 | application/advanced_component_service.py:29 `from infrastructure import component_packages` 与 application/__init__.py「只依赖 domain」声明不一致 | P3 保留:硬引用仅版本常量,inspect/install 仍走注入端口;登记不改 | 批2 扫描观察项 A |
| C7 | HEAD 固有 test/code 矛盾(F-30):phone_control_only 用例 vs HEAD 代码已对 relogin_ocr 暴露 download | 不在本轮修(修=动既有 27 项);既有改动已含正确重写 | 纯 HEAD worktree 单测复现 |
| C8 | 批8 docs 扫描 #18/#19:条款入口路径(帮助→设置)与「直发→直接提交」清理,需改条款正文并触发 r4→r5 升版(用户重新同意) | 与 B9 决策(「清条款直发+升版本:只记录、未执行、未排期」)同源,属用户已拍板的待排期项 → 本轮 DEFERRED 不动,版本不升 | B9 + 批8 扫描 #18/#19 与 docs/USER_AGREEMENT.md、index.html 内嵌逐字契约测试绑定 |
| C9 | server/bot/bot.js:114 users.json 解析失败「静默清空重建」与 server/bot/handled_messages.js「解析失败显式抛错」两种策略并存 | 保留分歧并如实注释(批13 已写裁决注释):bot.js 的 users.json 是低价值缓存,降级重建可接受;handled_messages 的已处理消息表丢一条会重复回复,必须抛错。两文件价值不同,策略不同是设计而非疏漏 | 批13 执行者裁决注释 + 质检员抽查通过 |
