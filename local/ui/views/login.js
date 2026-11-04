/* 顶栏登录胶囊、结果条与运行日志呈现。 */
function paintLogin() {
  const pill = $("#pill");
  const detail = $("#status-detail");
  /* 不显示剩余时间（学校不公布有效期，工具不估算，架构方案 4.5）：
   * 已登录时胶囊旁写上次校验时刻，详情卡写「有效多久：学校不公布」。 */
  const ok = S.login.ok;
  let cls = "pill";
  let text = "未登录";
  let sub = "";
  let note = "点右上角「登录」开始使用";
  let state = "none";
  if (S.busy && !S.login.loginPending) {
    cls += " is-busy";
    /* 忙时胶囊只表达登录结论，不拿「正在处理」替换它（计划进度属于报名区域） */
    text = S.login.present === false ? "未登录" : "已登录";
    sub = "";
    note = S.stopping ? "正在停止计划；已报名的场次不受影响"
      : "登录状态保持不变；计划进度见报名区域";
    state = S.login.present === false ? "none" : "ok";
  } else if (S.demo) {
    /* 演示模式必须自己说出来：不能借「登录有效」的外观掩盖没有真实会话（R20） */
    cls += " is-warn";
    text = "演示模式";
    sub = "内存样例";
    note = "不读取登录信息、不访问学校，只演示界面与流程";
    state = "demo";
  } else if (S.autoLogin) {
    /* 电脑正在用保存的账号自动登录（中继进度事件 origin=auto）：只说明在做什么，不出横幅 */
    cls += " is-busy";
    text = "自动登录中…";
    note = "学校说登录失效了，电脑正在用保存的账号自动登录";
    state = "pending";
  } else if (S.login.loginPending) {
    /* 登录窗口仍在等待用户完成；不能把旧的有效/失效结论伪装成成功。 */
    cls += " is-busy";
    text = "登录中…";
    note = "请在弹出的浏览器中完成登录；取消或关闭窗口后会保留原状态";
    state = "pending";
  } else if (S.login.checking || (ok === null && S.login.present === true)) {
    /* 正在真实校验：本机有会话也不提前宣布「已登录」，等学校接口结论 */
    cls += " is-busy";
    text = "检查登录…";
    note = "正在检查登录状态，马上就好";
    state = "checking";
  } else if (S.login.present === false) {
    /* 从没登录过（session.json 缺失/解析不了/没有 token）：引导首次登录，
     * 不算失效。check 失败也是「还没登录」，不是「登录状态坏了」。 */
    cls += " is-none";
    note = "点右上角「登录」，在打开的浏览器中完成登录";
  } else if (S.login.result === "unknown" && ok === false) {
    /* 学校接口没应答/网络异常：不能误报成「重新登录」，会话原样保留 */
    cls += " is-none";
    text = "登录待确认";
    note = "暂时无法确认登录状态；检查网络后点「刷新」，先不用重新登录";
    state = "unknown";
  } else if (ok === false && S.login.present !== false) {
    /* 登录过且确认失败/过期，才叫登录已失效；hours_left=0 单独出现
     * 不代表首次未登录。present 未知（老载荷）时维持保守判失效。 */
    cls += " is-bad";
    text = "登录已失效";
    note = "重新登录后可继续使用";
    state = "bad";
  } else if (ok === true) {
    cls += " is-ok";
    text = "已登录";
    /* 只报事实：上次向学校校验的时刻；在别处登录（比如手机上的学校页面）会让这里失效 */
    sub = lastCheckText() ? lastCheckText() + " 校验" : "";
    note = "学校确认登录有效；有效多久学校不公布，工具不估算";
    state = "ok";
  }
  if (termsLocked() && !S.demo && state !== "pending") {
    /* 没同意条款时登录、登录检查都停用：胶囊明说在等条款，不报旧结论 */
    cls = "pill is-none";
    text = "等同意条款";
    sub = "";
    note = "同意使用条款后才会检查登录";
    state = "terms";
  }
  S.login.view = { state: state, text: text, sub: sub, note: note };
  pill.className = cls;
  pill.dataset.state = state;
  pill.setAttribute("aria-label", text + (sub ? "，" + sub : ""));
  $("#pill-text").textContent = text;
  $("#pill-sub").textContent = sub;
  detail.textContent = note;
  const loginBtnText = $("#btn-login-text");
  /* 只在「确实登录过」的几种状态里叫重新登录；首次使用和未知状态都叫登录 */
  if (loginBtnText) loginBtnText.textContent = state === "bad" || state === "warn" || state === "ok" ? "重新登录" : "登录";
  const loginBtn = $("#btn-login");
  /* 按原型：未登录/失效时转实心更醒目，有效时回到描边 */
  const solid = state === "none" || state === "bad";
  loginBtn.classList.toggle("btn-solid", solid);
  loginBtn.classList.toggle("btn-line", !solid);
  if (typeof paintStatusCards === "function") paintStatusCards();
}

function setBusy(busy) {
  S.busy = !!busy;
  /* 计划开跑先暂停引导（运行状态优先），收尾后从原步骤继续 */
  if (S.busy && S.tour.open && !S.tour.paused) tourPauseNow();
  if (!S.busy && S.tour.paused) tourResumeNow();
  paintLogin();
  updateControls();
}

let resultTimer = null;

function setResult(result) {
  const el = $("#result");
  clearTimeout(resultTimer);
  resultTimer = null;
  if (!result) {
    el.hidden = true;
    el.textContent = "";
    el.className = "result";
    return;
  }
  el.hidden = false;
  const cls = result.ok === true ? "is-ok" : (result.ok === "partial" ? "is-partial"
    : (result.ok === "neutral" ? "is-neutral" : "is-bad"));
  el.className = "result " + cls;
  el.innerHTML = "<strong>" + esc(result.title || "") + "</strong><span>" + esc(result.text || "") + "</span>" +
    (result.action ? "<button class=\"result-action\" type=\"button\" id=\"result-action\">" + esc(result.action.label) + "</button>" : "");
  if (result.action) {
    const btn = el.querySelector("#result-action");
    btn.addEventListener("click", result.action.run);
  }
  /* 登录成功的结论 6 秒后自动收起；其他结论留到用户确认 */
  if (result.autoClose) resultTimer = setTimeout(() => { if (!S.busy) setResult(null); }, Math.max(0, result.autoClose - Date.now()));
}

function addLog(line) {
  const box = $("#log");
  const text = String(line == null ? "" : line);
  /* 同一句话（含 worker 已打印的成功结论）只留一条：coordinator 的重复终态
   * 与 UI 摘要不能给用户两个成功结论（RC-06）。 */
  if (S.recentLogs.indexOf(text) >= 0) return;
  S.recentLogs.push(text);
  if (S.recentLogs.length > 40) S.recentLogs.shift();
  const nowMs = businessNowMs();
  const stamp = nowMs === null ? "待校准" : clockParts(nowMs).time;
  /* worker 已记录事件发生的业务时刻，不能再叠加当前接收时间。 */
  const sourceTime = text.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s/);
  const hasSourceTime = sourceTime && toTs(sourceTime[1]) !== null;
  /* 每行一层小条：按脚本前缀着色（[X] 红 / [!] 橙 / [OK] 绿），原话不改 */
  const row = document.createElement("div");
  row.className = "lg";
  const kind = text.indexOf("[X]") === 0 ? "bad"
    : text.indexOf("[!]") === 0 ? "warn"
    : (text.indexOf("[OK]") === 0 || text.indexOf("▶") === 0) ? "ok" : "";
  if (kind) row.dataset.k = kind;
  row.textContent = hasSourceTime ? text : stamp + "  " + text;
  box.appendChild(row);
  while (box.childElementCount > 500) box.removeChild(box.firstChild);
  box.scrollTop = box.scrollHeight;
  /* 收起时顶栏显示最新一句 */
  const last = $("#log-last");
  if (last && text.trim()) last.textContent = stamp + "  " + text.trim();
  requestAnimationFrame(() => { box.scrollTop = box.scrollHeight; });
}

/* 每轮 check 的唯一时钟入口：结构化载荷整份替换旧状态（R08）。
 * 没有结构化结论（旧载荷/本轮没采样）就明确落 unknown——不能凭失败文本
 * 推断「本机慢 N 秒」，也不能把上一轮的 warn 无限保留。 */
