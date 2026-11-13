# -*- coding: utf-8 -*-
"""统一脱敏：样机结果写盘前的最后一道闸。

规则来自计划 20261112-esm-verify 的 rules.must：
  - 本机路径一律替换为 <资源根> / <用户目录>
  - 隧道域名、tailnet 名、100.x 地址一律替换为通道名（tailscale / cloudflare）
  - 只保留协议、端口、User-Agent、版本号和探针结果

用法：
  python redact.py --selftest        # 跑内置断言
  python redact.py --check FILE...   # 检查已落盘文件里还有没有残留
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from typing import Any, Iterable

# (编译后的正则, 替换文本)。顺序有意义：先长后短，先具体后一般。
PATTERNS = [
    # file:// 地址里的主机段（UNC 共享或虚拟机共享盘名）：整段替换
    (re.compile(r"file://[^/\s\"'<>]+/[^\"'<>\r\n]*"), "file://<资源根>"),
    # Windows 盘符路径（含 file:///D:/... 里的写法）；http:// 里的 "p:/" 由前置字符挡掉。
    # 路径可能含空格（如 Shared Folders），一直匹配到引号、换行或尖括号为止。
    (re.compile(r"(?<![\w])[A-Za-z]:[\\/][^\r\n\"'<>|,)\]}]*"), "<资源根>"),
    # UNC 共享路径（同上，允许空格）
    (re.compile(r"\\\\[^\r\n\"'<>|,)\]}]+"), "<资源根>"),
    # 虚拟机共享盘在 file:// 的 pathname 里的写法
    (re.compile(r"/Shared%20Folders/[^\"'<>\r\n]*"), "<资源根>"),
    # macOS / Linux 用户目录（允许空格）
    (re.compile(r"/Users/[^\r\n\"'<>]+"), "<用户目录>"),
    (re.compile(r"/home/[^\r\n\"'<>]+"), "<用户目录>"),
    # Cloudflare 临时隧道
    (re.compile(r"\b[a-z0-9][a-z0-9-]*\.trycloudflare\.com\b", re.I), "cloudflare"),
    # Tailscale MagicDNS（<host>.<tailnet>.ts.net）
    (re.compile(r"\b[a-z0-9][a-z0-9.-]*\.ts\.net\b", re.I), "tailscale"),
    # Tailscale 100.x 地址
    (re.compile(r"\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "100.x"),
]


# X2（返修）：回环地址与空串不是机器名，不进脱敏名单。
# 否则 127.0.0.1 会被替成 <主机名>，「页面经 127.0.0.1 供页」这条证据就丢了。
def strip_port(name: str) -> str:
    # location.host 带端口（如 127.0.0.1:8765），端口不属于机器名，先去掉再判断
    text = str(name or "").strip()
    if text.startswith("["):
        end = text.find("]")
        return text[1:end] if end > 0 else text
    if text.count(":") == 1:
        return text.split(":", 1)[0]
    return text


def is_loopback_name(name: str) -> bool:
    text = strip_port(name).strip("[]").lower()
    if text == "localhost":
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


def usable_names(names: Iterable[str]) -> list[str]:
    """返回真正需要脱敏的机器名：去掉空串、过短的串和回环地址。"""
    out: list[str] = []
    for raw in names:
        name = strip_port(raw)
        if len(name) < 3 or is_loopback_name(name):
            continue
        if name not in out:
            out.append(name)
    return out


def redact_text(text: str, extra_names: Iterable[str] = ()) -> str:
    out = str(text)
    # 先按路径模式整段替换，再替换单独出现的主机名；反过来的话，UNC 的 \主机\ 会先变成 \<主机名>\，路径模式就匹配不上了
    for pattern, repl in PATTERNS:
        out = pattern.sub(repl, out)
    for name in usable_names(extra_names):
        out = re.sub(re.escape(name), "<主机名>", out, flags=re.I)
    return out


def redact_obj(value: Any, extra_names: Iterable[str] = ()) -> Any:
    """递归脱敏；dict 的键也一并处理（Host 头会当键用）。"""
    if isinstance(value, str):
        return redact_text(value, extra_names)
    if isinstance(value, dict):
        return {redact_text(k, extra_names): redact_obj(v, extra_names)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_obj(item, extra_names) for item in value]
    return value


def find_residual(text: str, extra_names: Iterable[str] = ()) -> list[str]:
    found: list[str] = []
    for name in usable_names(extra_names):
        if re.search(re.escape(name), str(text), flags=re.I):
            found.append("hostname:" + name)
    for pattern, _repl in PATTERNS:
        for match in pattern.finditer(str(text)):
            found.append(match.group(0))
    return found


SELFTEST_INPUT = {
    "file": "Q:\\fictional-root\\sample-dir\\lib\\util.py",
    "url": "file:///Q:/fictional-root/sample-dir/ui/index.html",
    "tunnel": "https://quiet-forest-1234.trycloudflare.com/",
    "tailnet": "my-pc.tail1234.ts.net:8765",
    "ts_ip": "http://100.101.102.103:8765/index.html",
    "user": "/Users/someone/Library/Application Support",
    "keep": "http://127.0.0.1:8765/index.html",
    "share_url": "file://share-host/Shared%20Folders/Projects/sample/page.html",
    "unc": "\\\\share-host\\Shared Folders\\Projects\\sample\\data.json",
}


def selftest() -> int:
    red = redact_obj(SELFTEST_INPUT)
    cases = [
        ("盘符路径", "Q:\\" not in json.dumps(red, ensure_ascii=False)),
        ("file URL 里的盘符", "Q:/" not in json.dumps(red, ensure_ascii=False)),
        ("隧道域名", "trycloudflare" not in json.dumps(red, ensure_ascii=False)),
        ("tailnet 名", "ts.net" not in json.dumps(red, ensure_ascii=False)),
        ("100.x", "100.101" not in json.dumps(red, ensure_ascii=False)),
        ("用户目录", "/Users/someone" not in json.dumps(red, ensure_ascii=False)),
        ("保留回环地址", red["keep"] == "http://127.0.0.1:8765/index.html"),
        ("保留协议与端口", ":8765" in red["ts_ip"]),
        ("file 主机段与共享盘", "share-host" not in json.dumps(red, ensure_ascii=False) and "Shared%20Folders" not in json.dumps(red, ensure_ascii=False)),
        ("含空格的 UNC 路径", "Projects" not in json.dumps(red, ensure_ascii=False)),
        ("无残留", not find_residual(json.dumps(red, ensure_ascii=False))),
        # X2：回环地址与空串不进名单、不被替换；真机器名仍照常替换
        ("回环与空串不进名单", usable_names(["127.0.0.1", "localhost", "::1", "[::1]", ""]) == []),
        ("回环地址原样保留", redact_text("http://127.0.0.1:8765/ localhost [::1]", ["127.0.0.1", "localhost", "::1", "[::1]", ""]) == "http://127.0.0.1:8765/ localhost [::1]"),
        ("空串不替换", redact_text("abc def", [""]) == "abc def"),
        ("真机器名仍脱敏", redact_text("host-sample-x:8765", ["host-sample-x"]) == "<主机名>:8765"),
        ("带端口的回环不进名单", usable_names(["127.0.0.1:8765", "localhost:8765", "[::1]:8765"]) == []),
        ("带端口的回环原样保留", redact_text("http://127.0.0.1:8765/", ["127.0.0.1:8765"]) == "http://127.0.0.1:8765/"),
    ]
    failed = [name for name, ok in cases if not ok]
    for name, ok in cases:
        print(("PASS  " if ok else "FAIL  ") + name)
    print(json.dumps(red, ensure_ascii=False, indent=2))
    return 1 if failed else 0


def check_files(paths: Iterable[str], extra_names: Iterable[str] = ()) -> int:
    bad = 0
    for path in paths:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        hits = find_residual(text, extra_names)
        if hits:
            bad += 1
            print("FAIL  %s 残留 %d 处：%s" % (path, len(hits), ", ".join(sorted(set(hits))[:8])))
        else:
            print("PASS  %s" % path)
    return 1 if bad else 0


def main() -> int:
    # X2 同源：自检要打印中文，stdout 不是 UTF-8 时（管道、重定向）改为 UTF-8 + replace，避免抛编码错误
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--check", nargs="*", default=None)
    parser.add_argument("--name", action="append", default=None,
                        help="额外要脱敏的主机名，可重复")
    args = parser.parse_args()
    names = args.name or []
    if args.selftest:
        return selftest()
    if args.check is not None:
        return check_files(args.check, names)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
