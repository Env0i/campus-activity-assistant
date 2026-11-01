#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""持久设备信任存储测试：全程 fake DPAPI，不写真实凭据文件。

只验证哈希落盘、幂等、过期清理与撤销语义；不读、不写任何真实设备信任文件。

@author Author
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from infrastructure import credential_store  # noqa: E402
from infrastructure.phone_session_store import (  # noqa: E402
    DEVICE_TTL_SECONDS,
    PhoneSessionStore,
)


def fake_seal(raw: bytes) -> bytes:
    return bytes(b ^ 0x5A for b in raw)


def fake_unseal(raw: bytes) -> bytes:
    return bytes(b ^ 0x5A for b in raw)


def _rmtree(path: Path) -> None:
    import shutil
    shutil.rmtree(str(path), ignore_errors=True)


class StoreBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="campus-device-"))
        self.addCleanup(lambda: _rmtree(self.tmp))
        self.path = self.tmp / "phone-session.dpapi.json"
        self.store = PhoneSessionStore(self.path)
        patcher = mock.patch.multiple(
            credential_store, _protect=fake_seal, _unprotect=fake_unseal)
        patcher.start()
        self.addCleanup(patcher.stop)


class AddAndValidateTests(StoreBase):
    def test_revoke_cannot_be_overwritten_by_inflight_validation(self):
        self.store.add_device("tok-1", now=1000)
        entered, release = threading.Event(), threading.Event()
        original = self.store._load
        def blocked_load():
            document = original()
            entered.set()
            release.wait(2)
            return document
        with mock.patch.object(self.store, "_load", side_effect=blocked_load):
            validator = threading.Thread(target=lambda: self.store.validate_device("tok-1", now=1001))
            validator.start()
            self.assertTrue(entered.wait(2))
            revoker = threading.Thread(target=self.store.revoke_all)
            revoker.start()
            revoker.join(0.1)
            release.set()
            validator.join(3)
            revoker.join(3)
        self.assertFalse(self.path.exists(), "撤销结束后不得被较早开始的校验重建")

    def test_add_then_validate(self):
        self.assertTrue(self.store.add_device("tok-1", now=1000))
        self.assertTrue(self.store.validate_device("tok-1", now=1000))
        self.assertFalse(self.store.validate_device("tok-2", now=1000))

    def test_empty_token_is_rejected(self):
        for value in ("", None):
            with self.subTest(value=value):
                self.assertFalse(self.store.add_device(value, now=1000))
                self.assertFalse(self.store.validate_device(value, now=1000))
        self.assertFalse(self.path.exists())

    def test_duplicate_add_is_idempotent(self):
        self.store.add_device("tok-1", now=1000)
        self.store.add_device("tok-1", now=2000)
        document = credential_store.load_document(self.path)
        self.assertEqual(len(document["devices"]), 1)
        self.assertEqual(document["devices"][0]["last_seen_at"], 2000)

    def test_multiple_devices_are_kept(self):
        self.store.add_device("tok-1", now=1000)
        self.store.add_device("tok-2", now=1000)
        document = credential_store.load_document(self.path)
        self.assertEqual(len(document["devices"]), 2)
        self.assertTrue(self.store.validate_device("tok-2", now=1000))


class FileShapeTests(StoreBase):
    def test_file_contains_hash_not_token(self):
        self.store.add_device("tok-secret-value", now=1000)
        raw = self.path.read_bytes()
        self.assertNotIn(b"tok-secret-value", raw, "token 明文绝不能落盘")
        document = credential_store.load_document(self.path)
        self.assertNotEqual(document["devices"][0]["token_hash"], "tok-secret-value")
        self.assertEqual(len(document["devices"][0]["token_hash"]), 64,
                         "存的是 SHA-256 十六进制")

    def test_corrupt_file_means_no_trust(self):
        self.path.write_text("{broken json", encoding="utf-8")
        self.assertFalse(self.store.validate_device("tok-1", now=1000))
        # 损坏文件不应让程序崩溃，也不应把任意 token 当成可信
        self.assertTrue(self.store.add_device("tok-1", now=1000))
        self.assertTrue(self.store.validate_device("tok-1", now=1000))

    def test_unsupported_version_means_no_trust(self):
        self.path.write_text(json.dumps({"version": 9, "dpapi": "AAAA"}),
                             encoding="utf-8")
        self.assertFalse(self.store.validate_device("tok-1", now=1000))


class ExpiryAndRevokeTests(StoreBase):
    def test_device_expires_after_one_year(self):
        self.store.add_device("tok-1", now=1000)
        later = 1000 + DEVICE_TTL_SECONDS + 1
        self.assertFalse(self.store.validate_device("tok-1", now=later))
        self.assertEqual(credential_store.load_document(self.path)["devices"], [],
                         "过期记录必须被清掉")

    def test_fresh_device_survives_just_before_expiry(self):
        self.store.add_device("tok-1", now=1000)
        self.assertTrue(self.store.validate_device(
            "tok-1", now=1000 + DEVICE_TTL_SECONDS - 1))

    def test_revoke_all_deletes_file(self):
        self.store.add_device("tok-1", now=1000)
        self.assertTrue(self.store.revoke_all())
        self.assertFalse(self.path.exists())
        self.assertFalse(self.store.validate_device("tok-1", now=1000))
        self.assertFalse(self.store.revoke_all(), "重复撤销不报错")

    def test_revoke_all_does_not_resurrect_after_reload(self):
        self.store.add_device("tok-1", now=1000)
        self.store.revoke_all()
        self.assertFalse(PhoneSessionStore(self.path).validate_device("tok-1", now=1000))


if __name__ == "__main__":
    unittest.main()
