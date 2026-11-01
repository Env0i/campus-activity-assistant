#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DPAPI 凭据存储测试：全程 fake DPAPI，不调用真实 CryptProtectData。

只验证落盘形状、明文边界与降级结论；不读、不写任何真实凭据文件。

@author Author
"""
from __future__ import annotations

import base64
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from infrastructure import credential_store  # noqa: E402
from infrastructure.credential_store import CredentialStoreError  # noqa: E402

# 真实 DPAPI 入口仅供「非 Windows 降级」用例调用；其余用例一律走假封印
REAL_PROTECT = credential_store._protect


def fake_seal(raw: bytes) -> bytes:
    """可逆假封印：只要不是明文即可，绝不调用系统 DPAPI。"""
    return bytes(b ^ 0x5A for b in raw)


def fake_unseal(raw: bytes) -> bytes:
    return bytes(b ^ 0x5A for b in raw)


class FakeDpapiBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="campus-cred-"))
        self.addCleanup(lambda: _rmtree(self.tmp))
        self.path = self.tmp / "relogin-credentials.dpapi.json"
        patcher = mock.patch.multiple(
            credential_store, _protect=fake_seal, _unprotect=fake_unseal)
        patcher.start()
        self.addCleanup(patcher.stop)


def _rmtree(path: Path) -> None:
    import shutil
    shutil.rmtree(str(path), ignore_errors=True)


class SaveShapeTests(FakeDpapiBase):
    def test_failed_atomic_replace_keeps_previous_document(self):
        credential_store.save_document(self.path, {"devices": ["old-test-hash"]})
        original = self.path.read_bytes()
        with mock.patch.object(credential_store.os, "replace", side_effect=OSError):
            with self.assertRaises(OSError):
                credential_store.save_document(self.path, {"devices": []})
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.tmp.iterdir()), [self.path])

    def test_saved_file_contains_no_plaintext_password(self):
        credential_store.save(self.path, "stu-2099", "S3cret-Pass!")
        raw = self.path.read_bytes()
        self.assertNotIn(b"S3cret-Pass!", raw, "明文密码绝不能落盘")
        self.assertNotIn("S3cret-Pass!", raw.decode("utf-8"))
        doc = json.loads(raw.decode("utf-8"))
        self.assertNotIn("password", doc, "外层 JSON 不得带密码字段")
        self.assertEqual(doc["version"], 1)
        self.assertEqual(doc["username"], "stu-2099")
        self.assertTrue(doc["dpapi"])
        # 密文 blob 里确实封着两份凭据，但以密文形态存在
        sealed = base64.b64decode(doc["dpapi"], validate=True)
        self.assertNotIn(b"S3cret-Pass!", sealed)
        self.assertIn(b"S3cret-Pass!", fake_unseal(sealed))

    def test_load_roundtrips_through_fake_dpapi(self):
        credential_store.save(self.path, "stu-2099", "S3cret-Pass!")
        value = credential_store.load(self.path)
        self.assertEqual(value, {"username": "stu-2099", "password": "S3cret-Pass!"})

    def test_overwrite_replaces_old_ciphertext(self):
        credential_store.save(self.path, "u1", "old-pass")
        credential_store.save(self.path, "u2", "new-pass")
        raw = self.path.read_bytes()
        self.assertNotIn(b"old-pass", raw)
        self.assertEqual(credential_store.load(self.path)["password"], "new-pass")


class ReadAndClearTests(FakeDpapiBase):
    def test_stored_username_and_has_credentials(self):
        self.assertFalse(credential_store.has_credentials(self.path))
        credential_store.save(self.path, "stu-2099", "S3cret-Pass!")
        self.assertTrue(credential_store.has_credentials(self.path))
        self.assertEqual(credential_store.stored_username(self.path), "stu-2099")

    def test_clear_deletes_ciphertext_and_is_idempotent(self):
        credential_store.save(self.path, "stu-2099", "S3cret-Pass!")
        self.assertTrue(credential_store.clear(self.path))
        self.assertFalse(self.path.exists(), "清除必须删掉密文文件")
        self.assertFalse(credential_store.has_credentials(self.path))
        self.assertFalse(credential_store.clear(self.path))

    def test_corrupt_file_reports_not_saved(self):
        self.path.write_text("{broken json", encoding="utf-8")
        self.assertFalse(credential_store.has_credentials(self.path))
        self.path.write_text(json.dumps({"version": 1, "dpapi": "!!notb64!!"}),
                             encoding="utf-8")
        self.assertFalse(credential_store.has_credentials(self.path))

    def test_incomplete_payload_is_rejected(self):
        self.path.write_text(json.dumps({
            "version": 1, "username": "u",
            "dpapi": base64.b64encode(fake_seal(
                json.dumps({"username": "u"}).encode("utf-8"))).decode("ascii"),
        }), encoding="utf-8")
        with self.assertRaises(CredentialStoreError):
            credential_store.load(self.path)
        self.assertFalse(credential_store.has_credentials(self.path))


class DocumentStoreTests(FakeDpapiBase):
    def test_document_roundtrip(self):
        credential_store.save_document(self.path, {"devices": [{"token_hash": "ab"}]})
        self.assertEqual(credential_store.load_document(self.path),
                         {"devices": [{"token_hash": "ab"}]})

    def test_document_file_keeps_only_version_and_ciphertext(self):
        credential_store.save_document(self.path, {"devices": [{"token_hash": "ab"}]})
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(sorted(doc), ["dpapi", "version"],
                         "非凭据文档不额外暴露字段")
        self.assertNotIn("devices", doc)

    def test_document_requires_dict(self):
        with self.assertRaises(CredentialStoreError):
            credential_store.save_document(self.path, ["not", "a", "dict"])
        self.assertFalse(self.path.exists())

    def test_document_dpapi_failure_writes_nothing(self):
        with mock.patch.object(
                credential_store, "_protect",
                side_effect=CredentialStoreError("CryptProtectData 失败")):
            with self.assertRaises(CredentialStoreError):
                credential_store.save_document(self.path, {"devices": []})
        self.assertFalse(self.path.exists())

    def test_document_unsupported_version_is_rejected(self):
        self.path.write_text(json.dumps({"version": 2, "dpapi": "AAAA"}),
                             encoding="utf-8")
        with self.assertRaises(CredentialStoreError):
            credential_store.load_document(self.path)

    def test_document_corrupt_json_is_rejected(self):
        self.path.write_text("{broken json", encoding="utf-8")
        with self.assertRaises(CredentialStoreError):
            credential_store.load_document(self.path)
        self.path.write_text(json.dumps({"version": 1, "dpapi": "!!notb64!!"}),
                             encoding="utf-8")
        with self.assertRaises(CredentialStoreError):
            credential_store.load_document(self.path)


class DegradationTests(FakeDpapiBase):
    def test_dpapi_failure_never_falls_back_to_plaintext(self):
        with mock.patch.object(
                credential_store, "_protect",
                side_effect=CredentialStoreError("CryptProtectData 失败")):
            with self.assertRaises(CredentialStoreError):
                credential_store.save(self.path, "u", "p")
        self.assertFalse(self.path.exists(), "DPAPI 失败不得回退写明文")

    def test_non_windows_raises_without_plaintext(self):
        posix = types.SimpleNamespace(name="posix")
        with mock.patch.object(credential_store, "_protect", REAL_PROTECT), \
                mock.patch.object(credential_store, "os", posix):
            with self.assertRaises(CredentialStoreError):
                credential_store.save(self.path, "u", "p")
        self.assertFalse(self.path.exists())

    def test_unprotect_failure_is_not_silently_accepted(self):
        credential_store.save(self.path, "u", "p")
        with mock.patch.object(
                credential_store, "_unprotect",
                side_effect=CredentialStoreError("CryptUnprotectData 失败")):
            with self.assertRaises(CredentialStoreError):
                credential_store.load(self.path)
            self.assertFalse(credential_store.has_credentials(self.path))


if __name__ == "__main__":
    unittest.main()
