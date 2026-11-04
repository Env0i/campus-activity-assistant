/* 条款弹窗呈现：版本/状态/底部操作区/全文切换/焦点恢复（只读 S.terms，不发桥接）。 */

function paintTerms() {
  /* 标题里的程序要求版本：状态未知时写「尚未确认」，不给一个看似确定的
   * 版本号让用户以为自己在读某一版（设计稿状态矩阵）。 */
  const version = S.terms.unknown ? "尚未确认" : (S.terms.version || "—");
  const inDialog = $("#dlg-terms-version");
  if (inDialog) inDialog.textContent = version;
  const inHelp = $("#help-terms-version");
  if (inHelp) inHelp.textContent = version;
}

/* 底部操作区按模式收敛：只读只显示关闭；保存中禁三控件并显示「正在保存…」；
 * 超时未确认禁同意与暂不使用、亮出「重新确认状态」，关闭权限恢复。 */
function applyTermsFooter() {
  const dialog = $("#dlg-terms");
  if (!dialog) return;
  const accept = $("#btn-terms-accept");
  const decline = $("#btn-terms-decline");
  const close = $("#btn-terms-close");
  const recheck = $("#btn-terms-recheck");
  const x = dialog.querySelector(".dlg-x");
  const esc = dialog.querySelector(".help-esc");
  const saving = !!S.terms.saving;
  const unconfirmed = !!S.terms.unconfirmed;
  const viewOnly = !!S.terms.viewOnly;
  if (close) close.hidden = !viewOnly;
  if (recheck) {
    recheck.hidden = !unconfirmed;
    if (!unconfirmed) {
      recheck.disabled = false;
      recheck.textContent = "重新确认状态";
    }
  }
  if (decline) {
    decline.hidden = viewOnly;
    decline.disabled = saving || unconfirmed;
  }
  if (accept) {
    accept.hidden = viewOnly;
    /* 方案 A：未勾选「我已阅读以上全部条款」时同意按钮保持禁用。
     * 只有明确读到 checked === false 才算没勾——用例的 DOM 桩里没有这个
     * 复选框（或没有布尔 checked），按旧路径放行，避免桩本身制造门禁。 */
    const agree = $("#chk-terms-agree");
    /* 只读（同版本已同意）时勾选没有意义，整条藏掉；保存中禁点，别让勾选
     * 在请求飞行时改动。 */
    const agreeWrap = $(".terms-agree");
    if (agreeWrap) agreeWrap.hidden = viewOnly;
    if (agree) agree.disabled = saving || unconfirmed;
    const agreed = !agree || agree.checked !== false;
    accept.disabled = viewOnly || saving || unconfirmed || !agreed;
    accept.textContent = saving ? "正在保存…" : "我已阅读并同意";
    accept.title = (viewOnly || saving || unconfirmed || agreed)
      ? "同意当前版本的使用条款与隐私告知，之后才能登录和报名"
      : "先勾选左边的「我已阅读以上全部条款」，才能点同意";
  }
  if (x) x.disabled = saving;
  if (esc) {
    esc.textContent = saving ? "正在保存…"
      : (viewOnly || unconfirmed) ? "Esc 关闭" : "Esc 暂不使用";
  }
}

// 三份文档在同一个全文区里并列，切换只改可见性：正文比对的仍是各自容器。
// 第三份（MIT 许可证）内容不在 HTML 里：首次切到时由控制器经桥懒加载。
// 每处 DOM 都判空：这个函数也会在复位链上跑，节点缺失时不能让开弹窗整条链断掉。
function switchTermsDoc(which) {
  const tabs = [["#tab-terms-agreement", which === "agreement"],
                ["#tab-terms-privacy", which === "privacy"],
                ["#tab-terms-license", which === "license"]];
  for (let i = 0; i < tabs.length; i++) {
    const tab = $(tabs[i][0]);
    if (!tab) continue;
    if (tab.classList && typeof tab.classList.toggle === "function") {
      tab.classList.toggle("is-on", tabs[i][1]);
    }
    if (typeof tab.setAttribute === "function") {
      tab.setAttribute("aria-pressed", tabs[i][1] ? "true" : "false");
    }
  }
  const agreeDoc = $("#doc-terms-agreement");
  const privDoc = $("#doc-terms-privacy");
  const licDoc = $("#doc-terms-license");
  if (agreeDoc) agreeDoc.hidden = which !== "agreement";
  if (privDoc) privDoc.hidden = which !== "privacy";
  if (licDoc) licDoc.hidden = which !== "license";
  paintTermsToc();
}

/* 升版改动摘要（设计文档 9.4，按 r4 正文第 8 节变更记录归纳成 6 条）。
 * 正文文字不改（全文与 docs 逐字一致的契约），「本版新增」用节标题上的 data-new 标出。 */
const TERMS_CHANGES = [
  "报名默认直接调用学校的报名接口提交，不经过学校页面；页面点击只在直接提交不可用时兜底。",
  "报名前会向学校获取运行时密钥，只放在本次运行的内存里，不写磁盘、不写日志。",
  "程序替你登录时，会替你勾选学校登录页上的《隐私协议》。",
  "开抢时会在短时间内多次提交报名；登录失效时能自动登录就自动登录一次后继续。",
  "用本工具登录，会让同一账号在别处的登录失效（包括手机上的学校页面）。",
  "只找到学校登录页的《隐私协议》，不声称合规；只服务本人账号，不代他人报名。",
];
const TERMS_NEW_SECTIONS = {
  agreement: ["1.", "3.", "5.", "8."],
  privacy: ["1.", "3.", "5."],
};

function termsUpdateMode() {
  const t = S.terms || {};
  return !t.unknown && !!t.acceptedVersion && !!t.version && t.acceptedVersion !== t.version;
}

/* 打开条款时：之前同意过旧版，就先列出这一版改了什么，并在正文里标出对应的节 */
function paintTermsUpdate() {
  const box = $("#terms-update");
  const update = termsUpdateMode();
  if (box) {
    box.hidden = !update;
    const from = $("#terms-update-from");
    if (from) from.textContent = (S.terms && S.terms.acceptedVersion) || "—";
    const list = $("#terms-update-list");
    if (list) list.innerHTML = update ? TERMS_CHANGES.map((text) => "<li>" + esc(text) + "</li>").join("") : "";
  }
  Object.keys(TERMS_NEW_SECTIONS).forEach((doc) => {
    const heads = document.querySelectorAll('.terms-doc[data-doc="' + doc + '"] .terms-section > h3') || [];
    Array.from(heads).forEach((head) => {
      if (!head || !head.dataset) return;
      const text = String(head.textContent || "");
      const isNew = update && TERMS_NEW_SECTIONS[doc].some((prefix) => text.indexOf(prefix) === 0);
      if (isNew) head.dataset.new = "1";
      else delete head.dataset.new;
    });
  });
}

/* 完整条款左侧的章节目录：跟着当前页签重画，点一下滚到那一节 */
function paintTermsToc() {
  const toc = $("#terms-toc");
  if (!toc) return;
  const full = $("#dlg-terms-full-text");
  const open = !!full && full.hidden === false;
  const body = $(".terms-body");
  if (body && body.classList) body.classList.toggle("has-toc", open);
  toc.hidden = !open;
  if (!open) { toc.innerHTML = ""; return; }
  const doc = document.querySelector(".terms-doc:not([hidden])");
  const heads = doc ? Array.from(doc.querySelectorAll(".terms-section > h3, .terms-section > h4") || []) : [];
  toc.innerHTML = heads.map((head, i) => '<button type="button" data-toc="' + i + '">'
    + esc(String(head.textContent || "")) + "</button>").join("");
}

/* MIT 页签的就地渲染：只读 S.licenseText，不发桥接（加载走 controllers）。
 * loading/ok/error 三态互斥：pre 只在 ok 显示（textContent 原样塞入，不解析 HTML），
 * 失败亮人话 + 「重新读取」，都不清其他页签。 */
function paintLicenseDoc() {
  const pre = $("#license-pre");
  const status = $("#license-status");
  const retry = $("#btn-license-retry");
  if (!pre || !status || !retry) return;
  const lt = S.licenseText;
  if (!lt || lt.state === "loading") {
    pre.hidden = true;
    status.hidden = false;
    status.textContent = "正在读取随包许可文件…";
    retry.hidden = true;
    return;
  }
  if (lt.state === "ok") {
    pre.textContent = lt.text;
    pre.hidden = false;
    status.hidden = true;
    status.textContent = "";
    retry.hidden = true;
    return;
  }
  pre.hidden = true;
  status.hidden = false;
  status.textContent = lt.text || "没有读到随包许可文件。";
  retry.hidden = false;
}

function toggleTermsFull() {
  const full = $("#dlg-terms-full-text");
  const btn = $("#btn-terms-full");
  if (!full || !btn) return;
  full.hidden = !full.hidden;
  /* 方案 A：文末元信息与全文同显隐——它物理上在 section 之外（全文与 docs
   * 逐字一致的契约不许在容器里加字），所以显隐要跟着这一处一起翻。 */
  const meta = $("#terms-doc-meta");
  if (meta) meta.hidden = full.hidden;
  /* 要点与全文是同一阅读区的两种视图，不是叠加：进全文时收起要点，
   * 否则读者要先滚过整段要点才看到正文与文末版本。 */
  const summary = $("#dlg-terms-summary");
  if (summary) summary.hidden = !full.hidden;
  /* 要点⇄全文在同一阅读区切换：按钮文案、aria-expanded、工具行标题三处
   * 同步；阅读区滚回顶部，焦点留在触发按钮上（切换不抢焦点）。 */
  btn.textContent = full.hidden ? "查看完整条款" : "返回条款要点";
  btn.setAttribute("aria-expanded", full.hidden ? "false" : "true");
  const title = $("#dlg-terms-view-title");
  if (title) title.textContent = full.hidden ? "条款要点" : "完整条款";
  const body = $(".terms-body");
  if (body) body.scrollTop = 0;
  paintTermsToc();
}

/* 条款弹窗里的局部反馈：保存失败只在这里说下一步，不刷大屏 */
function termsStatus(text, tone) {
  const box = $("#dlg-terms-status");
  if (!box) return;
  if (!text) {
    box.hidden = true;
    box.textContent = "";
    return;
  }
  box.hidden = false;
  box.dataset.tone = tone || "warn";
  box.textContent = text;
  /* 反馈与阅读区同在唯一滚动区内：失败/未知/重新确认等非空消息置顶立即可见；
   * 只归零阅读区自身 scrollTop，不碰焦点、不滚整页，清空分支的提前 return 不受影响。 */
  const body = $(".terms-body");
  if (body) body.scrollTop = 0;
}

/* 只读查看（已同意同版）的状态行文案（纯函数，用例直接断言字符串）：
 * 好消息一行说完（用户拍板的合并精简，20261031）——哪两份文档（书名号
 * 仍是 doc-link 蓝链，委托点击开全文）、哪个版本（<b>）、何时同意（当年内
 * 省略年份，consentTimeText）。未同意首跑与版本不一致分支不走这里。 */
function termsViewOnlyLineHtml(version, acceptedAt) {
  const when = acceptedAt
    ? "（" + esc(consentTimeText(acceptedAt)) + " 同意）"
    : "（同意时间未记录）";
  return "已同意" +
    '<button type="button" class="doc-link" data-doc="agreement">《用户协议》</button>与' +
    '<button type="button" class="doc-link" data-doc="privacy">《隐私政策》</button>' +
    " <b>" + esc(version || "版本未知") + "</b>" + when +
    "；更新后会再次展示并要求重新同意。";
}

/* 只读态状态行上屏：副行 #dlg-terms-sub 的「程序要求版本…同意后才能…」
 * 是同意前的说明，只读态不再重复显示（收起）。 */
function paintTermsViewOnlyStatus(acceptedAt) {
  const box = $("#dlg-terms-status");
  const sub = $("#dlg-terms-sub");
  if (sub) sub.hidden = true;
  if (!box) return;
  box.hidden = false;
  box.dataset.tone = "info";
  box.innerHTML = termsViewOnlyLineHtml(termsDocVersion(), acceptedAt);
  /* 与 termsStatus 同规矩：反馈在唯一滚动区内置顶可见 */
  const body = $(".terms-body");
  if (body) body.scrollTop = 0;
}

/* ---- 弹窗/焦点等 DOM 细节的窄接口：条款用例（controller）只按名调用 ---- */

function termsDialogAvailable() {
  /* 可打开 = 弹窗存在且当前没开（已打开时不重置任何状态）。 */
  const dialog = $("#dlg-terms");
  return !!dialog && !dialog.open;
}

function termsDialogIsOpen() {
  const dialog = $("#dlg-terms");
  return !!(dialog && dialog.open);
}

function showTermsDialog() {
  const dialog = $("#dlg-terms");
  if (!dialog || dialog.open) return;
  dialog.showModal();
  /* 首次焦点放在可聚焦标题：Tab 从标题开始遍历整段条款（设计稿键盘条） */
  const heading = $("#dlg-terms-title");
  if (heading) { try { heading.focus(); } catch (err) { /* 标题不可聚焦就算了 */ } }
}

function closeTermsDialog() {
  const dialog = $("#dlg-terms");
  if (dialog && dialog.open) dialog.close();
}

function closeHelpIfOpen() {
  /* 任何时刻都不叠两个 open dialog：帮助入口先关帮助（关闭后按来源重开） */
  const help = $("#help");
  if (help && help.open) help.close();
}

function resetTermsFullView() {
  const full = $("#dlg-terms-full-text");
  if (full) {
    full.hidden = true;
    /* 方案 A：全文收起时文末元信息也要收起，避免只留一行版本号悬在要点下面 */
    const meta = $("#terms-doc-meta");
    if (meta) meta.hidden = true;
    const summary = $("#dlg-terms-summary");
    if (summary) summary.hidden = false;
    const btn = $("#btn-terms-full");
    if (btn) {
      btn.textContent = "查看完整条款";
      btn.setAttribute("aria-expanded", "false");
    }
    /* 每次打开都回到「要点」视图：工具行标题与正文视图同步复位 */
    const title = $("#dlg-terms-view-title");
    if (title) title.textContent = "条款要点";
  }
  /* 全文里有两份文档，重开时回到第一份，避免上次停在哪份就停在哪份；
     放在 if (full) 外面：全文容器缺失时 tab 高亮也不该留在上一份。 */
  switchTermsDoc("agreement");
  /* 副行（版本句）是每次打开的视图态：只读态由 paintTermsViewOnlyStatus
   * 收起，其余路径打开时在这里复位显示。 */
  const sub = $("#dlg-terms-sub");
  if (sub) sub.hidden = false;
}

function termsDocVersion() {
  /* 内嵌全文的版本字段：同意/复查都只认这一份（不是后端自报版本）。 */
  const node = $("#dlg-terms-document-version");
  return String((node && node.textContent) || "").trim();
}

function setRecheckBusy(busy) {
  const button = $("#btn-terms-recheck");
  if (!button) return;
  button.disabled = !!busy;
  button.textContent = busy ? "正在核对…" : "重新确认状态";
}

function focusHelpButton() {
  const helpBtn = $("#btn-help");
  if (helpBtn) { try { helpBtn.focus(); } catch (err) { /* 焦点落不下去就算了 */ } }
}

/* 方案 A 的勾选门：controller 只问结论、不碰 DOM。
 * fail-closed：读不到复选框、或读不到布尔 true，都算没勾。 */
function termsAgreeMissing() {
  /* fail-closed：读不到复选框、或读不到布尔 true，都算没勾。
   * 反面写法（元素不存在=已勾选）会让「HTML 被改坏」静默变成放行。 */
  const box = $("#chk-terms-agree");
  return !box || box.checked !== true;
}

/* 每次打开弹窗都回到未勾选：勾选不跨实例复用，也不落盘。 */
function resetTermsAgree() {
  const box = $("#chk-terms-agree");
  if (box) box.checked = false;
}

/* 关闭后按来源恢复焦点：帮助入口重开帮助并聚焦帮助里的「查看条款」；
 * 设置入口回设置抽屉里的「查看条款」（抽屉不是模态，一直开着，不重开帮助）；
 * 横幅入口回被点的按钮（入口已消失就落回 #btn-help）；自动弹与同意成功回 #btn-help。 */
function restoreTermsFocusTo(source, back) {
  if (source === "help") {
    const help = $("#help");
    if (help && !help.open) help.showModal();
    const entry = $("#btn-help-terms-view");
    if (entry) { try { entry.focus(); } catch (err) { /* 入口不可聚焦就算了 */ } return; }
  }
  if (source === "settings") {
    const entry = $("#btn-help-terms");
    if (entry) { try { entry.focus(); } catch (err) { /* 入口不可聚焦就算了 */ } return; }
  }
  if (back && document.body && document.body.contains(back)) {
    try { back.focus(); } catch (err) { /* 落到 #btn-help */ }
    if (document.activeElement === back) return;
  }
  const fallback = $("#btn-help");
  if (fallback) { try { fallback.focus(); } catch (err) {} }
}
