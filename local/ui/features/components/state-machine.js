/* 两个组件行（手机控制、验证码识别）共用的纯函数状态机：输入一行组件快照与
 * 调用方带来的画面事实，输出这一行的状态与画共有部分要用的派生事实。
 * 不碰 DOM、不读 window、不用定时器、不读时钟；ctx 里没给的当没有。
 * 八个状态对应界面上的哪种样子、共用绘制怎么消费这些事实，见
 * docs/UI_SPEC.md 的「组件状态机」一节。 */

/* 等锁超过这么久还没有结论就当超时，界面上给一个「重试」。
 * 口径与状态层的 local/domain/component_rules.py 里 COMPONENT_CHECK_TIMEOUT_S 一致，
 * 两边算法不同（那边按等待起点算，这边按这一次点的重试起点算），30 秒这个数要一起改。 */
const PROBE_TIMEOUT_S = 30;

/* 这台状态机只会给出这些状态与这些读状态，顺序就是判断的先后；测试按这两份清单核对
 * 「推导只返回清单里的值」，一个地方就能看全这台机有哪些状态。 */
export const COMPONENT_STATES = Object.freeze([
  "downloading", "verifying", "checking", "outdated", "broken", "enabled",
  "disabled", "missing",
]);

export const COMPONENT_PROBES = Object.freeze(["", "waiting", "timeout", "unreadable"]);

/* 状态与界面的对应（判断顺序即先后优先级，与改前两份认阶段逐行相同）：
 * missing 没装——标题行放「下载并安装」，出现「没装」块；
 * downloading 下载中——标题行放「取消下载」，进度块说正在下载；
 * verifying 校验中——按钮变「校验中…」禁用，进度条打满；
 * checking 检查中（组件事务锁被别的进程占着、还没结论）——进度块收着，说明行说正在确认，不说没装；
 * outdated 需要更新（主程序升级后旧组件包）——主按钮变「更新组件」；
 * broken 已装但加载失败——主按钮变「重新安装」；
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
  // 手机行开着的时候组件已在用，界面按装好画，不再走下载/检查的中间态
  if (env.running) state = "enabled";
  const downloading = state === "downloading" || state === "verifying";
  /* 读状态：拿不到结论的那几种情况由行自己说明白，界面据此决定藏按钮还是给「重试」。
   * 下载和校验中不判——那几档的事进度块已经说过了。 */
  const hasBase = env.retryWaitBase !== undefined && env.retryWaitBase !== null;
  const waited = Number(source.lock_wait_s) || 0;
  const overWait = !!source.check_timed_out
    && (!hasBase || waited - Number(env.retryWaitBase) >= PROBE_TIMEOUT_S);
  let probe = "";
  if (downloading) probe = "";
  else if (source.read_error) probe = "unreadable";
  else if (overWait) probe = "timeout";
  else if (source.busy || String(source.status || "") === "checking") probe = "waiting";
  return {
    state: state,
    /* 下载事务的原样事实：进度块与失败红条都从这里取数 */
    downloadState: dl,
    download: download,
    failed: dl === "failed",
    cancelled: dl === "cancelled",
    downloading: downloading,
    /* 在加载：下载、校验或安装中的任何一个——进度块此时要显示 */
    loading: downloading || installing,
    installing: installing,
    busy: !!env.busy,
    /* 读状态：空 = 读到结论了；waiting 等锁中、timeout 等太久、unreadable 读不到 */
    probe: probe,
    /* 组件位置的电脑端专用接口回包（取不到就是 null），共有绘制画「会装到 / 装在」用 */
    location: env.location || null,
  };
}
