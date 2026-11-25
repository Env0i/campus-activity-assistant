"""在真实 UI 页注入已登录与已校准北京时间态后捕获 19 张验收截图（K7）。

所有路径均基于仓库相对位置推导，不依赖宿主机绝对路径、外网或真实账号数据。
用法：python design/evidence/2026-11-25/ui-refresh-impl/scripts/capture_evidence.py
"""
from __future__ import annotations

import functools
import http.server
import json
import socketserver
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = Path(__file__).resolve().parents[5]
UI_DIR = REPO_ROOT / "local" / "ui"

# 固定业务时刻：2026-11-06 13:55:00（北京时间 UTC+8），对应 UTC 05:55:00
NOW_EPOCH_S = int(datetime(2026, 11, 6, 5, 55, 0, tzinfo=timezone.utc).timestamp())


def build_activities() -> list[dict]:
    """构造覆盖倒计时琥珀/下一批/同抢/选中/重叠/睡眠错过/已报名/简介五态的脱敏样例。"""
    return [
        {
            "id": "act-open-signed",
            "name": "校园志愿服务领航营（已报名可取消）",
            "type": "志愿公益",
            "sign_start": "2026-11-06 08:00:00",
            "sign_end": "2026-11-06 20:00:00",
            "act_start": "2026-11-07 14:00:00",
            "act_end": "2026-11-07 16:00:00",
            "place": "大学生活动中心报告厅",
            "points": "2",
            "wage": "10",
            "reward_state": "ready",
            "mode": "pre_register",
            "signed": True,
            "cancel_allowed": True,
            "qxbm": 1,
            "cancel_deadline": "2026-11-06 19:30:00",
            "checkin_required": True,
            "checkin_start": "2026-11-07 13:45:00",
            "checkin_end": "2026-11-07 14:15:00",
            "checkout_required": True,
            "checkout_start": "2026-11-07 15:50:00",
            "checkout_end": "2026-11-07 16:15:00",
            "audience_code": "3",
            "audience": "年级：2026；分公司：示例第一分公司、示例第二分公司、示例第三分公司、示例第四分公司、示例第五分公司",
            "description": "面向热心公益服务的同学开展志愿岗前培训与实务交流，现场包含小组演练与服务时长认定说明。",
        },
        {
            "id": "act-soon-1",
            "name": "青年创新创业实训沙龙",
            "type": "创新创业",
            "sign_start": "2026-11-06 14:00:00",
            "sign_end": "2026-11-06 18:00:00",
            "act_start": "2026-11-08 09:00:00",
            "act_end": "2026-11-08 11:30:00",
            "place": "创新工场 203 路演厅",
            "points": "1.5",
            "wage": "20",
            "reward_state": "ready",
            "mode": "pre_register",
            "cancel_allowed": True,
            "signed": False,
            "checkin_required": True,
            "checkin_start": "2026-11-08 08:45:00",
            "checkin_end": "2026-11-08 09:15:00",
            "checkout_required": False,
            "audience_code": "2",
            "audience": "2026 级",
            "description": "邀请往届竞赛获奖团队复盘项目路演、商业计划书撰写要点与答辩节奏控制。",
        },
        {
            "id": "act-soon-2",
            "name": "专升本学长经验分享会",
            "type": "学术讲座",
            "sign_start": "2026-11-06 14:00:00",
            "sign_end": "2026-11-06 18:30:00",
            "act_start": "2026-11-08 10:00:00",
            "act_end": "2026-11-08 12:00:00",
            "place": "图书馆二楼学术报告厅",
            "points": "1",
            "wage": "",
            "reward_state": "ready",
            "mode": "",
            "cancel_allowed": False,
            "signed": False,
            "checkin_required": None,
            "attendance_state": "pending",
            "checkout_required": False,
            "audience_code": "2",
            "audience": "全体专升本学生",
            "description": (
                "第一段：聚焦专升本课程衔接、实验学分认证与时间管理方法，现场提供选课路线示例与常见坑点清单。\n\n"
                "第二段：结合往年学业规划数据与跨专业修读案例，拆解不同专业培养方案的学时安排、二课分获取节奏以及毕业资格复核关键节点。\n\n"
                "第三段：预留四十分钟自由提问与一对一材料核对环节，参会同学请提前十五分钟进场完成签到核验，散场后按指引签退领取证明。"
                "此外还会现场发布本学期后续六场专题辅导预约日历与常见问答手册，方便同学按周规划学分进度，不再临时扎堆抢名额。"
            ),
        },
        {
            "id": "act-later-clash",
            "name": "数字素养与文献检索进阶课",
            "type": "文体活动",
            "sign_start": "2026-11-06 16:30:00",
            "sign_end": "2026-11-06 21:00:00",
            "act_start": "2026-11-07 14:30:00",
            "act_end": "2026-11-07 16:30:00",
            "place": "明德楼 B402",
            "points": "",
            "wage": "30",
            "reward_state": "ready",
            "mode": "instant_signup",
            "cancel_allowed": False,
            "signed": False,
            "checkin_required": True,
            "checkin_start": "2026-11-07 14:20:00",
            "checkin_end": "2026-11-07 14:40:00",
            "checkout_required": False,
            "audience_code": "0",
            "audience": "全校",
            "description": "",
        },
        {
            "id": "act-sleep-missed-known",
            "name": "秋季心理健康主题工作坊",
            "type": "学术讲座",
            "sign_start": "2026-11-06 12:30:00",
            "sign_end": "2026-11-06 19:00:00",
            "act_start": "2026-11-09 15:00:00",
            "act_end": "2026-11-09 17:00:00",
            "place": "博学楼 A108",
            "points": "1",
            "wage": "",
            "reward_state": "ready",
            "mode": "instant_signup",
            "cancel_allowed": True,
            "signed": False,
            "missed_by_sleep": True,
            "description": None,
        },
        {
            "id": "act-sleep-missed-unknown",
            "name": "清晨阳光体育打卡启动仪式",
            "type": "文体活动",
            "sign_start": "",
            "sign_end": "2026-11-06 11:00:00",
            "act_start": "2026-11-10 07:30:00",
            "act_end": "2026-11-10 08:30:00",
            "place": "田径场主席台",
            "points": "1",
            "wage": "",
            "reward_state": "ready",
            "mode": "pre_register",
            "signed": False,
            "missed_by_sleep": True,
            "audience_code": "5",
            "audience": "仅限示例社团在册成员",
            "description": "早锻炼积分打卡首场启动活动。",
        },
    ]


def make_bootstrap(items: list[dict], missing_type: list[str] | None = None) -> dict:
    return {
        "demo": False,
        "version": "2.4.0",
        "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/example-only",
        "terms": {"version": "v1", "accepted_version": "v1", "unknown": False, "declined": False},
        "business_clock": {
            "schema": 1,
            "owner_id": "evidence-capture",
            "generation": 1,
            "state": "ready",
            "epoch_s": NOW_EPOCH_S,
            "tick_s": 0,
            "sampled_tick_s": 0,
            "uncertainty_s": 0.04,
            "source": "ntp",
            "age_s": 2,
            "reason": "已与公共北京时间校准",
        },
        "login": {"present": True, "result": "valid", "ok": True, "checking": False, "hours_left": 9.4},
        "prefs": {
            "welcome_seen": True,
            "tour_version": 3,
            "filter": {
                "q": "", "status": "all", "time": "all", "sort": "open",
                "checkin": "all", "checkout": "all",
                "types": missing_type if missing_type is not None else [],
            },
            "retry_policy": {"retry_for_s": 120, "max_attempts": 0},
        },
        "retry_options": {"default": 120, "choices": [{"value": 120, "label": "2 分钟"}, {"value": 300, "label": "5 分钟"}]},
        "advanced_features": {
            "ocr": {"installed": True, "ready": True, "state": "ready"},
            "phone": {"running": False},
            "auto_login": {"ready": False, "saved_account": False, "ocr_ready": False},
        },
        "activities": items,
    }


def make_desktop_init_script(boot_payload: dict) -> str:
    boot_json = json.dumps(boot_payload, ensure_ascii=False)
    items_json = json.dumps(boot_payload["activities"], ensure_ascii=False)
    clock_json = json.dumps(boot_payload["business_clock"], ensure_ascii=False)
    return f"""
(() => {{
  const boot = {boot_json};
  const items = {items_json};
  const clock = {clock_json};
  window.pywebview = {{
    api: {{
      bootstrap: async () => boot,
      clock_snapshot: async () => clock,
      clock_now: async () => clock,
      check: async (roundId) => {{
        setTimeout(() => window.onBackend && window.onBackend.check({{
          round: roundId, ok: true, valid: true, present: true, result: "valid", hours_left: 9.4,
        }}), 10);
        return {{ ok: true, queued: true }};
      }},
      list_activities: async (roundId) => {{
        setTimeout(() => window.onBackend && window.onBackend.activities({{
          round: roundId, ok: true, items,
        }}), 15);
        return {{ ok: true, queued: true }};
      }},
      save_prefs: async () => ({{ ok: true }}),
      front_ready: async () => ({{ ok: true }}),
      cancel_activity: async (id) => ({{ ok: true, activity_id: id }}),
      check_update: async () => ({{ ok: true, latest: "2.4.0", has_update: false }}),
      probe_ocr: async () => ({{ ok: true, state: "ready" }}),
    }},
  }};
  document.addEventListener("DOMContentLoaded", () => {{
    setTimeout(() => window.dispatchEvent(new Event("pywebviewready")), 20);
  }});
}})();
"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "application/javascript; charset=utf-8",
        ".mjs": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".json": "application/json; charset=utf-8",
    }

    def log_message(self, format: str, *args) -> None:
        return


def start_server() -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = functools.partial(QuietHandler, directory=str(UI_DIR))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port


def assert_no_horizontal_overflow(page, label: str) -> None:
    overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
    assert not overflow, f"{label}: 存在横向溢出"


def assert_l2_single_line(page, label: str) -> None:
    bad = page.evaluate("""() => {
      const items = [];
      document.querySelectorAll('.l2-l > *').forEach((el) => {
        const cs = getComputedStyle(el);
        const lh = parseFloat(cs.lineHeight) || 20;
        if (el.getBoundingClientRect().height > lh * 1.65) items.push("wrap:" + el.textContent.trim());
        if (!el.classList.contains('sign-end') && el.parentElement) {
          const pRect = el.parentElement.getBoundingClientRect();
          const eRect = el.getBoundingClientRect();
          if (eRect.right > pRect.right + 1) items.push("clip:" + el.textContent.trim());
        }
      });
      return items;
    }""")
    assert not bad, f"{label}: 第二层子元素发生折行或被裁剪: {bad}"


def wait_ready_desktop(page, items: list[dict]) -> None:
    page.wait_for_function(
        "() => window.__modulesReady === true && typeof window.onBackend === 'object' "
        "&& typeof S !== 'undefined' && S.login && S.login.ok === true && !S.login.checking "
        "&& typeof clockUiState === 'function' && clockUiState() === 'ready'"
    )
    page.evaluate(f"""() => {{
      window.onBackend.activities({{ ok: true, items: {json.dumps(items, ensure_ascii=False)} }});
      S.selected = new Set(["act-soon-1"]);
      S.sleepWindow = {{ from: {NOW_EPOCH_S - 6000}, to: {NOW_EPOCH_S - 300} }};
      S.plan.tasks = new Map([["t-sleep", {{ activity_id: "act-sleep-missed-known", status: "failed", attempts: 0 }}]]);
      if (typeof paintLogin === "function") paintLogin();
      if (typeof render === "function") render();
    }}""")
    page.wait_for_selector(".row")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old_png in OUT_DIR.glob("*.png"):
        old_png.unlink()

    items = build_activities()
    httpd, port = start_server()
    base_url = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)

            # 1. 桌面主流程与多档视口
            ctx = browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
            page = ctx.new_page()
            page.add_init_script(make_desktop_init_script(make_bootstrap(items)))
            page.goto(f"{base_url}/index.html", wait_until="networkidle")
            wait_ready_desktop(page, items)
            assert_no_horizontal_overflow(page, "TimelineWide")
            page.screenshot(path=str(OUT_DIR / "TimelineWide.png"))

            for name, w, h in (
                ("TimelineCompact.png", 1040, 800),
                ("TimelineMed.png", 900, 800),
                ("TimelineNarrow.png", 680, 800),
                ("TimelineShort.png", 1280, 600),
            ):
                page.set_viewport_size({"width": w, "height": h})
                page.evaluate("() => { if (typeof applyBand === 'function') applyBand(); }")
                page.wait_for_timeout(120)
                if name == "TimelineNarrow.png":
                    list_w = page.evaluate("() => { const el = document.querySelector('#list'); return el ? el.getBoundingClientRect().width : 0; }")
                    # 若 680px 下列表列已超过 430px，则进一步收窄窗口保证列表容器贴近 <=430px 实测第二层不换行
                    if list_w > 430:
                        page.set_viewport_size({"width": 430, "height": 800})
                        page.evaluate("() => { if (typeof applyBand === 'function') applyBand(); }")
                        page.wait_for_timeout(120)
                    assert_l2_single_line(page, name)
                assert_no_horizontal_overflow(page, name)
                page.screenshot(path=str(OUT_DIR / name))

            # 2. 更多筛选 + 保留不在列表中的已选类型
            page.set_viewport_size({"width": 1280, "height": 800})
            page.evaluate("""() => {
              if (typeof applyBand === 'function') applyBand();
              S.filter.types = ["创新创业", "往期保留类别"];
              S.filterOpen = true;
              const pop = document.querySelector('#filter-pop');
              if (pop) pop.hidden = false;
              if (typeof paintMoreFilters === 'function') paintMoreFilters();
              if (typeof render === 'function') render();
            }""")
            page.wait_for_timeout(120)
            page.screenshot(path=str(OUT_DIR / "TimelineFilters.png"))
            page.evaluate("""() => {
              S.filter.types = [];
              S.filterOpen = false;
              const pop = document.querySelector('#filter-pop');
              if (pop) pop.hidden = true;
              if (typeof render === 'function') render();
            }""")

            # 3. 简介浮层 5 态
            for fname, act_id, expand in (
                ("DescNormal.png", "act-open-signed", False),
                ("DescLong.png", "act-soon-2", False),
                ("DescEmpty.png", "act-later-clash", False),
                ("DescFail.png", "act-sleep-missed-known", False),
                ("DescScope.png", "act-sleep-missed-unknown", False),
            ):
                page.evaluate(f"""() => {{
                  const btn = document.querySelector('.desc-btn[data-desc="{act_id}"]');
                  if (btn) btn.click();
                  else if (typeof openDescDialog === 'function') openDescDialog('{act_id}', null);
                }}""")
                if expand:
                    page.evaluate("() => { const b = document.querySelector('#btn-desc-scope-more'); if (b && !b.hidden) b.click(); }")
                page.wait_for_timeout(80)
                page.screenshot(path=str(OUT_DIR / fname))
                page.evaluate("() => { const d = document.querySelector('#dlg-desc'); if (d && d.open) d.close(); }")

            # 4. 设置抽屉两张
            page.evaluate("""() => {
              S.advanced = {
                ocr: { installed: true, ready: true, state: "ready" },
                phone: { running: false },
                auto_login: { ready: false, saved_account: false, ocr_ready: false },
              };
              if (typeof openSettings === 'function') openSettings();
              if (typeof paintAdvanced === 'function') paintAdvanced();
              const body = document.querySelector('#settings .draw-b');
              if (body) body.scrollTop = 0;
            }""")
            page.wait_for_timeout(120)
            page.screenshot(path=str(OUT_DIR / "SettingsLoginTwo.png"))

            page.evaluate("""() => {
              const rows = document.querySelectorAll('#settings .help-tool-row details');
              rows.forEach((d) => { d.open = true; });
              const body = document.querySelector('#settings .draw-b');
              if (body) body.scrollTop = body.scrollHeight;
            }""")
            page.wait_for_timeout(120)
            page.screenshot(path=str(OUT_DIR / "SettingsProgCard.png"))
            page.evaluate("() => { if (typeof closeSettings === 'function') closeSettings(false); }")

            # 5. 列表刷新中 & 刷新失败保留旧列表
            page.evaluate("""() => {
              const list = document.querySelector('#list');
              if (list) list.scrollTop = 0;
              S.listRefreshFail = false;
              S.listState = "loading";
              if (typeof render === 'function') render();
            }""")
            page.wait_for_timeout(100)
            page.screenshot(path=str(OUT_DIR / "ListRefreshing.png"))

            page.evaluate("""() => {
              S.listState = "ready";
              S.listRefreshFail = true;
              S.listError = "连不上学校站点";
              if (typeof render === 'function') render();
            }""")
            page.wait_for_timeout(100)
            page.screenshot(path=str(OUT_DIR / "ListRefreshFail.png"))

            # 6. 横幅三态（通知、可收起、收起后 #pill 提示点）
            page.evaluate(f"""() => {{
              S.listRefreshFail = false;
              S.listState = "ready";
              S.listError = "";
              S.secondOpen = {{ at: {NOW_EPOCH_S - 20} }};
              if (typeof render === 'function') render();
              if (typeof paintBanners === 'function') paintBanners();
            }}""")
            page.wait_for_timeout(80)
            page.screenshot(path=str(OUT_DIR / "BannerNotice.png"))

            page.evaluate("""() => {
              S.secondOpen = null;
              S.login.present = true;
              S.login.result = "expired";
              S.login.ok = false;
              S.login.checking = false;
              if (typeof paintLogin === 'function') paintLogin();
              if (typeof render === 'function') render();
              if (typeof paintLogin === 'function') paintLogin();
            }""")
            page.wait_for_timeout(80)
            page.screenshot(path=str(OUT_DIR / "BannerCollapse.png"))

            page.click('[data-act="banner-collapse"]')
            page.wait_for_timeout(80)
            has_dot = page.evaluate("() => document.querySelector('#pill').classList.contains('collapsed-warn')")
            assert has_dot, "收起可折叠横幅后 #pill 未显示 collapsed-warn"
            page.screenshot(path=str(OUT_DIR / "BannerCollapsedDot.png"))
            ctx.close()

            # 7. 手机页 390x844
            mctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            mctx.add_cookies([{"name": "campus_phone_csrf", "value": "evidence-csrf", "url": base_url}])
            mpage = mctx.new_page()
            mobile_state = {
                "seq": 1,
                "state": {
                    "paired": True,
                    "terms_ok": True,
                    "busy": False,
                    "login": {"present": True, "result": "valid", "ok": True, "checking": False, "hours_left": 9.4},
                    "business_clock": make_bootstrap(items)["business_clock"],
                    "activities": items,
                    "retry_policy": {"retry_for_s": 120, "max_attempts": 0},
                    "retry_options": {"default": 120, "choices": [{"value": 120, "label": "2 分钟"}]},
                },
                "events": [],
            }
            mpage.route("**/api/state*", lambda route: route.fulfill(
                status=200, content_type="application/json",
                body=json.dumps(mobile_state, ensure_ascii=False),
            ))
            mpage.goto(f"{base_url}/m/index.html", wait_until="networkidle")
            mpage.wait_for_selector(".card-4l")
            mpage.evaluate("""() => {
              if (typeof model !== "undefined") {
                model.filter.status = "all";
                if (typeof refreshControls === "function") refreshControls();
                if (typeof renderItems === "function") renderItems();
              }
            }""")
            mpage.wait_for_timeout(180)
            assert_no_horizontal_overflow(mpage, "PhoneTimeline")
            assert_l2_single_line(mpage, "PhoneTimeline")
            mpage.screenshot(path=str(OUT_DIR / "PhoneTimeline.png"))
            mctx.close()
            browser.close()
    finally:
        httpd.shutdown()

    pngs = sorted(p.name for p in OUT_DIR.glob("*.png"))
    print(f"Captured {len(pngs)} PNGs:", pngs)
    assert len(pngs) >= 19, f"Expected >= 19 PNGs, got {len(pngs)}"


if __name__ == "__main__":
    main()
