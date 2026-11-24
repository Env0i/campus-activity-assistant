/**
 * owner 私聊的「取消报名」按钮：确认卡、10 分钟有效期、结果卡。
 *
 * 为什么单独一个模块：bot.js 在代码结构名单里已经顶格，取消链路要读脚本结果、
 * 判过期、拼 toast，塞进 bot.js 必然超限。这里只依赖构造时注入的 execFile 与日志，
 * 测试可以按实例换掉假实现。
 *
 * 前置校验（点击人、会话、owner）在 bot.js 的 handleCardAction 已经做完，
 * 这里不重复实现：两处各写一份，只要有一处放松就会越权。
 *
 * @author Author
 */
const CANCEL_CONFIRM_TTL_MS = 10 * 60 * 1000;
const CANCEL_GROUP_DENIED = '群里只提供查询；取消报名只对本人私聊开放';

class CancelActions {
  constructor(deps) {
    this.deps = deps || {};
  }

  /** 跑一次 cancel_signup.py：确认卡与取消结果都只有一行 JSON。 */
  run(args) {
    const { execFile, py, appDir } = this.deps;
    return new Promise(function start(resolve) {
      execFile(py, ['scripts/signup/cancel_signup.py'].concat(args),
        { cwd: appDir, timeout: 120000, maxBuffer: 2 * 1024 * 1024 },
        function done(err, stdout, stderr) {
          resolve({
            ok: !err,
            out: String(stdout || '').trim(),
            err: String(stderr || '').trim() || (err ? String(err.message || err) : ''),
          });
        });
    });
  }

  /** 脚本约定 stdout 最后一行才是结果；前面允许有日志，解析失败一律当没有结果。 */
  lastJsonLine(out) {
    const lines = String(out || '').split('\n')
      .map(function trim(s) { return s.trim(); })
      .filter(function keep(s) { return s.length > 0; });
    if (!lines.length) return null;
    try {
      return JSON.parse(lines[lines.length - 1]);
    } catch (e) {
      return null;
    }
  }

  /** 点击入口：c:<base64> 出确认卡（不提交），x:<base64> 提交取消。 */
  async handle(data, text) {
    const { log, decodeBtnValue } = this.deps;
    let payload;
    try {
      payload = decodeBtnValue(text.slice(2));
    } catch (e) {
      log('cancel value decode failed:', e.message);
      return { toast: { type: 'error', content: '按钮数据坏了，重新打开「我的报名」再点' } };
    }
    if (!payload || !payload.i) {
      return { toast: { type: 'error', content: '按钮数据不完整' } };
    }
    const name = String(payload.n || '活动');
    return text.startsWith('c:')
      ? await this.confirm(payload, name)
      : await this.submit(payload, name);
  }

  /** 第一次点只出确认卡：用按钮自带信息生成，不查学校、不提交任何东西。 */
  async confirm(payload, name) {
    const res = await this.run([
      'confirm', '--id', String(payload.i), '--name', name,
      '--start', String(payload.s || ''),
      '--end', String(payload.e || ''),
      '--place', String(payload.p || ''),
    ]);
    const card = this.lastJsonLine(res.out);
    if (!card || !card.header) {
      this.deps.log('cancel confirm card failed:', res.err.slice(0, 200));
      return { toast: { type: 'error', content: '确认卡没能生成，稍后再试' } };
    }
    return {
      toast: { type: 'info', content: '确认后立即取消' },
      card: { type: 'raw', data: card },
    };
  }

  /** 点确认后立即换上无按钮「正在取消」卡，脚本在后台跑，结果发新私聊。 */
  submit(payload, name) {
    const { log } = this.deps;
    const issued = Number(payload.t);
    if (!issued || Date.now() - issued > CANCEL_CONFIRM_TTL_MS) {
      log('cancel confirm expired:', issued);
      return { toast: { type: 'info', content: '确认卡已过期，请重新点「取消报名」' } };
    }
    this.runInBackground(String(payload.i), name);
    return {
      toast: { type: 'info', content: '正在取消，结果稍后私聊发你' },
      card: { type: 'raw', data: submittingCard(name) },
    };
  }

  /** 后台跑取消脚本：结束后把结果卡发到 owner 私聊，出错只留日志、不重试取消。 */
  runInBackground(id, name) {
    const { log, replyCard, ownerP2pChatId } = this.deps;
    this.run(['run', '--id', id, '--name', name]).then(async (res) => {
      if (res.err) log('cancel script stderr:', res.err.slice(0, 200));
      const result = this.lastJsonLine(res.out);
      if (!result || !result.kind || !result.card) {
        log('cancel result unreadable:', res.out.slice(0, 200));
        return;
      }
      const chatId = ownerP2pChatId ? ownerP2pChatId() : '';
      if (!chatId || !replyCard) {
        log('cancel result skipped: missing owner chatId or replyCard');
        return;
      }
      const sent = await replyCard(chatId, result.card);
      if (!sent) log('cancel result private send failed');
    }).catch((err) => {
      log('cancel background error:', err && err.message ? err.message : err);
    });
  }

  /** 私聊点「我的报名」按钮：先回执，再在后台按文字查询路径发新私聊。 */
  queryMine(chatId) {
    const { log, answer, ownerP2pChatId } = this.deps;
    const target = (ownerP2pChatId && ownerP2pChatId()) || chatId;
    if (target && answer) {
      Promise.resolve().then(() => answer(target, 'mine', '')).catch((err) => {
        log('mine button background error:', err && err.message ? err.message : err);
      });
    }
    return { toast: { type: 'info', content: '正在查「我的报名」，稍后私聊发你' } };
  }
}

function submittingCard(name) {
  return {
    config: { wide_screen_mode: true },
    header: {
      template: 'grey',
      title: { tag: 'plain_text', content: '正在取消' },
      subtitle: { tag: 'plain_text', content: '稍后私聊发你结果' },
    },
    elements: [
      { tag: 'div', text: { tag: 'lark_md',
        content: `**${name || '活动'}**\n正在提交取消，结果马上发到你的私聊。` } },
      { tag: 'note', elements: [{ tag: 'plain_text', content: '只对本人生效' }] },
    ],
  };
}

module.exports = { CancelActions, CANCEL_GROUP_DENIED, CANCEL_CONFIRM_TTL_MS };
