/* 登录恢复的视图层：账号状态、自动登录结论与账号表单的绘制方法包；
 * 不发桥接请求，不调编排层的方法。 */


import { PhonePanel, agoText } from "../phone-access/state.js";
import { loginChecklistModel } from "./state-recovery.js";
import { phoneShow } from "../phone-access/view.js";

function paintLastAndPhone(cred, ocrReady) {
  // CR09 / CR10：两行原型没有、代码里有真实信号，保留（kept_not_in_prototype）
  const lastLine = $("#relogin-last-used");
  if (lastLine) {
    const origin = String(cred.last_origin || "");
    const ago = Number((cred.automatic && cred.automatic.last_used_ago_s) || 0);
    if (origin === "auto_ocr") lastLine.textContent = "最近一次登录：由电脑自动恢复完成。";
    else if (origin === "phone_manual") lastLine.textContent = "最近一次登录：在手机上手动完成。";
    else if (ago > 0) lastLine.textContent = "最近一次自动恢复：" + agoText(ago) + "。";
    else lastLine.textContent = "最近一次登录：暂无记录。";
  }
  const phonePath = $("#relogin-phone-path");
  if (phonePath) {
    phonePath.textContent = ocrReady
      ? "手机上重新登录：验证码先由电脑自动识别，认不出来再由你输入。"
      : "手机上重新登录：验证码由你输入；手机上也可以输账号密码，默认不保存。";
  }
}

function paintChecklistSteps(model, busy, formOn, ask) {
  const headStatus = $("#relogin-head-status");
  if (headStatus) headStatus.className = "adv-s " + model.headCls;
  // CR07 / CR20：总结论与二步状态；保存的密码被拒走 CR18 的单独红字，这里不再写括号
  const headText = $("#relogin-head-status-text");
  if (headText) headText.textContent = model.headStatus;
  const s1No = $("#cred-step1-no");
  if (s1No) { s1No.className = "lstep-no" + (model.s1Cls ? " " + model.s1Cls : ""); s1No.textContent = model.s1Mark; }
  // CR06：只用这一次的打码账号只用后端给的 staged_hint，没有就不编
  const credLine = $("#relogin-credential-status");
  if (credLine) { credLine.textContent = model.s1Sub; credLine.className = model.s1SubCls; credLine.hidden = false; }
  // CR05：表单展开或清除确认中隐藏；否则没有账号「填写账号密码」，有账号「更换」
  const slot = $("#btn-credentials-manage");
  if (slot) {
    slot.hidden = formOn || ask;
    slot.disabled = busy;
    slot.textContent = model.slotLabel;
    slot.className = "btn " + model.slotCls;
  }
  const s2No = $("#cred-step2-no");
  if (s2No) { s2No.className = "lstep-no" + (model.s2Cls ? " " + model.s2Cls : ""); s2No.textContent = model.s2Mark; }
  const s2Sub = $("#relogin-ocr-sub");
  if (s2Sub) { s2Sub.textContent = model.s2Sub; s2Sub.className = model.s2SubCls; }
  const s2Btn = $("#btn-relogin-ocr-step");
  if (s2Btn) {
    s2Btn.textContent = model.s2BtnLabel;
    s2Btn.dataset.action = model.s2Action;
    s2Btn.disabled = busy;
  }
  const autoPath = $("#relogin-auto-path");
  if (autoPath) { autoPath.textContent = model.foot; }
}

export const recoveryPaintPack = {

  /* 登录恢复一组（settings-gap 三、CR01–CR22，原型 credView，Main.dc.html 1388–1398），D6 改为「还差 N 步」二步清单。
   * 审核决定 A3：先看 saved 再看 staged——暂存区也会放保存账号的副本（手机重新登录要用），所以 staged 单独为真
   * 不等于「只用这一次」；「这次运行的账号」= 没保存、但暂存区有（CR06）。
   * 冲突 5（CR20）：这次运行的账号和保存过的一样能自动登录，所以识别已启用时结论行写「已启用」。
   * 「这次那份被学校拒了」时 staged 变假、automatic.state 是 paused：表里没有这一档的文案，按「还没有账号密码」显示。 */
  paintRelogin(cred, ocrRow) {
    const busy = !!PhonePanel.busy;
    const storeOk = !(cred.store_available === false || cred.available === false);
    const formOn = !!PhonePanel.credForm;
    const ask = !!PhonePanel.clearConfirm;
    const model = loginChecklistModel(cred, ocrRow);
    paintChecklistSteps(model, busy, formOn, ask);
    // CR03 的「存储不可用」原型没有、代码里有真实信号，保留（kept_not_in_prototype）
    const storeNote = $("#relogin-store-note");
    if (storeNote) storeNote.hidden = storeOk;
    paintLastAndPhone(cred, model.ocrReady);
    // CR11 / CR14 / CR15：表单、勾选项与按钮
    phoneShow("#credential-editor", formOn);
    PhonePanel.paintCredForm();
    // CR16 / CR17：「清除已保存」只有保存过的账号才有，表单和确认展开时隐藏；确认块红底
    phoneShow("#relogin-clear-row", model.saved && !formOn && !ask);
    const credClear = $("#btn-credentials-clear");
    if (credClear) credClear.disabled = busy;
    phoneShow("#relogin-clear-confirm", ask);
    // CR18：保存的密码学校不认，单独一条红字
    phoneShow("#relogin-bad", model.bad && model.has && !formOn);
    // CR19 / CR21：操作结果就地说，不再写抽屉底部那一行
    const note = $("#credential-note");
    if (note) {
      note.textContent = PhonePanel.credNote;
      note.hidden = !PhonePanel.credNote;
      note.className = PhonePanel.credNoteTone === "bad" ? "ph-err" : "ph-note";
    }
    const dismissNote = $("#btn-dismiss-credential-note");
    if (dismissNote) dismissNote.hidden = !PhonePanel.credNote;
  },



  /* CR12 / CR14：保存按钮随勾选项改名，账号或密码为空时禁用。
   * 本机加密存储不可用（kept）时只能「只用这一次」，勾选项锁住；而且手机控制和验证码识别都没装时没处用，按钮不开。 */
  paintCredForm() {
    const st = PhonePanel.state;
    const cred = (st.advanced && st.advanced.credential) || {};
    const storeOk = !(cred.store_available === false || cred.available === false);
    const onceBox = $("#credential-once");
    if (onceBox) {
      if (!storeOk) onceBox.checked = true;
      onceBox.disabled = !!PhonePanel.busy || !storeOk;
    }
    const once = !storeOk || !!(onceBox && onceBox.checked);
    const user = $("#credential-user");
    const pass = $("#credential-pass");
    const empty = !String((user && user.value) || "").trim() || !String((pass && pass.value) || "");
    const phoneRow = Object.assign({}, st.feature || {}, PhonePanel.feature("phone_control"));
    const ocrRow = PhonePanel.feature("relogin_ocr");
    const usable = !!phoneRow.ready || !!(ocrRow.ready || cred.ocr_ready);
    const save = $("#btn-credentials-save");
    if (save) {
      save.textContent = once ? "只用这一次" : "保存到本机";
      save.disabled = !!PhonePanel.busy || empty || (!storeOk && !usable);
    }
  },

};
