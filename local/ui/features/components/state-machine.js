/* 两个组件行（手机控制、验证码识别）共用的纯函数状态机：输入一行组件快照与
 * 调用方带来的画面事实，输出这一行的状态与画共有部分要用的派生事实。
 * 不碰 DOM、不读 window、不用定时器、不读时钟；ctx 里没给的当没有。
 * 八个状态对应界面上的哪种样子、共用绘制怎么消费这些事实，见
 * docs/UI_SPEC.md 的「组件状态机」一节。 */

/* 状态与界面的对应（判断顺序即先后优先级，与改前两份认阶段逐行相同）：
 * missing 没装——标题行放「下载并安装」，出现「没装」块；
 * downloading 下载中——标题行放「取消下载」，进度块说正在下载；
 * verifying 校验中——按钮变「校验中…」禁用，进度条打满；
 * checking 检查中（组件事务锁被别的进程占着、还没结论）——进度块说「正在检查组件…」，不说没装；
 * outdated 需要更新（主程序升级后旧组件包）——主按钮变「更新组件」；
 * broken 已装但加载失败——放「重新导入组件包」；
 * enabled 组件可用且启用位开着；disabled 组件在本机但启用位没开。
 * enabled 与 disabled 落到哪个界面状态由两个组件各自决定：手机行把 enabled 当
 * 「装好未开启」、识别行把它当「已启用」，所以这里只报事实，不做界面命名。 */
export function componentState(row, ctx) {
  const source = row || {};
  const download = source.download || {};
  const env = ctx || {};
  const dl = String(download.state || "");
  const installing = !!env.installing;
  let state;
  if (dl === "downloading") state = "downloading";
  else if (dl === "verifying") state = "verifying";
  else if (String(source.status || "") === "checking") state = "checking";
  else if (String(source.status || "") === "outdated") state = "outdated";
  else if (String(source.status || "") === "failed") state = "broken";
  else if (source.ready) state = "enabled";
  else if (source.available) state = "disabled";
  else state = "missing";
  const downloading = state === "downloading" || state === "verifying";
  return {
    state: state,
    /* 下载事务的原样事实：进度块与失败红条都从这里取数 */
    downloadState: dl,
    download: download,
    failed: dl === "failed",
    cancelled: dl === "cancelled",
    downloading: downloading,
    /* 在加载：下载、校验、检查或安装中的任何一个——进度块此时要显示 */
    loading: downloading || state === "checking" || installing,
    installing: installing,
    busy: !!env.busy,
    /* 组件位置的电脑端专用接口回包（取不到就是 null），共有绘制画「会装到 / 装在」用 */
    location: env.location || null,
  };
}
