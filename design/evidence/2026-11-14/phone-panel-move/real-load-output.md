# 真加载断言输出（test_ui_modules.NativeLoadSmokeTests，四例）

- 真加载 = node 真实动态 import 加载 main.js（临时副本目录里的 package.json type: module），
  不是拼接沙箱；输出为 unittest -v 的原文，运行时间 2026-11-14 21:1x (UTC+6)。
- 其中「挂回的每个名字有定义」一条的断言由「是函数」放宽为「有定义」，是本批唯一放宽的
  现有断言；其余三例是本批新增的三类真加载断言（成员清单逐个相等、识别行下载与取消、
  手机行开启）。

test_real_load_ocr_download_and_cancel_send_their_requests (test_ui_modules.NativeLoadSmokeTests.test_real_load_ocr_download_and_cancel_send_their_requests)
真加载下点识别行的「下载并安装」与「取消下载」：各发出一次对应请求。 ... ok
test_real_load_phone_panel_has_exactly_the_same_members (test_ui_modules.NativeLoadSmokeTests.test_real_load_phone_panel_has_exactly_the_same_members)
真加载装配后的 PhonePanel：成员名排序后与搬之前逐个相等，一个不多一个不少。 ... ok
test_real_load_start_sends_the_start_request (test_ui_modules.NativeLoadSmokeTests.test_real_load_start_sends_the_start_request)
真加载下点手机行的「开启手机访问」：发出开启请求。 ... ok
test_real_module_load_attaches_every_reported_name (test_ui_modules.NativeLoadSmokeTests.test_real_module_load_attaches_every_reported_name)
真加载后，模块图报告里挂回的每个名字在 window 上都得有定义（函数或对象 ... ok

----------------------------------------------------------------------
Ran 4 tests in 3.169s

OK
