# -*- coding: utf-8 -*-
"""测试夹具：测试创建的 Api 在结束时停掉它的自动重登线程。

local/app.py 的 Api 在构造时启动 auto-relogin 后台线程，只有 shutdown() 会停；
测试不收的话全量会累积上百个线程，每秒扫 sys.path 抢导入锁，把计时类用例拖红
（2026-11-06 排查）。这里只停线程：shutdown() 还会收计划、写生命周期记录，
副作用比停线程大。不 import app，避免夹具导入时就拉起 webview。
"""
from __future__ import annotations


def stop_auto_relogin_on_cleanup(testcase, api):
    """把 api 的自动重登 monitor 登记到 testcase.addCleanup，测试结束即停。

    必须在构造后立刻取 monitor——有的用例随后会把 api._auto_relogin 换成假对象，
    清理时再读属性就停不到真线程。
    """
    monitor = getattr(api, "_auto_relogin", None)
    if monitor is not None:
        testcase.addCleanup(monitor.stop)
    return api
