#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器直发传输：守护线程发 GET signUp，物理并发上限 2，禁止自动重定向。

不打印 token 与完整 URL；网络异常只回安全错误类别。
@author Author
"""
from __future__ import annotations

import math
import queue
import threading
import time
import urllib.error
import urllib.request

MAX_PHYSICAL_INFLIGHT = 2
MAX_TIMEOUT_S = 8.0


def build_no_redirect_opener():
    """构造绕过代理且不自动跟随重定向的 urllib opener（3xx 原样返回）。"""

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


class DirectTransport:
    """已签名直发传输：try_submit 立即返回，物理满额 / 关闭 / 重复则拒绝。"""

    def __init__(self, event_queue, opener=None, monotonic_fn=time.monotonic):
        self._queue = event_queue if event_queue is not None else queue.Queue()
        self._opener = opener if opener is not None else build_no_redirect_opener()
        self._monotonic = monotonic_fn
        self._lock = threading.Lock()
        self._active = set()
        self._seen = set()
        self._closed = False

    def try_submit(self, ticket: dict) -> bool:
        """仅在未关闭、未重复、物理并发未满上限时启动后台请求。"""
        request_id = ticket["request_id"]
        with self._lock:
            if self._closed or request_id in self._seen:
                return False
            if len(self._active) >= MAX_PHYSICAL_INFLIGHT:
                return False
            self._seen.add(request_id)
            self._active.add(request_id)
        thread = threading.Thread(target=self._run, args=(ticket,), daemon=True)
        try:
            thread.start()
        except RuntimeError:
            with self._lock:
                self._active.discard(request_id)
            return False
        return True

    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def _emit(self, ticket: dict, kind: str, **extra) -> None:
        event = {
            "kind": kind,
            "request_id": ticket.get("request_id"),
            "attempt_no": ticket.get("attempt_no"),
        }
        event.update(extra)
        self._queue.put(event)

    def _effective_timeout(self, ticket: dict, now: float) -> float:
        cand = float(ticket.get("timeout_s", MAX_TIMEOUT_S))
        budget_left = float(ticket["request_deadline"]) - now
        if math.isnan(cand) or math.isnan(budget_left):
            return float("nan")
        return min(cand, MAX_TIMEOUT_S, budget_left)

    def _run(self, ticket: dict) -> None:
        request_id = ticket["request_id"]
        committed = False
        try:
            with self._lock:
                now = self._monotonic()
                try:
                    timeout_s = self._effective_timeout(ticket, now)
                    invalid = (
                        not math.isfinite(timeout_s)
                        or timeout_s <= 0
                        or now >= float(ticket["request_deadline"])
                    )
                except Exception:
                    timeout_s = 0.0
                    invalid = True
                if self._closed or invalid:
                    self._emit(ticket, "not_started")
                    return
                self._emit(ticket, "started")
                committed = True
            self._perform(ticket, timeout_s)
        except Exception as exc:
            kind = "failed" if committed else "not_started"
            self._emit(ticket, kind, error_class=type(exc).__name__)
        finally:
            with self._lock:
                self._active.discard(request_id)

    def _perform(self, ticket: dict, timeout_s: float) -> None:
        try:
            request = urllib.request.Request(
                ticket["url"], headers=ticket.get("headers", {}), method="GET",
            )
            response = self._opener.open(request, timeout=timeout_s)
        except urllib.error.HTTPError as exc:
            self._complete_from(ticket, exc)
            return
        except Exception as exc:
            self._emit(ticket, "failed", error_class=type(exc).__name__)
            return
        self._complete_from(ticket, response)

    def _complete_from(self, ticket: dict, response) -> None:
        try:
            status = int(getattr(response, "status", None) or getattr(response, "code", 200))
            body = response.read()
        except Exception as exc:
            self._emit(ticket, "failed", error_class=type(exc).__name__)
            return
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
        self._emit(ticket, "completed", http_status=status, body_bytes=body)
