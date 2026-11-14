/* 登录恢复的视图层：账号状态、自动登录结论与账号表单的绘制方法包；
 * 不发桥接请求，不调编排层的方法。 */


import { PhonePanel, agoText } from "../phone-access/state.js";
import { maskAccount } from "./state-recovery.js";
import { phoneShow } from "../phone-access/view.js";



export const recoveryPaintPack = {

  /* 登录恢复一组（settings-gap 三、CR01–CR22，原型 credView，Main.dc.html 1388–1398）。
   * 审核决定 A3：先看 saved 再看 staged——暂存区也会放保存账号的副本（手机重新登录要用），所以 staged 单独为真
   * 不等于「只用这一次」；「这次运行的账号」= 没保存、但暂存区有（CR06）。
   * 冲突 5（CR20）：这次运行的账号和保存过的一样能自动登录，所以识别已启用时结论行写「已启用」。
   * 「这次那份被学校拒了」时 staged 变假、automatic.state 是 paused：表里没有这一档的文案，按「还没有账号密码」显示。 */
  paintRelogin(cred, ocrRow) {
    const busy = !!PhonePanel.busy;
    const saved = !!cred.saved;
    const once = !saved && !!cred.staged;
    const has = saved || once;
    const ocrReady = !!(ocrRow.ready || cred.ocr_ready);
    const ocrInstalled = !ocrReady && !!ocrRow.available && String(ocrRow.status || "") !== "failed";
    const storeOk = !(cred.store_available === false || cred.available === false);
    const formOn = !!PhonePanel.credForm;
    const ask = !!PhonePanel.clearConfirm;

    // CR05：表单展开或清除确认中隐藏；否则没有账号「填写账号密码」，有账号「更换」
    const slot = $("#btn-credentials-manage");
    if (slot) {
      slot.hidden = formOn || ask;
      slot.disabled = busy;
      slot.textContent = has ? "更换" : "填写账号密码";
    }
    // CR06：没账号时不显示这一行；只用这一次的打码账号只用后端给的 staged_hint，没有就不显示，不编
    const credLine = $("#relogin-credential-status");
    if (credLine) {
      const text = saved ? "已保存账号 " + maskAccount(cred.username) + "。"
        : (once && cred.staged_hint
          ? "这次运行可以用账号 " + String(cred.staged_hint) + " 重新登录，关闭工具后自动清除。" : "");
      credLine.textContent = text;
      credLine.hidden = !text;
    }
    // CR07 / CR20：四种结论；保存的密码被拒走 CR18 的单独红字，这里不再写括号
    const autoPath = $("#relogin-auto-path");
    if (autoPath) {
      let text;
      let cls = "";
      if (!has) {
        text = "失效后自动登录：未启用，还没有账号密码。登录失效后要手动重新登录；报名计划开放前 100 秒内失效的场次会直接结束。";
      } else if (ocrReady) {
        text = "失效后自动登录：已启用。登录失效时电脑自己重新登录，报名计划等开放或提交时也一样，不用你动手。";
        cls = "up-ok";
      } else if (ocrInstalled) {
        text = "失效后自动登录：验证码识别本机已装，还没启用（在上面“高级功能”里点“启用”）。现在登录失效时要你输验证码；报名计划开放前 100 秒内失效的场次会直接结束。";
        cls = "up-warn";
      } else if (String(ocrRow.status || "") === "checking") {
        text = "失效后自动登录：正在检查验证码识别组件。";
      } else if (String(ocrRow.status || "") === "outdated") {
        text = "失效后自动登录：验证码识别组件需要随新版本更新（在上面“高级功能”里点“更新组件”）。更新前登录失效时要你输验证码；报名计划开放前 100 秒内失效的场次会直接结束。";
        cls = "up-warn";
      } else {
        text = "失效后自动登录：还缺验证码识别组件（在上面的“高级功能”里一键安装）。现在登录失效时要你输验证码；报名计划开放前 100 秒内失效的场次会直接结束。";
        cls = "up-warn";
      }
      autoPath.textContent = text;
      autoPath.className = cls;
    }
    // CR03 的「存储不可用」、CR09、CR10 三行原型没有、代码里有真实信号，保留（kept_not_in_prototype）
    const storeNote = $("#relogin-store-note");
    if (storeNote) storeNote.hidden = storeOk;
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
    // CR11 / CR14 / CR15：表单、勾选项与按钮
    phoneShow("#credential-editor", formOn);
    PhonePanel.paintCredForm();
    // CR16 / CR17：「清除已保存」只有保存过的账号才有，表单和确认展开时隐藏；确认块红底
    phoneShow("#relogin-clear-row", saved && !formOn && !ask);
    const credClear = $("#btn-credentials-clear");
    if (credClear) credClear.disabled = busy;
    phoneShow("#relogin-clear-confirm", ask);
    // CR18：保存的密码学校不认，单独一条红字
    phoneShow("#relogin-bad", !!cred.paused && has && !formOn);
    // CR19 / CR21：操作结果就地说，不再写抽屉底部那一行
    const note = $("#credential-note");
    if (note) {
      note.textContent = PhonePanel.credNote;
      note.hidden = !PhonePanel.credNote;
      note.className = PhonePanel.credNoteTone === "bad" ? "ph-err" : "ph-note";
    }
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
