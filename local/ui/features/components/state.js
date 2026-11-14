/* 组件组件的状态层：导入弹窗的标题表、下载失败原因表与失败文案的拼法；都是
 * 不碰 DOM 的纯推导。 */


/* IM03：导入自检的结论文案，字面照原型 impCheck（Main.dc.html 1368–1376），拼法按后端实际回包的字段：
 * 通过时回 ok / kind / feature / version；失败时只回 kind / feature / text，没有这个包自己的版本。
 * 所以：
 *   - 「大小和哈希都对得上」不写：自检只读了清单，没核每个文件的哈希（安装时才核），说出来就是替它担保；
 *   - 「这个组件包是给 x 用的」不写：失败回包里没有包的版本，只能说和现在的程序版本不配套（需要后端补 package_version）；
 *   - Tailscale 的 exe 只能按文件名认；其余 exe 照后端原话说不是组件包。 */
export const IMPORT_TITLE = { relogin_ocr: "验证码识别", phone_control: "手机控制" };



/* PH11：下载失败照原型拼「下载没有完成：原因，可以重试。」。G2：限流、超时和断网分开说——
 * 限流是 GitHub 按出口 IP 限制查询次数，等一会或去发布页手动下载都能绕过，不是连不上；
 * 超时（连上了但没在时限内回包）与连不上（根本没连上）也要分开，用户才知道该等还是查网络；
 * 认不出的码（比如这个版本没有发布组件包、校验没过）回落后端原话，不硬套。 */
export const PHONE_DOWNLOAD_REASON = {
  network_error: "连不上发布页",
  http_error: "GitHub 暂时无法响应，请稍后重试",
  rate_limited: "GitHub 暂时限制了查询次数，过一会再试，或到发布页手动下载后导入",
  timeout: "连接超时",
  not_published: "发布页上还没有这个版本的组件包，可以稍后再试，或手动下载后导入",
};



export function downloadFailText(download) {
  const snap = download || {};
  const code = String(snap.error_code || "");
  const reason = PHONE_DOWNLOAD_REASON[code];
  // 限速与「发布页上还没有」的原因文案自己说了怎么办，结尾不再加「可以重试」
  if ((code === "rate_limited" || code === "not_published") && reason) return "下载没有完成：" + reason + "。";
  if (reason) return "下载没有完成：" + reason + "，可以重试。";
  return String(snap.text || "下载没有完成，可以重试。");
}
