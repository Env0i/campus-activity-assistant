#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器自动报名的日志、学校接口查询、token 检查与 owner 私聊通知。

路径和配置由调用方在每次调用时传入，便于测试按环境变量重定向路径并替换入口。
@author Author
"""
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def write_log(msg, default_log_file):
    # 落点每次调用时解析：测试重定向到临时文件，不会碰真实登录目录
    path = os.environ.get("GRAB_LOG_FILE") or default_log_file
    line = "%s %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass    # 日志写不进去不能反过来把报名流程炸掉
    print(line, flush=True)


def read_token(session_file):
    try:
        with open(session_file, "r", encoding="utf-8") as f:
            return str(json.load(f).get("token") or "").strip()
    except Exception:
        return ""


def post_json(api_base, path, payload=None, token="", referer="", ua=UA):
    body = json.dumps(payload if payload is not None else {}).encode("utf-8")
    req = urllib.request.Request(api_base + path, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("token", token)
    req.add_header("Referer", referer)
    req.add_header("User-Agent", ua)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        try:
            raw = resp.read().decode("utf-8", "replace")
        finally:
            resp.close()
        return json.loads(raw)
    except Exception as exc:
        return {"code": -1, "message": type(exc).__name__}


def check_joined(act_id, *, join_info_fn=None, post_fn=None, token_fn):
    """getJoinInfo：未报名时 data 为 null，报名后 data 是对象。"""
    try:
        if join_info_fn is not None:
            data = join_info_fn(act_id, token_fn())
        else:
            data = post_fn("/rjyHdCyr/getJoinInfo/" + act_id, {}, token_fn())
    except Exception:
        return False
    if not isinstance(data, dict) or data.get("code") != 1:
        return False
    return data.get("data") not in (None, {}, [])


def recheck_not_4001(act_id, *, join_info_fn, token_fn, log_fn=None) -> bool:
    """4001 复查：只认明确 code=4001 为仍失效；网络/HTTP/解码异常不算失效。"""
    try:
        data = join_info_fn(act_id, token_fn())
    except Exception as exc:
        if log_fn is not None:
            log_fn("[i] 4001 复查遇到网络或接口异常（%s），不判登录失效，继续本场"
                   % type(exc).__name__)
        return True
    if isinstance(data, dict) and str(data.get("code") or "").strip() == "4001":
        return False
    return True


def ensure_valid_token(login_dir, log_fn):
    """报名前确认 token 可用；失效就先跑一次自动登录。"""
    chk = subprocess.run(["/usr/bin/python3", os.path.join(login_dir, "auto_login.py"), "--check"],
                         capture_output=True, text=True, timeout=90)
    if chk.returncode == 0:
        return True
    log_fn("[i] token 已失效，先执行自动登录")
    run = subprocess.run(["/usr/bin/python3", os.path.join(login_dir, "auto_login.py"), "--force"],
                         capture_output=True, text=True, timeout=300)
    return run.returncode == 0


def send_owner_notify(title, lines, template="green", *, log_fn):
    """私聊发交互卡片：优先用 users.json 里登记的 p2p chat_id；
    没登记（owner 还没私聊过机器人）就直接按 open_id 发，避免静默退化到群发。"""
    try:
        import notify as nt
        cfg = nt.load_config()["notify"]
        app = cfg.get("feishu_app") or {}
        token = nt._tenant_token(app) if app else None
        if not token:
            log_fn("[x] 取 tenant_access_token 失败，通知未发送")
            return False

        chat_id = nt._p2p_chat_id(cfg)
        owner = os.environ.get("PRIVATE_OWNER_OPEN_ID", "").strip()
        if chat_id:
            rid, rid_type = chat_id, "chat_id"
        elif owner:
            rid, rid_type = owner, "open_id"
        else:
            log_fn("[x] 既无 p2p chat_id 也无 owner open_id，通知未发送")
            return False

        card = {
            "config": {"wide_screen_mode": True},
            "header": {"template": template,
                       "title": {"tag": "plain_text", "content": title}},
            "elements": [{"tag": "div", "text": {"tag": "lark_md",
                                                 "content": "\n".join(lines)}}],
        }
        ok, body = nt._post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=" + rid_type,
            {"receive_id": rid, "msg_type": "interactive",
             "content": json.dumps(card, ensure_ascii=False)}, token=token)
        if ok and nt._business_ok(body, "feishu"):
            log_fn("[i] 私聊卡片已发送（%s）" % rid_type)
            return True
        log_fn("[i] 私聊卡片失败（%s）：%s" % (rid_type, str(body)[:120]))
        return bool(nt.send_private(title + "\n" + "\n".join(lines)))
    except Exception as exc:
        log_fn("[x] 通知失败：%s" % type(exc).__name__)
        return False


def build_detail_url(school_origin, act_id):
    return (school_origin + "/stu/#/secondClassroom/student/activity/"
            "studentActivity/activityDetails?activityId=%s&from=acList" % act_id)


def wait_until(ts):
    while True:
        left = ts - time.time()
        if left <= 0:
            return
        time.sleep(min(0.2, left))
