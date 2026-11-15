# 真加载四条的输出与删 import 变异的输出

- 真加载 = 原生动态 import 加载 main.js（不走拼接）：普通脚本与模块从临时副本目录
  读，模块的 import 由 node 的真实加载器解析。拼接测试里模块名字恰好是全局的，
  缺 import 这类缺陷只有真加载才暴露。
- 复跑命令（仓库根）：
  `python -B -m unittest discover -s local/tests -p "test_ui_modules.py" -v -k NativeLoadSmokeTests`
  （8 例全过：本批新增四条加上一批的四条。）

## 本批新增四条通过

- 真加载下点设置按钮打开抽屉：发出一次验证码识别的组件位置请求
  （`test_real_load_settings_drawer_asks_the_ocr_component_location`，ok）；
  断言 `advanced_component_location` 与 `relogin_ocr` 各出现一次。
- 真加载下点识别行「启用」：发出启用请求，识别行说明里出现「验证码识别已启用。」
  （`test_real_load_ocr_enable_says_enabled_in_the_row`，ok；先断言说明看得见，
  再断言文字与请求）。
- 真加载下点「打开所在文件夹」：发出打开目录请求
  （`test_real_load_ocr_open_dir_sends_the_open_dir_request`，ok）。
- 真加载下识别行下载失败（原因连不上发布页）、调挂回的 paintOcrDownload 后：
  红条看得见，文字是「下载没有完成：连不上发布页，可以重试。」
  （`test_real_load_ocr_failed_download_paints_the_retry_bar`，ok；先断言看得见，
  再断言文字）。这条红条的文字经 view-ocr.js 里 downloadFailText 的 import 拼出。

## 删 import 变异：第四条真的变红，守卫缺 import 一类非空

在临时目录下的仓库副本里删掉 view-ocr.js 引 downloadFailText 的那一行 import，
仓库本体不动。两段输出（完整原文在结果目录 real-load-mutation-output.txt）：

一、模块图守卫（副本里跑 `node tools/code_shape/ui_modules.mjs`）：
  `missing_imports` 非空——view-ocr.js 第 103 行两处引用 downloadFailText、
  定义在 features/components/state.js，没有 import；
  ```
  missing_imports = [
    { "file": "features/components/view-ocr.js", "name": "downloadFailText",
      "line": 103, "defined_in": "features/components/state.js" },
    { "file": "features/components/view-ocr.js", "name": "downloadFailText",
      "line": 103, "defined_in": "features/components/state.js" }
  ]
  ```

二、只跑真加载第四条用例：FAILED（failures=1），退出码 1——
  ```
  AssertionError: '下载没有完成，可以重试。' != '下载没有完成：连不上发布页，可以重试。'
  ```
  红条退回「下载没有完成，可以重试。」的兜底文案：类型判断落空后走 `download.text`
  兜底分支，失败原因「连不上发布页」丢了。这正是拼接测试发现不了的坏法——
  同样的副本里跑拼接类用例照常绿（见 wiring.md 的五条变异）。
