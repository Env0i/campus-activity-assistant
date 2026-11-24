# -*- coding: utf-8 -*-
"""pywebview 本地服务的脚本类型登记：把 .js 显式登记为 text/javascript。

桌面窗口的页面由 pywebview 自带的本地服务提供，脚本的类型头由标准库 mimetypes 决定，
而 mimetypes 在 Windows 上会读注册表——有的电脑把 .js 记成 text/plain（装过某些软件
之后会出现）。普通脚本不在乎类型头，模块脚本严格要求 JavaScript 类型，类型不对时
整张模块图都不加载，界面永远停在兜底提示上，重装也没用；所以不能指望用户的注册表，
只能由程序自己登记。 """

import mimetypes


def register_script_types():
    """把 .js 显式登记为 text/javascript，压过注册表可能记下的 text/plain。"""
    mimetypes.add_type("text/javascript", ".js")
