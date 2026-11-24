#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SNTP 报文构造、校验解析与传输失败原因白名单分类。

@author Author
"""
from __future__ import annotations

import os
import socket
import struct
import time

__all__ = [
    "SNTP_PORT",
    "NTP_UNIX_DELTA",
    "ERA_CANDIDATES",
    "ERA_MIN_YEAR",
    "ERA_MAX_YEAR",
    "MAX_ROOT_DELAY_S",
    "FAILURE_TIMEOUT",
    "FAILURE_DNS",
    "FAILURE_BAD_PACKET",
    "FAILURE_PEER",
    "FAILURE_TRANSPORT",
    "FAILURE_REASONS",
    "SNTPPacketError",
    "classify_failure",
    "build_client_packet",
    "parse_server_packet",
]

SNTP_PORT = 123
NTP_UNIX_DELTA = 2208988800          # 1900-1970 秒
ERA_CANDIDATES = 4                   # 2^32 秒 ≈ 136 年，取 4 个候选足够覆盖
ERA_MIN_YEAR, ERA_MAX_YEAR = 2020, 2099
MAX_ROOT_DELAY_S = 0.5               # 服务器根延迟上限（秒）

# 失败原因白名单：对外只给这些粗分类，不带异常原文、地址或请求内容。
FAILURE_TIMEOUT = "timeout"
FAILURE_DNS = "dns_error"
FAILURE_BAD_PACKET = "bad_packet"
FAILURE_PEER = "peer_mismatch"
FAILURE_TRANSPORT = "transport_error"
FAILURE_REASONS = (FAILURE_TIMEOUT, FAILURE_DNS, FAILURE_BAD_PACKET,
                   FAILURE_PEER, FAILURE_TRANSPORT)


class SNTPPacketError(Exception):
    """NTP 响应未通过校验：畸形、重放、未同步、来源不符等。"""


def classify_failure(exc: BaseException) -> str:
    """把传输异常收敛成白名单原因；拿不准就报 transport_error。"""
    if isinstance(exc, SNTPPacketError):
        return FAILURE_BAD_PACKET
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return FAILURE_TIMEOUT
    if isinstance(exc, socket.gaierror):
        return FAILURE_DNS
    if isinstance(exc, ValueError):
        return FAILURE_BAD_PACKET
    text = str(exc or "")
    if "解析不到" in text:
        return FAILURE_DNS
    return FAILURE_TRANSPORT


def _beijing_year_candidates(seconds_u32: int):
    """NTP 秒是 32 位模数：枚举 era 候选，落在 2020..2099 年的必须唯一。
    发包与解码都不依赖系统年份，避免错误 OS 日期选错 era。"""
    out = []
    for era in range(-1, ERA_CANDIDATES):
        value = seconds_u32 + era * (1 << 32)
        ntp_epoch = value - NTP_UNIX_DELTA
        year = time.gmtime(ntp_epoch).tm_year if ntp_epoch > 0 else -1
        if ERA_MIN_YEAR <= year <= ERA_MAX_YEAR:
            out.append(ntp_epoch)
    return out


def _new_nonce() -> bytes:
    """每轮每源一个完整 64 位标识：冷启动也不得用全零（全零会被当成重放）。"""
    while True:
        raw = os.urandom(8)
        if raw != b"\x00" * 8:
            return raw


def build_client_packet(nonce: bytes | None = None) -> tuple[bytes, bytes]:
    """48 字节客户端请求 + 本轮完整 64 位标识（放在 transmit 位置，服务器回显到 originate）。

    LI=0/VN=4/Mode=3；标识用密码学随机数，同一秒内的两个请求也互不相同，
    不再用业务时钟估计值（同秒重发会得到相同高位，无法区分本轮）。
    布局：0 头部 | 4 根延迟 | 8 根分散 | 12 参考ID | 16/24/32/40 四个 64 位时间戳。
    """
    nonce = _new_nonce() if nonce is None else bytes(nonce)
    if len(nonce) != 8 or nonce == b"\x00" * 8:
        raise ValueError("时钟请求标识必须是 8 字节且非全零")
    secs, frac = struct.unpack("!II", nonce)
    li_vn_mode = (0 << 6) | (4 << 3) | 3
    packet = struct.pack("!BBBb9I2I", li_vn_mode, 0, 6, -21,
                         0, 0, 0,        # 根延迟/分散/参考ID
                         0, 0,           # 参考时间戳
                         0, 0,           # originate 由客户端置零
                         0, 0,           # receive 时间戳（客户端为零）
                         secs, frac)     # transmit（本轮标识）
    return packet, nonce


def _ntp_timestamp(data: bytes, offset: int, what: str) -> float:
    """64 位 NTP 时间戳（32 秒 + 32 小数）→ 业务 UTC epoch 秒。
    era 以整数秒唯一落在 2020..2099 判定；小数部分保留，不引入 1 秒量化误差。"""
    secs, frac = struct.unpack("!II", data[offset:offset + 8])
    if secs == 0 and frac == 0:
        raise SNTPPacketError("%s 时间戳为零" % what)
    cands = _beijing_year_candidates(secs)
    if len(cands) != 1:
        raise SNTPPacketError("%s era 候选不唯一，无法确定日期" % what)
    return cands[0] + frac / (1 << 32)


def parse_server_packet(data: bytes, nonce, source: str) -> dict:
    """校验并解析服务器响应；返回
    {source, server_recv, server_xmit, root_delay, root_delay_raw, dispersion}。

    originate 必须 8 字节全等：只比秒的高 32 位会把「同一秒的另一个请求」
    当成自己的响应。任何不符合都抛 SNTPPacketError，不作为样本。
    """
    if not isinstance(data, (bytes, bytearray)) or len(data) < 48:
        raise SNTPPacketError("响应长度不足 48 字节")
    li_vn_mode = data[0]
    li, vn, mode = li_vn_mode >> 6, (li_vn_mode >> 3) & 0x7, li_vn_mode & 0x7
    if vn != 4:
        raise SNTPPacketError("版本不是 4")
    if mode != 4:
        raise SNTPPacketError("不是服务器模式响应")
    if li == 3:
        raise SNTPPacketError("服务器报告未同步（LI=3）")
    stratum = data[1]
    if not 1 <= stratum <= 15:
        raise SNTPPacketError("stratum 越界（0/KoD 或 >15）")
    # 根延迟是有符号 16.16 定点数；负值不能用来抵消误差，只按绝对值计入
    root_delay_raw = struct.unpack("!i", data[4:8])[0] / 65536.0
    if abs(root_delay_raw) > MAX_ROOT_DELAY_S:
        raise SNTPPacketError("根延迟越界")
    root_delay = abs(root_delay_raw)
    dispersion = struct.unpack("!I", data[8:12])[0] / 65536.0
    expected = (struct.pack("!II", int(nonce) & 0xFFFFFFFF, 0)
                if isinstance(nonce, int) else bytes(nonce))
    if len(expected) != 8:
        raise SNTPPacketError("本轮请求标识长度不对")
    if bytes(data[24:32]) != expected:
        raise SNTPPacketError("originate 与本次请求不符（重放或错配）")
    server_recv = _ntp_timestamp(data, 32, "接收")
    server_xmit = _ntp_timestamp(data, 40, "发送")
    if server_xmit < server_recv:
        raise SNTPPacketError("服务器处理时间为负")
    return {"source": source, "server_recv": server_recv, "server_xmit": server_xmit,
            "root_delay": root_delay, "root_delay_raw": root_delay_raw,
            "dispersion": dispersion}
