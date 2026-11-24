/* 设置「程序」组的飞书提醒：地址输入框与就地反馈。 */

/* 输入框只在打开抽屉时对齐已保存的地址（syncInput），平时不覆盖正在输入的草稿；
 * 反馈行是上一次保存或发测试消息的结果，tone 为 ok / warn。 */
export function paintFeishuRow(syncInput) {
  const input = $("#feishu-url");
  if (input && syncInput) input.value = String(S.feishuWebhook || "");
  const line = $("#feishu-note");
  if (!line) return;
  const note = S.feishuNote || null;
  line.hidden = !note;
  line.textContent = note ? String(note.text || "") : "";
  line.className = note && note.tone === "warn" ? "ph-note ph-err" : "ph-note";
}
