# -*- coding: utf-8 -*-
"""计划校验纯函数：单条校验、选择集内冲突与已报名时段冲突检查。

纯函数：不读墙钟、不写状态、不直接依赖 signup_plan 或 infrastructure；
时间解析、模式分类、区间重叠判定与 TaskSpec 构造均由调用方注入。
错误字典结构与 kind 名称是冻结契约，必须逐字保持一致。

@author Author
"""
from __future__ import annotations

from typing import Iterable


def signed_occupancy(rows: Iterable[dict], skip_ids: set[str]) -> list[dict]:
    """把学校已报名活动收敛成冲突基线；只保留判定所需字段，不携带任何凭证。"""
    occupancy: list[dict] = []
    seen: set[str] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        aid = str(row.get("id") or row.get("activity_id") or "")
        if not aid or aid in seen or aid in skip_ids:
            continue
        seen.add(aid)
        occupancy.append({
            "activity_id": aid,
            "name": str(row.get("name") or "活动"),
            "act_start": str(row.get("act_start") or ""),
            "act_end": str(row.get("act_end") or ""),
        })
    return occupancy


def _validate_activity_item(index: int, activity: dict, seen: set[str],
                            now_ts: float, parse_ts, classify_mode,
                            make_spec, errors: list[dict]):
    aid = str(activity.get("id") or "")
    name = str(activity.get("name") or "活动")
    if not aid:
        errors.append({"kind": "missing_id", "index": index, "name": name})
        return None
    if aid in seen:
        errors.append({"kind": "duplicate_id", "activity_id": aid, "name": name})
        return None
    seen.add(aid)
    if bool(activity.get("signed")):
        errors.append({"kind": "already_signed", "activity_id": aid, "name": name})
    sign_start = str(activity.get("sign_start") or "")
    sign_end = str(activity.get("sign_end") or "")
    act_start = str(activity.get("act_start") or "")
    act_end = str(activity.get("act_end") or "")
    if parse_ts(sign_start) is None:
        errors.append({"kind": "invalid_sign_start", "activity_id": aid, "name": name})
    if classify_mode(sign_start, sign_end, now_ts) == "closed":
        errors.append({"kind": "sign_end_passed", "activity_id": aid,
                       "name": name, "sign_end": sign_end})
    start = parse_ts(act_start)
    end = parse_ts(act_end)
    if start is None or end is None:
        errors.append({"kind": "activity_time_unknown", "activity_id": aid, "name": name})
    elif end <= start:
        errors.append({"kind": "activity_time_invalid", "activity_id": aid, "name": name})
    return make_spec(activity, "", bool(activity.get("headed")), now=now_ts)


def _find_spec_overlaps(specs: list, parse_ts, overlap_fn) -> list[dict]:
    conflicts: list[dict] = []
    for index, left in enumerate(specs):
        left_start = parse_ts(left.act_start)
        left_end = parse_ts(left.act_end)
        if left_start is None or left_end is None or left_end <= left_start:
            continue
        for right in specs[index + 1:]:
            right_start = parse_ts(right.act_start)
            right_end = parse_ts(right.act_end)
            if right_start is None or right_end is None or right_end <= right_start:
                continue
            if overlap_fn(left_start, left_end, right_start, right_end):
                conflicts.append({
                    "left": {"activity_id": left.activity_id, "name": left.name,
                             "act_start": left.act_start, "act_end": left.act_end},
                    "right": {"activity_id": right.activity_id, "name": right.name,
                              "act_start": right.act_start, "act_end": right.act_end},
                })
    return conflicts


def _find_signed_conflicts(specs: list, signed_activities, parse_ts,
                           overlap_fn) -> tuple[list[dict], list[dict]]:
    selected_ids = {spec.activity_id for spec in specs}
    signed_overlaps: list[dict] = []
    signed_time_unknown: list[dict] = []
    for row in signed_occupancy(signed_activities or [], selected_ids):
        signed_start = parse_ts(row["act_start"])
        signed_end = parse_ts(row["act_end"])
        if signed_start is None or signed_end is None or signed_end <= signed_start:
            if not any(item["activity_id"] == row["activity_id"]
                       for item in signed_time_unknown):
                signed_time_unknown.append(dict(row, reason="activity_time_unknown"))
            continue
        for spec in specs:
            start = parse_ts(spec.act_start)
            end = parse_ts(spec.act_end)
            if start is None or end is None or end <= start:
                continue
            if overlap_fn(start, end, signed_start, signed_end):
                signed_overlaps.append({
                    "activity_id": spec.activity_id,
                    "name": spec.name,
                    "act_start": spec.act_start,
                    "act_end": spec.act_end,
                    "signed": {"activity_id": row["activity_id"], "name": row["name"],
                               "act_start": row["act_start"], "act_end": row["act_end"]},
                })
    return signed_overlaps, signed_time_unknown


def validate_plan_rows(rows: list[dict], now_ts: float, signed_activities, *,
                       parse_ts, classify_mode, overlap_fn, make_spec) -> dict:
    """按固定顺序执行单项校验、自冲突与已报名冲突校验。"""
    errors: list[dict] = []
    specs: list = []
    seen: set[str] = set()
    for index, activity in enumerate(rows):
        spec = _validate_activity_item(
            index, activity, seen, now_ts, parse_ts, classify_mode, make_spec, errors)
        if spec is not None:
            specs.append(spec)
    conflicts = _find_spec_overlaps(specs, parse_ts, overlap_fn)
    if conflicts:
        errors.append({"kind": "activity_overlap", "conflicts": conflicts})
    signed_overlaps, signed_time_unknown = _find_signed_conflicts(
        specs, signed_activities, parse_ts, overlap_fn)
    if signed_time_unknown:
        errors.append({"kind": "signed_activity_time_unknown",
                       "activity_id": signed_time_unknown[0]["activity_id"],
                       "name": signed_time_unknown[0]["name"],
                       "activities": signed_time_unknown})
    if signed_overlaps:
        errors.append({"kind": "signed_activity_overlap",
                       "activity_id": signed_overlaps[0]["activity_id"],
                       "name": signed_overlaps[0]["name"],
                       "signed": signed_overlaps[0]["signed"],
                       "overlaps": signed_overlaps})
    return {
        "ok": not errors and bool(specs),
        "errors": errors,
        "conflicts": conflicts,
        "signed_overlaps": signed_overlaps,
        "signed_time_unknown": signed_time_unknown,
        "specs": specs,
    }
