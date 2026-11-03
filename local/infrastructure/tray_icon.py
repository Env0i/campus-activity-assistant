"""系统托盘图标：窗口藏起来以后，靠它把窗口叫回来或者退出。

为什么自己用 WinForms 画：pywebview 6.2.1 没有托盘 API（包内 grep 不到 tray），
而 pythonnet 本来就是 pywebview 在 Windows 上的依赖，NotifyIcon 可以直接用，
不必新增 pip 依赖。仓库里没有 .ico 资源，先用系统图标顶上。

失败不要紧：start() 返回 False 就当没有托盘，主程序照常跑；窗口藏起来之后
还能从手机页的「显示电脑窗口」叫回来。
"""

import threading

TOOLTIP = "校园活动预报名工具（后台运行中）"


class TrayIcon:
    """一个托盘图标：双击/「显示窗口」唤回界面，「退出」走正常收尾流程。"""

    def __init__(self, on_show=None, on_exit=None, tooltip: str = TOOLTIP):
        self._on_show = on_show
        self._on_exit = on_exit
        self._tooltip = str(tooltip or TOOLTIP)
        self._form = None
        self._context = None
        self._icon = None
        self._thread = None
        self._ready = threading.Event()

    # ---------- 生命周期 ----------
    def start(self) -> bool:
        """建图标并跑消息循环；返回是否真的建起来了（最多等 5 秒）。"""
        if self._thread is not None:
            return self._icon is not None
        self._thread = threading.Thread(target=self._run, name="tray-icon", daemon=True)
        self._thread.start()
        self._ready.wait(5.0)
        return self._icon is not None

    def stop(self) -> None:
        """撤掉图标（可从任意线程调）：真正的清理动作投递回消息循环线程。"""
        form = self._form
        if form is None:
            return
        try:
            from System import Action

            form.BeginInvoke(Action(self._dispose))
        except Exception:
            pass

    def notify(self, title: str, text: str) -> bool:
        """在托盘图标上弹一条系统通知气泡，点气泡把窗口叫回来。

        用的是同一个 NotifyIcon 的 ShowBalloonTip，不引入新依赖。托盘没建起来时
        返回 False、不抛异常；真正的显示动作投递回消息循环线程去做。
        """
        form = self._form
        if form is None or self._icon is None:
            return False
        try:
            from System import Action

            form.BeginInvoke(Action(lambda: self._show_balloon(title, text)))
            return True
        except Exception:
            return False

    def _show_balloon(self, title: str, text: str) -> None:
        try:
            from System.Windows.Forms import ToolTipIcon

            self._icon.BalloonTipTitle = str(title or "")[:63]
            self._icon.BalloonTipText = str(text or "")[:255]
            self._icon.BalloonTipIcon = ToolTipIcon.Info
            self._icon.ShowBalloonTip(8000)
        except Exception:
            pass

    def _dispose(self) -> None:
        try:
            if self._icon is not None:
                self._icon.Visible = False
        except Exception:
            pass
        try:
            if self._context is not None:
                # ApplicationContext.ExitThread 只结束消息循环，不留任何窗口
                self._context.ExitThread()
        except Exception:
            pass

    # ---------- 消息循环 ----------
    def _run(self) -> None:
        try:
            import clr

            clr.AddReference("System.Windows.Forms")
            clr.AddReference("System.Drawing")
            from System.Drawing import Point, Size, SystemIcons
            from System.Windows.Forms import (
                Application,
                ApplicationContext,
                ContextMenuStrip,
                Form,
                FormBorderStyle,
                FormStartPosition,
                FormWindowState,
                NotifyIcon,
                ToolStripMenuItem,
                ToolStripSeparator,
            )
        except Exception:
            self._ready.set()
            return
        try:
            # 这个窗体永远不 Show：只借它的窗口句柄把清理动作投递回本线程。
            # 早先直接把消息循环挂在窗体上，宿主窗体被显示出来，于是第一次点
            # 「隐藏到后台」就多出一个空白小窗；现在循环用 ApplicationContext，
            # 没有任何窗口参与。
            form = Form()
            form.ShowInTaskbar = False
            form.Text = self._tooltip
            form.FormBorderStyle = getattr(FormBorderStyle, "None")  # None 是 Python 关键字
            form.WindowState = FormWindowState.Minimized
            form.StartPosition = FormStartPosition.Manual
            form.Location = Point(-4000, -4000)
            form.Size = Size(1, 1)
            form.Opacity = 0
            _ = form.Handle  # 强制建句柄，BeginInvoke 才有目标

            icon = NotifyIcon()
            icon.Icon = SystemIcons.Application
            icon.Text = self._tooltip[:63]  # WinForms 上限 63 个字符
            menu = ContextMenuStrip()
            show_item = ToolStripMenuItem("显示窗口")
            show_item.Click += lambda sender, args: self._fire(self._on_show)
            exit_item = ToolStripMenuItem("退出")
            exit_item.Click += lambda sender, args: self._fire(self._on_exit)
            menu.Items.Add(show_item)
            menu.Items.Add(ToolStripSeparator())
            menu.Items.Add(exit_item)
            icon.ContextMenuStrip = menu
            icon.DoubleClick += lambda sender, args: self._fire(self._on_show)
            # 后台结束的通知气泡：点一下等于「显示窗口」
            icon.BalloonTipClicked += lambda sender, args: self._fire(self._on_show)
            icon.Visible = True

            context = ApplicationContext()
            self._form = form
            self._context = context
            self._icon = icon
            self._ready.set()
            Application.Run(context)
        except Exception:
            self._ready.set()
        finally:
            try:
                if self._icon is not None:
                    self._icon.Visible = False
                    self._icon.Dispose()
            except Exception:
                pass
            self._icon = None

    # ---------- 菜单回调 ----------
    def _fire(self, callback) -> None:
        """菜单回调不占消息循环线程：pywebview 的窗口操作自己会回主线程。"""

        def _run() -> None:
            try:
                if callback is not None:
                    callback()
            except Exception:
                pass

        threading.Thread(target=_run, name="tray-action", daemon=True).start()
