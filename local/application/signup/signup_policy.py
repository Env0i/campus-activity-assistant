# -*- coding: utf-8 -*-
"""报名 worker 的提交节奏状态机 BurstPolicy 与 13 个节奏常量。

从 grab.py 搬出，是黄金风暴 / 常规全速 / 404 自适应退避 / 5xx 降速地板与
13 个节奏常量的唯一来源。告警写日志与「业务时钟读数无效」异常通过两个可被
子类覆盖的钩子（_log 与 _clock_error）延迟解析，本模块不 import grab 或
business_clock，也不在 import 时绑定外部函数。

@author Author
"""
from __future__ import annotations

import math

from domain.signup.retry_window import ADAPTIVE_SECONDS

# ---------------------------------------------------------------------------
# 黄金风暴 / 常规全速 / 404 自适应（2026-10-28 用户确认方案）
#
# 开放瞬间 0~1.6 秒内最多 10 轮、最小间隔 90ms；随后 180ms 常规全速；
# 连续 3 次 404 视为接口未就绪/限流，1.6 倍指数退避、上限 3 秒，并把有效
# 窗口自动扩到起点起 25 分钟；收到非 404 真实响应立即切回全速。
# sign_end 永远是硬截止，扩窗不得越过它。
#
# 旧 RC-05（2 秒起、1.5 倍、8 秒封顶）纯函数保留在 grab.py 不动：test_retry_policy
# 直接锁定它们的数值契约。
# ---------------------------------------------------------------------------

GOLDEN_WINDOW_S = 1.6            # 开放后黄金窗口
GOLDEN_INTERVAL_S = 0.09         # 黄金阶段最小间隔（90ms）
GOLDEN_ROUNDS = 10               # 黄金阶段最多轮次
FULL_SPEED_INTERVAL_S = 0.18     # 常规全速最小间隔（180ms）
NOT_READY_404_LIMIT = 3          # 连续 404 视为接口未就绪
BACKOFF_FACTOR = 1.6             # 自适应退避倍率
BACKOFF_MAX_S = 3.0              # 自适应退避上限
ADAPTIVE_WINDOW_S = ADAPTIVE_SECONDS   # 自适应扩窗上限（25 分钟）
# --- v4 直发核心：调度账本与降速地板（§3/§5/§12）---
SERVER_ERROR_MIN_GAP_S = 0.5     # 5xx 之后的最小间隔地板
ADAPTIVE_IN_GOLDEN = False       # golden 内默认不进 adaptive（真实 200 才退黄金）
MAX_INFLIGHT_DEFAULT = 2
INFLIGHT_TTL_S = 8.0             # 非 lost pending 超过此时长不再占发射名额
NOT_READY_SLOWDOWN_AFTER_S = 20.0  # 纯 404 段持续超过此时长开始降速
NOT_READY_SLOW_GAP_S = 0.8         # 纯 404 慢未就绪的最小间隔地板


class BurstPolicy:
    """黄金风暴/常规全速/404 自适应的显式状态机与真实请求记账。

    纯调度与记账，不做任何 I/O：时间读数全部走注入的 clock（单测里是虚拟
    时钟，绝不真实 sleep 1.6 秒）。四个阶段 golden / full_speed /
    adaptive_backoff / terminal 的转移规则见类常量上方注释。

    不变量：
    * attempts 只数真正发出过的 signUp 请求，单调递增；
    * pending 里每笔都有唯一 request_id，响应按归属结算，乱序合法；
    * 同一 request 重复结算只算一次；别家响应不改本场结论；
    * effective_deadline 只会因自适应扩窗变大，且永不越过 sign_end；
    * hard_deadline 一旦冻结就不再改写，sign_end 截止永远优先于扩窗；
    * 进入 terminal 后拒绝再发起任何动作（用户停止同此）；
    * 登记序 == 发送序（attempt_no 严格递增），倒扫 _order 即倒序扫发送序
      ——这是乱序结算安全（F06 5xx 地板、连击重算）的前提。
    """

    PHASE_GOLDEN = "golden"
    PHASE_FULL_SPEED = "full_speed"
    PHASE_ADAPTIVE = "adaptive_backoff"
    PHASE_TERMINAL = "terminal"
    _clock_error = RuntimeError

    def _log(self, msg):
        """告警输出钩子：子类在调用时读取外层日志函数，不在 import 时绑定。"""
        return None

    def __init__(self, open_ts, base_deadline, sign_end_ts=None,
                 max_attempts=0, clock=None, retry_start=None,
                 allow_extend=True):
        self._clock = clock
        self.open_ts = float(open_ts)
        self.retry_start = float(retry_start if retry_start is not None else open_ts)
        self.sign_end_ts = float(sign_end_ts) if sign_end_ts else None
        self.max_attempts = int(max_attempts or 0)
        self.hard_deadline = float(base_deadline)
        if self.sign_end_ts:
            self.hard_deadline = min(self.hard_deadline, self.sign_end_ts)
        self.effective_deadline = self.hard_deadline
        self.attempts = 0
        self.streak_404 = 0
        self.golden_rounds = 0
        self._phase = self.PHASE_GOLDEN
        self._backoff_s = FULL_SPEED_INTERVAL_S
        self._requests = {}
        self._seq = 0
        self._stopped = False
        # 显式 --retry-for 时禁扩窗（用户给的秒数是硬承诺，不被自适应拉长）
        self._allow_extend = bool(allow_extend)
        # §5 5xx 降速地板（倒扫派生，见 _derive_min_gap）
        self._min_gap = 0.0
        # 发送序（只追加，绝不重排/删除）与相关缓存
        self._order = []
        self._last_attempt_no = 0
        self._level_prev = False            # 上一次 _apply_level 的 ungated 电平
        self._seg_has_throttled = False     # 缓存：最新连击段内是否出现 429
        self._seg_oldest_issued = None      # 缓存：最新连击段最旧 issued_at

    # -- 时间读数 ---------------------------------------------------------
    def _now(self):
        if self._clock is None:
            import time as _time
            return _time.monotonic()
        return float(self._clock.monotonic() if hasattr(self._clock, "monotonic")
                     else self._clock())

    def _wall_now(self):
        """业务墙上时钟读数：只认 clock.now()（业务 epoch），不回退墙钟。

        clock 不可用或读数无效（None/NaN/±inf/无法转换）时抛 _clock_error
        （由上层统一转 unconfirmed），绝不静默回退 time.time()——那会让扩窗/截止
        在时钟失效时偷偷按真实墙钟走，破坏「时钟不可用即停止发射」的契约。
        """
        if self._clock is None:
            import time as _time
            return _time.time()
        if hasattr(self._clock, "now"):
            raw = self._clock.now()
        else:
            raw = self._clock()
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise self._clock_error("业务时钟读数无效")
        if not math.isfinite(value):
            raise self._clock_error("业务时钟读数无效")
        return value

    def _elapsed(self):
        """单调时钟读数（issued_at/TTL/慢地板用），永不抛 ClockUnavailable。"""
        return float(self._clock.elapsed_s()) if self._clock is not None else self._now()

    # -- 发送序倒扫（乱序安全的核心） ---------------------------------------
    def _recompute_streak(self):
        """按发送序（新→旧）倒扫 _order，返回最新连击段的 (长度, 含429, 最旧issued_at)。

        与登记序同口径：首个已结算的非 404/throttled（更新的 real/server_error）
        断连击——止步于此，更旧的段不看。pending/lost 跳过（不参与判定）。
        """
        n = 0
        has_throttled = False
        oldest_issued = None
        for rid in reversed(self._order):
            rec = self._requests[rid]
            if rec["status"] != "settled":
                continue                     # pending / lost：不看
            if rec["kind"] not in ("404", "throttled"):
                break                        # 更新的 real/5xx：段已断
            n += 1
            if rec["kind"] == "throttled":
                has_throttled = True
            issued = rec.get("issued_at")
            if issued is not None and (oldest_issued is None or issued < oldest_issued):
                oldest_issued = issued
        return n, has_throttled, oldest_issued

    def _derive_min_gap(self):
        """5xx 降速地板：按发送序倒扫，最新「有定论」的记录说了算（§5/F06）。

        倒扫取最新有定论者，天然乱序安全：
        - server_error（5xx）→ 0.5；
        - 404 且状态码==404（未就绪）或 real 且状态码==200（干净成功）→ 0；
        - throttled(429) / 非200 real / 无状态码 bare404 → 跳过（看更旧）；
        - 全部跳过（从未有定论）→ 0。
        替代 feature 的事件式 _note_min_gap/_clear_min_gap（旧 5xx 晚到会在新
        200 之后错误置 0.5 的 F06 缺陷）。
        """
        for rid in reversed(self._order):
            rec = self._requests[rid]
            if rec["status"] != "settled":
                continue                     # pending/lost：跳过
            kind = rec["kind"]
            status = rec.get("http_status")
            if kind == "server_error":
                return SERVER_ERROR_MIN_GAP_S
            if kind == "404" and status == 404:
                return 0.0
            if kind == "real" and status == 200:
                return 0.0
            # throttled / non-200 real / bare 404 → 跳过，看更旧
            continue
        return 0.0

    # -- 阶段与调度 -------------------------------------------------------
    @property
    def phase(self):
        self._apply_level()
        return self._phase

    def current_phase(self):
        """只读返回当前 phase，不触发 _apply_level（回调路径不读时钟）。"""
        return self._phase

    def _golden_time_up(self):
        """黄金墙钟是否已到点；clock 不可用时返回 False（保守留在 golden）。"""
        try:
            return self._wall_now() >= self.open_ts + GOLDEN_WINDOW_S
        except Exception:
            return False

    def _apply_level(self):
        """电平/边沿两层重算：streak、5xx 地板、种子边沿、golden 退出、phase。

        电平：当前事实直接决定 level（ungated = streak>=3 且段内含 429）。
        边沿：level 从 false→true 才给退避种子，true→false 且非 ADAPTIVE 才清——
        否则单个 429 每次重算都重置退避/清种子，把种子语义打碎。
        """
        if self._stopped or self._phase == self.PHASE_TERMINAL:
            return
        n, has_throttled, oldest_issued = self._recompute_streak()
        self.streak_404 = n
        self._seg_has_throttled = has_throttled
        self._seg_oldest_issued = oldest_issued
        self._min_gap = self._derive_min_gap()
        ungated = n >= NOT_READY_404_LIMIT and has_throttled
        # 边沿：false→true 给种子；true→false 且非 ADAPTIVE 清种子
        if ungated and not self._level_prev:
            self._backoff_s = self._seed_backoff()
        elif (not ungated and self._level_prev
              and self._phase != self.PHASE_ADAPTIVE):
            self._backoff_s = FULL_SPEED_INTERVAL_S
        self._level_prev = ungated
        # golden：默认不进 adaptive（ADAPTIVE_IN_GOLDEN=False）；轮数/墙钟到点退位
        if self._phase == self.PHASE_GOLDEN:
            if self.golden_rounds >= GOLDEN_ROUNDS or self._golden_time_up():
                self._exit_golden()
            return
        self._refresh_phase(ungated)

    def _exit_golden(self):
        """golden 的唯一出口：退到 FULL_SPEED，按当前事实决定是否带种子进 adaptive。

        统一从这里退出，避免路径分叉把 golden 内累积的种子清掉。
        """
        if self._phase != self.PHASE_GOLDEN:
            return
        self._phase = self.PHASE_FULL_SPEED
        n, has_throttled, _ = self._recompute_streak()
        ungated = n >= NOT_READY_404_LIMIT and has_throttled
        self._refresh_phase(ungated)
        if ungated and self._backoff_s == FULL_SPEED_INTERVAL_S:
            self._backoff_s = self._seed_backoff()

    def _refresh_phase(self, ungated):
        """按已重算的 ungated 电平刷 phase。gated 必须在退出 golden 之后判定。

        ADAPTIVE_IN_GOLDEN=False（§3 常量开关）⇒ gated 的第二项恒假，即 golden
        内永不进 ADAPTIVE；改成 True 才会让 golden 内的段也切 phase（死分支，
        留着是为了让开关真的能切，不是遗留代码）。
        """
        in_golden_ok = ADAPTIVE_IN_GOLDEN if self._phase == self.PHASE_GOLDEN else True
        if ungated and in_golden_ok:
            if self._phase != self.PHASE_ADAPTIVE:
                self._phase = self.PHASE_ADAPTIVE
        else:
            if self._phase == self.PHASE_ADAPTIVE:
                self._phase = self.PHASE_FULL_SPEED
                self._backoff_s = FULL_SPEED_INTERVAL_S

    def _seed_backoff(self):
        """退避种子值：一段含 throttled 的连击降速后从这里起步。"""
        return min(BACKOFF_MAX_S, FULL_SPEED_INTERVAL_S * BACKOFF_FACTOR)

    def interval_s(self):
        """下一次尝试前必须等待的最小间隔（base / 5xx 地板 / 纯404慢地板 取 max）。"""
        self._apply_level()
        if self._phase == self.PHASE_GOLDEN:
            base = GOLDEN_INTERVAL_S
        elif self._phase == self.PHASE_ADAPTIVE:
            base = min(BACKOFF_MAX_S, max(FULL_SPEED_INTERVAL_S, self._backoff_s))
        else:
            base = FULL_SPEED_INTERVAL_S
        # §12：纯 404 段一直未就绪（服务器晚开几分钟）时降速到 0.8s 地板——
        # 段内一旦混进 throttled 就交给退避，出现 real 立即随连击清零而解除。
        slow_floor = 0.0
        if (self.streak_404 > 0 and not self._seg_has_throttled
                and self._seg_oldest_issued is not None):
            age_s = self._elapsed() - self._seg_oldest_issued
            if age_s > NOT_READY_SLOWDOWN_AFTER_S:
                slow_floor = NOT_READY_SLOW_GAP_S
        # §5：5xx 后的最小间隔地板，与退避/黄金/慢未就绪取 max
        return max(base, self._min_gap, slow_floor)

    def next_interval_after_wait(self):
        """等待完本次间隔后推进退避计数，返回下一轮间隔。"""
        if self._phase == self.PHASE_ADAPTIVE:
            if self._level_prev and self._backoff_s == FULL_SPEED_INTERVAL_S:
                # 段内种子边沿已消耗（_backoff_s 已是 seed），此处只兜底
                # 进 ADAPTIVE 时按 level 重放种子，否则从全速起步被错算成「无退避」
                self._backoff_s = self._seed_backoff()
            self._backoff_s = min(BACKOFF_MAX_S,
                                  max(FULL_SPEED_INTERVAL_S, self._backoff_s) * BACKOFF_FACTOR)
        return self.interval_s()

    def can_attempt(self):
        """是否还允许发起新的一次提交（次数/截止/停止都算）。"""
        if self._stopped or self._phase == self.PHASE_TERMINAL:
            return False
        if self.attempts >= self.max_attempts > 0:
            return False
        if self._wall_now() >= self.effective_deadline:
            return False
        return True

    def extend_deadline_for_adaptive(self):
        """404 连击触发自适应扩窗：有效截止拉到起点起 25 分钟，sign_end 仍硬截。

        显式 --retry-for 时（allow_extend=False）整条扩窗路径不生效：
        用户给的秒数是硬承诺，不能被自适应偷偷拉长。
        """
        if not self._allow_extend:
            return self.effective_deadline
        target = self.retry_start + ADAPTIVE_WINDOW_S
        if self.sign_end_ts:
            target = min(target, self.sign_end_ts)
        if target > self.effective_deadline:
            self.effective_deadline = target
        return self.effective_deadline

    # -- 请求记账 ---------------------------------------------------------
    def register_request(self):
        """为一笔真实发出的 signUp 请求分配唯一 ID 并入账。"""
        self._seq += 1
        request_id = "req-%d" % self._seq
        attempt_no = self.attempts + 1
        # 不变量：attempt_no 严格递增 ⇒ 登记序 == 发送序，倒扫 _order 才等价
        # 按发送顺序从新到旧（乱序结算的安全前提）。本方法跑在回调里，
        # assert 被 -O 剥掉或异常被吞都会漏账，所以只记日志不抛。
        if attempt_no <= self._last_attempt_no:
            self._log("attempt_no 未递增（%s → %s）：倒序重算不再等于发送序"
                      % (self._last_attempt_no, attempt_no))
        self._last_attempt_no = attempt_no
        # issued_at 只在登记时读一次单调时钟（永不抛 ClockUnavailable），
        # 供纯 404 慢地板（段起点 = 段最旧 issued_at）与 inflight TTL 复用。
        self._requests[request_id] = {"status": "pending", "kind": None,
                                      "attempt_no": attempt_no,
                                      "issued_at": self._elapsed()}
        self._order.append(request_id)   # 只追加，绝不重排/删除
        self.attempts += 1
        if self._phase == self.PHASE_GOLDEN:
            self.golden_rounds += 1
        return request_id

    def settle(self, request_id, kind, http_status=None):
        """结算一笔请求的响应归属；kind ∈ {404, throttled, server_error, real, lost}。

        乱序合法：响应可按任意顺序回来；重复结算同一笔只认第一次。
        - 404：计入连击段；连击达阈值只扩窗，不切 phase（§4）；
        - throttled：计入连击段、连击达阈值给退避种子（含 throttled 才给），
          但不结束 golden（§4）；单个 429 只结算，不单独触发退避；
        - server_error：断开连击、设 5xx 地板（§5），永不切 phase；
        - real：断开连击；http_status==200 时结束 golden 并回 FULL_SPEED（§11），
          非 200 real 只断连击、不结束 golden；
        - lost：不结算，请求保持未决，终态如实报「未确认」。
        http_status 记原始 HTTP 状态码，供 §5/§11 判定。
        """
        record = self._requests.get(request_id)
        if record is None or record["status"] == "settled":
            return None
        if http_status is not None:
            record["http_status"] = http_status
        if kind == "lost":
            record["kind"] = "lost"
            return record          # 不改 status，仍是 pending
        record["status"] = "settled"
        record["kind"] = kind
        # prev 必须在 _apply_level 之前取：_apply_level 会把重算结果写回 streak_404
        prev_len = self.streak_404
        # 连击/地板/种子/phase 全部交给 _apply_level：按发送顺序倒序重算（乱序安全），
        # 不再在 settle 里做 +=1 / =0——旧 404 后到不得重建连击，非 200 real 断连击但不退黄金（§11）。
        self._apply_level()
        if kind == "real" and http_status == 200 and self._phase == self.PHASE_GOLDEN:
            # §11：200-real 事件驱动结束 golden（接口已就绪，与它是否清连击无关）。
            self._exit_golden()
        # 扩窗边沿只看长度（§4「纯 404 段不切 phase，只扩窗」）；种子边沿在 _apply_level
        self._maybe_extend_window(prev_len, self.streak_404)
        return record

    def _maybe_extend_window(self, prev_len, new_len):
        """扩窗边沿：只看连击长度（404 与 throttled 同等计入），new>prev 每增长一次就扩一次。

        判据刻意不含 has_throttled——纯 404 也照常扩窗（§4），纯 404 的 20s→0.8s
        慢地板依赖这个能力。extend_deadline_for_adaptive 幂等且被 sign_end 硬截；
        显式 --retry-for 时整条路径不生效。
        """
        if new_len >= NOT_READY_404_LIMIT and new_len > prev_len:
            self.extend_deadline_for_adaptive()

    def pending_ids(self):
        return [rid for rid, rec in self._requests.items()
                if rec["status"] == "pending"]

    def pending_count(self):
        return len(self.pending_ids())

    def inflight_count(self):
        """占发射名额的在途请求数（§2）：pending、非 lost、且未超 INFLIGHT_TTL_S。

        lost 不占名额——页面重载/导航中止只发 requestfailed，若继续占名额，
        名额会一点点占满直到永久不发。pending 超过 INFLIGHT_TTL_S 也不占名额
        （等不回来的请求不该堵死发射），但它仍是 pending：终态如实报「未确认」，
        迟到响应照常结算。
        """
        now = self._elapsed()
        count = 0
        for rec in self._requests.values():
            if rec["status"] != "pending" or rec["kind"] == "lost":
                continue
            issued = rec.get("issued_at")
            if issued is not None and now - issued >= INFLIGHT_TTL_S:
                continue
            count += 1
        return count

    def settled_kind(self, request_id):
        rec = self._requests.get(request_id)
        return rec["kind"] if rec and rec["status"] == "settled" else None

    # -- 终态 -------------------------------------------------------------
    def stop(self, reason):
        """进入终态；之后 can_attempt() 恒 False，不再发起本场任何动作。"""
        self._stopped = True
        self._phase = self.PHASE_TERMINAL
        self.stop_reason = reason
        return reason

    @property
    def stopped(self):
        return self._stopped


def wait_before_next_submit(budget, gap: float, *, clock_unavailable, next_gap_fn) -> float:
    """按剩余预算截断等待，返回下一轮间隔（不越过 sign_end / 时长上限）。"""
    try:
        remain = budget.remaining_s()
    except clock_unavailable:
        raise
    budget.sleep(min(max(0.0, float(gap)), max(0.0, remain)))
    return next_gap_fn(gap)
