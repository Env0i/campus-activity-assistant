/* 条款弹窗呈现：版本/状态/底部操作区/全文切换/焦点恢复（只读 S.terms，不发桥接）。 */

function paintTerms() {
  /* 标题里的程序要求版本：状态未知时写「尚未确认」，不给一个看似确定的
   * 版本号让用户以为自己在读某一版（设计稿状态矩阵）。 */
  const version = S.terms.unknown ? "尚未确认" : (S.terms.version || "—");
  const inDialog = $("#dlg-terms-version");
  if (inDialog) inDialog.textContent = version;
  const inHelp = $("#help-terms-version");
  if (inHelp) inHelp.textContent = version;
  paintTermsMeta();
}

/* TM02（原型 Main:1571 句式）：元信息行的状态段按真实状态拼——
 * unknown 不声称任何同意状态（版本位已是「尚未确认」，本机读不到记录，
 * 不能断言「你还没有同意」）；有已同意版本且不是当前版 →
 * 「你之前同意的是 <旧版>，新版还没同意。」；没有任何同意记录 →
 * 「你还没有同意。」；已同意当前版不显示状态段（该态由只读合并行接管，
 * 副行整体收起，见 paintTermsViewOnlyStatus）。 */
function termsMetaStateHtml() {
  const t = S.terms || {};
  if (t.unknown) return "";
  const prev = String(t.acceptedVersion || "");
  if (!prev) return "你还没有同意。";
  if (t.version && prev !== t.version) {
    return "你之前同意的是 <b>" + esc(prev) + "</b>，新版还没同意。";
  }
  return "";
}

function paintTermsMeta() {
  const state = $("#terms-sub-state");
  if (state) state.innerHTML = termsMetaStateHtml();
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
    /* TM04（原型 Main:894）：同意钮名照原型叫「同意并继续」 */
    accept.textContent = saving ? "正在保存…" : "同意并继续";
    accept.title = (viewOnly || saving || unconfirmed || agreed)
      ? "同意当前版本的使用条款与隐私，之后才能登录和报名"
      : "先勾选左边的「我已阅读以上全部条款」，才能点同意";
  }
  if (x) x.disabled = saving;
  if (esc) {
    /* TM01（decisions 014 修订）：Esc 在同意态与只读态都等于「关闭」，
     * 不再有「Esc 暂不使用」——拒绝只走「暂不使用」钮；保存中照旧提示。 */
    esc.textContent = saving ? "正在保存…" : "Esc 关闭";
  }
  /* FU01/TM08（decisions 第 1 条）：小框在场的保存/未确认态同样收口——
   * 同意、暂不（同意/使用）与勾选在途时禁点；文案照原型，禁用条件同阅读器。 */
  const surface = termsActiveSurface();
  if (surface === "intro") {
    const introAccept = $("#btn-terms-intro-accept");
    const introDecline = $("#btn-terms-intro-decline");
    const introAgree = $("#chk-terms-intro-agree");
    if (introAgree) introAgree.disabled = saving || unconfirmed;
    if (introDecline) introDecline.disabled = saving || unconfirmed;
    if (introAccept) {
      introAccept.disabled = saving || unconfirmed || termsIntroAgreeMissing();
      introAccept.textContent = saving ? "正在保存…" : "同意并继续";
    }
  }
  if (surface === "update") {
    const tuAccept = $("#btn-tu-accept");
    const tuDecline = $("#btn-tu-decline");
    const tuFull = $("#btn-tu-full");
    if (tuDecline) tuDecline.disabled = saving || unconfirmed;
    if (tuFull) tuFull.disabled = saving || unconfirmed;
    if (tuAccept) {
      /* TM08：更新框没有勾选门（原型 Main:881 脚部无勾选，焦点直接落同意钮），
       * 只拦保存中/未确认。 */
      tuAccept.disabled = saving || unconfirmed;
      tuAccept.textContent = saving ? "正在保存…" : "同意新版条款";
    }
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

/* 升版改动摘要（TM09，设计文档 9.4，按 r6 正文第 8 节变更记录归纳成 3 条）。
 * 正文文字不改（全文与 docs 逐字一致的契约），「本版新增」用节标题上的 data-new 标出。
 * 条款更新框（#dlg-terms-update）的变更清单也用这一份数据（原型 Main:880 的 tu-list 版式）。 */
const TERMS_CHANGES = [
  "手机访问会经过的第三方：Cloudflare 临时隧道或你自己的 Tailscale 网络",
  "下载安装包与组件包时会访问 GitHub，下载后先核对 SHA-256",
  "手机配对记录只存摘要，保存在本机，一年后失效",
];
const TERMS_NEW_SECTIONS = {
  agreement: ["8."],
  privacy: ["1.", "3."],
};

function termsUpdateMode() {
  const t = S.terms || {};
  return !t.unknown && !!t.acceptedVersion && !!t.version && t.acceptedVersion !== t.version;
}

/* 打开条款阅读器时：之前同意过旧版，就在正文里标出这一版改动的节
 * （旧的 #terms-update 内嵌区块已删，改动清单挪进条款更新框 paintTermsUpdateBox）。 */
function paintTermsNewMarks() {
  const update = termsUpdateMode();
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

/* 完整条款左侧的章节目录：TM01（原型 Main:394）宽档常显——要点视图也在，
 * 跟着当前页签重画，点一下滚到那一节；窄档（≤719px）由样式收起，
 * 这里不再做「只在全文视图显示」的开关（旧开关类名已删）。 */
function paintTermsToc() {
  const toc = $("#terms-toc");
  if (!toc) return;
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

/* 阅读器只呈现全文（decisions 第 1 条：要点视图已删，原文由全文阅读器取代）。
 * 旧的 toggleTermsFull「要点⇄全文」切换随 #btn-terms-full 一起删除。 */

/* 条款弹窗里的局部反馈：保存失败只在这里说下一步，不刷大屏。
 * FU01/TM08（decisions 第 1 条）：同意/保存也可能发生在两个小框里——
 * 反馈跟当前开着的那个面走（阅读器/首次说明框/条款更新框互斥，同一时刻
 * 只有一个 <dialog> open），小框不滚阅读区。 */
function termsStatus(text, tone) {
  const surface = termsActiveSurface();
  const box = surface === "intro" ? $("#dlg-terms-intro-status")
    : surface === "update" ? $("#dlg-terms-update-status")
    : $("#dlg-terms-status");
  if (!box) return;
  if (!text) {
    box.hidden = true;
    box.textContent = "";
    return;
  }
  box.hidden = false;
  box.dataset.tone = tone || "warn";
  box.textContent = text;
  /* 阅读器内的反馈与阅读区同在唯一滚动区内：失败/未知/重新确认等非空消息置顶
   * 立即可见；只归零阅读区自身 scrollTop，不碰焦点、不滚整页，清空分支的提前
   * return 不受影响。小框（intro/update）没有这条滚动区，不做归零——
   * 状态行的家在阅读器里，没有面打开时也按阅读器处理（与旧行为一致）。 */
  if (surface !== "intro" && surface !== "update") {
    const body = $(".terms-body");
    if (body) body.scrollTop = 0;
  }
}

/* 当前可以交互的条款面（FU01/TM08，decisions 第 1 条）：三个 <dialog> 不叠层，
 * 同一时刻最多开一个，DOM 的 open 状态就是唯一事实；返回 "" 表示没有条款面打开。
 * 按钮接线与反馈路由都按它分流，不再各自维护一份「哪个框开着」的状态。 */
function termsActiveSurface() {
  const reader = $("#dlg-terms");
  if (reader && reader.open) return "reader";
  const intro = $("#dlg-terms-intro");
  if (intro && intro.open) return "intro";
  const update = $("#dlg-terms-update");
  if (update && update.open) return "update";
  return "";
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

/* 两个小框的可打开判断（FU01/TM08）：同一时刻最多一个条款 <dialog> open，
 * 已打开时重入是空操作（后台 refresh 的再入不许打断在途交互）。 */
function termsBoxAvailable(id) {
  const dialog = $(id);
  return !!dialog && !dialog.open;
}

/* ×/Esc 的去向（TM01 三语义，decisions 014 修订）：只读打开与同意态打开都等于
 * 「关闭」——不再等于拒绝，拒绝只走「暂不使用」钮（declineTerms 落盘）；
 * 从首启说明框 / 条款更新框打开的等于「回到原来的小框」（FU01/TM08，本任务
 * 已接线：S.terms.box 记着等在后面的小框）。openTermsReader 已按来源写好
 * S.terms.xClose（back/close），这里只读。 */
function termsCloseIntent() {
  return S.terms.xClose === "back" ? "back" : "close";
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

/* ---- FU01/TM08 两个小框的呈现（decisions 第 1 条，呈现在此、编排归 controllers）---- */

/* FU01（原型 Main:799-807）：六条要点从 store 的 FIRST_USE_POINTS 渲染——
 * .pts 版式（粗体标题＋说明行）由 styles.css 承担；第六条是入口行，link 标记
 * 把句中「现在就看」换成链接钮（原型 Main:806），点击由 app.js 委托给
 * openTermsReader("intro")。每次打开都回到未勾选（勾选不落盘，同方案 A）。 */
function paintTermsIntro() {
  const list = $("#dlg-terms-intro-points");
  if (list) {
    list.innerHTML = FIRST_USE_POINTS.map((point) => {
      const text = String(point.text || "");
      const body = point.link
        ? esc(text).replace("现在就看",
            '<button type="button" class="doc-link" id="btn-terms-intro-fulltext">现在就看</button>')
        : esc(text);
      return "<li><b>" + esc(String(point.title || "")) + "</b><span>" + body + "</span></li>";
    }).join("");
  }
  const status = $("#dlg-terms-intro-status");
  if (status) { status.hidden = true; status.textContent = ""; }
  const agree = $("#chk-terms-intro-agree");
  if (agree) agree.checked = false;
}

/* TM08（原型 Main:879-880）：副题版本读真实值（X=程序要求的当前版、Y=本机已同意版），
 * 示意值不进产品（plan decisions 第 5 条）；变更清单用 TERMS_CHANGES 的 r6 内容，
 * 每条琥珀「新增」徽章照原型 tu-list。 */
function paintTermsUpdateBox() {
  const version = $("#terms-update-version");
  if (version) version.textContent = (S.terms && S.terms.version) || "—";
  const from = $("#terms-update-from");
  if (from) from.textContent = (S.terms && S.terms.acceptedVersion) || "—";
  const list = $("#terms-update-list");
  if (list) {
    list.innerHTML = TERMS_CHANGES.map((text) =>
      '<li><span class="tu-new">新增</span><span>' + esc(String(text)) + "</span></li>").join("");
  }
  const status = $("#dlg-terms-update-status");
  if (status) { status.hidden = true; status.textContent = ""; }
}

function showTermsIntroBox() {
  const dialog = $("#dlg-terms-intro");
  if (!dialog || dialog.open) return;
  dialog.showModal();
  /* 焦点落标题（tabindex=-1）：Tab 从标题起遍历，与全文阅读器同规矩；
   * 原型 FirstUse 未指定打开焦点（Main:1828 只钉了更新框的同意钮）。 */
  const heading = $("#dlg-terms-intro-title");
  if (heading) { try { heading.focus(); } catch (err) { /* 标题不可聚焦就算了 */ } }
}

function closeTermsIntroBox() {
  const dialog = $("#dlg-terms-intro");
  if (dialog && dialog.open) dialog.close();
}

function showTermsUpdateBox() {
  const dialog = $("#dlg-terms-update");
  if (!dialog || dialog.open) return;
  dialog.showModal();
  /* TM08（原型 Main:1828）：打开时焦点落「同意新版条款」 */
  const accept = $("#btn-tu-accept");
  if (accept) { try { accept.focus(); } catch (err) { /* 落不下就算了 */ } }
}

function closeTermsUpdateBox() {
  const dialog = $("#dlg-terms-update");
  if (dialog && dialog.open) dialog.close();
}

/* 全文关掉后回到等在后面的小框（FU01/TM08，decisions 第 1 条）：×/Esc 关全文
 * ＝回到原来的小框，不等于拒绝；返回是否真有小框被唤回，没有就由调用方
 * 走普通来源焦点恢复。 */
function reopenTermsBox() {
  const box = S.terms.box || "";
  if (box === "intro") { showTermsIntroBox(); return true; }
  if (box === "update") { showTermsUpdateBox(); return true; }
  return false;
}

function closeHelpIfOpen() {
  /* 任何时刻都不叠两个 open dialog：帮助入口先关帮助（关闭后按来源重开） */
  const help = $("#help");
  if (help && help.open) help.close();
}

function resetTermsReaderView() {
  /* 全文常显（要点视图已删）：文末元信息块也随之常显，不再做显隐切换。
   * 打开时阅读区滚回顶部，别停在上一轮滚到的位置。 */
  /* 静态 HTML 里 #dlg-terms-full-text 默认 hidden（结构契约钉住默认态）；
   * 阅读器是唯一呈现面，打开时在这里取消隐藏——否则页签/目录正常而正文空白
   * （visual-verify 2026-11-08 截到）。 */
  const fullText = $("#dlg-terms-full-text");
  if (fullText) fullText.hidden = false;
  const body = $(".terms-body");
  if (body) body.scrollTop = 0;
  /* 全文里有两份文档，重开时回到第一份，避免上次停在哪份就停在哪份。 */
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
 * fail-closed：读不到复选框、或读不到布尔 true，都算没勾。
 * FU01：首次说明框用自己的勾选框（#chk-terms-intro-agree）走同一个门；
 * TM08：条款更新框没有勾选门（原型 Main:881 脚部无勾选，同意钮打开即可点）。 */
function termsAgreeMissing() {
  /* fail-closed：读不到复选框、或读不到布尔 true，都算没勾。
   * 反面写法（元素不存在=已勾选）会让「HTML 被改坏」静默变成放行。 */
  const surface = termsActiveSurface();
  if (surface === "update") return false;
  const box = surface === "intro" ? $("#chk-terms-intro-agree") : $("#chk-terms-agree");
  return !box || box.checked !== true;
}

/* 首次说明框的勾选门（views 侧只读 DOM，供 applyTermsFooter 复算禁用态）：
 * 与 termsAgreeMissing 同一 fail-closed 读法，但固定读 intro 的勾选框——
 * 按钮禁用是呈现，不随「当前哪个面开着」漂移。 */
function termsIntroAgreeMissing() {
  const box = $("#chk-terms-intro-agree");
  return !box || box.checked !== true;
}

/* 每次打开弹窗都回到未勾选：勾选不跨实例复用，也不落盘。 */
function resetTermsAgree() {
  const box = $("#chk-terms-agree");
  if (box) box.checked = false;
}

/* 关闭后按来源恢复焦点：help 来源是搬移遗留的兜底——查看条款入口已在
 * 「设置 → 条款与隐私」（#btn-help-terms），仍重开帮助并把焦点交给该入口；
 * 设置入口回设置抽屉里的「查看条款」（抽屉不是模态，一直开着，不重开帮助）；
 * 横幅入口回被点的按钮（入口已消失就落回 #btn-help）；自动弹与同意成功回 #btn-help。 */
function restoreTermsFocusTo(source, back) {
  if (source === "help") {
    const help = $("#help");
    if (help && !help.open) help.showModal();
    /* NEEDS-HUMAN 7（c3-dialogs-gap）：旧的帮助内入口 id 已随搬移不存在，
     * 死引用改指设置抽屉里的「查看条款」（#btn-help-terms），焦点归还不再落空。 */
    const entry = $("#btn-help-terms");
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
