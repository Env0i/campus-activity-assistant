# -*- coding: utf-8 -*-
"""Windows DPAPI 凭据存储；非 Windows 明确降级，不写明文密码。"""
from __future__ import annotations

import base64
import binascii
import ctypes
import json
import os
import tempfile
from ctypes import wintypes
from pathlib import Path


class CredentialStoreError(RuntimeError):
    pass


if os.name == "nt":
    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _protect(raw: bytes) -> bytes:
    if os.name != "nt":
        raise CredentialStoreError("DPAPI 只在 Windows 可用")
    data = _Blob()
    data.cbData = len(raw)
    data.pbData = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    out = _Blob()
    crypt = ctypes.windll.crypt32.CryptProtectData
    crypt.argtypes = [ctypes.POINTER(_Blob), wintypes.LPCWSTR,
                      ctypes.POINTER(_Blob), wintypes.LPVOID, wintypes.LPVOID,
                      wintypes.DWORD, ctypes.POINTER(_Blob)]
    crypt.restype = wintypes.BOOL
    if not crypt(ctypes.byref(data), "campus-activity-watch credentials",
                 None, None, None, 1, ctypes.byref(out)):
        raise CredentialStoreError("CryptProtectData 失败")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _unprotect(raw: bytes) -> bytes:
    if os.name != "nt":
        raise CredentialStoreError("DPAPI 只在 Windows 可用")
    data = _Blob()
    data.cbData = len(raw)
    data.pbData = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    out = _Blob()
    crypt = ctypes.windll.crypt32.CryptUnprotectData
    crypt.argtypes = [ctypes.POINTER(_Blob), ctypes.POINTER(wintypes.LPWSTR),
                      ctypes.POINTER(_Blob), wintypes.LPVOID, wintypes.LPVOID,
                      wintypes.DWORD, ctypes.POINTER(_Blob)]
    crypt.restype = wintypes.BOOL
    if not crypt(ctypes.byref(data), None, None, None, None, 1, ctypes.byref(out)):
        raise CredentialStoreError("CryptUnprotectData 失败")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def save_document(path: Path, document: dict) -> None:
    """把任意 JSON 文档按 DPAPI 封装落盘；账号密码走的也是这条路径。

    外层只保留版本、可选的账号名与密文，明文永远不落地。
    载荷结构由调用方自己定义（凭据是 username/password，设备信任是 devices）。
    """
    if not isinstance(document, dict):
        raise CredentialStoreError("只能封装 JSON 对象")
    payload = json.dumps(document, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    sealed = _protect(payload)
    outer = {"version": 1}
    # 账号名只用于设置页显示，不是秘密；密码与 token 只在密文里
    if document.get("username"):
        outer["username"] = str(document["username"])
    outer["dpapi"] = base64.b64encode(sealed).decode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    # 先写完整密文再原子换位，读者不会遇到被截断一半的信任/凭据文档。
    descriptor, pending = tempfile.mkstemp(prefix="." + path.name + "-", suffix=".part",
                                          dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(outer, ensure_ascii=False))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        if os.path.exists(pending):
            os.unlink(pending)


def load_document(path: Path) -> dict:
    """读回 save_document 写出的文档；损坏、版本不支持都抛 CredentialStoreError。"""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise CredentialStoreError("凭据文件损坏") from exc
    if not isinstance(doc, dict):
        raise CredentialStoreError("凭据文件结构不正确")
    if doc.get("version") != 1:
        raise CredentialStoreError("凭据文件版本不支持")
    try:
        raw = base64.b64decode(str(doc.get("dpapi") or ""), validate=True)
    except (ValueError, TypeError) as exc:
        raise CredentialStoreError("凭据文件损坏") from exc
    value = json.loads(_unprotect(raw).decode("utf-8"))
    if not isinstance(value, dict):
        raise CredentialStoreError("凭据内容不是 JSON 对象")
    return value


def save(path: Path, username: str, password: str) -> None:
    save_document(path, {"username": str(username), "password": str(password)})


def load(path: Path) -> dict:
    value = load_document(path)
    if not value.get("username") or not value.get("password"):
        raise CredentialStoreError("凭据内容不完整")
    return {"username": str(value["username"]), "password": str(value["password"])}


def stored_username(path: Path) -> str:
    """只给桌面设置页显示账号名；解密出的密码不离开本函数。"""
    value = load(path)
    password = value.pop("password", "")
    try:
        return str(value.get("username") or "")
    finally:
        password = ""


def has_credentials(path: Path) -> bool:
    try:
        return bool(stored_username(path))
    except (OSError, ValueError, KeyError, TypeError, CredentialStoreError,
            json.JSONDecodeError, binascii.Error):
        return False


def clear(path: Path) -> bool:
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


__all__ = ["CredentialStoreError", "save", "load", "save_document",
           "load_document", "stored_username", "has_credentials", "clear"]
