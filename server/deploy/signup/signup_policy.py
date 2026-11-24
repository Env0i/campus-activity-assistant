#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器自动报名的黄金风暴、全速、404 自适应状态机与响应分类。

纯调度与记账，不做任何 I/O，与本机提交节奏保持同一套阶段/字段契约（独立实现）。
@author Author
"""

# ---------------------------------------------------------------------------
# 黄金风暴 / 常规全速 / 404 自适应（2026-10-28 用户确认方案，与本机契约一致）
#
# 开放瞬间 0~1.6 秒内最多 10 轮、最小间隔 90ms；随后 180ms 常规全速；
# 连续 3 次 404 视为接口未就绪/限流，1.6 倍指数退避、上限 3 秒，并把有效
# 窗口自动扩到起点起 25 分钟；收到非 404 真实响应立即切回全速。
# sign_end 永远是硬截止，扩窗不得越过它。
# ---------------------------------------------------------------------------

GOLDEN_WINDOW_S = 1.6            # 开放后黄金窗口
GOLDEN_INTERVAL_S = 0.09         # 黄金阶段最小间隔（90ms）
GOLDEN_ROUNDS = 10               # 黄金阶段最多轮次
FULL_SPEED_INTERVAL_S = 0.18     # 常规全速最小间隔（180ms）
NOT_READY_404_LIMIT = 3          # 连续 404 视为接口未就绪
BACKOFF_FACTOR = 1.6             # 自适应退避倍率
BACKOFF_MAX_S = 3.0              # 自适应退避上限
ADAPTIVE_WINDOW_S = 1500.0       # 自适应扩窗上限（25 分钟）


class BurstPolicy:
    """黄金风暴/常规全速/404 自适应的显式状态机与真实请求记账。

    纯调度与记账，不做任何 I/O：时间读数全部走注入的 clock（单测里是虚拟
    时钟，绝不真实 sleep 1.6 秒）。四个阶段 golden / full_speed /
    adaptive_backoff / terminal 的转移规则见类常量上方注释。

    不变量：
    * attempts 只数真正发出过的 signUp 请求，单调递增；
    * pending 里每笔都有唯一 request_id，响应按归属结算，乱序合法；
    * 同一 request 重复通知只算一次；别家响应不改本场结论；
    * effective_deadline 只会因自适应扩窗变大，且永不越过 sign_end；
    * hard_deadline 一旦冻结就不再改写，sign_end 截止永远优先于扩窗；
    * 进入 terminal 后拒绝再发起任何动作（用户停止同此）。
    """

    PHASE_GOLDEN = "golden"
    PHASE_FULL_SPEED = "full_speed"
    PHASE_ADAPTIVE = "adaptive_backoff"
    PHASE_TERMINAL = "terminal"

    def __init__(self, open_ts, base_deadline, sign_end_ts=None,
                 max_attempts=0, clock=None, retry_start=None):
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

    # -- 时间读数 ---------------------------------------------------------
    def _now(self):
        if self._clock is None:
            import time as _time
            return _time.monotonic()
        return float(self._clock.monotonic() if hasattr(self._clock, "monotonic")
                     else self._clock())

    def _wall_now(self):
        if self._clock is None:
            import time as _time
            return _time.time()
        return float(self._clock.time() if hasattr(self._clock, "time")
                     else self._clock())

    # -- 阶段与调度 -------------------------------------------------------
    @property
    def phase(self):
        self._refresh_phase()
        return self._phase

    @property
    def round(self):
        """当前轮次计数：黄金阶段是黄金轮次，之后随真实请求递增。"""
        return self.golden_rounds if self._phase == self.PHASE_GOLDEN else self.attempts

    @property
    def backoff_s(self):
        """当前退避间隔（日志字段 backoff_s 的唯一来源）。"""
        if self._phase == self.PHASE_ADAPTIVE:
            return min(BACKOFF_MAX_S, max(FULL_SPEED_INTERVAL_S, self._backoff_s))
        return self._backoff_s

    def _refresh_phase(self):
        """按已观察事实刷新阶段；非 404 响应会让黄金/退避立即退位。"""
        if self._phase == self.PHASE_TERMINAL:
            return
        if self._phase == self.PHASE_GOLDEN:
            now = self._wall_now()
            if self.golden_rounds >= GOLDEN_ROUNDS or now >= self.open_ts + GOLDEN_WINDOW_S:
                self._phase = self.PHASE_FULL_SPEED
                self._backoff_s = FULL_SPEED_INTERVAL_S
            return
        if self._phase == self.PHASE_ADAPTIVE and self.streak_404 < NOT_READY_404_LIMIT:
            self._phase = self.PHASE_FULL_SPEED
            self._backoff_s = FULL_SPEED_INTERVAL_S

    def interval_s(self):
        """下一次尝试前必须等待的最小间隔。"""
        self._refresh_phase()
        if self._phase == self.PHASE_GOLDEN:
            return GOLDEN_INTERVAL_S
        if self._phase == self.PHASE_ADAPTIVE:
            return min(BACKOFF_MAX_S, max(FULL_SPEED_INTERVAL_S, self._backoff_s))
        return FULL_SPEED_INTERVAL_S

    def next_interval_after_wait(self):
        """等待完本次间隔后推进退避计数，返回下一轮间隔。"""
        if self._phase == self.PHASE_ADAPTIVE:
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
        """404 连击触发自适应扩窗：有效截止拉到起点起 25 分钟，sign_end 仍硬截。"""
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
        self._requests[request_id] = {"status": "pending", "kind": None,
                                      "attempt_no": self.attempts + 1}
        self.attempts += 1
        if self._phase == self.PHASE_GOLDEN:
            self.golden_rounds += 1
        return request_id

    def settle(self, request_id, kind):
        """结算一笔请求的响应归属；kind ∈ {404, real, lost}。

        乱序合法：响应可以按任意顺序回来；重复结算同一笔只认第一次。
        404 会加连击并可能进退避；real 清连击并退出退避/黄金。
        lost（响应体丢失/读不出）不结算：请求保持未决，终态如实报「未确认」。
        """
        record = self._requests.get(request_id)
        if record is None or record["status"] == "settled":
            return None
        if kind == "lost":
            record["kind"] = "lost"
            return record          # 不改 status，仍是 pending
        record["status"] = "settled"
        record["kind"] = kind
        if kind == "404":
            self.streak_404 += 1
            if self.streak_404 >= NOT_READY_404_LIMIT:
                if self._phase != self.PHASE_TERMINAL:
                    self._phase = self.PHASE_ADAPTIVE
                    self._backoff_s = min(BACKOFF_MAX_S,
                                          FULL_SPEED_INTERVAL_S * BACKOFF_FACTOR)
                self.extend_deadline_for_adaptive()
        elif kind == "real":
            self.streak_404 = 0
            if self._phase == self.PHASE_GOLDEN:
                self._phase = self.PHASE_FULL_SPEED
                self._backoff_s = FULL_SPEED_INTERVAL_S
            elif self._phase == self.PHASE_ADAPTIVE:
                self._phase = self.PHASE_FULL_SPEED
                self._backoff_s = FULL_SPEED_INTERVAL_S
        return record

    def pending_ids(self):
        return [rid for rid, rec in self._requests.items()
                if rec["status"] == "pending"]

    def pending_count(self):
        return len(self.pending_ids())

    def settled_kind(self, request_id):
        rec = self._requests.get(request_id)
        return rec["kind"] if rec and rec["status"] == "settled" else None

    def request_ids(self):
        """按发出顺序列出所有 request_id（日志/测试核对唯一性用）。"""
        return ["req-%d" % i for i in range(1, self._seq + 1)]

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


def classify_response(response):
    """把一次 signUp 响应归类为 404 / real / lost。

    HTTP 404 明确是「接口未就绪/限流」；其余 HTTP 状态（含 200+JSON、
    5xx）都算真实响应，必须结束黄金阶段。响应体丢失时不能挂成 404。
    """
    if response is None:
        return "lost"
    status = getattr(response, "status", 200)
    try:
        status_code = int(status)
    except (TypeError, ValueError):
        status_code = 200
    return "404" if status_code == 404 else "real"
