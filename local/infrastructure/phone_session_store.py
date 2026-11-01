# -*- coding: utf-8 -*-
"""手机持久设备信任：只存 token 的 SHA-256，DPAPI 封装落盘。

设计边界：
- 文件里没有 token 明文，也没有账号密码；拿到文件的人无法反推出可用 token。
- 读写异常一律按「没有持久设备信任」处理，调用方回落到重新配对。
- 过期记录在下一次校验时顺便清理，不额外跑定时任务。

@author Author
"""
from __future__ import annotations

import hashlib
import hmac
import threading
import time
from pathlib import Path

from infrastructure import credential_store
from infrastructure.credential_store import CredentialStoreError

DEVICE_TTL_SECONDS = 365 * 24 * 3600
DOCUMENT_VERSION = 1


def _hash_token(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _as_seconds(value) -> float:
    """把整数、浮点或 None 统一成秒；无法解释时退回当前时间。"""
    if value is None:
        return time.time()
    try:
        return float(value)
    except (TypeError, ValueError):
        return time.time()


class PhoneSessionStore:
    """设备信任的唯一入口；一个文件对应一台电脑。"""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def _load(self) -> dict:
        try:
            document = credential_store.load_document(self.path)
        except (OSError, ValueError, CredentialStoreError):
            return {"version": DOCUMENT_VERSION, "devices": []}
        devices = document.get("devices")
        if not isinstance(devices, list):
            return {"version": DOCUMENT_VERSION, "devices": []}
        clean = [item for item in devices
                 if isinstance(item, dict) and isinstance(item.get("token_hash"), str)]
        return {"version": DOCUMENT_VERSION, "devices": clean}

    def _save(self, document: dict) -> None:
        credential_store.save_document(self.path, document)

    def add_device(self, token: str, now=None) -> bool:
        """记一台可信设备；同一个 token 重复加入只更新时间，不加新记录。"""
        value = str(token or "")
        if not value:
            return False
        stamp = _as_seconds(now)
        with self._lock:
            document = self._load()
            digest = _hash_token(value)
            for item in document["devices"]:
                if hmac.compare_digest(str(item.get("token_hash") or ""), digest):
                    item["last_seen_at"] = stamp
                    item["created_at"] = _as_seconds(item.get("created_at"))
                    break
            else:
                document["devices"].append({"token_hash": digest, "created_at": stamp,
                                            "last_seen_at": stamp})
            self._save(document)
        return True

    def validate_device(self, token: str, now=None) -> bool:
        """校验设备 token；顺便清掉过期记录，返回是否命中。"""
        value = str(token or "")
        if not value:
            return False
        stamp = _as_seconds(now)
        with self._lock:
            document = self._load()
            digest = _hash_token(value)
            kept = []
            matched = False
            for item in document["devices"]:
                last_seen = _as_seconds(item.get("last_seen_at"))
                if stamp - last_seen > DEVICE_TTL_SECONDS:
                    continue
                kept.append(item)
                if not matched and hmac.compare_digest(
                        str(item.get("token_hash") or ""), digest):
                    item["last_seen_at"] = stamp
                    matched = True
            if matched or len(kept) != len(document["devices"]):
                document["devices"] = kept
                self._save(document)
        return matched

    def revoke_all(self) -> bool:
        """撤销全部设备信任；返回是否真的删掉了文件。"""
        with self._lock:
            try:
                return credential_store.clear(self.path)
            except OSError:
                return False


__all__ = ["PhoneSessionStore", "DEVICE_TTL_SECONDS", "DOCUMENT_VERSION"]
