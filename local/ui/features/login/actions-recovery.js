/* 登录恢复的编排层：保存的账号与登录恢复的动作方法包（去保存、保存、展开与
 * 收起表单、清除的询问取消确认与执行）；发桥接请求的方法都放在这一层。 */


import { openSettings } from "../shell/actions-settings.js";
import { PhonePanel } from "../phone-access/state.js";



export const recoveryActionsPack = {

  /* PH24「去保存」（CR22）：打开设置的登录组、展开账号密码表单并聚焦账号框。表单已经开着就不清用户输到一半的内容 */
  goSaveCredentials() {
    if (typeof openSettings === "function") openSettings("login");
    if (!PhonePanel.credForm) {
      PhonePanel.credNote = "";
      const onceBox = $("#credential-once");
      if (onceBox) onceBox.checked = false;
    }
    PhonePanel.credForm = true;
    const editor = $("#credential-editor");
    if (editor) editor.hidden = false;
    PhonePanel.paint();
    const user = $("#credential-user");
    if (user && typeof user.focus === "function") user.focus();
  },



  /* CR11 / CR12 / CR19：勾了「只在这次运行中用」或本机加密存储不可用，就只把账号放进内存（prepare_phone_relogin，
   * 不落盘）；否则加密保存。成功后收起表单、就地说一句；失败留着表单，只给通用文案，不带异常原文。 */
  async saveCredentials() {
    const user = $("#credential-user");
    const pass = $("#credential-pass");
    if (!user || !pass) return;
    const username = String(user.value || "");
    const password = String(pass.value || "");
    const cred = (PhonePanel.state.advanced && PhonePanel.state.advanced.credential) || {};
    const onceBox = $("#credential-once");
    const once = !!(onceBox && onceBox.checked) || !cred.available;
    let result = null;
    PhonePanel.busy = true;
    PhonePanel.paint();
    try {
      result = once
        ? await api("prepare_phone_relogin", username, password)
        : await api("save_relogin_credentials", username, password);
    } catch (err) {
      // 失败原因可能含账号细节，只给通用文案，不把异常原文带给用户
      result = { ok: false, text: "账号信息没有保存。" };
    } finally {
      user.value = "";
      pass.value = "";
      PhonePanel.busy = false;
    }
    if (result && result.ok) {
      PhonePanel.credForm = false;
      PhonePanel.credNote = once ? "已准备好，只在这次运行中使用。" : "已加密保存到本机。";
      PhonePanel.credNoteTone = "ok";
    } else {
      PhonePanel.credNote = String((result && result.text) || "账号信息没有保存。");
      PhonePanel.credNoteTone = "bad";
    }
    await PhonePanel.refresh();
  },



  /* CR05：标题行按钮展开表单——清掉旧反馈和上次的输入，勾选项回到默认（保存到本机） */
  openCredForm() {
    PhonePanel.credForm = true;
    PhonePanel.credNote = "";
    const user = $("#credential-user");
    const pass = $("#credential-pass");
    const onceBox = $("#credential-once");
    if (user) user.value = "";
    if (pass) pass.value = "";
    if (onceBox) onceBox.checked = false;
    PhonePanel.paint();
    if (user && typeof user.focus === "function") user.focus();
  },



  /* CR15：取消——清空输入并收起表单 */
  cancelCredForm() {
    PhonePanel.credForm = false;
    const user = $("#credential-user");
    const pass = $("#credential-pass");
    if (user) user.value = "";
    if (pass) pass.value = "";
    PhonePanel.paint();
  },



  /* 清除账号先展开确认行：这是不可撤销的动作，不能一点就删 */
  askClearCredentials() {
    PhonePanel.clearConfirm = true;
    PhonePanel.credNote = "";
    PhonePanel.paint();
  },



  cancelClearCredentials() {
    PhonePanel.clearConfirm = false;
    PhonePanel.paint();
  },



  async confirmClearCredentials() {
    PhonePanel.clearConfirm = false;
    PhonePanel.paint();
    await PhonePanel.clearCredentials();
  },



  async clearCredentials() {
    let result = null;
    try {
      result = await api("clear_relogin_credentials");
    } catch (err) {
      result = { ok: false };
    }
    PhonePanel.credNote = (result && result.ok) ? "已清除本机保存的账号密码。" : "清除没有完成。";
    PhonePanel.credNoteTone = (result && result.ok) ? "ok" : "bad";
    await PhonePanel.refresh();
  },

};
