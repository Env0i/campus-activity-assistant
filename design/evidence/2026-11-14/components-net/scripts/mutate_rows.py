#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三组变异的行清单加一组场景探针（只放数据，不放逻辑；定位与执行见同目录 mutate_reads.py）。

每行一个 9 元组：
  (编号, 一行是什么, 文件相对 local/ui/, 函数名, 那一行去空白后的原文, 方式, 换掉的文字, 换成什么, 组名)
方式只有两种："blank" = 整行换成空语句（换掉/换成两格只作说明）；
"replace" = 在该行内把「换掉的文字」替换成「换成什么」，必须恰好出现一次。

组「认阶段」——views/phone.js 的 phonePhase 九行、views/settings.js 的 ocrPhase 八行。
带条件的分支整行换成空语句，让输入落到后面的分支；最后兜底的那一行把返回的字面量
换掉（phonePhase 的 missing 换成 disabled，ocrPhase 的 missing 换成 off）。
组「读进行中标志」——从面板对象上读 PhonePanel.busy / PhonePanel.pending /
PhonePanel.installing / OcrPanel.busy 的每一处（赋值不算），把这一处读取换成它空闲时
的值（busy 与 installing 换成 false，pending 换成空字符串）。
组「使用点」——四个绘制函数（paint、paintRelogin、paintPhoneAccess、paintOcrDownload）
里局部变量 busy、pending、installing 的每一个使用点；由它们算出来的 starting、loading
的使用点也算，按它依赖的标志归类。换法：busy、installing、loading、starting 换成 false，
!installing 换成 true，!!pending 换成 false，pending 与字符串的比较换成 false；
同一行有两个变量就是两行。
组「检查中场景探针」——两个 loading 定义里认 checking 的那一项，换掉后「检查中」场景
必须由「进度块显示」这句断言接住；这一组不是使用点，单独计数。

行按「文件、函数、那一行的文字」定位，不按行号——下一批要搬文件，行号会变，文字不会。

OVERRIDES：人工复判的结论改写。脚本机械地只出「行为测试已守 / 只有字面断言守 / 没人守」
三类；标了名字的行按这里的文字出结论并单独计数——
  busy-paint / busy-paint-remove：paint 里读 busy 的那一行与其唯一使用点，操作的
  #btn-phone-feature-remove 在页面里不存在，只在按路径加载的旧测试的桩里有，改写为
  「页面里没有这个元素」。
  installing-failText-ocr：failText 的消费点只有两处——红条一行被「installing 时整条
  清空」拦下（settings.js 红条那行），取消句一行要求 dl === "cancelled" 而拼句要求
  dl === "failed"，两者互斥；installing 为假时 !installing 本来就为真，换掉不改变
  任何输入下的输出与请求，判「等价」。

@author Author
"""

# 认阶段
PHASE_ROWS = [
    ("phone-on", "手机控制", "views/phone.js", "phonePhase",
     'if (st && st.running) return "on";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("phone-downloading", "手机控制", "views/phone.js", "phonePhase",
     'if (dl === "downloading") return "downloading";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("phone-verifying", "手机控制", "views/phone.js", "phonePhase",
     'if (dl === "verifying") return "verifying";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("phone-checking", "手机控制", "views/phone.js", "phonePhase",
     'if (row && row.status === "checking") return "checking";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("phone-outdated", "手机控制", "views/phone.js", "phonePhase",
     'if (row && row.status === "outdated") return "outdated";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("phone-broken", "手机控制", "views/phone.js", "phonePhase",
     'if (row && row.status === "failed") return "broken";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("phone-off", "手机控制", "views/phone.js", "phonePhase",
     'if (row && row.ready) return "off";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("phone-disabled", "手机控制", "views/phone.js", "phonePhase",
     'if (row && row.available) return "disabled";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("phone-missing", "手机控制", "views/phone.js", "phonePhase",
     'return "missing";', "replace", 'return "missing";', 'return "disabled";', "认阶段"),
    ("ocr-downloading", "验证码识别", "views/settings.js", "ocrPhase",
     'if (dl === "downloading") return "downloading";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("ocr-verifying", "验证码识别", "views/settings.js", "ocrPhase",
     'if (dl === "verifying") return "verifying";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("ocr-checking", "验证码识别", "views/settings.js", "ocrPhase",
     'if (feature && String(feature.status || "") === "checking") return "checking";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("ocr-outdated", "验证码识别", "views/settings.js", "ocrPhase",
     'if (feature && String(feature.status || "") === "outdated") return "outdated";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("ocr-broken", "验证码识别", "views/settings.js", "ocrPhase",
     'if (feature && String(feature.status || "") === "failed") return "broken";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("ocr-on", "验证码识别", "views/settings.js", "ocrPhase",
     'if (feature && feature.ready) return "on";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("ocr-off", "验证码识别", "views/settings.js", "ocrPhase",
     'if (feature && feature.available) return "off";', "blank", "（整行）", "（空语句）", "认阶段"),
    ("ocr-missing", "验证码识别", "views/settings.js", "ocrPhase",
     'return "missing";', "replace", 'return "missing";', 'return "off";', "认阶段"),
]

# 读进行中标志
READ_ROWS = [
    ("busy-startPolling", "手机控制·轮询", "views/phone.js", "startPolling",
     "if (PhonePanel.busy || document.hidden) return;", "replace", "PhonePanel.busy", "false", "读进行中标志"),
    ("busy-paint", "面板重画", "views/phone.js", "paint",
     "const busy = !!PhonePanel.busy;", "replace", "PhonePanel.busy", "false", "读进行中标志"),
    ("busy-paintRelogin", "登录恢复", "views/phone.js", "paintRelogin",
     "const busy = !!PhonePanel.busy;", "replace", "PhonePanel.busy", "false", "读进行中标志"),
    ("busy-paintCredFormOnce", "登录恢复·表单", "views/phone.js", "paintCredForm",
     "onceBox.disabled = !!PhonePanel.busy || !storeOk;", "replace", "PhonePanel.busy", "false", "读进行中标志"),
    ("busy-paintCredFormSave", "登录恢复·表单", "views/phone.js", "paintCredForm",
     "save.disabled = !!PhonePanel.busy || empty || (!storeOk && !usable);", "replace", "PhonePanel.busy", "false", "读进行中标志"),
    ("busy-paintPhoneAccess", "手机访问", "views/phone.js", "paintPhoneAccess",
     "const busy = !!PhonePanel.busy;", "replace", "PhonePanel.busy", "false", "读进行中标志"),
    ("pending-paintPhoneAccess", "手机访问", "views/phone.js", "paintPhoneAccess",
     'const pending = String(PhonePanel.pending || "");', "replace", "PhonePanel.pending", '""', "读进行中标志"),
    ("installing-paintPhoneAccess", "组件安装路径", "views/phone.js", "paintPhoneAccess",
     "const installing = !!(PhonePanel.installing && PhonePanel.installing.phone_control);",
     "replace", "!!(PhonePanel.installing && PhonePanel.installing.phone_control)",
      "!!(false && PhonePanel.installing.phone_control)", "读进行中标志"),
    ("busy-enableFeature", "手机访问·启用", "views/phone.js", "enableFeature",
     "if (PhonePanel.busy) return;", "replace", "PhonePanel.busy", "false", "读进行中标志"),
    ("busy-toggleStart", "手机访问·开启", "views/phone.js", "toggleStart",
     "if (PhonePanel.busy || PhonePanel.pending) return;", "replace", "PhonePanel.busy", "false", "读进行中标志"),
    ("pending-toggleStart", "手机访问·开启", "views/phone.js", "toggleStart",
     "if (PhonePanel.busy || PhonePanel.pending) return;", "replace", "PhonePanel.pending", '""', "读进行中标志"),
    ("busy-toggleStop", "手机访问·关闭", "views/phone.js", "toggleStop",
     "if (PhonePanel.busy || PhonePanel.pending) return;", "replace", "PhonePanel.busy", "false", "读进行中标志"),
    ("pending-toggleStop", "手机访问·关闭", "views/phone.js", "toggleStop",
     "if (PhonePanel.busy || PhonePanel.pending) return;", "replace", "PhonePanel.pending", '""', "读进行中标志"),
    ("busy-downloadComponent", "组件下载", "views/phone.js", "downloadComponent",
     "if (PhonePanel.busy) return;", "replace", "PhonePanel.busy", "false", "读进行中标志"),
    ("installing-paintOcrDownload", "组件安装路径", "views/settings.js", "paintOcrDownload",
     "const installing = !!(window.PhonePanel && window.PhonePanel.installing",
     "replace", "window.PhonePanel && window.PhonePanel.installing", "window.PhonePanel && false", "读进行中标志"),
    ("ocrBusy-paintOcrDownload", "验证码识别·面板", "views/settings.js", "paintOcrDownload",
     "const busy = !!OcrPanel.busy || !!(window.PhonePanel && window.PhonePanel.busy);",
     "replace", "OcrPanel.busy", "false", "读进行中标志"),
    ("phoneBusy-paintOcrDownload", "验证码识别·面板", "views/settings.js", "paintOcrDownload",
     "const busy = !!OcrPanel.busy || !!(window.PhonePanel && window.PhonePanel.busy);",
     "replace", "window.PhonePanel.busy", "false", "读进行中标志"),
    ("busy-enableOcr", "验证码识别·启用", "views/settings.js", "enableOcr",
     "if (OcrPanel.busy) return;", "replace", "OcrPanel.busy", "false", "读进行中标志"),
]

# 使用点（paint、paintRelogin、paintPhoneAccess、paintOcrDownload 里 busy / pending /
# installing 与由它们算出的 starting / loading 的每个使用点）
USE_ROWS = [
    ("busy-paint-remove", "面板重画：移除组件按钮禁用（页面里没有这个元素）", "views/phone.js", "paint",
     "if (phoneRemove) phoneRemove.disabled = busy;", "replace", "busy", "false", "使用点"),
    ("busy-paintRelogin-manage", "登录恢复：入口按钮（填写账号密码/更换）禁用", "views/phone.js", "paintRelogin",
     "slot.disabled = busy;", "replace", "busy", "false", "使用点"),
    ("busy-paintRelogin-clear", "登录恢复：「清除已保存」按钮禁用", "views/phone.js", "paintRelogin",
     "if (credClear) credClear.disabled = busy;", "replace", "busy", "false", "使用点"),
    ("pending-startingDef", "手机访问：starting 的来源（pending 与 \"starting\" 的比较）", "views/phone.js", "paintPhoneAccess",
     'const starting = pending === "starting";', "replace", 'pending === "starting"', "false", "使用点"),
    ("installing-loadingDef", "组件安装：loading 定义里的 installing（安装计入进度态）", "views/phone.js", "paintPhoneAccess",
     'const loading = downloading || phase === "checking" || installing;', "replace", "installing", "false", "使用点"),
    ("busy-installBtn", "组件安装：标题行「下载并安装」禁用条件里的 busy", "views/phone.js", "paintPhoneAccess",
     "install.disabled = busy || installing;", "replace", "busy", "false", "使用点"),
    ("installing-installBtn", "组件安装：标题行「下载并安装」禁用条件里的 installing", "views/phone.js", "paintPhoneAccess",
     "install.disabled = busy || installing;", "replace", "installing", "false", "使用点"),
    ("busy-cancelBtn", "组件安装：标题行「取消下载」禁用条件里的 busy", "views/phone.js", "paintPhoneAccess",
     'cancel.disabled = busy || phase === "verifying";', "replace", "busy", "false", "使用点"),
    ("busy-featureBtn", "手机访问：标题行按钮（重新导入/启用/换包）禁用", "views/phone.js", "paintPhoneAccess",
     "featureBtn.disabled = busy;", "replace", "busy", "false", "使用点"),
    ("starting-lead", "手机访问：开启中的 lead 文案", "views/phone.js", "paintPhoneAccess",
     '? (starting ? "正在开启，先不要切换通道。" : "选一条通道再开启。没开启时不监听端口，手机连不上电脑。")',
     "replace", "starting", "false", "使用点"),
    ("installing-missingShow", "组件安装：「没装」块显示条件里的 !installing", "views/phone.js", "paintPhoneAccess",
     'phoneShow("#phone-missing", phase === "missing" && !installing);', "replace", "!installing", "true", "使用点"),
    ("loading-loadingShow", "组件安装：进度块显示的 loading", "views/phone.js", "paintPhoneAccess",
     'phoneShow("#phone-loading", loading);', "replace", ", loading);", ", false);", "使用点"),
    ("installing-missingErr", "组件安装：没装红条条件里的 !installing", "views/phone.js", "paintPhoneAccess",
     'const missingErr = ((phase === "missing" || phase === "outdated") && !installing)',
     "replace", "!installing", "true", "使用点"),
    ("installing-importLine", "组件安装：导入行显示条件里的 !installing", "views/phone.js", "paintPhoneAccess",
     'phoneShow("#phone-import-line", (phase === "missing" || phase === "outdated") && failed && !installing);',
     "replace", "!installing", "true", "使用点"),
    ("loading-locAfter", "组件安装：「装在」行显示条件里的 !loading", "views/phone.js", "paintPhoneAccess",
     'const after = phoneShow("#phone-loc-after", phase !== "missing" && !loading && !!loc);',
     "replace", "loading", "false", "使用点"),
    ("busy-openLoc", "组件安装：「打开所在文件夹」按钮禁用", "views/phone.js", "paintPhoneAccess",
     "if (open) open.disabled = busy;", "replace", "busy", "false", "使用点"),
    ("installing-progText", "组件安装：进度字「正在安装组件…」的 installing", "views/phone.js", "paintPhoneAccess",
     'phoneText("#phone-prog-text", installing ? "正在安装组件…"', "replace", "installing", "false", "使用点"),
    ("loading-loadingErr", "组件安装：进度区错误行的 loading", "views/phone.js", "paintPhoneAccess",
     'phoneText("#phone-loading-error", loading ? notes.loading : "");', "replace",
     "loading ? notes.loading", "false ? notes.loading", "使用点"),
    ("busy-chanRadio", "手机访问：通道单选禁用条件里的 busy", "views/phone.js", "paintPhoneAccess",
     "radio.disabled = busy || !!pending;", "replace", "busy", "false", "使用点"),
    ("pending-chanRadio", "手机访问：通道单选禁用条件里的 !!pending", "views/phone.js", "paintPhoneAccess",
     "radio.disabled = busy || !!pending;", "replace", "!!pending", "false", "使用点"),
    ("busy-startBtn", "手机访问：「开启手机访问」禁用条件里的 busy", "views/phone.js", "paintPhoneAccess",
     "start.disabled = busy || !!pending || loading || tsBad;", "replace", "busy", "false", "使用点"),
    ("pending-startBtn", "手机访问：「开启手机访问」禁用条件里的 !!pending", "views/phone.js", "paintPhoneAccess",
     "start.disabled = busy || !!pending || loading || tsBad;", "replace", "!!pending", "false", "使用点"),
    ("loading-startBtn", "手机访问：「开启手机访问」禁用条件里的 loading", "views/phone.js", "paintPhoneAccess",
     "start.disabled = busy || !!pending || loading || tsBad;", "replace", "loading", "false", "使用点"),
    ("starting-startText", "手机访问：「启动中…」按钮文案", "views/phone.js", "paintPhoneAccess",
     'start.textContent = starting ? "启动中…" : "开启手机访问";', "replace", "starting", "false", "使用点"),
    ("starting-recheckShow", "手机访问：启动中收起「重新检测」", "views/phone.js", "paintPhoneAccess",
     'const recheck = phoneShow("#btn-tailscale-recheck", tsBad && !starting);', "replace", "starting", "false", "使用点"),
    ("busy-recheckBtn", "手机访问：「重新检测」按钮禁用", "views/phone.js", "paintPhoneAccess",
     "if (recheck) recheck.disabled = busy;", "replace", "busy", "false", "使用点"),
    ("starting-hint", "手机访问：Cloudflare 启动中的提示行", "views/phone.js", "paintPhoneAccess",
     'if (starting && selected === "cloudflare") hint = "正在建立临时隧道，最多等 20 秒。";',
     "replace", "starting", "false", "使用点"),
    ("busy-copyBtn", "手机访问：「复制」按钮禁用", "views/phone.js", "paintPhoneAccess",
     "copyButton.disabled = busy || !st.running;", "replace", "busy", "false", "使用点"),
    ("busy-stopBtn", "手机访问：「关闭手机访问」禁用条件里的 busy", "views/phone.js", "paintPhoneAccess",
     "stop.disabled = busy || !!pending;", "replace", "busy", "false", "使用点"),
    ("pending-stopBtn", "手机访问：「关闭手机访问」禁用条件里的 !!pending", "views/phone.js", "paintPhoneAccess",
     "stop.disabled = busy || !!pending;", "replace", "!!pending", "false", "使用点"),
    ("pending-stopText", "手机访问：「关闭中…」按钮文案的 pending 比较", "views/phone.js", "paintPhoneAccess",
     'stop.textContent = pending === "stopping" ? "关闭中…" : "关闭手机访问";',
     "replace", 'pending === "stopping"', "false", "使用点"),
    ("busy-addPairBtn", "手机访问：「再配对一台手机」按钮禁用", "views/phone.js", "paintPhoneAccess",
     "if (addPair) addPair.disabled = busy;", "replace", "busy", "false", "使用点"),
    ("installing-loadingDef-ocr", "验证码识别：loading 定义里的 installing", "views/settings.js", "paintOcrDownload",
     'const loading = downloading || phase === "checking" || installing;', "replace", "installing", "false", "使用点"),
    ("busy-downloadBtn-ocr", "验证码识别：「下载并安装」禁用条件里的 busy", "views/settings.js", "paintOcrDownload",
     "downloadBtn.disabled = busy || installing;", "replace", "busy", "false", "使用点"),
    ("installing-downloadBtn-ocr", "验证码识别：「下载并安装」禁用条件里的 installing", "views/settings.js", "paintOcrDownload",
     "downloadBtn.disabled = busy || installing;", "replace", "installing", "false", "使用点"),
    ("busy-enableBtn-ocr", "验证码识别：「启用」按钮禁用", "views/settings.js", "paintOcrDownload",
     "enable.disabled = busy;", "replace", "busy", "false", "使用点"),
    ("busy-reimportBtn-ocr", "验证码识别：「重新导入组件包」按钮禁用", "views/settings.js", "paintOcrDownload",
     "reimport.disabled = busy;", "replace", "busy", "false", "使用点"),
    ("busy-cancelBtn-ocr", "验证码识别：「取消下载」禁用条件里的 busy", "views/settings.js", "paintOcrDownload",
     'cancel.disabled = busy || phase === "verifying";', "replace", "busy", "false", "使用点"),
    ("installing-failText-ocr", "验证码识别：失败红条拼句条件里的 !installing", "views/settings.js", "paintOcrDownload",
     'const failText = failed && !installing && (phase === "missing" || phase === "outdated")',
     "replace", "!installing", "true", "使用点"),
    ("installing-errLine-ocr", "验证码识别：红条安装中清空的 installing", "views/settings.js", "paintOcrDownload",
     'ocrText("#ocr-download-error", installing ? "" : (OcrPanel.error || failText));',
     "replace", "installing", "false", "使用点"),
    ("installing-missingShow-ocr", "验证码识别：「没装」块显示条件里的 !installing", "views/settings.js", "paintOcrDownload",
     'ocrShow("#ocr-missing", phase === "missing" && !installing);', "replace", "!installing", "true", "使用点"),
    ("installing-importLine-ocr", "验证码识别：导入行显示条件里的 !installing", "views/settings.js", "paintOcrDownload",
     'ocrShow("#ocr-import-line", (phase === "missing" || phase === "outdated") && failed && !installing);',
     "replace", "!installing", "true", "使用点"),
    ("loading-loadingShow-ocr", "验证码识别：进度块显示的 loading", "views/settings.js", "paintOcrDownload",
     'ocrShow("#ocr-loading", loading);', "replace", ", loading);", ", false);", "使用点"),
    ("installing-progText-ocr", "验证码识别：进度字「正在安装组件…」的 installing", "views/settings.js", "paintOcrDownload",
     'ocrText("#ocr-prog-text", installing ? "正在安装组件…"', "replace", "installing", "false", "使用点"),
    ("loading-locAfter-ocr", "验证码识别：「装在」行显示条件里的 !loading", "views/settings.js", "paintOcrDownload",
     'ocrShow("#ocr-loc-after", phase !== "missing" && !loading && !!loc);', "replace", "loading", "false", "使用点"),
    ("busy-openLoc-ocr", "验证码识别：「打开所在文件夹」按钮禁用", "views/settings.js", "paintOcrDownload",
     "if (openLoc) openLoc.disabled = busy;", "replace", "busy", "false", "使用点"),
]

# 检查中场景探针：两个 loading 定义里认 checking 的那一项（不是使用点，单独计数）
PROBE_ROWS = [
    ("checking-loadingDef-phone", "检查中探针：手机控制 loading 定义里认 checking 的那一项", "views/phone.js", "paintPhoneAccess",
     'const loading = downloading || phase === "checking" || installing;', "replace", 'phase === "checking"', "false", "检查中场景探针"),
    ("checking-loadingDef-ocr", "检查中探针：验证码识别 loading 定义里认 checking 的那一项", "views/settings.js", "paintOcrDownload",
     'const loading = downloading || phase === "checking" || installing;', "replace", 'phase === "checking"', "false", "检查中场景探针"),
]

ROWS = PHASE_ROWS + READ_ROWS + USE_ROWS + PROBE_ROWS

# 人工复判的结论改写（见文件头说明）
OVERRIDES = {
    "busy-paint": "页面里没有这个元素",
    "busy-paint-remove": "页面里没有这个元素",
    "installing-failText-ocr": "等价",
}
