/* 顶部横幅的视图。 */

import { loginBannerHtml } from "../login/view.js";
import { termsLocked } from "../terms/state.js";
import { runtimeErrorCopy } from "./state-runtime.js";

/* 一次只显示一条，按优先级取最前面那条（决策 014 第 12 条；顺序照原型 attention()）：
 * 程序组件缺失 > 条款未同意 > 断网 > 电脑刚睡眠过 > 登录待确认 > 登录已失效 > 北京时间问题
 * > 工具已经开着（note） > 旧数据迁移（MG01/MG02，原型 attention() 最后两条）。 */
export function paintBanners() {
  const parts = [];
  if (S.runtime.error) {
    /* 组件问题只挂一条横幅（一个主要提示 + 恢复动作），不在满屏重复 */
    const copy = runtimeErrorCopy();
    parts.push('<div class="banner" data-tone="bad" role="alert"><span class="grow"><b>' + esc(copy.title) + "。</b>" +
      esc(copy.hint) + "</span>" +
      '<button class="btn btn-ghost" type="button" data-act="runtime-refresh">重新检查</button></div>');
  }
  if (S.terms.unknown) {
    /* TM07 照原型 Main:2138：未知态横幅拆成标题＋两句正文（日志那条归
     * markTermsUnknown，原型 Main:1180，只写一次）；停用学校动作并给
     * 唯一的重试入口；不自动弹窗——用户点开的才是可确认的同意动作 */
    parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>条款状态没能确认。</b>' +
      "读不到你同意过哪一版。登录、活动列表和报名计划暂时停用，打开条款重新确认后恢复。</span>" +
      '<button class="btn btn-ghost" type="button" data-act="terms-open">查看条款</button></div>');
  } else if (termsLocked()) {
    /* TM06 照原型 Main:2138：之前同意过旧版（acceptedVersion 存在且 ≠ 当前版）
     * 说「更新了，还没有同意新版」；从没同意或拒绝过保留原句。 */
    const updated = !!S.terms.acceptedVersion && !!S.terms.version &&
      S.terms.acceptedVersion !== S.terms.version;
    parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>' +
      (updated ? "使用条款更新了，还没有同意新版。" : "还没有同意使用条款。") +
      (updated ? "同意后才能登录、查看活动和开始报名计划。"
        : (S.terms.declined ? "登录、活动列表和报名计划保持停用。"
                            : "同意后才能登录、查看活动列表与开始报名计划。")) +
      "</span>" +
      '<button class="btn btn-ghost" type="button" data-act="terms-open">查看条款</button></div>');
  }
  if (!S.online) {
    /* 断网横幅照原型 Main.dc.html:1849：给一句下一步，并让用户自己重新检测 ——
     * 网络事件不可靠（系统仍认为联网时请求会一直挂着），所以不能只等 online 事件。 */
    parts.push('<div class="banner" data-tone="bad" role="alert"><span class="grow"><b>网络断开了。</b>' +
      (S.busy ? "到点时还没恢复，这次报名会失败。恢复以后看一眼计划结果。" : "恢复以后点“刷新”。") + "</span>" +
      '<button class="btn btn-ghost" type="button" data-act="net-recheck">重新检测</button></div>');
  }
  if (S.sleepGap) {
    /* LS21 照原型：写约几分钟，并点名睡眠期间到了开放时间的计划场次。
     * 睡眠窗口没记下来（当时业务时钟不可用）时不能断言「没有场次」，沿用原来的提醒句。 */
    const minutes = Math.max(1, Math.round(S.sleepGap / 60000));
    const missed = S.sleepWindow ? sleepMissedNames() : null;
    const detail = missed === null ? "要是睡过了开放时间，就赶不上了。看看计划和运行记录。"
      : missed.length ? "期间" + missed.map((name) => "「" + esc(name) + "」").join("") + "到了开放时间，没有提交。"
      : "期间没有场次到开放时间。";
    parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>电脑刚才睡眠了约 ' + minutes +
      " 分钟。</b>" + detail + "</span>" +
      '<button class="btn btn-ghost" type="button" data-act="sleep-ok">知道了</button></div>');
  }
  parts.push(...[loginBannerHtml(S.login.view || {}, S.busy)].filter(Boolean));
  if (!S.demo && typeof clockUiState === "function" && clockUiState() === "unavailable") {
    parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>北京时间还没校准。</b>' +
      "校准后才能开始报名计划；已保存的登录不受影响。</span>" +
      '<button class="btn btn-ghost" type="button" data-act="clock-open">查看时间</button></div>');
  }
  if (S.secondOpen) {
    /* GL01 note 档（原型 attention() 的 second，排在时钟之后）：又开了一次，第二份已退出，窗口已切回来 */
    parts.push('<div class="banner" data-tone="note" role="status"><span class="grow"><b>工具已经开着。</b>' +
      "刚才又打开了一次，已切回这个窗口。同一台电脑只运行一份，免得同一场被提交两遍。</span>" +
      '<button class="btn btn-ghost" type="button" data-act="second-ok">知道了</button></div>');
  }
  if (S.migration && !S.migrationDismissed) {
    /* MG01/MG02（原型 Main:2146/2147 的 attention() 末两条）：迁移成功与失败互斥。
     * 成功走 note 档，「知道了」只收本次运行内的横幅（不落盘）；失败走警示档，
     * 「登录」复用登录失效横幅的同一入口（data-act=login → openLogin）。 */
    const mg = S.migration;
    if (mg.login_failed && mg.other_failed) {
      /* 登录和其他都失败：U+2060 连住末尾两字，防单字掉行 */
      parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>旧版本的数据没能搬过来。</b>' +
        "旧文件还留在原来的位置；重新登录一次就行，设置要重新调⁠一下。</span>" +
        '<button class="btn btn-ghost" type="button" data-act="login">登录</button></div>');
    } else if (mg.login_failed) {
      parts.push('<div class="banner" data-tone="warn" role="alert"><span class="grow"><b>旧版本的登录信息没能搬过来。</b>' +
        "设置和运行记录已经搬好；重新登录一次就行，旧文件还留在原来的位置。</span>" +
        '<button class="btn btn-ghost" type="button" data-act="login">登录</button></div>');
    } else if (mg.other_failed) {
      parts.push('<div class="banner" data-tone="note" role="status"><span class="grow"><b>旧版本的设置或运行记录没能搬过来。</b>' +
        "登录信息已经搬好，不用重新登录；旧文件还留在原来的位置。</span>" +
        '<button class="btn btn-ghost" type="button" data-act="migrated-ok">知道了</button></div>');
    } else {
      parts.push('<div class="banner" data-tone="note" role="status"><span class="grow"><b>已把旧版本的数据搬到新位置。</b>' +
        "登录、设置和运行记录都在，不用重新登录。位置在设置的“本机数据”里。</span>" +
        '<button class="btn btn-ghost" type="button" data-act="migrated-ok">知道了</button></div>');
    }
  }
  $("#banners").innerHTML = parts.slice(0, 1).join("");
}

/* ---------------------------------------------------------------- 动作 */
