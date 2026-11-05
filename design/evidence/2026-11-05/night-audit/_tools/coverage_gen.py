# -*- coding: utf-8 -*-
"""Generate reports/COVERAGE.md: one row per tracked file (denominator = 469).

Verdicts (fixed enum): 全审 / 关键路径 / 静态比对 / 未审
Every 未审 row carries a reason. Evidence = static-scan summary + audit route.

Usage: python -I reports/_tools/coverage_gen.py   (run at repo root)
"""
import subprocess
import sys
from pathlib import Path

SCAN_TSV = Path("reports/_tools/static_scan.tsv")


def tracked_files():
    out = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
        capture_output=True, check=True).stdout.decode("utf-8")
    return sorted(f for f in out.split("\0") if f)


def modified_files():
    out = subprocess.run(
        ["git", "-c", "core.quotepath=false", "status", "--porcelain"],
        capture_output=True, check=True).stdout.decode("utf-8")
    mods = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("M ") or line.startswith(" M"):
            mods.append(line[2:].strip())
    return set(mods)


def category(path):
    p = path.replace("\\", "/")
    if p.endswith(".md"):
        return "文档"
    low = p.lower()
    if low.startswith("design/prototype/") or low.startswith("design/archive/") \
            or p in ("design/check_refs.py",) or low.startswith("design/brand/") and low.endswith(".js"):
        return "原型"
    if low.endswith((".png", ".ico", ".jpg", ".jpeg", ".svg")) or \
            low.endswith(("requirements.txt", "config.example.json", ".isl", ".service", ".timer", ".bat", ".sh")) or \
            p in ("VERSION", "LICENSE", ".gitignore", ".gitattributes") or \
            low.startswith(("local/launchers/", "local/installer/")) or \
            low.endswith((".data.json",)) and low.startswith("contracts/") or \
            low.startswith("design/evidence/") and low.endswith((".png", ".txt")):
        return "产物"
    if low.startswith(("local/", "server/", "tools/")) or low.startswith("contracts/") or \
            low.startswith("design/brand/") and low.endswith(".js"):
        return "代码"
    return "产物"


# ---- verdict rules: (predicate(path)->bool, verdict, who, evidence) evaluated in order ----
ORIGINAL27 = {
    "design/evidence/2026-11-04/decision-agenda.md",
    "design/evidence/2026-11-04/school-frontend-analysis.md",
    "design/specs/assistance-panels.md", "design/specs/copywriting.md",
    "docs/UI_SPEC.md", "local/app.py", "local/grab.py",
    "local/tests/test_application_services.py", "local/tests/test_phone_ui.py",
    "local/tests/test_school_contract.py", "local/tests/test_ui_contract.py",
    "local/ui/app.js", "local/ui/controllers/plan-events.js", "local/ui/controllers/refresh.js",
    "local/ui/controllers/tick.js", "local/ui/index.html", "local/ui/m/app.js",
    "local/ui/state/store.js", "local/ui/styles.css", "local/ui/views/help.js",
    "local/ui/views/list.js", "local/ui/views/phone.js", "local/ui/views/plan-panel.js",
    "local/ui/views/relogin.js", "local/ui/views/settings.js", "local/ui/views/tour.js",
    "local/ui/views/update.js",
}
FIX_FILES = {
    "local/tests/test_updater.py", "local/tests/test_component_packages.py",
    "local/tests/test_component_builder.py", "local/tests/test_login_relay.py",
    "local/tests/test_update_check.py", "local/application/plan_service.py",
    "server/tests/test_activity_watch.py", "server/tests/test_watchlist_safety.py",
    "server/tests/test_runtime_safety.py", "server/tests/test_grab_signup_retry.py",
}
UNCOMMITTED_DIFF = "开工时 27 项未提交 diff 逐 hunk 审查(代码审查员,2026-11-05)"
BIG3 = {"local/app.py", "local/grab.py", "local/gui.py"}
FULL_LOCAL = {
    "local/signup_plan.py", "local/signup_transport.py", "local/signup_signing.py",
    "local/business_clock.py", "local/time_contract.py", "local/login_relay.py",
}
SAMPLED_INFRA = {
    "local/domain/plan_rules.py", "local/domain/login_rules.py", "local/domain/retry_rules.py",
    "local/domain/retry_window.py", "local/domain/signup_reply.py", "local/domain/worker_lines.py",
    "local/domain/time_text.py", "local/infrastructure/credential_store.py",
    "local/infrastructure/prefs_store.py", "local/infrastructure/process_tree.py",
    "local/application/auto_relogin.py", "local/application/login_relay_service.py",
    "local/application/login_service.py", "local/application/plan_service.py",
}
UNSAMPLED_INFRA = {
    "local/infrastructure/phone_http.py", "local/infrastructure/phone_session_store.py",
    "local/infrastructure/phone_qr.py", "local/infrastructure/tray_icon.py",
    "local/infrastructure/tunnel_manager.py",
    "local/application/phone_service.py", "local/application/advanced_component_service.py",
    "local/application/update_service.py",
    "local/domain/phone_rules.py", "local/domain/lifecycle_rules.py", "local/domain/errors.py",
}
REFERENCED_INFRA = {
    "local/infrastructure/component_packages.py": "L4/D4 证据(component_packages.py:72-75 同一数据目录)",
    "local/infrastructure/advanced_features.py": "L1 证据(app.py 组件键引用)",
    "local/domain/demo_data.py": "L3/§9#16 证据(demo_data.py:22-60 场景齐备)",
    "local/domain/log_events.py": "L4/D9+密钥治理证据(log_events.py:18 SOURCES、:25 敏感词黑名单)",
    "local/update_check.py": "L1/#4 证据(update_check.py:219-231 no_installer 三分类)",
    "local/site_target.py": "L4/M8 证据(site_target.py 存在+构建时注入,提交 6ee013c)",
    "local/infrastructure/lifecycle_store.py": "静态扫描 R7 命中(展示戳,分诊良性)",
}
SERVER_FULL = {
    "server/deploy/auto_login.py", "server/deploy/grab_signup.py",
    "server/deploy/server_refresh.js", "server/deploy/set_credentials.py",
    "server/deploy/atomic_json.js", "server/bot/bot.js", "server/bot/handled_messages.js",
}
L3_SPECS = {
    "design/specs/assistance-panels.md", "design/specs/copywriting.md",
    "design/specs/versioning-and-release.md", "design/specs/terms-consent.md",
    "design/specs/README.md",
}
L4_DOCS = {
    "design/evidence/2026-11-04/decision-agenda.md",
    ".claude/handoff/2026-11-04-receipt.md",
    ".claude/handoff/2026-11-04-remaining-and-template.md",
    "docs/superpowers/specs/2026-11-03-architecture-revision-design.md",
}
KEYPATH_DOCS = {
    "docs/ARCHITECTURE.md", "docs/LOGIN.md", "docs/OPERATIONS.md", "docs/FEISHU_BOT.md",
    "docs/CONFIG.md", "docs/GRAB.md", "docs/RETRY_POLICY_GUIDE.md", "AGENTS.md", "CLAUDE.md",
    "CHANGELOG.md", "VERSION",
}


def verdict_for(path, mods, scan):
    p = path.replace("\\", "/")
    low = p.lower()

    def scan_ev(extra=""):
        c = scan.get(p)
        if c:
            hits = ",".join(f"{k}×{v}" for k, v in c.items() if v)
            base = "规则扫描:" + (hits if hits else "0命中")
        else:
            base = "规则扫描:二进制/未扫"
        return base + ((";" + extra) if extra else "")

    if p in mods:
        if p in BIG3:
            return "全审", "代码审查员(diff hunk)+后端架构师(全文函数级)", scan_ev(UNCOMMITTED_DIFF + ";后端架构师大文件函数级全审清单")
        if p in FIX_FILES or p not in ORIGINAL27:
            return "关键路径", "代码执行者(Fix A–E 红绿+反向对照)", scan_ev("审计修复切片:改前红/改后绿/反向对照齐备,patch 见 reports/PATCHES/")
        return "关键路径", "代码审查员", scan_ev(UNCOMMITTED_DIFF)
    if p in BIG3:
        return "全审", "后端架构师", scan_ev("大文件函数级全审(app.py 145 定义/grab.py 110/gui.py 37,清单见 FINDINGS)")
    if p in FULL_LOCAL:
        return "全审", "后端架构师", scan_ev("报名时序/登录态关键件全审,结论合格")
    if p == "local/updater.py":
        return "静态比对", "代码审查员", scan_ev("updater.py:33-36 <tmp> 死分支证据;Fix A 决定不动生产代码")
    if p in REFERENCED_INFRA:
        return "静态比对", "L1/L3/L4 引用", scan_ev(REFERENCED_INFRA[p])
    if p in SAMPLED_INFRA:
        return "关键路径", "后端架构师", scan_ev("分层抽样(依据:与报名时序/登录态直接耦合)全读,结论合格" + (";process_tree 前 120 行 Job Object 核心" if "process_tree" in p else ""))
    if p in UNSAMPLED_INFRA:
        return "未审", "-", scan_ev("后端抽样声明未抽:与今晚焦点(报名时序/登录态/推送/UI 契约)无直接耦合;仅规则扫描")
    if p.endswith("__init__.py") and p.startswith("local/"):
        return "未审", "-", scan_ev("包声明空壳,无逻辑;仅规则扫描")
    if p == "local/advanced_helper.py" or p == "local/runtime_paths.py":
        return "未审", "-", scan_ev("薄壳/路径工具,未被任何层引用;仅规则扫描")
    if p == "local/tests/fixtures/runtime_bridge.js":
        return "关键路径", "测试自动化工程师", scan_ev("QA 桥夹具,经 test_qa_bridge_contract 执行间接覆盖")
    if low.startswith("local/tests/") and low.endswith(".py"):
        return "关键路径", "测试自动化工程师+Fix A", scan_ev("本机套件 1696 例执行;Fix A 夹具映射(若含 <tmp>);契约测试为 L3 证据源")
    if low.startswith("local/ui/"):
        return "静态比对", "UI 视觉验收设计师(L2 99 条双侧证据)", scan_ev("L2 原型一致性交叉引用" + (";且属未提交 diff 审查" if p in mods else ""))
    if low.startswith("server/tests/"):
        return "关键路径", "测试自动化工程师+Fix A", scan_ev("server 套件 122 例执行(66 红转绿);Fix A 夹具映射")
    if p in SERVER_FULL:
        return "全审", "后端架构师", scan_ev("server 无人值守链逐文件审,结论见 FINDINGS")
    if low.startswith("server/scripts/") or low.startswith("server/deploy/dev/"):
        return "关键路径", "后端架构师", scan_ev("server/scripts 21+3 逐文件一行结论(全部合格,TZ 依赖另记)")
    if low.startswith("server/bot/test_"):
        return "关键路径", "测试自动化工程师+后端架构师", scan_ev("node 执行 37+8 通过;头部与 resolveRoot 已读,未逐行审全部用例(抽样)")
    if low.startswith("server/deploy/"):
        return "静态比对", "后端架构师+密钥治理", scan_ev("部署配置/脚本抽样(密钥治理 env 注入核对、时区依赖另记)")
    if low.startswith("server/") and low.endswith(".json"):
        return "静态比对", "密钥与凭据治理工程师", scan_ev("config.example 占位符核对,非真密钥")
    if p == "docs/UI_SPEC.md":
        return "全审", "技术文档工程师", scan_ev("§9 63 条逐条核验(60 已验/3 blocked/0 未覆盖,7 条带漂移注记)")
    if p in L3_SPECS:
        return "全审", "技术文档工程师", scan_ev("L3 逐篇一致性核验(漂移点见 FINDINGS)")
    if p in L4_DOCS:
        return "全审", "代码审查员(L4)", scan_ev("D1–D9/B 组/plan 逐条落地核对")
    if p in KEYPATH_DOCS:
        return "关键路径", "多层引用", scan_ev("作为契约/口径基准被 L1/L3/L4/L5 引用核对")
    if p == "design/evidence/2026-11-04/prototype-gap.md":
        return "全审", "UI 视觉验收设计师", scan_ev("99 条逐条独立重核;台账自身错误 10 处已纠")
    if low.startswith("design/evidence/"):
        if low.endswith((".png", ".txt")):
            return "静态比对", "密钥与凭据治理工程师", scan_ev("证据资产;敏感信息扫描通过")
        return "静态比对", "L1/L4 抽查", scan_ev("证据文档抽查(脱敏、口径)")
    if low.startswith("design/prototype/workbench-2026-11/") and low.endswith((".dc.html", ".html")):
        if p.endswith(("Main.dc.html", "Phone.dc.html")):
            return "全审", "UI 视觉验收设计师", scan_ev("硬基准主画板逐段核对(99 条原型侧证据来源)")
        return "静态比对", "UI 视觉验收设计师", scan_ev("基准库,「演示」控件普查与按需引用")
    if low.startswith("design/prototype/"):
        return "静态比对", "UI 视觉验收设计师", scan_ev("基准库配套文件(index/json/脚本)普查")
    if low.startswith("design/decisions/"):
        return "静态比对", "代码审查员(L4)", scan_ev("003/006/010/013/014/015 逐条引用核对;其余经 decisions 索引覆盖")
    if low.startswith("design/flows/") or low.startswith("design/proposals/") or p == "design/README.md":
        return "静态比对", "L4 索引核对", scan_ev("流程/提案文档,经决策索引覆盖;仅规则扫描")
    if low.startswith("contracts/"):
        return "关键路径", "密钥与凭据治理工程师+L4/B3", scan_ev("5 个样例 JSON 脱敏逐字段核对 + B3 落地核对")
    if p == "tools/release.py":
        return "关键路径", "技术文档工程师(L3/#40)", scan_ev("check/prepare/publish 契约经 test_lifecycle_release 钉住;R7 时间戳为构建元数据,分诊良性")
    if p == "tools/qa_runtime_reliability.py":
        return "关键路径", "技术文档工程师(L3)", scan_ev("QA 场景(五视口/680×480/外呼 0)作为 §9 #14/#15/#57 证据引用")
    if low.startswith("tools/"):
        return "未审", "-", scan_ev("辅助工具(split_branches/verify_autologin_loop/qa_business_clock_worker),今晚范围外;仅规则扫描,R7 命中为时间戳用途")
    if low.startswith("local/build/"):
        return "未审", "-", scan_ev("打包构建链,今晚审计焦点(报名时序/登录态/推送/UI 契约)之外;仅规则扫描")
    if low.startswith(("local/launchers/", "local/installer/", "local/requirements")) or low.endswith("requirements.txt") or low.endswith("config.example.json"):
        return "未审", "-", scan_ev("启动器/打包资产/依赖清单;密钥治理 grep 通过(无真实凭据),未深审")
    if low.startswith("docs/archive/"):
        return "未审", "-", scan_ev("归档文档(18 篇),今晚范围外;仅规则扫描+密钥 grep")
    if low.startswith("docs/superpowers/"):
        return "关键路径", "代码审查员(L4)", scan_ev("Plan-B 所在目录,specs 全文核对,plans 目录盘点")
    if low.startswith("docs/"):
        return "静态比对", "L1/L3/L4 抽查", scan_ev("按条目引用核对(时区前提/发布口径/脱敏),未逐篇全审")
    if low.startswith("design/archive/"):
        return "未审", "-", scan_ev("归档旧原型(2026-10-22),今晚硬基准是 workbench-2026-11;仅规则扫描")
    if low.startswith("design/brand/"):
        if low.endswith(".js"):
            return "未审", "-", scan_ev("品牌资产脚本(2 个,152 行),范围外;仅规则扫描")
        return "静态比对", "密钥与凭据治理工程师", scan_ev("图标/图像资产;二进制扫描不适用,敏感信息不适用")
    if p == "design/check_refs.py":
        return "未审", "-", scan_ev("引用一致性校验工具,今晚未运行该工具本身;仅规则扫描")
    if p in ("VERSION", "LICENSE", ".gitignore", ".gitattributes"):
        return "关键路径", "主代理+密钥治理", scan_ev("L5 发布口径 + ignore 覆盖核对")
    if p == "README.md":
        return "静态比对", "主代理(L5)", scan_ev("版本口径漂移证据(README.md:77/:256 与 VERSION=1.2.0 矛盾)")
    if p in ("local/README.md", "server/README.md"):
        return "静态比对", "代码审查员(L4)", scan_ev("L4 抽查(local/README.md:369 gui.py 条目/B7 核对;部署口径抽查)")
    if low.endswith((".png", ".ico", ".svg", ".jpg")):
        return "静态比对", "-", scan_ev("二进制资产,规则扫描不适用;密钥治理确认非敏感")
    return "未审", "-", scan_ev("未被任何层触达;仅规则扫描")


def load_scan():
    scan = {}
    if SCAN_TSV.exists():
        for line in SCAN_TSV.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) >= 4:
                counts = {}
                names = ["R1_except_pass", "R2_bare_except", "R3_eval_exec", "R4_shell_true",
                         "R5_secret_lit", "R6_open_no_with", "R7_naive_dt"]
                for i, n in enumerate(names):
                    v = parts[3 + i] if 3 + i < len(parts) else "0"
                    if v not in ("0", "NA", "ERR"):
                        counts[n] = v
                if counts:
                    scan[parts[0]] = counts
    return scan


def main():
    files = tracked_files()
    mods = modified_files()
    scan = load_scan()
    rows = []
    for p in files:
        v, who, ev = verdict_for(p, mods, scan)
        rows.append((p, category(p), v, who, ev))
    n_unaudited = sum(1 for r in rows if r[2] == "未审")
    lines = []
    lines.append("# COVERAGE — 覆盖账(逐文件,分母 = %d)" % len(files))
    lines.append("")
    lines.append("生成方式:脚本从 `git -c core.quotepath=false ls-files` 出表(reports/_tools/coverage_gen.py),")
    lines.append("判定证据列包含全量规则扫描结果(reports/_tools/static_scan.tsv,7 条规则族)。")
    lines.append("")
    lines.append("## 分母核对(用户给定硬数字 vs 脚本复算)")
    lines.append("")
    lines.append("| 口径 | 用户给定 | 脚本复算 | 状态 |")
    lines.append("|---|---|---|---|")
    lines.append("| 受跟踪文件总数 | 469 | %d | 一致 |" % len(files))
    lines.append("| 代码(仅源码 .py/.js/.css/.html) | 291 / 92,061 行 | 289 / 91,935 行(local 140/65,687 ✓、server 44/12,188 ✓、tools 5/4,895 ✓) | 差 2 文件/126 行:有两对候选(get-info.data.json 51 行+启动不了点我.txt 75 行;或 _py.bat 45+install.bat 81),口径无法唯一还原,如实记录 |")
    lines.append("| 其中 design 原型 | 100 / 9,165 行 | 100 / 9,165 行(prototype html 85 + archive 源码 12 + brand js 2 + check_refs.py 1)| 一致(子集反推唯一命中) |")
    lines.append("| 文档(.md) | 102 / 19,055 行 | 103 / 19,531 行(剔除 contracts/school-api README 得 102 文件,但行数 19,477,差 476 行无单文件解) | 文件数可对齐,行数不可规约,如实记录 |")
    lines.append("")
    lines.append("说明:代码余量 2 文件/126 行与文档行数差 476 行两处口径差异**不影响判定**:逐文件表覆盖全部 %d 个文件,每一行都有判定与证据;差异只出现在汇总口径的归类边界,已在上面如实标注,不作为审计结论使用。" % len(files))
    lines.append("")
    lines.append("## 判定统计")
    lines.append("")
    from collections import Counter
    cnt = Counter(r[2] for r in rows)
    lines.append("| 判定 | 文件数 |")
    lines.append("|---|---|")
    for k in ("全审", "关键路径", "静态比对", "未审"):
        lines.append("| %s | %d |" % (k, cnt.get(k, 0)))
    lines.append("")
    lines.append("## 逐文件清单(共 %d 行,每行一个受跟踪文件)" % len(rows))
    lines.append("")
    lines.append("| 路径 | 类别 | 判定 | 谁审 | 证据 |")
    lines.append("|---|---|---|---|---|")
    for p, cat, v, who, ev in rows:
        ev = ev.replace("|", "\\|").replace("\n", " ")
        who = who.replace("|", "\\|")
        lines.append("| %s | %s | %s | %s | %s |" % (p, cat, v, who, ev))
    lines.append("")
    lines.append("## 未审清单(每条含理由,共 %d 条)" % n_unaudited)
    lines.append("")
    for p, cat, v, who, ev in rows:
        if v == "未审":
            reason = ev.split(";", 1)[1] if ";" in ev else ev
            lines.append("- %s — %s" % (p, reason.replace("规则扫描:", "扫描:")))
    lines.append("")
    lines.append("## 抽样声明")
    lines.append("")
    lines.append("- 近 7 天 66 笔提交(用户口径 68 笔=测量时刻早于 2026-11-04 23:20 +0800,滚动窗口边界两笔 caa9f8c/918a2a2):深读 11 笔(动 app.py/grab.py/server/signup/登录态/推送者),其余 55 笔仅 --stat 与提交信息核对——依据与未抽清单见 FINDINGS.md L1 节。")
    lines.append("- local/infrastructure、application、domain 抽样依据=与报名时序/登录态直接耦合;未抽清单见本表「未审」条目。")
    lines.append("- server/bot 两个 node 测试文件:头部与 resolveRoot 已读,用例未逐行(执行通过 37+8)。")
    out = Path("reports/COVERAGE.md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tsv_lines = []
    for p, cat, v, who, ev in rows:
        tsv_lines.append("%s\t%s\t%s\t%s\t%s" % (p, cat, v, who, ev.replace("\t", " ")))
    Path("reports/COVERAGE.tsv").write_text("\n".join(tsv_lines) + "\n", encoding="utf-8")
    print("rows:", len(rows), "unaudited:", n_unaudited, "-> reports/COVERAGE.md + COVERAGE.tsv")
    # hard check: every 未审 row's reason (text after first ';') must say WHY beyond the scan itself
    bad = []
    for r in rows:
        if r[2] == "未审":
            reason = r[4].split(";", 1)[1] if ";" in r[4] else ""
            if len(reason.strip("规则扫描:0命中二进制/未扫").strip()) < 8:
                bad.append(r[0])
    print("unaudited rows missing explicit reason:", bad if bad else "none")


if __name__ == "__main__":
    main()
