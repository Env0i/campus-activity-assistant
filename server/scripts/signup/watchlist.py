"""预报名清单：先记下「想报哪个活动」，到点由 watchlist_runner.py 自动抢。

和 state.json 分开放：state.json 记的是「抓取/推送进度」，属于机器状态；
watchlist.json 记的是「人的意愿」。两者的生命周期和回滚方式都不一样，
混在一起会让「清空去重状态」和「取消某个预报名」互相牵连。

命令行（机器人按钮回调也走这里）：
    python3 scripts/signup/watchlist.py add --id <活动id> --name <名称> --at "2026-10-23 19:00:00"
    python3 scripts/signup/watchlist.py remove --id <活动id>
    python3 scripts/signup/watchlist.py list

add 时传入的 open_at / lead / window / sign_end 是 runner 的冻结策略起点：
存下之后不再改写，watchlist_runner 原样交给 grab_signup，25 分钟自适应扩窗
（黄金风暴 / 404 退避那套 retry 策略）只发生在那一场的执行过程里，不会回写
清单。sign_end 可选，给了就是报名截止硬上限（grab_signup 的扩窗绝不越过它）。

状态流转：queued（排队）→ running（已拉起抓取）→ done / failed / missed。
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
# 跨进程锁与原子写复用 common 的实现（POSIX flock / Windows msvcrt 都真正加锁）
for _sub in ("signup", "lib"):
    _p = str(ROOT / "scripts" / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)
import fetch  # noqa: E402
import mine_rules as rules  # noqa: E402
from common import atomic_write_text, file_lock, load_session  # noqa: E402

# 测试时可以指到临时文件，避免污染真实清单
FILE = Path(os.environ.get("WATCHLIST_FILE") or (ROOT / "data" / "watchlist.json"))
LOCK = Path(os.environ.get("WATCHLIST_LOCK") or (FILE.parent / "watchlist.lock"))
FMT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LEAD = 100.0      # 提前多少秒打开详情页
DEFAULT_WINDOW = 120.0    # 开放后最多尝试多少秒
ACTIVE = ("queued", "running")


def now_str() -> str:
    return datetime.now().strftime(FMT)


def parse_at(text: str) -> datetime:
    """只接受绝对时间：相对说法（「明天」「今晚」）在定时任务里没有可靠语义。"""
    raw = str(text or "").strip()
    for fmt in (FMT, "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError("时间格式不对：%r（要 YYYY-MM-DD HH:MM:SS）" % raw)


def load() -> list:
    """读清单。文件不存在算空清单；解析失败抛错，绝不静默当成空。"""
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except Exception as exc:
        # 读坏了不静默清空：那是真人点出来的「预报名」，丢了就再也不会报名
        raise RuntimeError("watchlist.json 读取失败：%s" % exc)
    entries = data.get("entries") if isinstance(data, dict) else data
    return [e for e in (entries or []) if isinstance(e, dict) and e.get("id")]


def save(entries: list) -> None:
    """原子写（0600）：命令行增删与 runner 标记共用同一份文件。"""
    atomic_write_text(FILE, json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
                      mode=0o600)


@contextlib.contextmanager
def _transaction():
    """锁内读改写：并发 add/remove/mark 不丢用户预报名（P2-3）。

    锁内只做本地读改写，不联网、不刷新卡片；解析失败原样抛出，
    绝不用空清单覆盖已有内容。
    """
    with file_lock(LOCK):
        entries = load()
        state = {"changed": False}
        yield entries, state
        if state["changed"]:
            save(entries)


def find(entries: list, activity_id: str):
    for e in entries:
        if e.get("id") == activity_id:
            return e
    return None


def _refresh_card() -> None:
    """非点击场景的卡片刷新（runner 抢完一场后调用）。

    点击按钮引起的翻转不走这里：飞书要求按钮回调直接回传新卡片，
    客户端当场替换。如果点击时再用 PATCH 改一次，两次更新会互相覆盖，
    表现就是「刚变成已预报名，一眨眼又变回预报名」。
    """
    try:
        import grab_card
        grab_card.refresh()
    except Exception as exc:
        print("[!] 卡片刷新失败：%s" % exc)


def _list_items() -> list:
    """取一次活动列表，供冲突比对看「本人报了谁、清单里排着谁」。

    取不到就抛出：静默放行等于把两个撞车的场次一起排进清单，
    到点必然有一场白抢，还占着已报名的名额。
    """
    token = str(load_session().get("token") or "").strip()
    if not token:
        raise RuntimeError("没有登录态，没法确认已报名场次的时段，先不加入")
    try:
        return fetch.fetch_all(token)
    except Exception as exc:                                  # noqa: BLE001
        raise RuntimeError("取活动列表失败（%s），没法确认是否和已报名的撞上，先不加入"
                           % type(exc).__name__) from exc


def _span(item: dict):
    """一场活动的举办时段；没公布或写坏都算「查不到」，返回 None。"""
    return rules.interval(item.get("act_start"), item.get("act_end"))


def _span_text(item: dict) -> str:
    return rules.span_text(item.get("act_start"), item.get("act_end")) or "%s–%s" % (
        item.get("act_start") or "?", item.get("act_end") or "?")


def _conflict_note(activity_id: str, items: list, entries: list) -> str:
    """新场次和已报名、清单里排队中的场次比举办时段，半开区间重叠就算冲突。

    冲突、对方时段查不到都抛 RuntimeError（拒绝加入并说明）；只有新场次自己的
    举办时间没公布时返回一句备注——那时允许加入，硬拦下来等于凭空少一次报名机会。
    """
    target = next((it for it in items if it.get("id") == activity_id), None)
    mine = _span(target) if target else None
    if mine is None:
        return "举办时间未公布，暂时没法检查是否和已报名或排队的场次冲突"
    for item in items:
        if item.get("id") == activity_id or not item.get("signed"):
            continue
        other = _span(item)
        if other is None:
            raise RuntimeError("已报名的「%s」举办时间未知，可能和这场撞上，先不加入"
                               % (item.get("name") or "活动"))
        if rules.overlaps(mine, other):
            raise RuntimeError("和已报名的「%s」时段重叠：%s"
                               % (item.get("name") or "活动", _span_text(item)))
    for entry in entries:
        if entry.get("id") == activity_id or entry.get("status") not in ACTIVE:
            continue
        queued = next((it for it in items if it.get("id") == entry.get("id")), None)
        other = _span(queued) if queued else None
        if other is None:
            raise RuntimeError("清单里排着「%s」，但查不到它的举办时间，可能和这场撞上，先不加入"
                               % (entry.get("name") or "活动"))
        if rules.overlaps(mine, other):
            raise RuntimeError("和清单里排队的「%s」时段重叠：%s"
                               % (entry.get("name") or "活动", _span_text(queued)))
    return ""


def add(activity_id: str, name: str, open_at: str,
        lead: float = DEFAULT_LEAD, window: float = DEFAULT_WINDOW,
        sign_end: str = "", items: list = None) -> dict:
    """同一活动重复点「预报名」按覆盖处理，不叠出两条。

    items 是调用方先取好的活动列表（命令行路径总传）：传了就在写清单前做时段
    冲突检查，撞车或查不清直接拒绝，清单一个字节都不动。
    """
    start = parse_at(open_at)          # 先校验，避免把写坏的时间存进去
    end_ts = None
    if str(sign_end or "").strip():
        end_ts = parse_at(str(sign_end).strip())
        # 截止早于开放等于一开跑就过期：拒绝写入，不让清单带着坏策略排班
        if end_ts <= start:
            raise RuntimeError("报名截止（sign_end）不能早于开放时间：%s" % sign_end)
    # 老卡片留到第二天再点的情况：窗口已经过去了，排进去只会在下一分钟被标「错过」，
    # 还会给用户发一条莫名其妙的失败提醒。直接拒绝，并说清原因。
    if datetime.now() > start + timedelta(seconds=float(window)):
        raise RuntimeError(
            "这场报名窗口已经结束（%s 开放），预报名不适用" % open_at)
    with _transaction() as (entries, state):
        # 冲突检查放在锁内：清单刚被别的点击改过也能看到最新的排队场次
        note = _conflict_note(activity_id, items, entries) if items is not None else ""
        entry = find(entries, activity_id)
        if entry is None:
            entry = {"id": activity_id, "attempts": 0, "created_at": now_str()}
            entries.append(entry)
        entry.update({
            "name": name or entry.get("name") or "活动",
            "open_at": open_at,
            "lead": float(lead),
            "window": float(window),
            # 可选硬截止：空串表示学校没给，grab_signup 按窗口 + 自适应扩窗执行
            "sign_end": str(sign_end or "").strip(),
            "status": "queued",
            "result": "",
            "started_at": "",
            "finished_at": "",
        })
        state["changed"] = True
    if note:
        entry["conflict_note"] = note   # 只回给调用方看，事务已经写完，不会进清单文件
    return entry


def remove(activity_id: str) -> bool:
    with _transaction() as (entries, state):
        kept = [e for e in entries if e.get("id") != activity_id]
        if len(kept) == len(entries):
            return False
        entries[:] = kept
        state["changed"] = True
    return True


def mark(activity_id: str, **fields) -> dict:
    with _transaction() as (entries, state):
        entry = find(entries, activity_id)
        if entry is None:
            return {}
        entry.update(fields)
        state["changed"] = True
    return entry


def _add_line(entry: dict) -> str:
    """加入成功的那一行；举办时间没公布时把「没查冲突」一并写出来。"""
    line = "已加入预报名：%s  %s（提前 %d 秒开页面）" % (
        entry["name"], entry["open_at"], int(entry["lead"]))
    note = entry.get("conflict_note") or ""
    return line + ("（%s）" % note if note else "")


def _fmt_line(e: dict) -> str:
    status = {"queued": "排队", "running": "抓取中", "done": "已报名",
              "failed": "失败", "missed": "错过"}.get(e.get("status"), e.get("status") or "?")
    line = "%s  %s  %s" % (status, e.get("open_at", "?"), e.get("name") or "活动")
    if e.get("result"):
        line += "  (%s)" % e["result"]
    return line


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="预报名清单")
    sub = ap.add_subparsers(dest="cmd")

    p_add = sub.add_parser("add", help="加入预报名")
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--name", default="活动")
    p_add.add_argument("--at", required=True, help="报名开放时间 YYYY-MM-DD HH:MM:SS")
    p_add.add_argument("--lead", type=float, default=DEFAULT_LEAD)
    p_add.add_argument("--window", type=float, default=DEFAULT_WINDOW)
    p_add.add_argument("--sign-end", default="",
                       help="可选：报名截止时间（硬上限）YYYY-MM-DD HH:MM:SS")

    for name in ("remove", "cancel"):
        p_rm = sub.add_parser(name, help="取消预报名")
        p_rm.add_argument("--id", required=True)

    sub.add_parser("list", help="看清单")

    args = ap.parse_args(argv)
    if not args.cmd:
        args.cmd = "list"

    if args.cmd == "add":
        try:
            entry = add(args.id, args.name, args.at, args.lead, args.window,
                        args.sign_end, items=_list_items())
        except (ValueError, RuntimeError) as exc:
            print("[x] %s" % exc)
            return 1
        print(_add_line(entry))
        return 0

    if args.cmd in ("remove", "cancel"):
        try:
            removed = remove(args.id)
        except (ValueError, RuntimeError) as exc:
            # 清单损坏时明确失败，不用空清单覆盖（那是真人点出来的预报名）
            print("[x] %s" % exc)
            return 1
        if removed:
            print("已取消预报名：%s" % args.id)
            return 0
        print("清单里没有这条：%s" % args.id)
        return 1

    entries = load()
    if not entries:
        print("清单是空的。")
        return 0
    order = {"queued": 0, "running": 1, "done": 2, "failed": 3, "missed": 4}
    entries.sort(key=lambda e: (order.get(e.get("status"), 9), e.get("open_at") or ""))
    for e in entries:
        print(_fmt_line(e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
