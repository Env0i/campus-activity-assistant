# -*- coding: utf-8 -*-
"""学校 HTTP 请求层：直连 opener、网关签名、POST/GET 与 HTTP Date 粗校时。

学校接口必须绕开系统代理直连；网关签名算法与常量语义保持官网登录页一致，
`urllib` 与 `time` 一律由调用方按调用时命名空间传入，避免在模块导入时绑定而
切断测试对 `grab.urllib`、`grab.time` 或请求端口的替换接缝。

@author Author
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from email.utils import parsedate_to_datetime


def school_open(request, *, urllib_mod, timeout=None):
    """学校请求统一走「不走代理」的 opener。

    系统代理（Clash/公司代理）会把校内域名当外网转发或改写请求身份，现象是
    「浏览器能进、脚本 401」。更新检查、组件下载与飞书通知仍用 urllib 默认
    opener（跟随环境变量与 Windows 系统代理）。

    每次都按当前 urllib 现建 opener，而不是模块导入时建一次：测试替换
    grab.urllib 成替身时这条路径同样生效（替身没有 build_opener 就退回 urlopen）。
    """
    build_opener = getattr(urllib_mod.request, "build_opener", None)
    handler = getattr(urllib_mod.request, "ProxyHandler", None)
    if build_opener is None or handler is None:
        return urllib_mod.request.urlopen(request, timeout=timeout)
    return build_opener(handler({})).open(request, timeout=timeout)


def hmac_sha256_hex(message: bytes, key: bytes) -> str:
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def xor_base64(value: str, key: str) -> str:
    """复现官网 K0：按字符异或后按 Latin1 字节做 Base64。"""
    mixed = "".join(chr(ord(value[i]) ^ ord(key[i % len(key)]))
                    for i in range(len(value)))
    return base64.b64encode(mixed.encode("latin-1")).decode("ascii")


def encode_x_token(signature_hex: str, path: str, nonce: str, *,
                   client_key: str, hmac_fn=hmac_sha256_hex,
                   xor_fn=xor_base64) -> str:
    encoded = base64.b64encode(signature_hex.encode("utf-8")).decode("ascii")
    mask = hmac_fn(
        (path + "|" + nonce).encode("utf-8"),
        client_key.encode("utf-8"),
    )[:16]
    return xor_fn(encoded, mask)[::-1]


# 注意：这套网关签名的 canonical 里方法写死为 POST，只能给 _post 用；
# 直发 signUp 是 GET、本来就不带这四个头，不能把它原样挪给 GET，否则会静默算错。
def sign_request_headers(path: str, body: bytes, timestamp_ms: int, nonce: str, *,
                         raw_key: str, client_key: str,
                         hmac_fn=hmac_sha256_hex, encode_fn=None) -> dict:
    """按官网登录页 Z0 算法生成四个网关请求头。"""
    page_ticket = hmac_fn(
        raw_key.encode("utf-8"),
        client_key.encode("utf-8"),
    )
    body_hash = hashlib.sha256(body or b"").hexdigest()
    canonical = "\n".join(("POST", str(path), str(timestamp_ms), str(nonce),
                           body_hash, page_ticket))
    derived_key = hmac_fn(
        (page_ticket + "|" + str(int(timestamp_ms) // 1000) + "|"
         + str(path) + "|" + str(nonce)).encode("utf-8"),
        client_key.encode("utf-8"),
    )
    signature = hmac_fn(canonical.encode("utf-8"),
                        derived_key.encode("utf-8"))
    if encode_fn is None:
        x_token = encode_x_token(signature, str(path), str(nonce),
                                 client_key=client_key, hmac_fn=hmac_fn)
    else:
        x_token = encode_fn(signature, str(path), str(nonce))
    return {
        "X-Page-Ticket": page_ticket,
        "X-Timestamp": str(timestamp_ms),
        "X-Nonce": str(nonce),
        "X-Token": x_token,
    }


def request_nonce(*, time_mod) -> str:
    seed = "%d-%s-%s" % (int(time_mod.time() * 1000),
                         secrets.token_hex(8), secrets.token_hex(8))
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def _build_post_request(path, payload, *, api: str, referer: str, ua: str,
                        tok, get_token, sign_headers_fn, nonce_fn,
                        time_mod, urllib_mod):
    # JSON.stringify 的紧凑格式是签名 bodyHash 的输入；先定字节，再签名和发送。
    body = json.dumps(payload if payload is not None else {}, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    req = urllib_mod.request.Request(api + path, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/plain, */*")
    tok_value = tok if tok is not None else get_token()
    if tok_value:
        req.add_header("token", tok_value)
    req.add_header("Referer", referer)
    req.add_header("User-Agent", ua)
    req_headers = sign_headers_fn(path, body, int(time_mod.time() * 1000),
                                  nonce_fn())
    for name, value in req_headers.items():
        req.add_header(name, value)
    return req


def _decode_http_error(exc) -> dict:
    try:
        raw = exc.read().decode("utf-8", "replace")
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {
            "code": -1, "message": "HTTPError"
        }
    except Exception:
        return {"code": -1, "message": "HTTPError"}


def school_post(path, payload=None, tok=None, timeout=None, budget=None, *,
                api: str, referer: str, ua: str, get_token,
                sign_headers_fn, nonce_fn, open_fn, remember_date_fn,
                budget_exhausted_cls, time_mod, urllib_mod):
    """POST/GET 共用入口；传 budget 时超时被压进剩余预算。

    预算耗尽抛 BudgetExhausted，且不被本函数的通用 except 吞掉——
    否则「窗口到点」会被伪装成一次接口异常。
    """
    if budget is not None:
        timeout = budget.timeout_s(15 if timeout is None else timeout)
    req = _build_post_request(
        path, payload, api=api, referer=referer, ua=ua, tok=tok,
        get_token=get_token, sign_headers_fn=sign_headers_fn,
        nonce_fn=nonce_fn, time_mod=time_mod, urllib_mod=urllib_mod,
    )
    try:
        # timeout 可由调用方按剩余预算收紧：固定 15 秒会在 2 秒窗口里
        # 一次查询就把流程拖出截止（R03）
        resp = open_fn(req, timeout=15 if timeout is None else float(timeout))
        try:
            # L2：列表分页回包的 Date 头只侧带出来给列表筛选用，不改返回结构
            headers = getattr(resp, "headers", None)
            if headers is not None:
                remember_date_fn(headers.get("Date"))
            raw = resp.read().decode("utf-8", "replace")
        finally:
            resp.close()
        return json.loads(raw)
    except budget_exhausted_cls:
        raise
    except urllib_mod.error.HTTPError as exc:
        return _decode_http_error(exc)
    except Exception as exc:
        return {"code": -1, "message": type(exc).__name__}


def school_get(path, tok=None, timeout=None, *, api: str, referer: str, ua: str,
               get_token, open_fn, urllib_mod):
    """GET：详情接口（只读）与取消报名（run_cancel，唯一的写用途）共用；
    失败返回 code=-1 由调用方降级。取消接口不重试，成败以随后的复查为准。

    不打印 URL 之外的任何请求头；token 只在内存里使用，绝不进日志。
    """
    req = urllib_mod.request.Request(api + path, method="GET")
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("token", tok if tok is not None else get_token())
    req.add_header("Referer", referer)
    req.add_header("User-Agent", ua)
    try:
        resp = open_fn(req, timeout=15 if timeout is None else float(timeout))
        try:
            raw = resp.read().decode("utf-8", "replace")
        finally:
            resp.close()
        return json.loads(raw)
    except Exception as exc:
        return {"code": -1, "message": type(exc).__name__}


def _evaluate_http_date_offset(result: dict, raw, started_wall: float,
                               received_wall: float, rtt: float) -> dict:
    """基于 HTTP Date 与 RTT 计算偏移、不确定区间并给出粗校时判定。"""
    if not raw:
        result["detail"] = "服务器没有返回 Date"
        return result
    remote = parsedate_to_datetime(raw).timestamp()
    offset = remote - (started_wall + received_wall) / 2.0
    # 整秒分辨率最多丢 1 秒；往返延迟按一半计入不确定区间
    uncertainty = rtt / 2.0 + 1.0
    result["offset_s"] = round(offset, 3)
    result["uncertainty_s"] = round(uncertainty, 3)
    # 往返太慢时，中点估计已经不能支撑「慢几秒」这种结论
    if rtt > 2.0:
        result["detail"] = "往返耗时过长，只能算粗校验"
        return result
    low = abs(offset) - uncertainty
    high = abs(offset) + uncertainty
    if low > 3.0:
        result["state"] = "warn"
        result["detail"] = "差值区间整体超过 3 秒"
    elif high <= 3.0:
        result["state"] = "ok"
    else:
        result["detail"] = "差值区间跨过 3 秒阈值，无法断定"
    return result


def clock_sample(timeout_s=6.0, *, base: str, ua: str, open_fn,
                 time_mod, urllib_mod) -> dict:
    """用 HTTP Date 做一次粗校时，返回结构化结论（不调整任何本地时间）。

    HTTP Date 只有整秒分辨率，且响应里的时刻对应「服务器生成响应」，
    本机只能观测到发出请求和收到响应两个时刻。因此：

    * 偏移估计取区间中点，误差至少包含往返耗时的一半与整秒截断的 1 秒；
    * 差值的可信区间跨过告警阈值时，只能说「不确定」，不能断言本机慢 N 秒；
    * 没有 Date、解析失败、请求失败或往返太慢，一律 unknown。

    这不是精确对时，也绝不自动把差值加到报名时刻上。
    """
    started_wall = time_mod.time()
    started_mono = time_mod.monotonic()
    result = {
        "source": "http_date",
        "checked_at": started_wall,
        "rtt_s": None,
        "offset_s": None,
        "uncertainty_s": None,
        "state": "unknown",
        "detail": "",
    }
    try:
        req = urllib_mod.request.Request(base + "/stu/", method="HEAD")
        req.add_header("User-Agent", ua)
        resp = open_fn(req, timeout=max(0.5, float(timeout_s)))
        try:
            raw = resp.headers.get("Date")
        finally:
            resp.close()
        received_wall = time_mod.time()
        rtt = time_mod.monotonic() - started_mono
        result["rtt_s"] = round(rtt, 3)
        return _evaluate_http_date_offset(result, raw, started_wall, received_wall, rtt)
    except Exception as exc:  # noqa: BLE001 - 校时失败只影响提示，不影响报名
        result["detail"] = type(exc).__name__
        return result


def clock_skew(*, sample_fn):
    """兼容旧调用：只取偏移估计；没有可信样本返回 None。"""
    sample = sample_fn()
    return sample.get("offset_s") if sample.get("state") != "unknown" else None
