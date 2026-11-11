/* 更新通道呈现：状态文案、检查时间、新版本块、进度块与动作区显隐（只读 S.update，不发桥接）。 */
function fmtBytes(n) {
  const bytes = Number(n) || 0;
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + " MB";
  if (bytes >= 1024) return (bytes / 1024).toFixed(0) + " KB";
  return bytes + " B";
}

/* 进度行的体积一律按 MB 一位小数拼「A / B MB（P%）」（UP06，原型 Main.dc.html:1459
 * 「37.9 / 92.4 MB（41%）」），精度与 fmtBytes 的 MB 档一致。 */
function fmtMB(n) {
  return ((Number(n) || 0) / 1048576).toFixed(1);
}

/* 检查时间自己拼 MM-DD HH:mm（UP03）：不靠 toLocaleString——Chromium 的 zh-CN
 * 实际产出斜杠分隔（c3-dialogs-gap UP03 降档记录），原型是连字符。 */
function formatCheckedAt(ms) {
  const d = new Date(ms);
  const p2 = (n) => String(n).padStart(2, "0");
  return p2(d.getMonth() + 1) + "-" + p2(d.getDate()) + " " + p2(d.getHours()) + ":" + p2(d.getMinutes());
}

/* 哈希校验失败专句（UP08，原型 Main.dc.html:1123/1456）：后端 error_code 是
 * hash_mismatch（local/updater.py:112），经 application/update_service.run_download
 * 的 failed 回包随 result.error_code 下发；其余 error_code 照旧显示后端 result.text。 */
const UPDATE_HASH_MISMATCH_TEXT = "下载内容的哈希校验没通过，已放弃并删掉临时文件。旧版本和你的数据都没动。";

function updateErrorText(result) {
  if (String(result.error_code || "") === "hash_mismatch") return UPDATE_HASH_MISMATCH_TEXT;
  return String(result.text || "");
}

/* 更新七态（检查/可用/确认/下载/校验/安装/失败）+ 无安装器退回发布页：
   每个状态只留该状态唯一可做的动作，检查从不自动下载。 */
function paintUpdate() {
  const box = $("#update-status");
  const button = $("#btn-update-check");
  const state = S.update.state;
  const result = S.update.result || {};
  box.dataset.state = state;
  const inFlight = ["checking", "downloading", "downloading_delta", "downloading_full",
    "verifying", "applying", "launching"].indexOf(state) >= 0;
  button.disabled = inFlight;
  /* 文案照原型 Main.dc.html:1426-1442；版本号仍来自后端，不写死。 */
  const copy = { idle: "只有点“检查更新”时才联网，下载前还会再确认。", checking: "正在检查…", current: "已是最新正式版。",
    available: "发现新版本 " + (result.latest_version || "") + "。",
    no_installer: "发现新版本 " + (result.latest_version || "") + "，但没有可校验的安装包，只能到发布页手动下载。",
    preview: "当前是预览版本，最新正式版是 " + (result.latest_version || "") + "，不建议换回旧版本。",
    unavailable: "还没有正式发布的版本。",
    confirm: "发现新版本 " + (result.latest_version || "") + "。",
    downloading: "正在下载安装包…",
    downloading_delta: "正在下载增量包…",
    downloading_full: "正在下载安装包…",
    verifying: "正在比对大小和 SHA-256…",
    applying: "正在校验并准备更新目录…",
    ready_to_install: "安装包已通过大小和 SHA-256 校验。",
    ready_to_restart: "更新目录已准备好，关闭程序后完成切换。",
    launching: "正在启动安装程序…" };
  /* launching 与 no_installer 的具体文案由后端按真实原因下发（app.py 启动收口 /
     update_check.py 三类安装器缺失），固定文案只是后端没带 text 时的兜底；
     原型 Main.dc.html:1426-1442 的状态表保留不删。失败细节移入下方错误框（UP08）。 */
  box.textContent = state === "error" ? "暂时无法检查更新。"
    : state === "failed" ? "更新没有完成。"
    : ["launching", "no_installer", "applying", "ready_to_restart"].indexOf(state) >= 0
      ? (result.text || copy[state])
    : state === "downloading_full" && result.payload_kind === "installer_fallback"
      ? (result.text || copy[state])
    : copy[state] || copy.idle;
  /* 手动检查的结论带发生时间，避免把很久以前的结果误当成实时状态（UP03 连字符格式）。 */
  const checked = $("#update-checked-at");
  const at = result && Date.parse(result.checked_at);
  checked.hidden = state === "checking" || !Number.isFinite(at);
  checked.textContent = checked.hidden ? "" : "检查时间 " + formatCheckedAt(at);
  /* 错误框（UP08，原型 Main.dc.html:1456 ph-err）：红标题只在状态行，细节单独成块。 */
  const errBox = $("#update-error-box");
  const errText = (state === "error" || state === "failed") ? updateErrorText(result) : "";
  errBox.hidden = !errText;
  errBox.textContent = errText;
  const installer = result.installer && result.installer.url ? result.installer : null;
  const realBytes = installer && Number(installer.bytes) > 0 ? Number(installer.bytes) : 0;
  /* 新版本块（UP04，原型 Main.dc.html:775 up-v）：大版本数字＋体积说明；
   * 后端没带 bytes 时降级为只显示版本数字，不显示体积句。 */
  const versionBox = $("#update-version-box");
  versionBox.hidden = state !== "available";
  if (state === "available") {
    $("#update-version-num").textContent = result.latest_version || "";
    $("#update-version-note").textContent = realBytes > 0
      ? "完整安装包 " + fmtBytes(realBytes) + "，下载后先校验，再由你决定什么时候安⁠装" : "";
  }
  /* 确认问句（UP04，原型 Main.dc.html:776）：X=新版本号、Y=体积；
   * 后端没带体积时去掉括号段，问句其余部分不变。 */
  const confirmBox = $("#update-confirm-box");
  confirmBox.hidden = state !== "confirm";
  if (state === "confirm") {
    const size = realBytes > 0 ? "（" + fmtBytes(realBytes) + "）" : "";
    $("#update-confirm-question").textContent = "下载 " + (result.latest_version || "") + " 安装包" + size
      + "？只写临时目录，不动现在的程序和你的数据。校验通过后，什么时候安装由你决定。";
  }
  /* 进度块（UP06，原型 Main.dc.html:778-779/1459）：左「已下载」右「A / B MB（P%）」，
   * 校验中左句换「下载完成，正在校验」、右侧数字让位；百分比与 aria-valuenow 都来自真实回推。 */
  const progressBox = $("#update-progress-box");
  const loading = ["downloading", "downloading_delta", "downloading_full", "verifying"].indexOf(state) >= 0;
  progressBox.hidden = !loading;
  if (loading) {
    const done = Number(result.downloaded) || 0;
    const total = Number(result.total_bytes) || 0;
    const pct = total > 0 ? Math.floor(done / total * 100) : 0;
    $("#update-progress-label").textContent = state === "verifying" ? "下载完成，正在校验"
      : state === "downloading_delta" ? "已下载增量包" : "已下载";
    $("#update-progress-num").textContent = state === "verifying" ? ""
      : fmtMB(done) + " / " + fmtMB(total) + " MB（" + pct + "%）";
    $("#update-progress-bar").setAttribute("aria-valuenow", String(pct));
    const fill = $("#update-progress-fill");
    if (fill && fill.style) fill.style.width = pct + "%";
  }
  /* 下载中说明照原型 Main.dc.html:779：下载不影响正在跑的报名计划（下载/校验两态都显示）。 */
  const downloadNote = $("#update-download-note");
  if (downloadNote) downloadNote.hidden = !loading;
  /* 就绪块（UP11/UP12，原型 Main.dc.html:781 upbox）：黄警示独立成块＋安装向导句；
   * busy 时黄警示出现，按钮改「仍然启动安装程序」（下方显隐矩阵）。 */
  const readyBox = $("#update-ready-box");
  const ready = state === "ready_to_install" || state === "ready_to_restart";
  readyBox.hidden = !ready;
  $("#update-plan-warn").hidden = !(ready && S.busy);
  const install = $("#btn-update-install");
  const confirm = $("#btn-update-confirm");
  const launch = $("#btn-update-launch");
  const cancel = $("#btn-update-cancel");
  /* 每个状态只露一枚主动作钮（UP01，原型 Main.dc.html:1446-1451）：
   * available→下载并安装；confirm→确认下载＋取消（中间态两枚都要）；downloading→取消下载；
   * verifying→校验中…（disabled）；ready→（仍然）启动安装程序；launching→启动中…/关闭本工具…；
   * failed→重新下载（哈希失败或普通失败都这名字）；error→重试检查（原型 :1448）；其余→检查更新。 */
  const hasInstaller = !!installer;
  const showInstall = (state === "available" || state === "failed") && hasInstaller;
  const showConfirm = state === "confirm";
  const showLaunch = ready;
  const showCancel = showConfirm || ["downloading", "downloading_delta", "downloading_full",
    "verifying"].indexOf(state) >= 0;
  const showClose = state === "launching";
  install.hidden = !showInstall;
  install.textContent = state === "failed" ? "重新下载" : "下载并安装";
  confirm.hidden = !showConfirm;
  confirm.textContent = "确认下载";
  launch.hidden = !showLaunch;
  launch.textContent = state === "ready_to_restart"
    ? (S.busy ? "仍然重启并切换版本" : "重启并切换版本")
    : (S.busy ? "仍然启动安装程序" : "启动安装程序");
  cancel.hidden = !showCancel;
  cancel.textContent = state === "confirm" ? "取消" : state === "verifying" ? "校验中…" : "取消下载";
  cancel.disabled = state === "verifying";
  /* 启动分两段（UP01/UP10，原型 launching/launched 两槽）：后端先推「正在启动安装程序…」
   * （版本目录切换是「正在准备重启…」），启动成功再推「安装程序已启动。…」或
   * 「更新启动器已启动，…」（app.py update_launch 的两次 publish），前缀变了才把
   * 「启动中…」换成「关闭本工具…」；两个前缀都是后端文案的稳定契约
   * （test_launching_shows_backend_text、test_launcher_started_text_turns_button_into_close_tool）。 */
  const launched = showClose && /^(安装程序已启动|更新启动器已启动)/.test(String(result.text || ""));
  const close = $("#btn-update-close");
  if (close) {
    close.hidden = !showClose;
    close.textContent = launched ? "关闭本工具…" : "启动中…";
  }
  const pushing = showInstall || showConfirm || showLaunch || showClose;
  $("#update-flow").hidden = !(pushing || showCancel);
  /* 标题行右侧每步只留一个推进动作：流程按钮或「取消下载/校验中…」出现时收起「检查更新」（UP01） */
  button.hidden = pushing || showCancel;
  button.textContent = state === "checking" ? "检查中…" : state === "error" ? "重试检查" : "检查更新";
  /* 状态自己变了（不是用户刚点的那一下）：新出现的推进按钮先停 0.8 秒，防止连点误触 */
  if (S.update.paintedState !== state) {
    S.update.paintedState = state;
    if (pushing) {
      S.update.guardUntil = Date.now() + UPDATE_GUARD_MS;
      clearTimeout(S.update.guardTimer);
      S.update.guardTimer = setTimeout(paintUpdate, UPDATE_GUARD_MS + 20);
    }
  }
  const guarded = Date.now() < (Number(S.update.guardUntil) || 0);
  [install, confirm, launch].forEach((el) => { if (el) el.disabled = guarded; });
  /* 「启动中…」整段禁用（原型 launching 槽 slotOff 恒真），换上「关闭本工具…」才可点 */
  if (close) close.disabled = guarded || !launched;
}

const UPDATE_GUARD_MS = 800;

/* 帮助面板里的更新状态单元格：新结论到达时展开（呈现入口由更新用例与 help 共用）。 */
function revealUpdateStatus() {
  revealHelpStatus($("#update-status").parentElement);
}
