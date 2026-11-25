/* 活动简介浮层渲染（学校返回的简介与面向范围严格只用文本节点/textContent，绝不进 innerHTML）。 */
import { descModalModel } from "./state-desc.js";

function paintScopeNodes(box, lines) {
  while (box.firstChild) box.removeChild(box.firstChild);
  lines.forEach((line) => {
    const span = document.createElement("span");
    span.className = "scope-l";
    if (line.label) {
      const em = document.createElement("em");
      em.textContent = line.label;
      span.appendChild(em);
    }
    span.appendChild(document.createTextNode(line.text));
    box.appendChild(span);
  });
}

export function paintDescModal(model) {
  const title = $("#desc-title");
  if (!title) return;
  title.textContent = model.name;
  $("#desc-sub").textContent = model.sub;
  $("#desc-act-time").textContent = model.actTime;
  $("#desc-place").textContent = model.place;
  $("#desc-sign-time").textContent = model.signTime;
  paintScopeNodes($("#desc-scope"), model.scope.lines);
  const scopeMore = $("#btn-desc-scope-more");
  if (scopeMore) {
    scopeMore.hidden = !model.scope.hasMore;
    scopeMore.textContent = model.scopeToggleLabel;
  }
  const body = $("#desc-body");
  body.textContent = model.body;
  body.className = "desc-body" + (model.bodyMode ? " " + model.bodyMode : "");
  const bodyMore = $("#btn-desc-more");
  if (bodyMore) {
    bodyMore.hidden = !model.canToggleBody;
    bodyMore.textContent = model.bodyToggleLabel;
  }
  const retry = $("#btn-desc-retry");
  if (retry) {
    retry.hidden = !model.canRetry;
    retry.disabled = !!model.retryDisabled;
  }
}

export function paintDescIfOpen() {
  const dlg = $("#dlg-desc");
  if (!dlg || !dlg.open || !S.desc || !S.desc.id) return;
  const item = findItem(S.desc.id);
  if (!item) {
    if (dlg.close) dlg.close();
    return;
  }
  paintDescModal(descModalModel(item, {
    bodyExpanded: !!S.desc.bodyExpanded,
    scopeExpanded: !!S.desc.scopeExpanded,
    refreshing: S.listState === "loading",
  }));
}
