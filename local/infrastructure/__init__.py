# -*- coding: utf-8 -*-
"""基础设施层：所有外部副作用的适配器（文件、进程、时钟、下载）。

依赖方向约束：
- 本包只被 interface（app 外观）与 application 使用/注入，绝不反向依赖它们；
- 每个适配器提供可替换接口（显式路径/依赖参数或模块级替身点），测试可整体换桩；
- 可以引用 domain 的纯规则；不得 import app（app 有导入期副作用）。

@author Author
"""


# 桌面窗口的页面由 pywebview 自带的本地服务提供，脚本类型头来自标准库 mimetypes，
# 而 mimetypes 在 Windows 上会读注册表：有的电脑把 .js 记成 text/plain（装过某些
# 软件之后会出现）。普通脚本不在乎类型头，模块脚本严格要求 JavaScript 类型，类型
# 不对时整张模块图都不加载，界面停在兜底提示上。包在这里导入时登记一次；步骤 2
# 拆 Api、起窗代码搬出 app.py 时，改成起窗前显式调用，并把下面这两行删除。
from .webview_mime import register_script_types

register_script_types()
