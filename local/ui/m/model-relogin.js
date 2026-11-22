"use strict";

/* 手机页纯规则——重新登录与点阵屏（依赖 model.js 至 model-run.js 先加载）：
 * 补齐重登视图、配对点阵字形与配对状态成员，并把 PhoneModel 挂到 globalThis。 */

Object.assign(PhoneModel, {
  /* ---------------- 重新登录 sheet（计划 20261108-phone-1to1 任务 relogin-sheet；RL01–RL08/G11） ----------------
   * 六态呈现照原型 renderVals 的 rel 段（Phone.dc.html:881-905）与 beginRelogin/relCanSubmit/
   * autoRelogin（Phone:649-680）；纯函数出数据，renderRelogin 只做 DOM。 */

  /* RL02 忙态三句（原型 Phone:886-887）。旧句映射（对账态归并进三句）：
   *   正在校验验证码…            → verify（提交已被收下，等结果）
   *   正在准备验证码…            → prepare（worker 刚拉起，无需下图）／needCode（manual 等图）
   *   等待验证码…                → needCode
   *   提交结果未知，正在对账…    → verify（保持禁用，先对账再放行）
   *   验证码正在提交，请等待结果 → verify（同一张图还有在途提交） */
  RELOGIN_BUSY: {
    needCode: "正在向电脑要验证码…",
    prepare: "正在准备…",
    verify: "正在登录，请等结果",
  },

  /* G11 saveGain（原型 rel.saveGain，Phone:882）：装了识别→失效时电脑自己来；没装→手机输码 */
  relSaveGain(ocrReady) {
    return ocrReady ? "电脑会自己重新登录，不用你动手" : "只要输验证码";
  },

  /* 交接给用户输验证码：依据后端 login_relay 的 live 与 handoff 两字段（两者均为 true 才算）；
   * 后端仅在电脑自动识别认满阈值或识别结果不合规时置 handoff=true，本场结束后清掉。 */
  relHandoff(flow) {
    if (!flow || typeof flow !== "object" || Array.isArray(flow)) return false;
    return flow.live === true && flow.handoff === true;
  },

  /* RL04 needAcct：电脑没保存账号或保存的密码不对（paused）时手机输；
   * handoff 时账号密码由电脑自动填写，字段整块收起（原型 relNeedAcct/relHandoff，Phone:655/667） */
  relNeedAcct(flow, setup) {
    if (PhoneModel.relHandoff(flow)) return false;
    const s = setup || {};
    return !s.saved || !!s.paused;
  },

  /* RL04 lead 四态（原型 Phone:898 逐字）；RL07 relbad 无 lead（红错由 err 承担） */
  relLead(flow, setup) {
    const s = setup || {};
    if (s.paused) return "";
    if (PhoneModel.relHandoff(flow)) {
      return "电脑没认出验证码，换你来输。账号密码由电脑自动填写。";
    }
    const needAcct = !s.saved || !!s.paused;
    if (!needAcct) return "电脑会自动填账号密码，你只要输验证码。";
    return s.ocr_ready ? "电脑上没有保存账号密码，输入账号和密码就行。"
                       : "电脑上没有保存账号密码，账号、密码和验证码都要输。";
  },

  /* relCanSubmit（原型 Phone.dc.html:675-680 同一口径）：主钮什么时候能按——
   * needAcct 要账号密码都填，needCap 要 4 位验证码；stale/在途门禁另见 canSubmitRelogin */
  relCanSubmit(fields) {
    const f = fields || {};
    if (f.needAcct && (!String(f.user || "").trim() || !String(f.pass || ""))) return false;
    if (f.needCap && String(f.code || "").length !== 4) return false;
    return true;
  },

  /* RL07 relbad 固定句（原型 Phone:885/519/666）：保存的密码学校不认、自动登录已暂停 */
  RELBAD_TEXT: "电脑上保存的密码学校不认，自动登录已暂停。请输入新的账号密码；勾选保存会替换旧的。",

  /* B-P2-1（RL05）：失败结论句。safe_error 是服务端白名单里的英文安全码
     （login_relay_service._SAFE_ERRORS：eof/timeout/internal…），直出会变成
     「重新登录结束：bad_password」；其中 bad_password（学校明确说账号或密码不对，
     登录进程就此停手、不重试）按原型映射成整句，其余码保留「前缀+码」通用句 */
  RELOGIN_BAD_PASSWORD_TEXT:
    "学校说账号或密码不对。为了避免账号被锁，没有重试。核对后再登录。",
  reloginFailText(safeError, prefix) {
    const code = String(safeError || "");
    if (code === "bad_password") return PhoneModel.RELOGIN_BAD_PASSWORD_TEXT;
    return String(prefix || "重新登录结束：") + code;
  },

  /* 登录完成成功句：依据打开登录面板时记下的布尔值 firstLogin 与是否忙时切换「登录成功」或「重新登录成功」 */
  loginDoneText(firstLogin, planBusy) {
    if (firstLogin) {
      return planBusy ? "登录成功，报名计划照常继续。" : "登录成功，活动列表已刷新。";
    }
    return planBusy ? "重新登录成功，报名计划照常继续。"
      : "重新登录成功，活动列表已刷新。计划不会自动重新开始，要你重新核对后再点开始。";
  },

  /* RL01–RL08 重登 sheet 的呈现数据（原型 rel 段，Phone.dc.html:881-905）。
   * flow=state.login_relay、setup=state.relogin_setup（拿不到时不猜 needAcct，字段先收着）、
   * local={confirm,starting,submitting,entered,savedChoice,planBusy}。 */
  reloginView(flow, setup, local) {
    const f = (flow && typeof flow === "object") ? flow : {};
    const s = (setup && typeof setup === "object") ? setup : null;
    const o = local || {};
    const B = PhoneModel.RELOGIN_BUSY;
    const view = { spin: "", text: "", err: "", showForm: false, lead: "",
                   needAcct: false, needCap: false, autoCap: false, saveLine: "",
                   main: "", mainKind: "", refresh: false, cancel: false, done: "" };
    const saveGain = PhoneModel.relSaveGain(!!s && !!s.ocr_ready);
    /* G11 保存勾选小字（原型 Phone:342） */
    view.saveLine = "加密保存，只有这台电脑能解开。下次失效时" + saveGain
      + "。不勾的话，只在这次运行中有效。";
    /* needAcct 在所有态都要算：忙态虽然整组收起，字段显隐仍按 setup 走，
       否则 begin 在途的窗口里字段被藏住，提交中的凭据读取会扑空 */
    const state = String(f.state || "idle");
    view.needAcct = s ? PhoneModel.relNeedAcct(f, s) : false;
    const lead = s ? PhoneModel.relLead(f, s) : "";
    /* RL06 确认层（原型 relogin==='confirm'，Phone:889）：begin 之前拦一步 */
    if (o.confirm) {
      view.text = "用电脑上存的账号密码登录一次，验证码由电脑识别。"
        + "这会向学校发送一次账号密码，工具会替你勾选学校登录页上的“我已阅读并同意《隐私协议》”。"
        + (o.planBusy ? "成功后报名计划照常继续。" : "成功后会刷新活动列表，计划不会自动开始。");
      view.main = "自动登录一次";
      view.mainKind = "auto";
      view.cancel = true;
      return view;
    }
    /* RL03 auto 态（原型 relogin==='auto'，Phone:888）：电脑自己认图，手机可收起在后台等；
       终态不算（结论归 RL08/RL05），快照没带 live 时以状态名判断 */
    const terminal = state === "success" || state === "failed" || state === "canceled";
    if (String(f.mode || "") === "auto" && !terminal
        && (!!f.retrying || state === "starting" || state === "waiting_code"
            || state === "verifying")) {
      view.spin = "电脑正在自动登录";
      view.text = "验证码由电脑识别，手机上不用操作。电脑连续认错 3 次，才会转给你输入。";
      view.done = "收起，在后台继续";
      return view;
    }
    /* RL02 忙态：提交在途（含对账）与 verifying 归并为「正在登录，请等结果」 */
    if (o.submitting || state === "verifying") {
      view.spin = B.verify;
      return view;
    }
    if (o.starting || state === "starting") {
      /* manual 等图 / auto 无图（原型 relNeedCap 分支，Phone:886） */
      view.spin = (s && s.ocr_ready) ? B.prepare : B.needCode;
      return view;
    }
    /* RL01 captcha 态（原型 rel.isForm 且有挑战图，Phone:898/900） */
    if (state === "waiting_code" && f.challenge_id) {
      view.showForm = true;
      view.lead = lead;
      view.needCap = true;
      view.main = "提交验证码";
      view.mainKind = "submit";
      view.refresh = true;      // 换一张图：仍是 cancel+begin 两步，后端没有换图接口
      view.cancel = true;
      return view;
    }
    if (state === "waiting_code") {
      view.spin = B.needCode;   // manual 已开跑、图还在路上：不给空输入框
      return view;
    }
    /* RL08 完成态（原型 relogin==='done'，Phone:892-894）：两套文案 + 附言 */
    if (state === "success" && f.live) {
      view.text = PhoneModel.loginDoneText(!!o.firstLogin, o.planBusy)
        + (o.entered ? (o.savedChoice
          ? "账号已加密保存到电脑，下次失效时" + saveGain + "。"
          : "账号只在这次运行中有效，关闭工具后清除。") : "");
      view.done = "完成";
      return view;
    }
    /* RL05：失败结论进红条（safe_error 服务端透传；B-P2-1：bad_password 走原型整句，
       其余码保留通用句）；回表单初态可重试 */
    if ((state === "failed" || state === "canceled") && f.live) {
      view.err = PhoneModel.reloginFailText(String(f.safe_error || state));
    }
    /* 表单初态（RL04 lead 四态 / RL07 relbad 红错盖过原因） */
    view.showForm = true;
    view.lead = lead;
    view.autoCap = view.needAcct && !!s && !!s.ocr_ready;
    view.main = "登录";
    view.mainKind = "begin";
    view.cancel = true;
    if (s && s.paused) view.err = PhoneModel.RELBAD_TEXT;
    return view;
  },

  /* ---------------- 配对点阵屏（PA03；glyphs/ledOf 照抄 Phone.dc.html:377-406，run-wait 的 LED 计划板复用） ----------------
   * 字形表：每个字符 7 行、每行 '0'/'1' 串（空格 2 列、冒号 1 列、其余 5 列）。 */
  glyphs() {
    if (!PhoneModel._glyphs) PhoneModel._glyphs = {
      "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
      "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
      "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
      "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
      "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
      "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
      "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
      "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
      "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
      "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
      "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
      " ": ["00", "00", "00", "00", "00", "00", "00"],
      ":": ["0", "0", "1", "0", "1", "0", "0"],
    };
    return PhoneModel._glyphs;
  },
  /* 原型 ledOf 照抄：按行展开成点阵，字符间插 gap 点；blinkAt 指到哪个字符，
     那个字符的亮点就闪（配对屏用它当光标）。cap/capB/aria 供 LED 计划板复用 */
  ledOf(text, tone, cap, capB, blinkAt) {
    const G = PhoneModel.glyphs();
    let cols = 0;
    const dots = [];
    const chars = Array.from(text);
    chars.forEach((ch, i) => {
      cols += (G[ch] || G[" "])[0].length + (i < chars.length - 1 ? 1 : 0);
    });
    for (let r = 0; r < 7; r += 1) {
      chars.forEach((ch, i) => {
        const g = G[ch] || G[" "];
        for (let c = 0; c < g[0].length; c += 1) {
          dots.push({ cls: g[r][c] === "1" ? (i === blinkAt ? "blink" : "on") : "" });
        }
        if (i < chars.length - 1) dots.push({ cls: "gap" });
      });
    }
    return { cols: cols, dots: dots, tone: tone,
             cap: cap || "", capB: capB || "",
             aria: (cap || "") + " " + (capB || "") + " " + text };
  },
  /* 配对视图状态（PA01/PA03；原型 renderVals 的 pair 段，Phone.dc.html:908-910）：
   * LED 显示 code+"------" 前 6 位、满 3 位插空格；blinkAt 是光标点（满 3 位
   * 要跳过空格位）。锁定时 LED 转 off、tag 转「已锁定」；EX04 配错转 red。 */
  pairView(code, lockLeft, pairErr) {
    const text = String(code || "");
    const locked = (Number(lockLeft) || 0) > 0;
    const shown = (text + "------").slice(0, 6);
    const led = PhoneModel.ledOf(shown.slice(0, 3) + " " + shown.slice(3),
      locked ? "off" : (pairErr ? "red" : "amber"), "", "",
      locked ? -1 : (text.length < 3 ? text.length : text.length + 1));
    return {
      led: led,
      locked: locked,
      tag: locked ? "已锁定" : "输入配对码",
      tagTone: locked ? "red" : "",
      cap: locked ? (Number(lockLeft) || 0) + " 秒后可以再试"
        : (text.length
          ? (text.length < 6 ? "还差 " + (6 - text.length) + " 位" : "输完了，点“配对”")
          : "点上面的点阵屏，输入电脑上的 6 位数"),
      cantSubmit: locked || text.length !== 6,
      hasErr: !!pairErr,
      err: String(pairErr || ""),
    };
  },
  /* EX03：锁定倒计时每秒只做一步呈现递减；0 停住，不把本地计时当权威值 */
  pairTickLeft(left) {
    const n = Math.floor(Number(left) || 0);
    return n > 0 ? n - 1 : 0;
  },
  /* PA04/EX04 配错态错误条：N 来自服务端 remaining_attempts（BE1）。
   * 第 3 次失败（N=0）不拼尾句——服务端已落锁，下一次应答就是锁定态。
   * R-P3-6：句中的「60 秒」与 domain/phone_rules 的 IP_LOCK_S（配错落锁时长）
   * 耦合——改 IP_LOCK_S 必须同步改这句文案。 */
  pairWrongText(remainingAttempts) {
    const n = Number(remainingAttempts) || 0;
    return "配对码不对，请核对后重试。"
      + (n > 0 ? "再错 " + n + " 次要等 60 秒。" : "");
  },
  /* EX03 锁定态错误条：固定句；倒计时在屏下说明里（秒数来自服务端 retry_after_s） */
  pairLockedText() {
    return "尝试次数过多，请稍后再试。换一台设备也一样要等。";
  },
});

/* 纯状态导出：node vm 行为测试直接跑真实函数，不用搜字符串代替断言 */
if (typeof globalThis !== "undefined") globalThis.PhoneModel = PhoneModel;
