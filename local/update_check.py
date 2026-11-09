"""手动查询固定仓库的正式版本并挑选可校验的安装器资产；不接触凭证、数据根或安装流程。

@author Author
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

REPO_BASE = "https://github.com/Env0i/campus-activity-assistant"
LATEST_URL = REPO_BASE + "/releases/latest"
# G1：检查更新只读这份清单直链，不再碰 api.github.com（未登录请求按出口 IP 限 60 次/小时）
LATEST_MANIFEST_URL = REPO_BASE + "/releases/latest/download/manifest.json"
REPO_DOWNLOAD_PREFIX = "/Env0i/campus-activity-assistant/releases/download/"
TIMEOUT_S = 8
MAX_MANIFEST_BYTES = 64 * 1024
# 与 updater.DEFAULT_MAX_BYTES 同源口径：安装包下载上限（约 300 MB）
MAX_INSTALLER_BYTES = 300 * 1024 * 1024
MANIFEST_ASSET_NAME = "manifest.json"


def parse_version(value: str) -> tuple[int, int, int]:
    """只比较正式三段版本，避免1.10被字典序排到1.9之前。"""
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("invalid version")
    match = re.fullmatch(r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value)
    if not match:
        raise ValueError("invalid version")
    return tuple(int(part) for part in match.groups())


def tag_manifest_url(version: str) -> str:
    """按标签拼清单直链（G1）：资产下载地址不受未登录接口的出口 IP 限流。"""
    parse_version(version)
    return REPO_BASE + "/releases/download/v" + version + "/manifest.json"


def installer_asset_name(version: str) -> str:
    """安装器下载资产名：只用 ASCII（GitHub 会把中文前缀规范化成别的形式）。"""
    parse_version(version)
    return "campus-activity-watch-installer-v%s-win-x64.exe" % version


# 可在线下载的组件包：每个都是独立 Release 资产，命名、清单校验规则相同
COMPONENT_FEATURES = ("phone_control", "relogin_ocr")
COMPONENT_TITLES = {"phone_control": "手机控制", "relogin_ocr": "验证码识别"}


def component_asset_name(feature: str, version: str) -> str:
    """组件包的资产名：与安装器同一套版本口径；功能键里的下划线换成连字符。"""
    if feature not in COMPONENT_FEATURES:
        raise ValueError("unknown component")
    parse_version(version)
    return "campus-activity-watch-%s-v%s-win-x64.zip" % (feature.replace("_", "-"), version)


def phone_control_asset_name(version: str) -> str:
    """手机控制组件包的资产名（旧函数名，发布脚本与既有测试仍在用）。"""
    return component_asset_name("phone_control", version)


def is_release_asset_url(url, name) -> bool:
    """只接受本仓库 GitHub Release 资产的 HTTPS 下载地址，且路径尾段必须等于资产名。"""
    if not isinstance(url, str) or not isinstance(name, str) or not name:
        return False
    if not url or len(url) > 2048:
        return False
    try:
        parts = urlparse(url)
    except ValueError:
        return False
    if parts.scheme != "https" or (parts.hostname or "").lower() != "github.com":
        return False
    path = parts.path
    return (path.startswith(REPO_DOWNLOAD_PREFIX)
            and path.endswith("/" + name)
            and len(path) > len(REPO_DOWNLOAD_PREFIX) + len(name))


def select_release_assets(payload: dict, version: str) -> dict:
    """从 Release 资产里挑安装器、组件包与 manifest；命名或地址不符的条目一律不选中。"""
    empty = {"installer": None, "manifest_url": ""}
    empty.update({feature: None for feature in COMPONENT_FEATURES})
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list):
        return empty
    wanted = installer_asset_name(version)
    wanted_components = {component_asset_name(feature, version): feature
                         for feature in COMPONENT_FEATURES}
    picked = dict(empty)
    installer = None
    manifest_url = ""
    for item in assets:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        url = item.get("browser_download_url")
        if name == wanted and is_release_asset_url(url, name):
            size = item.get("size")
            if (isinstance(size, int) and not isinstance(size, bool)
                    and 0 < size <= MAX_INSTALLER_BYTES):
                installer = {"name": name, "url": url, "bytes": size}
        elif name in wanted_components and is_release_asset_url(url, name):
            # 组件包比安装器小得多，但仍按同一上限拦一次异常体积
            size = item.get("size")
            if (isinstance(size, int) and not isinstance(size, bool)
                    and 0 < size <= MAX_INSTALLER_BYTES):
                picked[wanted_components[name]] = {"name": name, "url": url, "bytes": size}
        elif name == MANIFEST_ASSET_NAME and is_release_asset_url(url, name):
            manifest_url = url
    picked["installer"] = installer
    picked["manifest_url"] = manifest_url
    return picked


def parse_manifest_entry(raw, version: str, name: str) -> dict:
    """校验 manifest 结构并取出指定资产的条目；任何不符都拒绝，不给可下载结论。"""
    if not isinstance(raw, (bytes, bytearray)):
        raise ValueError("manifest not bytes")
    data = json.loads(bytes(raw).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest not an object")
    if data.get("version") != version:
        raise ValueError("manifest version mismatch")
    files = data.get("files")
    if not isinstance(files, dict):
        raise ValueError("manifest files missing")
    entry = files.get(name)
    if not isinstance(entry, dict):
        raise ValueError("asset entry missing")
    sha = entry.get("sha256")
    size = entry.get("bytes")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
        raise ValueError("bad sha256")
    if (not isinstance(size, int) or isinstance(size, bool)
            or size <= 0 or size > MAX_INSTALLER_BYTES):
        raise ValueError("bad bytes")
    return {"sha256": sha.lower(), "bytes": size}


def parse_manifest(raw, version: str, installer_name: str) -> dict:
    """安装器清单条目；保留旧函数名给安装流程与既有测试使用。"""
    return parse_manifest_entry(raw, version, installer_name)


def payload_from_manifest(raw, version: str | None = None) -> dict:
    """把 Release 清单组装成与接口元数据同形的 payload，供既有的纯函数挑选资产（G1）。

    version 已给（下载组件时是本机版本）就要求清单版本严格一致；检查更新时留空，
    版本从清单自身的字段取。清单里没有它自己，这里补一条合成资产，
    select_release_assets 才能像以前一样挑出 manifest_url。
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise ValueError("manifest not bytes")
    data = json.loads(bytes(raw).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest not an object")
    manifest_version = data.get("version")
    parse_version(manifest_version)
    if version is not None and manifest_version != version:
        raise ValueError("manifest version mismatch")
    tag = data.get("tag")
    if not isinstance(tag, str) or not tag or tag != "v" + manifest_version:
        raise ValueError("manifest tag mismatch")
    files = data.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("manifest files missing")
    base = REPO_BASE + "/releases/download/" + tag + "/"
    assets = []
    for name, entry in files.items():
        if not isinstance(name, str) or not name or len(name) > 256:
            raise ValueError("bad asset name")
        if not isinstance(entry, dict):
            raise ValueError("bad asset entry")
        sha = entry.get("sha256")
        size = entry.get("bytes")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
            raise ValueError("bad sha256")
        if (not isinstance(size, int) or isinstance(size, bool)
                or size <= 0 or size > MAX_INSTALLER_BYTES):
            raise ValueError("bad bytes")
        assets.append({"name": name, "size": size, "browser_download_url": base + name})
    assets.append({"name": MANIFEST_ASSET_NAME, "size": len(raw),
                   "browser_download_url": tag_manifest_url(manifest_version)})
    return {"tag_name": tag, "draft": False, "prerelease": False, "assets": assets}


def resolve_component_asset(payload: dict, version: str, raw_manifest,
                            feature: str = "phone_control") -> dict:
    """把「组件资产 + Release 清单」解析成可用于下载的结论。

    三种结论分开给：没发组件（no_component）、清单对不上（manifest_invalid）、
    可以下载（available）。不给「退回手动下载页」这种模棱两可的中间态。
    """
    if feature not in COMPONENT_FEATURES:
        return {"state": "no_component", "error_code": "no_component", "asset": None,
                "text": "这个组件不支持在线下载。"}
    picked = select_release_assets(payload, version)
    asset = picked[feature]
    if asset is None:
        return {"state": "no_component", "error_code": "no_component", "asset": None,
                "text": "这个版本没有发布%s组件包。" % COMPONENT_TITLES[feature]}
    if not picked["manifest_url"]:
        return {"state": "manifest_invalid", "error_code": "manifest_invalid", "asset": None,
                "text": "组件包缺少清单，无法校验来源。"}
    try:
        entry = parse_manifest_entry(raw_manifest, version, asset["name"])
    except (ValueError, TypeError, UnicodeError):
        return {"state": "manifest_invalid", "error_code": "manifest_invalid", "asset": None,
                "text": "组件包清单不可用，已停止下载。"}
    if entry["bytes"] != asset["bytes"]:
        return {"state": "manifest_invalid", "error_code": "manifest_invalid", "asset": None,
                "text": "组件包大小与清单不一致，已停止下载。"}
    return {"state": "available", "error_code": "", "text": "",
            "asset": dict(asset, sha256=entry["sha256"], bytes=entry["bytes"])}


def resolve_phone_control_asset(payload: dict, version: str, raw_manifest) -> dict:
    """手机控制组件的解析结论（旧函数名，返回值不变）。"""
    return resolve_component_asset(payload, version, raw_manifest, "phone_control")


def _result(current: str, state: str, text: str, latest=None, error_code="") -> dict:
    return {"state": state, "current_version": current, "latest_version": latest,
            "url": LATEST_URL, "checked_at": datetime.now(timezone.utc).isoformat(),
            "text": text, "error_code": error_code, "installer": None}


def _fetch_bytes(url: str, limit: int, user_agent: str) -> bytes:
    """按上限拉一份响应体；超限按无效响应处理，不把大响应整个读进内存。"""
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=TIMEOUT_S) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("response too large")
    return raw


def evaluate_latest_release(current_version: str, payload: dict) -> dict:
    """远端落后于本机候选时只说明预览状态，不建议用户降级。"""
    current = parse_version(current_version)
    if not isinstance(payload, dict) or payload.get("draft") is not False or payload.get("prerelease") is not False:
        raise ValueError("not a published stable release")
    latest = parse_version(payload.get("tag_name"))
    version = ".".join(map(str, latest))
    if latest > current:
        return _result(current_version, "available", "发现新版本 " + version, version)
    if latest == current:
        return _result(current_version, "current", "当前为最新正式版", version)
    return _result(current_version, "preview", "当前为预览版本，最新正式版 " + version, version)


def _attach_installer(result: dict, payload: dict, raw_manifest=None) -> dict:
    """可用版本补上安装器与 manifest 校验信息；缺安装器或清单不可用时退回发布页状态。

    网络类失败重新抛出，交回 check_latest_release 统一分类成 error——
    「拿不到清单」和「清单内容不对」不是一回事，前者可重试。
    已经拿到的那份清单直接传进来，避免检查更新时再请求一次。
    """
    version = result["latest_version"]
    picked = select_release_assets(payload, version)
    installer = picked["installer"]
    if installer is None or not picked["manifest_url"]:
        return dict(result, state="no_installer", error_code="no_installer",
                    text="发现新版本 " + version + "，但没有可校验的安装包，请前往下载页手动下载。")
    try:
        raw = raw_manifest if raw_manifest is not None else _fetch_bytes(
            picked["manifest_url"], MAX_MANIFEST_BYTES, "TianSoftActivityPreRegistration-manifest")
        entry = parse_manifest(raw, version, installer["name"])
    except (ValueError, TypeError):
        return dict(result, state="no_installer", error_code="manifest_invalid",
                    text="发现新版本 " + version + "，但安装包校验信息不可用，请前往下载页手动下载。")
    if entry["bytes"] != installer["bytes"]:
        return dict(result, state="no_installer", error_code="manifest_invalid",
                    text="发现新版本 " + version + "，但安装包大小与校验信息不一致，请前往下载页手动下载。")
    return dict(result, installer=dict(installer, sha256=entry["sha256"], bytes=entry["bytes"]))


def check_latest_release(current_version: str) -> dict:
    """用户每次主动检查只发一个 GET（Release 清单直链），失败给分类而不泄露响应原文。

    G1：不走 api.github.com。未登录接口按出口 IP 限 60 次/小时，共享代理出口很容易打满；
    资产直链不受这个限流，清单里已有每个资产的大小与 SHA-256，校验一点不少。
    """
    try:
        parse_version(current_version)
        user_agent = "TianSoftActivityPreRegistration/" + current_version
        raw = _fetch_bytes(LATEST_MANIFEST_URL, MAX_MANIFEST_BYTES, user_agent)
        payload = payload_from_manifest(raw)
        result = evaluate_latest_release(current_version, payload)
        if result["state"] != "available":
            return result
        return _attach_installer(result, payload, raw_manifest=raw)
    except HTTPError as exc:
        if exc.code == 404:
            return _result(current_version, "unavailable", "暂无正式发布")
        if exc.code in (403, 429):
            return _result(current_version, "error", "GitHub 暂时限制了查询次数，过一会再试，或到发布页手动下载。", error_code="rate_limited")
        return _result(current_version, "error", "GitHub暂时无法响应，请稍后重试。", error_code="http_error")
    except (TimeoutError, socket.timeout):
        return _result(current_version, "error", "连接超时，请重试或查看发布页。", error_code="timeout")
    except URLError as exc:
        code = "timeout" if isinstance(exc.reason, (TimeoutError, socket.timeout)) else "network_error"
        return _result(current_version, "error", "暂时无法连接GitHub，请检查网络后重试。", error_code=code)
    except (ValueError, UnicodeError, TypeError):
        return _result(current_version, "error", "版本信息无法识别，请查看发布页。", error_code="invalid_response")
    except OSError:
        return _result(current_version, "error", "暂时无法连接GitHub，请检查网络后重试。", error_code="network_error")
