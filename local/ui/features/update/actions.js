/* 更新通道用例：检查/下载/取消/启动与在途收口（DOM 呈现见 views/update.js）。 */

function watchUpdate(requestId, ms) {
  clearTimeout(S.update.timer);
  /* 后端请求有8秒网络超时；桥接丢事件也不能让按钮永久停在进行中。 */
  S.update.timer = setTimeout(() => {
    if (S.update.requestId !== requestId) return;
    const stalled = S.update.state;
    if (["checking", "downloading", "downloading_delta", "downloading_full",
      "verifying", "applying", "launching"].indexOf(stalled) < 0) return;
    receiveUpdate({ request_id: requestId, state: stalled === "checking" ? "error" : "failed",
      text: "没有收到更新结果，请重试。", error_code: "timeout" });
  }, ms || 15000);
}

function isUpdateLaunched(state, text) {
  return state === "launching" && /^(安装程序已启动|更新启动器已启动)/.test(String(text || ""));
}

export function receiveUpdate(payload) {
  const data = payload || {};
  if (!data.request_id || data.request_id !== S.update.requestId) return;
  clearTimeout(S.update.timer);
  /* 合并而非替换：下载进度事件不一定带安装器信息，要保住检查阶段选好的那份。 */
  S.update.result = Object.assign({}, S.update.result || {}, data);
  const known = ["checking", "available", "no_installer", "current", "preview", "unavailable", "error",
    "confirm", "downloading", "downloading_delta", "downloading_full", "verifying",
    "applying", "ready_to_install", "ready_to_restart", "launching", "failed"];
  S.update.state = known.indexOf(data.state) >= 0 ? data.state : "error";
  paintUpdate();
  /* 检查、启动（二段已拉起前）与下载/校验在途阶段都续上看门狗；终态不再计时。 */
  const launched = isUpdateLaunched(S.update.state, data.text);
  if (S.update.state === "checking" || (S.update.state === "launching" && !launched)) {
    watchUpdate(S.update.requestId, 15000);
  } else if (["downloading", "downloading_delta", "downloading_full", "verifying", "applying"]
    .indexOf(S.update.state) >= 0) {
    watchUpdate(S.update.requestId, 60000);
  }
  revealUpdateStatus();
}

export function restoreUpdate(snapshot) {
  if (!snapshot || !snapshot.request_id) { paintUpdate(); return; }
  S.update.requestId = String(snapshot.request_id);
  /* checking 表示「任一更新动作在途」（检查或下载）；具体阶段只认 result.state。 */
  if (snapshot.checking) {
    const prior = snapshot.result || {};
    S.update.result = prior;
    S.update.state = ["checking", "downloading", "downloading_delta", "downloading_full",
      "verifying", "applying", "ready_to_restart", "launching"].indexOf(prior.state) >= 0
      ? prior.state : "checking";
    if (S.update.state === "checking"
        || (S.update.state === "launching" && !isUpdateLaunched(S.update.state, prior.text))) {
      watchUpdate(S.update.requestId, 15000);
    } else if (["downloading", "downloading_delta", "downloading_full", "verifying", "applying"]
      .indexOf(S.update.state) >= 0) {
      watchUpdate(S.update.requestId, 60000);
    }
  } else if (snapshot.result) receiveUpdate(snapshot.result);
  paintUpdate();
}

export function checkUpdate() {
  if (["checking", "downloading", "downloading_delta", "downloading_full", "verifying",
    "applying", "launching"].indexOf(S.update.state) >= 0) return;
  const requestId = "update-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8);
  S.update.requestId = requestId;
  S.update.result = null;
  S.update.state = "checking";
  watchUpdate(requestId);
  paintUpdate();
  api("check_update", requestId).then((res) => {
    /* 结果可以先于ack到达：完成后不再被ack改回检查中。 */
    if (S.update.requestId !== requestId || S.update.state !== "checking") return;
    if (!res || res.ok === false || res.queued === false) {
      receiveUpdate({ request_id: requestId, state: "error", text: res && res.text || "检查没能启动，请重试。" });
    } else if (res.skipped && res.request_id) {
      S.update.requestId = String(res.request_id);
      watchUpdate(S.update.requestId);
      /* 重载时可能接上已完成的在途请求；读取本地快照，不额外发网络检查。 */
      const attachedId = S.update.requestId;
      api("bootstrap").then((info) => {
        /* 快照晚到时用户可能已开新查询；只有仍在接管同一请求才允许恢复。 */
        if (S.update.requestId === attachedId) restoreUpdate(info && info.update_check);
      }).catch(() => {});
    }
  }).catch((err) => {
    if (S.update.requestId === requestId && S.update.state === "checking") {
      receiveUpdate({ request_id: requestId, state: "error", text: msg(err) });
    }
  });
}

/* 「下载并安装」先进确认态：下载必须是用户显式确认后的动作，检查从不自动下载。 */
export function startDownload() {
  const result = S.update.result;
  if (S.update.state !== "available" && S.update.state !== "failed") return;
  if (!result || !result.installer || !result.installer.url) return;
  S.update.state = "confirm";
  paintUpdate();
}

export function confirmDownload() {
  if (S.update.state !== "confirm") return;
  const result = S.update.result || {};
  const installer = result.installer;
  if (!installer || !installer.url) {
    receiveUpdate({ request_id: S.update.requestId, state: "failed",
      text: "没有可下载的安装包，请前往下载页。", error_code: "no_installer" });
    return;
  }
  const requestId = "dl-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8);
  S.update.requestId = requestId;
  S.update.state = "downloading";
  watchUpdate(requestId, 60000);
  paintUpdate();
  api("update_download", requestId).then((res) => {
    if (S.update.requestId !== requestId || S.update.state !== "downloading") return;
    if (!res || res.ok === false || res.queued === false) {
      receiveUpdate({ request_id: requestId, state: "failed",
        text: res && res.text || "下载没能启动，请重试。", error_code: "start_failed" });
    }
  }).catch((err) => {
    if (S.update.requestId === requestId && S.update.state === "downloading") {
      receiveUpdate({ request_id: requestId, state: "failed", text: msg(err), error_code: "start_failed" });
    }
  });
}

/* 取消只停本次下载：后端清理半成品并回推可用态，不动旧程序和用户数据。 */
export function cancelDownload() {
  if (S.update.state === "confirm") {
    S.update.state = (S.update.result && S.update.result.installer && S.update.result.installer.url) ? "available" : "no_installer";
    paintUpdate();
    return;
  }
  if (["downloading", "downloading_delta", "downloading_full", "verifying"].indexOf(
    S.update.state) < 0) return;
  const requestId = S.update.requestId;
  api("update_cancel").then((res) => {
    if (S.update.requestId !== requestId) return;
    if (res && res.ok === false) {
      receiveUpdate({ request_id: requestId, state: "failed",
        text: String(res.text || "没能取消下载，请重试。"), error_code: "cancel_failed" });
    }
  }).catch((err) => {
    if (S.update.requestId !== requestId) return;
    receiveUpdate({ request_id: requestId, state: "failed",
      text: "没能取消下载：" + msg(err), error_code: "cancel_failed" });
  });
}

/* 启动安装器是最后一个用户确认动作；关闭主程序由用户自己控制，不自动退出或重启。 */
export function launchInstaller() {
  if (S.update.state !== "ready_to_install" && S.update.state !== "ready_to_restart") return;
  const requestId = "launch-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8);
  S.update.requestId = requestId;
  S.update.state = "launching";
  watchUpdate(requestId, 15000);
  paintUpdate();
  api("update_launch", requestId).then((res) => {
    if (S.update.requestId !== requestId) return;
    if (!res || res.ok === false) {
      receiveUpdate({ request_id: requestId, state: "failed",
        text: res && res.text || "安装程序没能启动，请重试。", error_code: "launch_failed" });
    }
  }).catch((err) => {
    if (S.update.requestId === requestId) {
      receiveUpdate({ request_id: requestId, state: "failed", text: msg(err), error_code: "launch_failed" });
    }
  });
}
