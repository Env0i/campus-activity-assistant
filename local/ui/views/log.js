/* 运行日志展开/复制。 */
function setLogOpen(open, silent) {
  S.logOpen = !!open;
  const card = document.querySelector(".log-card");
  if (card) card.dataset.open = String(S.logOpen);
  $("#btn-log-toggle").textContent = S.logOpen ? "收起" : "展开";
  $("#btn-log-toggle").setAttribute("aria-expanded", String(S.logOpen));
  if (!silent) savePrefs({ log_open: S.logOpen });
}

function copyLog() {
  /* 日志正文是逐行小条：复制时按行拼回带换行的纯文本 */
  const lines = Array.from($("#log").children).map((row) => row.textContent);
  const text = lines.join("\n");
  const done = () => addLog("[i] 运行记录已复制");
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, () => addLog("[X] 复制没成功"));
  else {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); done(); } catch (err) { addLog("[X] 复制没成功"); }
    ta.remove();
  }
}

/* ---------------------------------------------------------------- 条款 */
/* 决策 013：条款门禁只拦「学校网络动作」——登录、真实校验、活动列表、报名
 * 计划。帮助、设置、条款本身与离线演示（demo，不碰学校系统）不受限。 */

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
