#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器直发报名签名：基于 cryptography 的 AES-128-ECB + PKCS7。

只做签名与运行时密钥形状校验，不读时钟、不联网、不回退自造算法、不打印密钥。
依赖缺失或加密调用失败统一抛出 SignerUnavailable，由调用方退回点击兜底。
@author Author
"""
from __future__ import annotations

RUNTIME_KEY_LEN = 16


class SignerUnavailable(RuntimeError):
    """签名不可用：cryptography 缺失或加密调用失败。"""


def pkcs7_pad(data: bytes) -> bytes:
    """PKCS7 填充：补齐 1..16 字节（整块也补一整块 16）。"""
    pad_len = 16 - (len(data) % 16)
    return data + bytes([pad_len]) * pad_len


def parse_runtime_key(payload) -> bytes | None:
    """从 runtime/profile 的返回里取运行时密钥；形状不对一律返回 None。

    与本机同口径：顶层 dict 的 data 字段必须是 16 个 ASCII 字母数字字符，
    UTF-8 字节直接当 AES-128 密钥，不做 hex/base64 二次解码，不打印值。
    """
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, str) or len(data) != RUNTIME_KEY_LEN:
        return None
    if not (data.isascii() and data.isalnum()):
        return None
    return data.encode("utf-8")


def _load_cipher_backend():
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except Exception as exc:
        raise SignerUnavailable("cryptography 不可用") from exc
    return Cipher, algorithms, modes


def encrypt_aes_ecb(plaintext_padded: bytes, key: bytes) -> bytes:
    """使用 cryptography 的 AES-128-ECB 加密已填充（16 字节倍数）明文。"""
    if len(plaintext_padded) % 16 != 0:
        raise ValueError("加密块只接受 16 字节倍数明文")
    if len(key) != RUNTIME_KEY_LEN:
        raise ValueError("AES-128 需要 16 字节 key")
    Cipher, algorithms, modes = _load_cipher_backend()
    try:
        encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
        return encryptor.update(plaintext_padded) + encryptor.finalize()
    except SignerUnavailable:
        raise
    except Exception as exc:
        raise SignerUnavailable("签名加密失败：%s" % type(exc).__name__) from exc


def build_signup_hash(activity_id: str, epoch_ms: int, key: bytes) -> str:
    """算报名 hash：AES-128-ECB(UTF-8('id,ms'), PKCS7) 的小写 hex。"""
    if not isinstance(activity_id, str) or not activity_id or any(
        ch in activity_id for ch in (",", "\n", "\r")
    ):
        raise ValueError("activity_id 非空且不含逗号/换行")
    if isinstance(epoch_ms, bool) or not isinstance(epoch_ms, int) or epoch_ms <= 0:
        raise ValueError("epoch_ms 为正整数")
    if not isinstance(key, (bytes, bytearray)) or len(key) != RUNTIME_KEY_LEN:
        raise ValueError("key 必须是 16 字节运行时密钥")
    plain = f"{activity_id},{epoch_ms}".encode("utf-8")
    ciphertext = encrypt_aes_ecb(pkcs7_pad(plain), bytes(key))
    return ciphertext.hex().lower()
