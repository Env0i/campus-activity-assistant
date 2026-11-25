/* 设置「程序」组的飞书提醒：标题行状态点、折叠展开与就地反馈。 */

/* 输入框只在打开抽屉时对齐已保存的地址（syncInput），平时不覆盖正在输入的草稿；
 * 反馈行是上一次保存或发测试消息的结果，tone 为 ok / warn。 */
export function paintFeishuRow(syncInput) {
  const input = $("#feishu-url");
  if (input && syncInput) input.value = String(S.feishuWebhook || "");
  const configured = !!String(S.feishuWebhook || "").trim();
  const status = $("#feishu-status");
  if (status) status.className = configured ? "adv-s green" : "adv-s";
  const statusText = $("#feishu-status-text");
  if (statusText) statusText.textContent = configured ? "已配置，报名结果和登录失效会发到群" : "未配置";
  const open = !!S.feishuOpen;
  const detail = $("#feishu-detail");
  if (detail) detail.hidden = !open;
  const toggle = $("#btn-feishu-toggle");
  if (toggle) toggle.setAttribute("aria-expanded", open ? "true" : "false");
  const line = $("#feishu-note");
  if (!line) return;
  const note = S.feishuNote || null;
  line.hidden = !note;
  line.textContent = note ? String(note.text || "") : "";
  line.className = note && note.tone === "warn" ? "ph-note ph-err" : "ph-note";
  const dismissBtn = $("#btn-dismiss-feishu-note");
  if (dismissBtn) dismissBtn.hidden = !note;
}
