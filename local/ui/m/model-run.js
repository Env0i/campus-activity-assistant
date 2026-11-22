"use strict";

/* 手机页纯规则——运行、结果、核对与更多面板（依赖 model.js、model-conflict.js、model-list.js 先加载）：
 * 补齐运行等待板、任务卡、确认文案、结果统计、核对批次与登录行成员。 */

Object.assign(PhoneModel, {
  /* ---------------- 运行与等待（计划 20261108-phone-1to1 任务 run-wait；G04 G10 RW01–RW03） ----------------
   * 板、四站进度与任务卡的取值照原型 renderVals 的 pending/running 段（Phone.dc.html:799-827）
   * 与 card()（Phone:842-848）；时刻只用 businessNowS，不读手机墙钟（决策 012）。 */

  /* 未确认 start 的对账窗：与 startPending 同源；超过它还没结果就按
     「还没有查到开始结果」呈现（RW02 的 pendingLong 口径） */
  PENDING_WINDOW_MS: 15000,
  pendingLong(pending, nowMs) {
    if (!pending || pending.done) return false;
    return (Number(nowMs) - Number(pending.at || 0)) >= PhoneModel.PENDING_WINDOW_MS;
  },
  /* RW02 等待板（原型 pending 分支，Phone.dc.html:799-803）：LED --:--:-- off 档，
     cap 与副题按 pendingLong 分两档；板题固定「开始请求已发出」 */
  pendingBoard(pending, nowMs) {
    const long = PhoneModel.pendingLong(pending, nowMs);
    return {
      tag: "核对中", tagTone: "off",
      led: PhoneModel.ledOf("--:--:--", "off",
                            long ? "还没有查到开始结果" : "正在核对开始结果", ""),
      title: "开始请求已发出",
      sub: long ? "电脑可能已经开始，也可能没收到。工具只查询结果，不会重复发送。"
                : "请先不要重复点击。",
    };
  },
  /* 场次的开放时刻（epoch 秒）：计划任务带 sign_start 学校时间文本，按北京时间换算；
     缺失返回 0（倒计时落归零档，不猜时刻） */
  taskOpenOf(task) {
    return PhoneModel.schoolSec(task && task.sign_start) || 0;
  },
  /* 四站进度（原型 rail 段，Phone.dc.html:819-825）：启动＝worker 已拉起（run_started_at），
     第二站＝详情页已开（page_opened_at），via=click（path）的场叫「打开页面」；
     开放提交＝提交中 hot、页开完转 now；核对结果恒空（结果在任务卡上逐场说） */
  taskRail(task, nowS) {
    const t = task || {};
    const passed = (v) => {
      const n = Number(v);
      return Number.isFinite(n) && n > 0
        && nowS !== null && nowS !== undefined && nowS >= n;
    };
    const started = passed(t.run_started_at);
    const prepped = passed(t.page_opened_at);
    return [
      { label: "启动", state: started ? "done" : "" },
      { label: String(t.path || "") === "click" ? "打开页面" : "准备好",
        state: prepped ? "done" : (started ? "now" : "") },
      { label: "开放提交", state: t.status === "submitting" ? "hot" : (prepped ? "now" : "") },
      { label: "核对结果", state: "" },
    ];
  },
  /* G04 运行板（原型 running 分支，Phone.dc.html:804-827）：当前场＝提交中优先，
     其次最早开放的等待场；等待态 tag 等开放/即将开放（gap>5/≤5）、LED 琥珀且 ≤10 秒
     转红（原型 gap>5/≤10 口径）、cap「开放时间」+capB（hms 带明天/后天前缀）；
     提交态 tag 与 LED 都红、cap「本次尝试到」；离线（off）LED 转 dim 档，且 cap 换成
     「状态已过时 / 最后同步 HH:MM:SS」（EX01，原型 Phone:826；lastOkText 是同步成功时
     记下的北京时间，钟不可用时落 --:--:--，不拿手机墙钟冒充）。时钟不可用不给倒计时，
     capB 退回当天时刻，不拿手机墙钟冒充。 */
  runBoard(plan, nowS, off, lastOkText) {
    const tasks = (plan && plan.tasks) || [];
    const active = tasks.filter((t) => t.status === "submitting");
    const wait = tasks.filter((t) => t.status === "waiting")
      .sort((a, b) => PhoneModel.taskOpenOf(a) - PhoneModel.taskOpenOf(b));
    const cur = active[0] || wait[0] || tasks[0];
    if (!cur) return null;
    const clockDown = nowS === null || nowS === undefined;
    const targetText = (epoch) => clockDown
      ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(epoch))
      : PhoneModel.hmsAt(epoch, nowS);
    let tag = ""; let tagTone = ""; let led = null; let sub = "";
    if (cur.status === "submitting") {
      tag = "正在提交"; tagTone = "red";
      const deadline = PhoneModel.taskDeadline(cur);
      led = PhoneModel.ledOf(deadline !== null && !clockDown
        ? PhoneModel.hhmmss(deadline - nowS) : "--:--:--",
        off ? "dim" : "red", "本次尝试到",
        deadline !== null ? targetText(deadline) : "");
      sub = active.length > 1
        ? "正在提交 " + active.length + " 场，每场结果单独显示。"
        : "已提交 " + (Number(cur.attempts) || 0) + " 次，最近：" + String(cur.last_reason || "");
    } else {
      const open = PhoneModel.taskOpenOf(cur);
      const gap = clockDown ? null : open - nowS;
      tag = gap !== null && gap <= 5 ? "即将开放" : "等开放";
      led = PhoneModel.ledOf(gap === null ? "--:--:--" : PhoneModel.hhmmss(gap),
        off ? "dim" : (gap !== null && gap <= 10 ? "red" : "amber"),
        "开放时间", targetText(open));
      const same = wait.filter((t) => PhoneModel.taskOpenOf(t) === open).length;
      sub = same > 1 ? "这一批 " + same + " 场同时提交，到点自动开始。"
                     : "这一场等开放，到点自动开始。";
    }
    /* EX01（原型 Phone:826）：离线时 cap 换「状态已过时 / 最后同步 HH:MM:SS」，
       倒计时与开放时刻照旧给出，只是注明数据可能过时 */
    if (off) {
      led.cap = "状态已过时";
      led.capB = "最后同步 " + (lastOkText || "--:--:--");
    }
    return { tag: tag, tagTone: tagTone, led: led, title: PhoneModel.itemTitle(cur),
             sub: sub, rail: PhoneModel.taskRail(cur, nowS) };
  },
  /* G10 任务卡（原型 card()，Phone.dc.html:842-848）：状态词与 tone 映射照抄
     （waiting 按报名模式分等待开放/准备报名，full/unconfirmed 从 failed 单列）；
     detail 优先级照抄——等待明细 → 页点击尾注 → 提交中明细覆盖；终态场：
     RS02 三句照原型 advance 的 reason（Phone.dc.html:560/564/565，次数取 attempts），
     其余仍用电脑口径 taskText（说法不另起一套）；取消的那场：计划停止给原型整句
     （finishState，Phone:580），手动取消透传后端 reason（signup_plan 给「你取消了这一场」）；
     取消钮只给等待中的场（原型 canCancel=status==='waiting'） */
  taskCard(task, maxAttempts, nowS) {
    const t = task || {};
    const st = String(t.status || "");
    const clockDown = nowS === null || nowS === undefined;
    const targetText = (epoch) => clockDown
      ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(epoch))
      : PhoneModel.hmsAt(epoch, nowS);
    const isPre = String(t.signup_mode || "") !== "instant_signup";
    const failedFull = st === "failed" && String(t.stop_reason || "") === "full";
    const failedAsk = st === "failed" && String(t.stop_reason || "") === "unconfirmed";
    const map = {
      waiting: ["", isPre ? "等待开放" : "准备报名"],
      submitting: ["run", "提交中"],
      success: ["ok", "报名成功"],
      already_signed: ["ok", "报名成功"],
      failed: [failedFull ? "" : (failedAsk ? "ask" : "bad"),
               failedFull ? "名额已满" : (failedAsk ? "待核对" : "报名未成功")],
      canceled: ["", "已取消"],
    };
    const toneAndLabel = map[st] || map.waiting;   // queued 等未知态按等待呈现，不编结论
    const attempts = Number(t.attempts) || 0;
    let detail;
    if (st === "waiting" || st === "queued") {
      const open = PhoneModel.taskOpenOf(t);
      if (!isPre) {
        detail = "已开放，正在准备提交";
      } else {
        const prepped = !clockDown && Number(t.page_opened_at) > 0
          && nowS >= Number(t.page_opened_at);
        detail = prepped ? "已准备好，" + targetText(open) + " 开放时提交"
                         : "等到 " + targetText(open) + " 开放";
      }
    } else if (st === "canceled") {                    // RS02（Phone:580/877）
      const reason = String(t.reason || "");
      detail = reason === "计划已停止" ? "计划已停止，这一场没有提交"
        : (reason || "已取消");
    } else if (st === "success") {                     // RS02 原型句（Phone:564）
      detail = "学校回“操作成功”，结束时向学校核对过：已报名";
    } else if (failedFull) {                           // RS02 原型句（Phone:560）
      detail = "学校说报名人数已满，这一场到此结束，不再提交。不是工具出错。已提交 "
        + attempts + " 次";
    } else if (failedAsk) {                            // RS02 原型句（Phone:565）
      detail = "已提交 " + attempts + " 次，没拿到确定回应；结束时向学校核对也没查到结果。"
        + "去活动页看一眼，或稍后刷新核对。工具不会再自动重发。";
    } else {
      detail = PhoneModel.taskText(t);
    }
    if (String(t.path || "") === "click" && st !== "canceled" && st !== "submitting") {
      detail += "。改用页面点击" + (t.path_reason ? "：" + t.path_reason : "");
    }
    if (st === "submitting") {
      const deadline = PhoneModel.taskDeadline(t);
      detail = "已提交 " + (Number(t.attempts) || 0) + " 次（"
        + (Number(maxAttempts) > 0 ? "上限 " + Number(maxAttempts) + " 次" : "不限次数") + "）"
        + (deadline !== null ? "，重试到 " + targetText(deadline) : "");
    }
    return { name: PhoneModel.itemTitle(t), tone: toneAndLabel[0], label: toneAndLabel[1],
             detail: detail, canCancel: st === "waiting" };
  },
  /* RW03/SH03/SH04 确认文案（原型 isConfirm 三档，Phone.dc.html:874-879）逐字照抄：
     常量放纯函数层供 node 用例直接调；取消一场那句带场名。
     sheets-ops 迁移停止/取消确认时复用同一容器 */
  confirmView(kind, taskName) {
    const copy = {
      cancelstart: {
        title: "取消这次等待？",
        text: "只是不再等这次结果。如果计划其实已经启动，刷新后还要再点“停止计划”。",
        no: "继续等", yes: "取消等待" },
      stop: {
        title: "停止报名计划？",
        text: "工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。",
        no: "继续计划", yes: "停止计划" },
      cancelTask: { title: "取消这一场？", text: "", no: "先不取消", yes: "取消这一场" },
    }[kind];
    if (!copy) return null;
    return Object.assign({}, copy, {
      text: kind === "cancelTask"
        ? "「" + String(taskName || "") + "」还没提交，取消后不会再报名，其他场次继续。"
        : copy.text });
  },

  /* ---------------- 结果页与条款态（计划 20261108-phone-1to1 任务 result-and-terms；RS01 TM01） ----------------
   * 统计与六支板头照原型 renderVals 的 result 段（Phone.dc.html:828-840）；
   * 统计由 state.plan.tasks 的 status/stop_reason 前端聚合（原型 c() 按 status 计数，
   * 这边名额已满/待核对是 failed 的 stop_reason——口径与 taskText 一致），不改后端。 */

  /* 计划是否已结束（RS01）：不忙且每场都到终态。queued/waiting/submitting 都算未结束；
     没有计划或空计划不算（原型 phase==='result' 只在全部终态后由 finishState 进入） */
  planFinished(plan, busy) {
    if (busy) return false;
    const tasks = (plan && plan.tasks) || [];
    if (!tasks.length) return false;
    const TERM = ["success", "already_signed", "failed", "canceled"];
    return tasks.every((t) => TERM.indexOf(String((t && t.status) || "")) >= 0);
  },
  /* RS01 结果页数据（原型 res 段，Phone.dc.html:828-840）：五类统计只显非零、
     tone ok/wait/bad/ask/wait 照原型 res.counts（832）；六支板头照 834-839 逐支；
     stopped 取计划级 status（signup_plan 停止后的终态快照即 stopped）；
     canRetry＝未成功+已取消（原型 833：bad + none > 0） */
  resultView(plan, busy) {
    if (!PhoneModel.planFinished(plan, busy)) return null;
    const tasks = (plan && plan.tasks) || [];
    const statusOf = (t) => String((t && t.status) || "");
    const reasonOf = (t) => String((t && t.stop_reason) || "");
    const ok = tasks.filter((t) => statusOf(t) === "success" || statusOf(t) === "already_signed").length;
    const full = tasks.filter((t) => statusOf(t) === "failed" && reasonOf(t) === "full").length;
    const ask = tasks.filter((t) => statusOf(t) === "failed" && reasonOf(t) === "unconfirmed").length;
    const bad = tasks.filter((t) => statusOf(t) === "failed"
      && reasonOf(t) !== "full" && reasonOf(t) !== "unconfirmed").length;
    const none = tasks.filter((t) => statusOf(t) === "canceled").length;
    const counts = [
      { tone: "ok", n: ok, text: "已报名" },
      { tone: "wait", n: full, text: "名额已满" },
      { tone: "bad", n: bad, text: "未成功" },
      { tone: "ask", n: ask, text: "待核对" },
      { tone: "wait", n: none, text: "已取消" },
    ].filter((x) => x.n > 0);
    const stopped = String((plan && plan.status) || "") === "stopped";
    const head = { text: "", tone: "" };
    let title = ""; let text = ""; let boardCls = "";
    if (stopped) {                                       // Phone:834
      head.text = ask ? "已停止，需确认" : "已停止";
      head.tone = ask ? "" : "off";
      title = "报名计划已停止";
      text = "已提交的场次保留原状态，还没提交的场次已取消。";
      if (ask) boardCls = "st-warn";
    } else if (ok && !bad && !ask && !none && !full) {   // Phone:835
      head.text = "报名成功"; head.tone = "green";
      title = "报名计划完成";
      text = "每场结束时都向学校核对过。";
      boardCls = "st-ok";
    } else if (ok) {                                     // Phone:836
      head.text = "部分完成";
      title = "报名计划部分完成";
      text = ask ? "有 " + ask + " 场需要到活动页核对，结果以学校为准。"
        : (full ? "有 " + full + " 场名额已满，不是工具出错。"
                : "结果以学校活动页为准。");
      boardCls = "st-warn";
    } else if (ask) {                                    // Phone:837
      head.text = "需确认";
      title = "计划已结束，有 " + ask + " 场需确认";
      text = "工具不会自动重发，到学校活动页核对。";
      boardCls = "st-warn";
    } else if (full && !bad) {                           // Phone:838
      head.text = "名额已满";
      title = "这次没报上：名额满了";
      text = "学校的名额在开放后被报满了，不是工具出错。";
      boardCls = "st-warn";
    } else {                                             // Phone:839
      head.text = "未成功"; head.tone = "red";
      title = "报名计划没有成功";
      text = "每场的原因都列在下面。";
      boardCls = "st-bad";
    }
    return { head: head, title: title, text: text, counts: counts,
             canRetry: bad + none > 0, boardCls: boardCls };
  },
  /* TM01 条款板（原型 Phone:798 逐字）：草稿态且电脑没同意条款时整板换成已暂停；
     LED 与倒计时一并停住——同意前没有「下一场」可言 */
  termsBoard() {
    return {
      tag: "已暂停", tagTone: "off",
      led: PhoneModel.ledOf("--:--:--", "off", "电脑上同意条款后才能报名", ""),
      title: "电脑上还没有同意条款",
      sub: "同意前只能看缓存，不能报名，也不能重新登录。",
    };
  },

  /* ---------------- 核对计划与更多 sheet（计划 20261108-phone-1to1 任务 sheets-ops；SH01 SH02 SH05） ----------------
   * 批次/条目照原型 batchMap（Phone.dc.html:767-779），登录行照原型 loginLine（Phone:937）；
   * 纯函数出数据，renderReview/refreshControls 只做 DOM。 */

  /* SH01 核对批次（原型 batchMap 逐支照抄）：已选场按开放状态分批——
   * 已开放（stOf=open）同归「现在」批，其余按开放时刻分批；批次头＝时刻（原型 hms(open)，
   * 这里 epoch 秒经 hmsAt 换算，时钟不可用时退回当天时刻，不给假倒计时）+ 数量注
   * （立即报名 N 场／预报名，同时提交 N 场／预报名 1 场）；条目带移除 aria 与时段。
   * 缺举办时段的场次回退「开放 …」说明（原型数据恒有时段，记 deviation）。 */
  reviewBatches(items, nowS) {
    const map = new Map();
    const keys = [];
    (items || []).slice()
      .sort((a, b) => PhoneModel.openEpochOf(a) - PhoneModel.openEpochOf(b))
      .forEach((item) => {
        const st = PhoneModel.stOf(item, nowS);
        const open = PhoneModel.openEpochOf(item);
        const key = st === "open" ? "now" : String(open);
        if (!map.has(key)) {
          map.set(key, {
            time: st === "open" ? "现在"
              : (nowS !== null && nowS !== undefined
                ? PhoneModel.hmsAt(open, nowS)
                : PhoneModel.hhmmss(PhoneModel.beijingSecOf(open))),
            instant: st === "open", items: [],
          });
          keys.push(key);
        }
        const span = PhoneModel.actSpan(item);
        map.get(key).items.push({
          id: item.id, name: PhoneModel.itemTitle(item),
          act: span ? "活动 " + span : PhoneModel.itemMeta(item),
          aria: "从计划移除 " + PhoneModel.itemTitle(item),
        });
      });
    return keys.map((k) => {
      const b = map.get(k);
      const n = b.items.length;
      b.note = b.instant ? "立即报名 " + n + " 场"
        : (n > 1 ? "预报名，同时提交 " + n + " 场" : "预报名 1 场");
      return b;
    });
  },

  /* SH05 登录行四态（原型 loginLine，Phone.dc.html:937 逐字）：
   * 前半句按 state.login（session_expired / session_present，与 ingest 同一口径），
   * 后半句按 relogin_setup——has=saved 且未暂停（密码不对时自动登录同样开不全，
   * 并入「没保存账号」支，与 relNeedAcct 同口径）；ocrOn=ocr_ready。 */
  loginLine(login, setup, flow) {
    const s = setup || {};
    if (PhoneModel.loginRaw(login) && PhoneModel.loginRecovering(login, flow)) {
      return "电脑正在自动重新登录。";
    }
    const expired = PhoneModel.loginExpired(login);
    const has = !!s.saved && !s.paused;
    const ocrOn = !!s.ocr_ready;
    return (expired ? "电脑上的登录已失效。" : "电脑上的登录有效。")
      + (has ? (ocrOn ? "失效时电脑会自己重新登录。" : "失效时只需在这里输验证码。")
             : (ocrOn ? "电脑上没保存账号，重新登录要输账号和密码。"
                      : "电脑上没保存账号，重新登录要输账号、密码和验证码。"));
  },
});
