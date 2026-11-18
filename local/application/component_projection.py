# -*- coding: utf-8 -*-
"""高级功能弹窗的状态投影：只做拼装，不读文件、不取锁、不发事件。

输入全部由组合根取好（偏好、组件状态、隧道状态、凭据与自动登录快照），
输出就是 `advanced_features_state` 的返回体。拆出来的目的有两个：

- 让组合根只负责「取数 + 转发」，簿记逻辑不再堆在 `Api` 里；
- 投影本身可以拿内存输入直接验，不必造一个完整的 `Api`。

@author Author
"""
from __future__ import annotations

# 隧道退出时的默认文案：进程异常退出后 status() 只会读到 stopped，
# 这份提示由调用方在本次响应里留档，投影原样呈现
_EXIT_TEXT = "Cloudflare 隧道已退出，重新开启会得到新地址。"


def _cloudflare_channel(*, status: dict, exit_notice: dict, executable: str) -> tuple:
    """Cloudflare 通道的三元结论：(state, text, error_code)。"""
    if exit_notice:
        # 进程已经退出：这次刷新就要报「退出」，不能因为读到的第二次状态是
        # stopped 就把通道重新说成可用——用户会照着旧地址去扫码。
        return ("exited",
                str(exit_notice.get("text") or _EXIT_TEXT),
                "tunnel_exited")
    if not executable:
        return ("missing", "没有找到 cloudflared，Cloudflare 通道目前不可用。",
                "cloudflared_missing")
    # 快速隧道地址每次开启都变，所以状态只有「可用/在运行」两档，
    # 且必须把「重启后要重新扫码」写进快照，界面照抄，不再自行判断
    running = bool(status.get("running"))
    return ("running" if running else "available",
            "Cloudflare 临时地址正在提供访问。" if running
            else "可用时由 Cloudflare 临时地址提供远程访问。",
            "")


def advanced_features_state(*, features: dict, advanced_busy: bool, downloads: dict,
                            tailscale: dict, cloudflare_status: dict,
                            cloudflare_exit: dict, cloudflare_executable: str,
                            credential: dict, phone_access: dict) -> dict:
    """帮助弹窗使用的高级功能快照；不返回密码、密文或安装路径。

    与原 `Api.advanced_features_state` 的输出逐键一致：features 里每行附带
    本次下载事务快照与 busy 标记，channels 给出两条通道各自的能力与限制，
    credential 只给打码后的账号与「有没有」这类布尔。
    """
    features = {key: dict(value) for key, value in features.items()}
    if advanced_busy:
        for feature in features.values():
            feature["busy"] = True
    # 组件下载事务的快照挂在各自那一行：界面据此显示下载中、失败、可取消
    for key, download in downloads.items():
        if key in features:
            features[key]["download"] = dict(download) if isinstance(download, dict) else {}
    cf_state, cf_text, cf_error = _cloudflare_channel(
        status=cloudflare_status, exit_notice=cloudflare_exit,
        executable=cloudflare_executable)
    return {
        "ok": True,
        "features": features,
        "channels": {
            "tailscale": dict(tailscale,
                              temporary=False,
                              restart_requires_pairing=False,
                              restart_note="地址固定：重启程序后手机仍可直接打开。"),
            "cloudflare": {
                "available": bool(cloudflare_executable),
                "error": cf_error,
                "state": cf_state,
                "text": cf_text,
                "temporary": True,
                "restart_requires_pairing": True,
                "restart_note": "临时地址：重启或重新开启后地址会变，手机需要重新扫码配对。",
            },
        },
        "phone_access": dict(phone_access),
        "credential": {
            # 保存账号只看本机加密存储；ddddocr 是否就绪单列，界面分开显示
            "available": bool(credential.get("store_available")),
            "store_available": bool(credential.get("store_available")),
            "saved": bool(credential.get("saved")),
            "username": str(credential.get("username") or ""),
            "ocr_ready": bool(credential.get("ocr_ready")),
            "automatic": dict(credential.get("automatic") or {}),
            # B4：这次运行内存里有没有「只用这一次」的账号；只给打码账号，绝无密码
            "staged": bool(credential.get("staged")),
            "staged_hint": str(credential.get("staged_hint") or ""),
            "last_origin": str(credential.get("last_origin") or ""),
            # 学校说保存的密码不对：自动登录已暂停，写入新密码后解除
            "paused": bool(credential.get("paused")),
        },
    }
