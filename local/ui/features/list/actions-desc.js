/* 活动简介浮层交互与焦点管理。 */
import { paintDescIfOpen } from "./view-desc.js";

export function restoreDescFocus() {
  const st = S.desc || {};
  const opener = st.opener;
  const id = st.id;
  S.desc = { id: "", bodyExpanded: false, scopeExpanded: false, opener: null };
  if (opener && opener.isConnected && opener.focus) { opener.focus(); return; }
  const fallback = id ? document.querySelector('.desc-btn[data-desc="' + cssEscape(id) + '"]') : null;
  if (fallback && fallback.focus) fallback.focus();
}

export function openDescDialog(id, opener) {
  const item = findItem(id);
  const dlg = $("#dlg-desc");
  if (!item || !dlg) return;
  S.desc = { id: String(item.id), bodyExpanded: false, scopeExpanded: false, opener: opener || null };
  if (!dlg.open && dlg.showModal) dlg.showModal();
  paintDescIfOpen();
  const title = $("#desc-title");
  if (title && title.focus) title.focus();
}

export function closeDescDialog() {
  const dlg = $("#dlg-desc");
  if (dlg && dlg.open && dlg.close) dlg.close();
  restoreDescFocus();
}

export function wireDescDialog() {
  const dlg = $("#dlg-desc");
  if (!dlg) return;
  dlg.addEventListener("close", restoreDescFocus);
  dlg.addEventListener("click", (event) => {
    if (event.target === dlg) closeDescDialog();
  });
  const closeBtn = $("#btn-desc-close");
  if (closeBtn) closeBtn.addEventListener("click", closeDescDialog);
  const moreBtn = $("#btn-desc-more");
  if (moreBtn) {
    moreBtn.addEventListener("click", () => { S.desc.bodyExpanded = !S.desc.bodyExpanded; paintDescIfOpen(); });
  }
  const scopeBtn = $("#btn-desc-scope-more");
  if (scopeBtn) {
    scopeBtn.addEventListener("click", () => { S.desc.scopeExpanded = !S.desc.scopeExpanded; paintDescIfOpen(); });
  }
  const retryBtn = $("#btn-desc-retry");
  if (retryBtn) {
    retryBtn.addEventListener("click", () => {
      if (S.listState === "loading") return;
      retryBtn.disabled = true;
      refresh(false);
    });
  }
}
