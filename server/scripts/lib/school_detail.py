"""学校详情、报名状态与取消三个接口的服务器端实现。

列表接口在 fetch.py；这里补 getInfo（签到签退与报名起止）、getJoinInfo（是否已报名）
和 cancel（取消报名）。请求构造与请求头照本机同口径：GET 只带 token / Referer /
User-Agent，POST 再额外带官网登录页公开的四个网关签名头（X-Page-Ticket、X-Timestamp、
X-Nonce、X-Token）。签名只用标准库实现，不引入依赖。

所有失败都抛 SchoolRequestError 的子类，由调用方决定怎么降级：这里不把失败伪装成
code=-1 的回包，也不打印请求头、token 或活动名。取消接口只发一次，重试由调用方按
「成败以复查为准」的口径决定——本模块绝不自动重试。

@author Author
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from common import (API_BASE, REFERER, SITE_CONFIGURED, USER_AGENT,
                    load_session)

# 三个接口的路径（拼在 API_BASE 之后），与学校前端实际调用一致。
DETAIL_PATH = "/rjyHd/getInfo/"
JOIN_INFO_PATH = "/rjyHdCyr/getJoinInfo/"
CANCEL_PATH = "/rjyHdCyr/cancel/"

# 官网入口脚本公开的请求安全参数。它们只保护请求完整性，不替代登录态 token；
# 页面脚本更新后若更换，必须重新核对并同步本机那份常量。
REQUEST_SECURITY_RAW_KEY = "7afdca069faa4acb8c0ab09322636245"
REQUEST_SECURITY_CLIENT_KEY = "Pq3Zk2A9xML7"

DEFAULT_TIMEOUT = 15.0


class SchoolRequestError(Exception):
    """学校请求失败的总类：调用方必须显式处理，不能当成功。"""

    kind = "error"

    def __init__(self, detail=""):
        super().__init__(str(detail))
        self.detail = str(detail)


class SchoolConfigError(SchoolRequestError):
    """站点未配置或没有登录态：一个请求都不该发出去。"""

    kind = "config"


class SchoolNetworkError(SchoolRequestError):
    """网络层失败（超时、连接被拒、DNS）：结果未知。"""

    kind = "network"


class SchoolHTTPError(SchoolRequestError):
    """HTTP 状态码不是 2xx；body 只留前 200 字供日志诊断。"""

    kind = "http"

    def __init__(self, status, body=""):
        super().__init__("HTTP %s" % status)
        self.status = int(status or 0)
        self.body = str(body or "")[:200]


class SchoolPayloadError(SchoolRequestError):
    """回包不是 JSON 对象：解析失败与接口异常分开报。"""

    kind = "payload"


def _require_token(token):
    value = str(token or "").strip()
    if not value:
        raise SchoolConfigError("缺少登录态")
    return value


def _hmac_hex(message, key):
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _xor_base64(value, key):
    """复现官网 K0：按字符异或后按 Latin1 字节做 Base64。"""
    mixed = "".join(chr(ord(value[i]) ^ ord(key[i % len(key)]))
                    for i in range(len(value)))
    return base64.b64encode(mixed.encode("latin-1")).decode("ascii")


def _x_token(signature, path, nonce):
    encoded = base64.b64encode(signature.encode("utf-8")).decode("ascii")
    mask = _hmac_hex((path + "|" + nonce).encode("utf-8"),
                     REQUEST_SECURITY_CLIENT_KEY.encode("utf-8"))[:16]
    return _xor_base64(encoded, mask)[::-1]


def sign_headers(path, body, timestamp_ms=None, nonce=None):
    """按官网算法生成四个网关请求头：canonical 里的方法写死 POST。

    timestamp_ms 与 nonce 只在测试里传入；正常调用按当前毫秒时间与随机串生成。
    """
    raw_key = REQUEST_SECURITY_RAW_KEY.encode("utf-8")
    client_key = REQUEST_SECURITY_CLIENT_KEY.encode("utf-8")
    ts = int(timestamp_ms if timestamp_ms is not None else time.time() * 1000)
    if not nonce:
        seed = "%d-%s" % (ts, secrets.token_hex(16))
        nonce = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
    page_ticket = _hmac_hex(raw_key, client_key)
    body_hash = hashlib.sha256(body or b"").hexdigest()
    canonical = "\n".join(("POST", str(path), str(ts), str(nonce),
                           body_hash, page_ticket))
    derived = _hmac_hex((page_ticket + "|" + str(ts // 1000) + "|"
                         + str(path) + "|" + str(nonce)).encode("utf-8"),
                        client_key)
    signature = _hmac_hex(canonical.encode("utf-8"), derived.encode("utf-8"))
    return {
        "X-Page-Ticket": page_ticket,
        "X-Timestamp": str(ts),
        "X-Nonce": str(nonce),
        "X-Token": _x_token(signature, str(path), str(nonce)),
    }


def _headers(token, extra=None):
    headers = {"Accept": "application/json, text/plain, */*",
               "token": token, "Referer": REFERER, "User-Agent": USER_AGENT}
    headers.update(extra or {})
    return headers


def _open(req, timeout):
    """学校请求绕开系统代理直连；单独成函数，测试可以整体替换掉网络。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=float(timeout)) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:      # noqa: BLE001 - 读错误体失败不影响错误类型
            body = ""
        raise SchoolHTTPError(exc.code, body) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise SchoolNetworkError(type(exc).__name__) from exc


def _parse(raw):
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise SchoolPayloadError("回包不是 JSON") from exc
    if not isinstance(data, dict):
        raise SchoolPayloadError("回包不是对象")
    return data


def _get(path, token, timeout):
    if not SITE_CONFIGURED:
        raise SchoolConfigError("未配置目标学校站点")
    req = urllib.request.Request(API_BASE + path, headers=_headers(_require_token(token)),
                                 method="GET")
    return _parse(_open(req, timeout))


def get_detail(activity_id, token, timeout=DEFAULT_TIMEOUT):
    """getInfo：签到签退要求与报名起止时间。读不出内容时抛错，返回空字典不猜。"""
    aid = str(activity_id or "").strip()
    if not aid:
        raise SchoolRequestError("缺少活动 id")
    return _get(DETAIL_PATH + urllib.parse.quote(aid, safe=""), token, timeout)


def get_join_info(activity_id, token, timeout=DEFAULT_TIMEOUT):
    """getJoinInfo：是否已报名。POST 必须带网关签名头，回包结构交给调用方判。"""
    aid = str(activity_id or "").strip()
    if not aid:
        raise SchoolRequestError("缺少活动 id")
    if not SITE_CONFIGURED:
        raise SchoolConfigError("未配置目标学校站点")
    path = JOIN_INFO_PATH + aid
    body = json.dumps({}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    extra = {"Content-Type": "application/json"}
    extra.update(sign_headers(path, body))
    req = urllib.request.Request(API_BASE + path, data=body,
                                 headers=_headers(_require_token(token), extra),
                                 method="POST")
    return _parse(_open(req, timeout))


def cancel_signup(activity_id, token, timeout=DEFAULT_TIMEOUT):
    """取消报名：只发一次，不重试。成败由调用方随后用 get_join_info 复查。"""
    aid = str(activity_id or "").strip()
    if not aid:
        raise SchoolRequestError("缺少活动 id")
    return _get(CANCEL_PATH + urllib.parse.quote(aid, safe=""), token, timeout)


def session_token():
    """现有登录态里的 token；读不到返回空串，由调用方决定是否跳过。"""
    try:
        return str((load_session() or {}).get("token") or "").strip()
    except Exception:      # noqa: BLE001 - 登录态文件缺失/损坏都按「没有」处理
        return ""

