# -*- coding: utf-8 -*-
"""桌面窗口外壳：关窗三选、隐藏与唤回、托盘、二次打开与计划结束提醒。

搬自 `app.Api` 的窗口一组方法。窗口对象、托盘、偏好、手机状态与计划负担一律
经端口拿：application 层不 import webview、tray_icon 或任何 infrastructure
模块，组合根负责把这些接上。

状态归属：`window` / `tray` / `hidden` / `minimized` / `close_approved` 随本
服务走，Api 上保留旧字段名的 property 代理，`main()` 里 `api._window = window`
的写法与各动作读 `api._window` 的语义都不变。关停屏障仍归
`application.desktop_lifecycle`，这里只管窗口本身。

@author Author
"""
from __future__ import annotations


class DesktopWindow:
    """窗口与托盘的唯一持有者；所有副作用经 ports 注入。"""

    def __init__(self, *, lock, coordination, ports):
        self._lock = lock
        self._coord = coordination
        self._ports = ports
        # 窗口对象由组合根在 create_window 之后赋进来（源码态与冻结态同一入口）
        self.window = None
        # 托盘图标：只在窗口藏起来以后才建，建不起来也不影响主程序
        self.tray = None
        # 窗口不在眼前（最小化或隐藏到后台）时，计划结束要发系统通知
        self.hidden = False
        self.minimized = False
        # 关窗弹窗里点过「退出」才放行：closing 事件返回 False 会取消关闭
        self.close_approved = False

    # ---------- 计划在跑：关窗必须先问 ----------
    def plan_active_for_close(self) -> bool:
        """计划在跑或已就绪：关窗必须先问，不能静默最小化/退出。"""
        plan = self._ports["plan"]()
        if plan is None:
            return False
        try:
            return plan.published_status() in {"running", "ready"}
        except Exception:  # noqa: BLE001 - 拿不到状态就按「没在跑」处理
            return False

    def _close_plan_burden(self) -> dict:
        """关窗问询用的计划负担（BE1，c3-dialogs-gap CW03/CW04/CW08）：
        waiting_count=还没提交的场数，next_batch_at=最近一批开放的北京时间 HH:MM:SS。

        只读协调器现有快照（statuses queued/waiting），不新造状态；时刻换算走
        注入的学校时间函数（决策 012），不读本机墙钟，钟不可用或拿不到批次时
        next_batch_at 给空串。任何异常都按「拿不到」处理：这两个字段只影响
        文案里的数字，绝不能把关窗问询本身卡死。
        """
        try:
            plan = self._ports["plan"]()
            if plan is None:
                return {"waiting_count": 0, "next_batch_at": ""}
            tasks = (plan.snapshot() or {}).get("tasks") or []
            pending = [task for task in tasks
                       if str(task.get("status") or "") in {"queued", "waiting"}]
            if not pending:
                return {"waiting_count": 0, "next_batch_at": ""}
            next_at = ""
            if self._ports["clock_ready"]():
                epochs = [self._ports["epoch_of"](str(task.get("sign_start") or ""))
                          for task in pending]
                epochs = [epoch for epoch in epochs if epoch is not None]
                if epochs:
                    # 学校时间文本输出 YYYY-MM-DD HH:MM:SS，取后段的时刻
                    next_at = self._ports["time_text_of"](min(epochs))[11:]
            return {"waiting_count": len(pending), "next_batch_at": next_at}
        except Exception:  # noqa: BLE001 - 只影响文案数字，不能卡死问询
            return {"waiting_count": 0, "next_batch_at": ""}

    def ask_window_close(self) -> dict:
        """把「要关了，你想怎样」推给界面去选；返回本次判定依据。

        tray_ok / phone_running / phone_live 让对话框先列出正在运行的东西，并说清
        「隐藏到后台」能不能用：托盘建不起来、手机又没连时隐藏就叫不回来。
        waiting_count / next_batch_at（BE1）给利害清单与退出代价写真实数字，只增不改。
        """
        plan_running = self.plan_active_for_close()
        action = self._ports["resolve_close_action"](self._ports["load_prefs"](), plan_running)
        try:
            tray_ok = bool(self._ports["ensure_tray"]())
        except Exception:  # noqa: BLE001 - 托盘建不起来按不可用
            tray_ok = False
        try:
            phone_running = bool(self._ports["phone_running"]())
            phone_live = bool(self._ports["phone_live"]())
        except Exception:  # noqa: BLE001 - 手机状态读不到按没连
            phone_running = phone_live = False
        payload = {"plan_running": plan_running, "default_action": action,
                   "tray_ok": tray_ok, "phone_running": phone_running, "phone_live": phone_live}
        payload.update(self._close_plan_burden())
        self._ports["emit"]("window_close_ask", payload)
        return dict(payload, ok=True)

    def request_window_close(self, action: str = "") -> dict:
        """界面四选的结果：hide 藏到后台 / minimize / exit / 先不关，remember_ 表示「以后都这样」。

        只认这几个词；记住的选择写进偏好的 window.close_action，
        下次点 X 直接照做（计划在跑时仍会先问）。

        hide 是唯一「先做再记」的选项：这条出口有门禁（托盘或手机访问必须至少
        通一条），门禁没过就不能把「以后都隐藏」写进偏好——否则下次点 X 会直接
        走到一条走不通的路上，而用户根本没成功隐藏过。
        """
        action = str(action or "")
        allowed = ("hide", "minimize", "exit",
                   "remember_hide", "remember_minimize", "remember_exit")
        if action not in allowed:
            return {"ok": False, "error": "bad_action", "text": "未知的关闭方式。"}
        remember = action.startswith("remember_")
        chosen = action[len("remember_"):] if remember else action
        if chosen == "hide":
            result = self.hide_window()
            result["remembered"] = False
            if not result.get("ok"):
                # 门禁没通过：原样返回失败原因，用户原来的偏好一个字都不动
                return result
            if remember:
                if self._remember_close_action("hide"):
                    result["remembered"] = True
                else:
                    # 已经藏起来了就别再翻回来，只是这次没记住
                    result["text"] = "窗口已隐藏，但偏好没有保存成功，这次先不记住。"
            return result
        if remember and not self._remember_close_action(chosen):
            return {"ok": False, "error": "prefs_busy",
                    "text": "偏好没有保存成功，这次先不记住。"}
        if chosen == "minimize":
            try:
                self.window.minimize()
            except Exception:  # noqa: BLE001 - 窗口不可用按失败返回
                return {"ok": False, "error": "no_window", "text": "窗口不可用，没能最小化。"}
            self.minimized = True
            return {"ok": True, "action": "minimize", "remembered": remember}
        self.close_approved = True
        try:
            self.window.destroy()
        except Exception:  # noqa: BLE001 - 窗口不可用按失败返回
            return {"ok": False, "error": "no_window", "text": "窗口不可用，没能退出。"}
        return {"ok": True, "action": "exit", "remembered": remember}

    def _remember_close_action(self, action: str) -> bool:
        """把「以后都这样」写进偏好的 window.close_action，返回是否写成功。"""
        prefs = self._ports["load_prefs"]()
        window = dict(prefs.get("window") or {}) if isinstance(prefs.get("window"), dict) else {}
        window["close_action"] = action
        return bool(self._ports["update_prefs"]({"window": window}))

    # ---------- 隐藏到后台（窗口消失、进程继续跑） ----------
    def hide_window(self) -> dict:
        """把窗口藏起来：手机访问、报名计划、校时全都继续跑。

        藏起来以后任务栏上就没有按钮了，所以必须先有一条能把界面叫回来的路：
        托盘图标，或者至少还有一条未过期的手机会话。两样都没有就拒绝隐藏——
        把窗口藏成再也打不开的样子，比不让它隐藏糟糕得多。
        """
        tray = self._ports["ensure_tray"]()
        if not tray:
            if not self._ports["phone_live"]():
                return {"ok": False, "error": "hide_unavailable",
                        "text": "托盘图标和手机访问都不可用：现在隐藏就没法把窗口叫回来，"
                                "这次先不隐藏。"}
            self._ports["log"]("托盘图标没有建起来：隐藏后请用手机页的「显示电脑窗口」叫回界面。")
        try:
            self.window.hide()
        except Exception:  # noqa: BLE001 - 窗口不可用按失败返回
            return {"ok": False, "error": "no_window", "text": "窗口不可用，没能隐藏。"}
        self._ports["log"]("窗口已隐藏到后台；进程继续运行，托盘或手机页可以唤回")
        self.hidden = True
        self._notify_window_hidden()
        return {"ok": True, "action": "hide", "hidden": True, "tray": self.tray is not None}

    def _notify_window_hidden(self) -> None:
        """隐藏成功后弹一次托盘系统通知（BE2，c3-dialogs-gap CW10）：窗口一藏，
        任务栏上就没有按钮了，托盘气泡是「怎么叫回来」的路标。

        托盘没建起来或 notify 抛错都吞掉：通知只是路标，不影响隐藏结果与返回值；
        同一次隐藏只在 hide_window 成功路径上调这一处。
        """
        try:
            if self.tray is not None:
                self.tray.notify("窗口已隐藏，工具在后台运行",
                                 "报名计划照常运行。点右下角托盘图标回来，"
                                 "也可以在手机页点“显示电脑窗口”。")
        except Exception:  # noqa: BLE001 - 通知失败不影响隐藏
            pass

    def show_window(self) -> dict:
        """把藏起来的窗口叫回来（托盘菜单、手机页都用这一个入口）。"""
        try:
            self.window.show()
        except Exception:  # noqa: BLE001 - 窗口不可用按失败返回
            return {"ok": False, "error": "no_window", "text": "窗口不可用，没能显示。"}
        try:
            # 从最小化里叫回来也走这里：隐藏和最小化一起清掉
            self.window.restore()
        except Exception:  # noqa: BLE001 - 恢复失败只当没最小化
            pass
        self.hidden = False
        self.minimized = False
        self._ports["log"]("窗口已从后台显示出来")
        return {"ok": True, "hidden": False, "tray": self.tray is not None}

    def window_visibility(self) -> dict:
        """窗口是否藏在托盘里（界面自动刷新活动列表前问一次）。

        pywebview 隐藏窗口时 WebView2 会不会把 document.hidden 置真无法离线验证，
        所以界面除了看 document.hidden，还要问这里：藏在托盘里的窗口不该每 10 分钟
        在后台悄悄访问学校。只读 hidden，不碰窗口、不联网，也不回别的字段。
        """
        with self._lock:
            return {"hidden": bool(self.hidden)}

    def _on_window_minimized(self) -> None:
        self.minimized = True

    def _on_window_restored(self) -> None:
        self.minimized = False

    def _on_second_open(self) -> None:
        """又打开了一次（GL01）：第二份已经退出，把这扇窗叫回前台并告诉界面。

        叫回复用 show_window（托盘、手机页同一入口，藏到后台或最小化都能叫回来）；
        at 是业务时钟秒，时钟不可用给 null，不拿本机墙钟冒充（决策 012）。
        界面据 second_open 出 note 横幅（Main:2145）。
        """
        try:
            self.show_window()
        except Exception:  # noqa: BLE001 - 叫不回来也要把事件送出去
            pass
        try:
            at = float(self._ports["clock_now"]())
        except Exception:  # noqa: BLE001 - 时钟不可用给 null
            at = None
        self._ports["emit"]("second_open", {"at": at})
        # 运行记录句照原型 Main:1181
        self._ports["emit"]("log", "又打开了一次，已切回这个窗口")

    def _notify_plan_done(self, snapshot) -> None:
        """窗口最小化或藏在后台时计划结束：托盘弹一条系统通知，点通知回到窗口。

        窗口就在眼前时不打扰；托盘建不起来就不发，结果仍在窗口里。
        """
        if not (self.hidden or self.minimized):
            return
        title, text = self._ports["plan_done_notice"]((snapshot or {}).get("tasks") or [])
        try:
            if self._ensure_tray() and self.tray is not None:
                self.tray.notify(title, text)
        except Exception:  # noqa: BLE001 - 通知失败不影响计划收尾
            pass

    # ---------- 托盘 ----------
    def _ensure_tray(self) -> bool:
        """懒建托盘图标；已经建过就直接复用。任何异常都只当作「没有托盘」。"""
        if self.tray is not None:
            return True
        try:
            tray = self._ports["tray_factory"](
                on_show=self.show_window,
                on_exit=lambda: self.request_window_close("exit"))
            if tray.start():
                self.tray = tray
                return True
        except Exception:  # noqa: BLE001 - 托盘建不起来按没有处理
            self.tray = None
        return False

    def _stop_tray(self) -> None:
        tray = self.tray
        self.tray = None
        if tray is not None:
            try:
                tray.stop()
            except Exception:  # noqa: BLE001 - 停托盘失败不影响退出
                pass


class DesktopWindowFields:
    """窗口与托盘旧字段名的显式代理（Api 继承，动作代码与夹具一行不改）。"""

    @property
    def _window(self): return self._desktop_window.window

    @_window.setter
    def _window(self, value) -> None:
        self._desktop_window.window = value

    @property
    def _tray(self): return self._desktop_window.tray

    @_tray.setter
    def _tray(self, value) -> None:
        self._desktop_window.tray = value

    @property
    def _window_hidden(self) -> bool: return self._desktop_window.hidden

    @_window_hidden.setter
    def _window_hidden(self, value: bool) -> None:
        self._desktop_window.hidden = value

    @property
    def _window_minimized(self) -> bool: return self._desktop_window.minimized

    @_window_minimized.setter
    def _window_minimized(self, value: bool) -> None:
        self._desktop_window.minimized = value

    @property
    def _close_approved(self) -> bool: return self._desktop_window.close_approved

    @_close_approved.setter
    def _close_approved(self, value: bool) -> None:
        self._desktop_window.close_approved = value
