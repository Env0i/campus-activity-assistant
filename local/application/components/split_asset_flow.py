# -*- coding: utf-8 -*-
"""拆分组件资产组的下载、校验、缓存与提交编排。

只做流程编排；服务状态字段变更与锁管理由 AdvancedComponentService 自己的
方法完成，本模块不直接触碰 service._lock。
@author Author
"""
from __future__ import annotations


def validate_split_group(service, assets) -> bool:
    required = {key for key, spec in service._artifacts.items()
                if spec["feature"] == service._feature}
    if (not assets or any(not isinstance(asset, dict) for asset in assets)
            or {asset.get("artifact_id") for asset in assets} != required
            or len(assets) != len(required)):
        service._fail("bad_artifact", "拆分组件资产组不完整。")
        return False
    return True


def _download_split_asset(service, asset, offset: int, total: int, step_bytes: int):
    last_progress = [offset]

    def progress(done, _expect):
        current = offset + int(done or 0)
        if (current - last_progress[0] < step_bytes
                and current < offset + int(asset.get("bytes") or 0)):
            return
        last_progress[0] = current
        service._set(downloaded=current, total=total)

    return service._download(
        asset["url"], name=asset["name"], expect_bytes=asset["bytes"],
        expect_sha256=asset["sha256"], root=service._root,
        progress=progress, cancel=lambda: service._cancel_flag)


def _verify_and_cache_asset(service, asset, archive: str) -> tuple[str, dict | None]:
    artifact_id = asset["artifact_id"]
    try:
        service._set(state="verifying", text="正在校验组件资产…")
        info = service._inspect_artifact(archive, artifact_id)
        if not (isinstance(info, dict) and info.get("ok") is True):
            service._fail(str((info or {}).get("kind") or "bad_artifact"),
                          str((info or {}).get("text") or "拆分组件资产不合规。"))
            return "integrity", None
        if service._cancelled():
            return "cancelled", None
        cached = service._cache_artifact(
            archive, artifact_id, root=service._root,
            expect_content_sha256=asset.get("content_sha256"))
        return "ok", cached
    finally:
        service._cleanup(archive)


def _prepare_missing_assets(service, assets, step_bytes: int,
                            classify_failure) -> tuple[str, dict]:
    prepared, missing = {}, []
    for asset in assets:
        cached = service._find_cached_artifact(asset, root=service._root)
        if cached is None:
            missing.append(asset)
        else:
            prepared[asset["artifact_id"]] = cached
    total = sum(int(asset.get("bytes") or 0) for asset in missing)
    service._set(total=total, downloaded=0)
    offset = 0
    for asset in missing:
        if service._cancelled():
            return "cancelled", prepared
        service._set(total=total, state="downloading", text="")
        got = _download_split_asset(service, asset, offset, total, step_bytes)
        if not got.get("ok"):
            code, text, network = classify_failure(got)
            if code == "cancelled":
                service._set(state="cancelled", text="", error_code="")
                return "cancelled", prepared
            service._fail(code, text)
            return ("failed" if network else "integrity"), prepared
        status, cached = _verify_and_cache_asset(service, asset, str(got.get("path") or ""))
        if status != "ok":
            return status, prepared
        prepared[asset["artifact_id"]] = cached
        offset += int(asset.get("bytes") or 0)
    return "ready", prepared


def run_split_assets(service, assets, *, step_bytes: int, classify_failure) -> str:
    """先复用或准备全部不可变资产，最后一次切换完整功能组。

    返回值告诉调用方能否改下完整单体包：installed / cancelled / failed 都
    不再回退；只有 integrity（下载成功但校验、缓存或提交不通过）允许回退。
    """
    if not validate_split_group(service, assets):
        return "failed"
    outcome, prepared = _prepare_missing_assets(service, assets, step_bytes, classify_failure)
    if outcome != "ready":
        return outcome
    return service._commit_split_group(assets, prepared)
