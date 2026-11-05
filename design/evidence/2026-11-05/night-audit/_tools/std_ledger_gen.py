# -*- coding: utf-8 -*-
"""Generate reports/STANDARDIZATION.md: 469-row ledger aligning every tracked
file to reports/STANDARD.md's eight criteria sections.

Row = 路径 / 判据节 / 判定(合规|已改|保留|N/A) / 理由 / 证据.
Usage: python -I reports/_tools/std_ledger_gen.py  (repo root)
"""
import subprocess
from collections import Counter

CANON = "canonical 多行正则(except...pass)"


def tracked():
    out = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "-z"],
                         capture_output=True, check=True).stdout.decode("utf-8")
    return sorted(f for f in out.split("\0") if f)


# ---- per-file overrides from the eight batch scans (批1-8) + root self-scan ----
# value = (判定, 判据节, 理由, 证据)
O = {}

# 批1 local/domain(扫描员全量判据命令,0 命中证据)
DOM_OK = ("合规", "§1/§2/§3/§4/§5/§6", "批1 扫描:纯函数层判据全过(import 0 反向/0 落盘/0 读钟/20 处 except 全窄捕)", "批1 判据命令 + 根级自扫")
for f in ("__init__.py", "demo_data.py", "errors.py", "lifecycle_rules.py", "log_events.py",
          "phone_rules.py", "plan_rules.py", "retry_rules.py", "retry_window.py",
          "signup_reply.py", "time_text.py", "worker_lines.py"):
    O["local/domain/" + f] = DOM_OK
O["local/domain/log_events.py"] = ("合规", "§5", "键名黑名单模块,§5 正面样板;批1 扫描确认", "批1 命令 11/12")
O["local/domain/phone_rules.py"] = ("保留", "§8", "MAX_IMAGE_BYTES/_PNG_MAGIC 跨进程镜像常量,注释已指明对端", "批1 P3-3")
O["local/domain/plan_rules.py"] = ("保留", "§8", "_NON_CONFLICT_TEXT 与 selection.js 双源,测试钉住(test_signup_plan:189)", "批1 P3-2")
O["local/domain/login_rules.py"] = ("已改", "§4", ":91 宽 except→(TypeError,ValueError)+注释;判据 1→0,反向 0→1", "std-1-domain.patch;批1 P2")

# 批2 local/application
APP_OK = ("合规", "§1/§2/§3/§4/§5/§6", "批2 扫描:now 全注入、0 写盘、0 硬路径、脱敏合格", "批2 判据命令")
for f in ("__init__.py", "auto_relogin.py", "login_service.py", "phone_service.py", "update_service.py"):
    O["local/application/" + f] = APP_OK
O["local/application/__init__.py"] = ("保留", "§1", "「只依赖 domain」声明与 advanced_component_service 直连 infrastructure 的口径出入(C6),P3 保留", "批2 观察项 A")
O["local/application/phone_service.py"] = ("合规", "§1/§3/§4/§5", "now 注入;:211/:216 canonical 命中为裁决合规(必要吞,批2 已核)", "批2 + 根级自扫")
O["local/application/advanced_component_service.py"] = ("已改", "§4", ":287 except-pass→_note 留痕(P2);:352 补注释;canonical 14→13", "std-2-application.patch")
O["local/application/plan_service.py"] = ("已改", "§4", ":378/:384/:388 finally 清理吞补注释(必要吞);Fix B 时钟门控为 §3 合规样板", "std-2-application.patch")
O["local/application/login_relay_service.py"] = ("已改", "§4", ":479/:481 补注释(时序核实:SUCCESS 先于回调);canonical 其余命中裁决合规", "std-2-application.patch")

# 批3 local/infrastructure + runtime_paths
for f in ("__init__.py", "advanced_features.py", "component_packages.py", "credential_store.py",
          "phone_http.py", "phone_qr.py", "phone_session_store.py", "prefs_store.py",
          "process_tree.py", "tray_icon.py", "tunnel_manager.py"):
    O["local/infrastructure/" + f] = ("合规", "§1/§2/§3/§4/§5/§6", "批3 扫描:os.replace 原子写齐、锁句柄 finally 收口、脱敏合格、0 盘符", "批3 判据命令")
O["local/infrastructure/tunnel_manager.py"] = ("已改", "§4", ":303 kill 兜底补裁决注释(std-10);deadline 用注入 monotonic", "std-10-infra-comments.patch;批3 V7")
O["local/infrastructure/lifecycle_store.py"] = ("已改", "§4", ":263/:140 留痕(std-3);:264 措辞修正+删未使用 as exc(std-15b);:33/:79 本机经过时长=J3.2 允许清单", "std-3/15b-infrastructure/wording.patch;批3 V1/V2")
O["local/infrastructure/phone_session_store.py"] = ("保留", "§3", "设备信任 TTL 用 time.time():非报名链、now 可注入,J3.2c 同类,意见性保留", "批3 V3")
O["local/infrastructure/tray_icon.py"] = ("已改", "§4", "6 处 broad pass 补裁决注释(std-10):装饰层失败语义,docstring 明示", "std-10-infra-comments.patch;批3 V5")
O["local/infrastructure/process_tree.py"] = ("已改", "§4", "5 处清理路径 pass 补裁决注释(std-10);外层 raise 保原异常", "std-10-infra-comments.patch;批3 V6")
O["local/infrastructure/prefs_store.py"] = ("合规", "§6", "锁句柄非 with 但双层 finally(J6.2 允许清单);:33 broad except=文档化契约非 pass", "批3 J6.2 核对")
O["local/runtime_paths.py"] = ("合规", "§6", "迁移 mkstemp+copy2+os.replace+finally unlink;0 盘符", "批3 扫描")

# local 根级源码(自扫+轮1深审)
O["local/app.py"] = ("已改", "§4", "13 处吞异常裁决注释(std-9a)+3 处措辞修正(std-15a,质检员文本);datetime=日志戳/兜底/epoch(J3.2);Fix C 已提交", "std-9a-app/std-15a-wording.patch;质检员 33 处全查 0 不符")
O["local/grab.py"] = ("已改", "§4", "8 处裸 except-pass 补注释(std-9b);datetime 命中=日志戳/nonce 种子(J3.2)", "std-9b-grab.patch;根级自扫;轮1 深审")
O["local/business_clock.py"] = ("已改", "§4", "2 处注释(std-9b)+:665 措辞修正(std-15b,质检员文本);:859 os_offset=设计;时间源实现=J3.2a", "std-9b-grab/std-15b-wording.patch;质检员抽查")
O["local/signup_transport.py"] = ("已改", "§4", ":170 裁决注释(std-9b):不吞会顶掉 except 的 return 致重复 failed/completed 缺失", "std-9b-grab.patch;质检员抽查")
O["local/login_relay.py"] = ("合规", "§4", "4 处 except-pass 注释 100% 在场(根级自扫裁决)", "根级自扫")
O["local/gui.py"] = ("保留", "§4/§3", "遗留 tkinter 壳:4 处裸 pass 不注(B7 决定删除);:820/:833 naive 时区=轮1 F-12 已记", "轮1 F-12;根级自扫")
O["local/signup_plan.py"] = ("合规", "§1/§3/§4", "轮1 深审合格;根级自扫 0 命中", "轮1 D 报告;根级自扫")
O["local/signup_signing.py"] = ("合规", "§1/§4/§5", "CNG 签名轮1 深审合格;自扫 0 命中", "轮1 D 报告")
O["local/time_contract.py"] = ("合规", "§3/§4", "UTC+8 唯一口径轮1 合格;自扫 0 命中", "轮1 D 报告")
O["local/site_target.py"] = ("合规", "§6/§8", "域名唯一真源;自扫 0 命中", "根级自扫;轮1 L4/M8")
O["local/update_check.py"] = ("合规", "§4/§6", "no_installer 三分类;自扫 0 except-pass", "根级自扫;轮1 L1/#4")
O["local/updater.py"] = ("保留", "§6", ":33-36 <tmp> 死分支(F-01b,恒回退无害);改=生产行为,轮1 记录未动", "根级自扫;轮1 F-01b")
O["local/advanced_helper.py"] = ("合规", "§4", "薄壳(61 行);自扫 0 命中", "根级自扫")
for f in ("build_advanced.py", "build_exe.py", "build_installer.py", "make_portable.py"):
    O["local/build/" + f] = ("保留", "全部", "打包构建链,轮1 范围外;仅静态扫描(轮1)+根级 grep 无违规命中", "轮1 COVERAGE;静态扫描")
for f in ("check_updates.bat", "grabs.bat", "install_components.bat", "run_debug.bat", "_py.bat", "启动不了点我.txt",
          "install.bat", "install_components.bat"):
    pass  # launchers handled by rule below

# 批4 local/ui(41 源文件)
UI_OK = ("合规", "§1/§2/§3/§4/§6", "批4 扫描:无 fs、无硬路径、businessNowMs 架构完整、文案为 1:1 契约", "批4 判据命令")
for f in ("app.js", "index.html", "styles.css", "led.js", "controllers/bridge.js", "controllers/clock.js",
          "controllers/plan-events.js", "controllers/prefs.js", "controllers/refresh.js", "controllers/terms.js",
          "controllers/tick.js", "controllers/window.js", "state/clock.js", "state/filters.js", "state/labels.js",
          "state/login.js", "state/plan.js", "state/rounds.js", "state/store.js", "state/task-display.js",
          "state/time.js", "views/clock-pop.js", "views/clock.js", "views/help.js", "views/list.js", "views/log.js",
          "views/login.js", "views/phone.js", "views/plan-panel.js", "views/selection.js", "views/settings.js",
          "views/status-cards.js", "views/tour.js", "views/update.js", "m/app.js", "m/index.html", "m/styles.css"):
    O["local/ui/" + f] = UI_OK
O["local/ui/styles.css"] = ("N/A", "全部", "纯样式,无路径/逻辑", "批4")
O["local/ui/m/styles.css"] = ("N/A", "全部", "纯样式", "批4")
O["local/ui/app.js"] = ("已改", "§4", ":67/:397/:503 吞异常补注释(std-4a);armedAt 死字段为观察项", "std-4a-ui.patch;批4 V3-V5")
O["local/ui/views/relogin.js"] = ("已改", "§4", ":74 取消重登失败静默→addLog 留痕(P2);空 flow 哨兵=轮1 Fix E 在位", "std-4a-ui.patch;批4 V1")
O["local/ui/views/terms.js"] = ("已改", "§4", ":363 空 catch 补注释(std-4a)", "std-4a-ui.patch;批4 V2")
O["local/ui/controllers/plan.js"] = ("已改", "§4/§2", ":265 吞异常补注释(std-4b);armedAt 死键 :84/:220 删除(std-16)", "std-4b-ui/std-16-armedat.patch")
O["local/ui/controllers/update.js"] = ("已改", "§4", ":65/:118 吞异常补注释(std-4b)", "std-4b-ui.patch;批4 V7/V8")
O["local/ui/state/plan.js"] = ("已改", "§2", "armedAt 死键 :59/:81 删除(std-16,全仓零读取核verified,契约测试反而禁止该字段)", "std-16-armedat.patch;批4 观察项")
O["local/ui/controllers/refresh.js"] = ("已改", "§3/§2", ":69 armedAt 死键删除(std-16);:309 Date.now 回退带注释仅显示同步窗", "std-16-armedat.patch;批4 研判")

# 批5 local/tests
T_OK = ("合规", "§7", "批5:夹具 dir= 全合法、0 恒真断言、0 脆弱日期、except-pass 15 处全为窄类型清理轮询形态", "批5 判据命令")
for i in range(1, 47):
    pass  # default rule below handles test_*.py
O["local/tests/test_retry_policy.py"] = ("已改", "§7", ":5 docstring <tmp> 路径→日期+命令口径(std-5)", "std-5-tests.patch;批5 J7.2")
O["local/tests/test_updater.py"] = ("已改", "§7", ":51 docstring <tmp>→gettempdir 口径(std-5)", "std-5-tests.patch;批5 J7.2")
O["local/tests/test_component_builder.py"] = ("保留", "§7", ":25 <tmp>/C:/bad 为负向测试输入,J7.2 允许清单豁免", "批5;STANDARD J7.2 允许清单")
O["local/tests/fixtures/business_clock.py"] = ("已改", "§2", "TestWallClock→WallClockStub(std-18a:pytest Test* 形状误导,非 TestCase,65 处引用 8 文件同步改名,计数守恒)", "std-18a-rename.patch;批5 §2")
O["local/tests/fixtures/runtime_bridge.js"] = ("合规", "§7", "桥夹具,经 test_qa_bridge_contract 执行覆盖", "批5;轮1")
for _f in ("test_real_data_contract.py", "test_update_check.py", "test_retry_phone_policy.py",
           "test_signup_plan.py", "test_session_persistence.py", "test_runtime_bundle.py"):
    O["local/tests/" + _f] = ("已改", "§2", "TestWallClock→WallClockStub import/实例化同步(std-18a/18b/18c,65↔65 守恒,模块测试+289 契约全绿)", "std-18a/18b/18c-rename.patch")
O["local/tests/test_retry_policy.py"] = ("已改", "§7/§2", "docstring <tmp> 口径(std-5)+TestWallClock 改名(std-18b)", "std-5-tests/std-18b-rename.patch")

# 批6 server
S_OK = ("合规", "§1/§2/§3/§4/§5/§6", "批6 扫描:business_now 注入/原子写/指纹化/命名合规", "批6 判据命令")
for f in ("activity_watch.py", "card.py", "common.py", "net_probe.py", "render.py", "run.py", "scan.py",
          "site_target.py", "token_probe.py", "trigger_server.py", "selfcheck.py", "regress.py",
          "dev/explore.py", "dev/probe_login.py", "dev/push_card.py"):
    O["server/scripts/" + f] = S_OK
O["server/scripts/fetch.py"] = ("保留", "§6", "latest.md/latest.json 直写无原子替换(V5,P3):撕裂风险低(latest.json 无消费方)", "批6 V5")
O["server/scripts/notify.py"] = ("已改", "§4", ":325/:350 吞异常裁决注释(std-12);token 缓存直写(V4,P3)仍保留涉写盘行为", "std-12-server-comments.patch;批6")
O["server/scripts/query.py"] = ("保留", "§3", ":115 naive now 进 classify(V2):改 business_now 涉行为,需服务器回归,保留", "批6 V2")
O["server/scripts/remind.py"] = ("保留", "§3", ":40 naive now(V3):同上保留", "批6 V3")
O["server/scripts/watchlist_runner.py"] = ("保留", "§3", ":137 naive now 进排班/错过判定(V1):同上保留", "批6 V1")
O["server/scripts/token_report.py"] = ("保留", "§6", ":194 报告直写(V6,P3)", "批6 V6")
O["server/scripts/watchlist.py"] = ("保留", "§3/§4", ":126 F-09 已记;_refresh_card 私有跨模块灰区(J2.4)", "批6;轮1 F-09")
O["server/scripts/grab_card.py"] = ("保留", "§3", ":64/79 F-09 已记;:108 同链", "批6;轮1")
O["server/scripts/login.py"] = ("已改", "§4", ":89 截图吞补裁决注释(std-12)", "std-12-server-comments.patch;批6")
O["server/bot/bot.js"] = ("已改", "§4/§6", ":114 补策略分歧裁决注释(std-13,C9:低价值缓存降级 vs handled_messages 显式抛错);:123 users.json 直写(P3)仍保留", "std-13-server-js-comments.patch;批6 V7/V8")
O["server/bot/handled_messages.js"] = ("合规", "§4/§6", "tmp+rename 原子写、解析失败显式抛:正面样板", "批6")
O["server/bot/test_bot_runtime.js"] = ("保留", "§7", ":30 <tmp> 常量带系统临时目录回退,改涉测试行为(P3)", "批6 V13")
O["server/bot/test_handled_messages.js"] = ("合规", "§7", "批6 合规", "批6")
O["server/deploy/auto_login.py"] = ("已改", "§4", "7 处吞异常裁决注释(std-11,含计划外 :679 文件锁 __exit__);时间口径=运维允许类", "std-11-autologin-comments.patch;批6")
O["server/deploy/grab_signup.py"] = ("保留", "§3/§4", "F-08/09/10/11 已记(涉行为,需真实回包);:746 已补注释(std-12);:721 有注释无限窄", "批6;std-12-server-comments.patch;轮1")
O["server/deploy/server_refresh.js"] = ("已改", "§4/§6", ":87/:90 evaluate 内回退补裁决注释(std-13,tokenWorks 下游核验已实读);atomic_json 全量使用", "std-13-server-js-comments.patch;批6")
O["server/deploy/atomic_json.js"] = ("合规", "§6", "wx+rename 正面样板", "批6")
O["server/deploy/set_credentials.py"] = ("合规", "§6", "os.replace", "批6")
O["server/deploy/sync_token.sh"] = ("已改", "§6", ":28 机器特定 <用户目录> 绝对路径→参数化+command -v 兜底(std-6)", "std-6-server.patch;批6 V9")
O["server/deploy/deploy.sh"] = ("合规", "§6", "占位符模板", "批6")
O["server/deploy/remote_install.sh"] = ("合规", "§5/§6", "env 注入,占位符", "批6;轮1 密钥治理")
O["server/deploy/make_template.sh"] = ("合规", "§5/§6", "占位符模板", "批6")
O["server/deploy/legacy/install_nginx_route.py"] = ("保留", "§6", "直写;legacy/README 明示已停用备查,豁免", "批6 豁免记录")
O["server/deploy/legacy/install_nginx_http_route.py"] = ("保留", "§6", "同上", "批6 豁免记录")
for f in ("campus-autologin.service", "campus-autologin.timer", "campus-login.service", "logrotate/campus"):
    O["server/deploy/" + f] = ("合规", "§5", "轮转/单元配置合规(weekly/rotate 8/5M)", "批6 J5.2")
O["server/tests/test_activity_watch.py"] = ("已改", "§7", ":4 注释 <tmp>→gettempdir 口径(std-6)", "std-6-server.patch;批6 V12")
O["server/tests/test_runtime_safety.py"] = ("已改", "§7", ":8 注释 <tmp>→gettempdir 口径(std-6)", "std-6-server.patch;批6 V12")
O["server/tests/test_grab_signup_retry.py"] = ("合规", "§7", "夹具走 gettempdir(轮1 Fix A)", "批6;轮1")
O["server/tests/test_watchlist_safety.py"] = ("合规", "§7", "同上", "批6;轮1")

# 批7 tools
O["tools/release.py"] = ("合规", "§2/§3/§4/§5/§8", "发布门禁链为正面样板;built_at/created=J3.2d;manifest 非原子但 publish 双核验兜住", "批7 台账")
O["tools/qa_runtime_reliability.py"] = ("已改", "§4/§6", ":310/:2985 清理吞补注释(std-7);外呼零容忍+固定锚点为正面样板", "std-7-tools.patch;批7 P3-3/4")
O["tools/qa_business_clock_worker.py"] = ("已改", "§6", ":14 docstring <tmp>→%TEMP% 口径(std-7)", "std-7-tools.patch;批7 P3-1")
O["tools/split_branches.py"] = ("已改", "§5", "run() 失败输出经 _redact 打码远端 URL 凭证段(std-19,端到端实测 no-secret);:112 时间戳=J3.2d", "std-19-splitbranches-redact.patch;批7 P3-6 闭环")
O["tools/verify_autologin_loop.py"] = ("已改", "§4/§6", ":82-83 宽 except→窄(OSError,subprocess.SubprocessError)+注释(std-7)", "std-7-tools.patch;批7 P3-2")

# 批8 docs/specs/root md
DOC_OK = ("合规", "§8", "批8 扫描:未见版本/旧口径/术语违规", "批8 判据命令")
for f in ("ARCHITECTURE.md", "CONFIG.md", "FEISHU_BOT.md", "GRAB.md", "LOGIN.md", "OPERATIONS.md",
          "PHONE_ACCESS.md", "PRIVACY_POLICY.md", "README.md", "RETRY_POLICY_GUIDE.md",
          "TIMING_AND_DEDUP_ANALYSIS.md", "UI_SPEC.md", "USER_AGREEMENT.md"):
    O["docs/" + f] = DOC_OK
O["docs/ARCHITECTURE.md"] = ("已改", "§8", ":177 Api 公开方法数 49→54(awk 实测复核,std-8c)", "std-8c-docs.patch;批8 #25")
O["docs/UI_SPEC.md"] = ("已改", "§8", ":352 版本基线+六步×3+§9 七条旧口径对齐实现(std-8a/8b);:122 直发登记待 r5(C8)", "std-8a/8b-docs.patch;批8")
O["docs/USER_AGREEMENT.md"] = ("保留", "§8", "入口路径+直发清理=r5 升版项(C8/B9,用户已拍板待排期)", "批8 #18/#19")
O["docs/PRIVACY_POLICY.md"] = ("保留", "§8", ":11 入口路径同 C8", "批8 #18")
O["docs/GRAB.md"] = ("已改", "§8", "「抢报名」×4 对齐词表(std-17,含判据驱动 :38/:40/:55)", "std-17-docs-p3.patch;批8 #27")
O["docs/LOGIN.md"] = ("已改", "§8", ":10 「绿色版」→「本机版开发(bat、python)」(std-17)", "std-17-docs-p3.patch;批8 #28")
O["docs/README.md"] = ("已改", "§8", ":13 「抢报名」→「报名」(std-17)", "std-17-docs-p3.patch;批8 #27")
O["docs/RETRY_POLICY_GUIDE.md"] = ("合规", "§8", "100 秒/直发/RISK-001 与实现一致", "批8")
O["docs/TIMING_AND_DEDUP_ANALYSIS.md"] = ("合规", "§8", "时点分析,头部已标日期", "批8")
O["docs/OPERATIONS.md"] = ("合规", "§8", "部署时区前提明示(F-09 依据)", "批8")
O["docs/CONFIG.md"] = ("合规", "§8", "示例占位符合规", "批8;轮1 密钥治理")
O["docs/FEISHU_BOT.md"] = ("合规", "§8", ":17 直发=飞书 webhook 语境,非用户文案", "批8")
O["docs/PHONE_ACCESS.md"] = ("合规", "§8", ":190 历史范围句", "批8")
O["README.md"] = ("已改", "§8", ":77/:256 版本口径+ :79 六步措辞对齐 VERSION(std-8a,F-29 闭环)", "std-8a-docs.patch;批8 P1-1/2")
O["AGENTS.md"] = ("合规", "§8", "本轮判据来源之一,干净", "批8")
O["CLAUDE.md"] = ("合规", "§8", "干净", "批8")
O["CHANGELOG.md"] = ("已改", "§8", "1.2.0 待发布段补 r4 记录(std-8d);已发布段不追改", "std-8d-docs.patch;批8 #29")
O["design/specs/copywriting.md"] = ("已改", "§8", "五步引导/时钟六态/浮层字段/删登录剩余残留/抢单注记/std 六态(std-8b)", "std-8b-docs.patch;批8 #5-9/24")
O["design/specs/assistance-panels.md"] = ("已改", "§8", "§3 状态表对齐 update.js 实际状态机(std-8b)", "std-8b-docs.patch;批8 #10")
O["design/specs/versioning-and-release.md"] = ("已改", "§8", ":11-12 基线行对齐 v1.1.1 已发布+去硬写(std-8a)", "std-8a-docs.patch;批8 P1-4")
O["design/specs/terms-consent.md"] = ("已改", "§8", ":188/:193 六步→五步(std-8d);直发残留登记待 r5(C8)", "std-8d-docs.patch;批8 #23")
O["design/specs/README.md"] = ("已改", "§8", "版本线/assistance-panels 描述/补 terms-consent 行(std-8c)", "std-8c-docs.patch;批8 #22")
O["design/README.md"] = ("已改", "§8", ":52 版本态+:71 五步状态注记(std-8c)", "std-8c-docs.patch;批8 #20/21")

# 规则化默认(按路径前缀)


def default_row(p):
    if p.startswith("design/prototype/"):
        return ("N/A", "全部", "原型基准物(workbench-2026-11 硬基准),八节判据不适用;轮1 静态扫描留档", "轮1 static_scan")
    if p.startswith("design/archive/"):
        return ("保留", "§8", "归档历史记录,J8.3 不追改;轮1 范围外", "轮1 COVERAGE")
    if p.startswith("design/evidence/"):
        if p.endswith((".png", ".txt")):
            return ("N/A", "全部", "证据资产(图片/文本),判据不适用;脱敏已核", "轮1 密钥治理")
        return ("保留", "§8", "过程记录,J8.3 不追改", "批8;轮1")
    if p.startswith("design/decisions/"):
        return ("保留", "§8", "决策记录,J8.3 不追改(009 六步注记与代码矛盾,留决策流程改状态)", "批8 只登记清单")
    if p.startswith("design/flows/") or p.startswith("design/proposals/"):
        return ("合规", "§8", "批8 抽查未列违规;索引层短文档", "批8")
    if p.startswith("design/brand/"):
        if p.endswith((".png", ".ico", ".svg")):
            return ("N/A", "全部", "品牌图像资产", "批4 同类裁决")
        return ("保留", "全部", "品牌 JS(2 个 152 行),范围外;静态扫描留档", "轮1 COVERAGE")
    if p == "design/check_refs.py":
        return ("保留", "全部", "引用校验工具,范围外;静态扫描留档", "轮1 COVERAGE")
    if p.startswith("design/proposals/"):
        return ("合规", "§8", "批8 抽查未列违规", "批8")
    if p.startswith("contracts/"):
        if p.endswith(".json"):
            return ("N/A", "全部", "契约样例数据(脱敏已核)", "轮1 密钥治理/L4-B3")
        return ("合规", "§5/§8", "契约 README:脱敏说明与样例分工,无版本硬写", "批8 范围外自查;轮1 B3")
    if p.startswith("docs/archive/") or p.startswith("docs/superpowers/"):
        return ("保留", "§8", "归档/带日期设计稿,J8.3 不追改", "批8")
    if p.startswith("local/launchers/") or p.startswith("local/installer/") or p.startswith("local/requirements"):
        return ("N/A", "全部", "启动器/打包资产/依赖清单,判据不适用;密钥治理已核", "轮1")
    if p.startswith("local/ui/") and p.endswith((".png", ".ico")):
        return ("N/A", "全部", "二进制图标资产", "批4 N/A")
    if p.startswith("local/tests/test_"):
        return T_OK
    if p in ("VERSION",):
        return ("合规", "§8", "版本唯一真源", "批8 J8.2")
    if p in ("LICENSE",):
        return ("N/A", "全部", "随包许可证", "轮1")
    if p in (".gitignore", ".gitattributes"):
        return ("合规", "§6", "ignore 覆盖核对通过", "轮1 密钥治理")
    return ("保留", "全部", "未匹配批次规则,人工复核项", "-")


def main():
    files = tracked()
    rows = []
    for p in files:
        if p in O:
            v, sec, why, ev = O[p]
        else:
            v, sec, why, ev = default_row(p)
        rows.append((p, v, sec, why, ev))
    cnt = Counter(r[1] for r in rows)
    L = []
    L.append("# STANDARDIZATION — 全量标准化台账(469 文件对齐 reports/STANDARD.md 八节)")
    L.append("")
    L.append("生成:reports/_tools/std_ledger_gen.py(规则化默认 + 批1-8 扫描裁决覆盖)。判定口径:")
    L.append("**合规**=判据命令 0 命中或裁决通过;**已改**=本轮改动(std-N patch,判据红→绿+反向对照);**保留**=不动的明确理由;**N/A**=判据不适用(资产/数据/样式)。")
    L.append("")
    L.append("## 判定统计")
    L.append("")
    L.append("| 判定 | 文件数 |")
    L.append("|---|---|")
    for k in ("合规", "已改", "保留", "N/A"):
        L.append("| %s | %d |" % (k, cnt.get(k, 0)))
    L.append("")
    L.append("## 修复批次索引(patch series,均未 commit)")
    L.append("")
    L.append("| patch | 批 | 内容 |")
    L.append("|---|---|---|")
    L.append("| std-1-domain.patch | 1 | login_rules.py:91 窄化 except |")
    L.append("| std-2-application.patch | 2 | advanced_component_service _note + 6 处注释 |")
    L.append("| std-3-infrastructure.patch | 3 | lifecycle_store :263/:140 留痕 |")
    L.append("| std-4a-ui.patch | 4a | relogin.js:74 addLog + terms/app 注释 |")
    L.append("| std-4b-ui.patch | 4b | controllers plan/update 注释 |")
    L.append("| std-5-tests.patch | 5 | 两处 docstring <tmp> 口径 |")
    L.append("| std-6-server.patch | 6 | sync_token.sh 参数化 + server 测试注释 |")
    L.append("| std-7-tools.patch | 7 | tools 三文件(窄化/注释/docstring) |")
    L.append("| std-9a-app.patch | 9a(根级补充) | app.py 13 处吞异常注释 |")
    L.append("| std-9b-grab.patch | 9b(根级补充) | grab/business_clock/signup_transport 11 处注释 |")
    L.append("| std-8a-docs.patch | 8a | README 版本口径(77/256/79) + versioning:11-12 |")
    L.append("| std-8b-docs.patch | 8b | copywriting + assistance-panels + UI_SPEC(:352/六步/§9 旧口径) |")
    L.append("| std-8c-docs.patch | 8c | design/README + specs/README + ARCHITECTURE 54 |")
    L.append("| std-8d-docs.patch | 8d | terms-consent 五步 + CHANGELOG r4 记录 |")
    L.append("| std-10-infra-comments.patch | 10 | process_tree/tray_icon/tunnel_manager 12 处裁决注释 |")
    L.append("| std-11-autologin-comments.patch | 11 | auto_login.py 7 处(含计划外 :679) |")
    L.append("| std-12-server-comments.patch | 12 | grab_signup/login/notify 4 处 |")
    L.append("| std-13-server-js-comments.patch | 13 | server_refresh.js + bot.js:114 策略分歧注释(C9) |")
    L.append("| std-15a-wording.patch | 15a | app.py 3 处措辞修正(质检员文本) |")
    L.append("| std-15b-wording.patch | 15b | business_clock/lifecycle_store/advanced_component_service 措辞 |")
    L.append("| std-16-armedat.patch | 16 | armedAt 死键 5 处删除(3 文件) |")
    L.append("| std-17-docs-p3.patch | 17 | docs 三文件词汇对齐(抢报名/绿色版) |")
    L.append("| std-18a/18b/18c-rename.patch | 18 | TestWallClock→WallClockStub(8 文件 65 处,计数守恒) |")
    L.append("| std-19-splitbranches-redact.patch | 19 | split_branches 失败输出 URL 凭证脱敏 |")
    L.append("")
    L.append("## 逐文件清单(%d 行)" % len(rows))
    L.append("")
    L.append("| 路径 | 判定 | 判据节 | 理由 | 证据 |")
    L.append("|---|---|---|---|---|")
    for p, v, sec, why, ev in rows:
        L.append("| %s | %s | %s | %s | %s |" % (p, v, sec, why.replace("|", "\\|"), ev.replace("|", "\\|")))
    L.append("")
    L.append("## 未改说明汇总")
    L.append("")
    L.append("- **保留(服务器侧行为类)**:V1-V3 naive now、F-08/09/10/11、bot.js :123 users.json 直写、auto_login :679 收口——全部涉行为且无服务器真实回归能力,待排期(DEFERRED/RISK)。注释级部分已在批 10-13 补齐。")
    L.append("- **保留(条款 r5)**:条款入口路径+直发清理=C8/B9 用户已拍板待排期。")
    L.append("- **保留(其余未做)**:fetch/token_report/notify V4 原子写与 bot.js :123 直写(涉服务器行为)、phone_session_store TTL 时钟(意见性)、gui.py 整体(B7 待删)。")
    L.append("- **保留(历史/归档)**:decisions/evidence/archive/superpowers/proposals 按 J8.3 不追改。")
    L.append("- **质检**:33 处吞异常批注经独立质检员全查 0 不符(26 相符/7 措辞修正已落 std-15a/15b);armedAt 清理经契约测试自证(该字段本就在禁用清单)。")
    L.append("- **N/A**:原型基准物、图像资产、样式表、契约样例 JSON、启动器与依赖清单。")
    out = "\n".join(L) + "\n"
    open("reports/STANDARDIZATION.md", "w", encoding="utf-8").write(out)
    print("rows:", len(rows), dict(cnt))


if __name__ == "__main__":
    main()
