# 组件与手机访问动手之前的安全网

- **基线提交**：`dda275e`（分支 refactor/step1；工作区开工时干净）。
- **执行日期**：2026-11-14（第一批 16:49 (UTC+6) 收尾；本轮返修同日续做）。
- **量的是什么**：桌面端组件与手机访问这块，在搬成模块之前给「认阶段」「读进行中标志」
  与「使用点」补行为测试安全网——
  - 认阶段（17 行）：`views/phone.js` 的 `phonePhase` 九行（on、downloading、verifying、
    checking、outdated、broken、off、disabled、missing）、`views/settings.js` 的
    `ocrPhase` 八行（downloading、verifying、checking、outdated、broken、on、off、missing）。
  - 读进行中标志（18 行）：从面板对象上读 `PhonePanel.busy`、`PhonePanel.pending`、
    `PhonePanel.installing`、`OcrPanel.busy` 的每一处（赋值不算）。
  - 使用点（46 行）：四个绘制函数（`paint`、`paintRelogin`、`paintPhoneAccess`、
    `paintOcrDownload`）里局部变量 busy、pending、installing 的每一个使用点；由它们算出
    的 starting、loading 的使用点也算，按它依赖的标志归类；同一行有两个变量就是两行。
    变异做法——把这一处的变量换成它空闲时的值（busy、installing、loading、starting 换
    false，!installing 换 true，!!pending 换 false，pending 与字符串的比较换 false）。
  - 检查中场景探针（2 行，不是使用点、单独计数）：两个 loading 定义里认 checking 的
    那一项。
- **变异怎么做**：`scripts/mutate_reads.py` 按「文件、函数、那一行的文字」定位（不按
  行号——下一批要搬文件，行号会变，文字不会），行清单在同目录 `scripts/mutate_rows.py`
  （只放数据，两组文件各不超过 500 行）。带条件的认阶段分支整行换成空语句、兜底行换
  返回字面量（phonePhase 的 missing 换成 disabled、ocrPhase 的换成 off）；读标志与使用点
  行把该处读取换成空闲值。只在临时目录下的仓库副本里做（副本按 git ls-files 复制，
  config.json 与两个 data 目录不进副本），仓库本体不动。变异后先 node --check，再跑相关
  测试集合。`等价`与`页面里没有这个元素`两类由人工复判：脚本机械地记「没人守」，
  mutate_rows.py 的 OVERRIDES 标了名字的行按标注出结论并单独计数。
- **相关测试集合（变异时跑什么）**：`test_phone_ui.py`、`test_reason_maps.py`、
  `test_ui_contract_components.py`、`test_ui_contract_settings.py`、`test_ui_contract_shell.py`、
  `test_ui_exit_paths_components.py`、`test_ui_reliability.py`，加两个新文件
  `test_ui_component_rows.py` 与 `test_ui_phone_access_rows.py`（存在才跑）。口径：直接断言
  这两个视图文件的行为（跑 node）或文字的测试全集——用「断言组件/手机访问 UI 产出
  元素」「读这两个文件源码」「run_js 里碰 PhonePanel/OcrPanel」三种搜索各扫一遍
  local/tests，命中的文件全部在此集合内，未命中的（例如 test_ui_contract_list 等其余界面
  契约）不断言这两个文件的产出。未变异基线：第一批时该集合 413 例全绿；本轮新用例加入
  后 450 例全绿。
- **结论口径**：变红用例里至少一条跑 node 的用例即「行为测试已守」，全是字面断言即
  「只有字面断言守」，没有用例变红即「没人守」；「等价」与「页面里没有这个元素」由人工
  复判。结论表多一列「有没有走整页清单的用例守着」——变红用例里有没有走整页脚本清单
  （fixtures.ui_harness 的 run_js）的，有则指名第一条；这一列只是给下一批写计划用的事实，
  「否」不要求补。
- **各组变异结论表的结论数字**：
  - `before.md`（第一批，补测试之前）：行为测试已守 21、没人守 14、只有字面断言守 0
    （共 35 行，认阶段 17 + 读标志 18）。
  - `after.md`（第一批补测试之后，本轮重跑加整页清单一列）：行为测试已守 34、
    页面里没有这个元素 1、没人守 0、只有字面断言守 0、等价 0（共 35 行）。原先按口径
    记「行为测试已守」的 `busy-paint` 一行改记「页面里没有这个元素」：paint 里读出的
    busy 唯一喂给 `if (phoneRemove) phoneRemove.disabled = busy`，而
    `#btn-phone-feature-remove` 在页面里不存在，变红的是按路径加载的旧测试的桩——
    单独计数，这一行删不删由下一批定。
  - `uses-before.md`（使用点，本轮补测试之前）：使用点 46 处——没人守 22、行为测试
    已守 22、等价 1（失败红条拼句条件里的 !installing，理由见该文件）、页面里没有这个
    元素 1（busy-paint-remove，同上）；另有检查中场景探针 2 行（行为测试已守，但守的
    只有按路径加载的旧用例，整页清单一列为否）。指挥会话量出的 19 处逐处对上（对照表
    见 uses-before.md 附录）。
  - `uses-after.md`（使用点，本轮补测试之后）：使用点 46 处——没人守 0、只有字面断言
    守 0、行为测试已守 44、等价 1、页面里没有这个元素 1；检查中探针 2 行整页清单一列
    变「是」（见下）。每条变异红的第一条断言都是本轮新用例里它自己那一句（用户看得到的
    那条）。
- **等价判定（唯一一处）**：失败红条拼句条件里的 `!installing`（settings.js paintOcrDownload）
  ——换掉以后用户看到的与发出的请求都不变：failText 只有红条一行与取消句两个消费点，
  红条一行在 installing 时整条清空、取消句要求 `dl === "cancelled"` 而拼句要求
  `dl === "failed"`（互斥），installing 为假时该条件本来就为真。让它不变的两行代码见
  uses-before.md 的等价判定一节。
- **新用例**：第一批 21 条、本轮返修再加 17 条（`test_ui_phone_access_rows.py` 12 条、
  `test_ui_component_rows.py` 5 条），共 38 条；每条按钮用例先断言看得见、再断言忙时
  禁用、并带空闲时可点的对照；在对应变异上第一个失败的断言是它自己那一句。
- **三个必有场景**（不管结论如何都必须有走整页清单的用例守着）：
  1. 手机控制在下载、验证码识别在安装，两行各显各的互不串 →
     `test_ui_component_rows.py` 的 `test_phone_downloads_while_ocr_installs_rows_do_not_mix`。
  2. 两个组件各自「正在安装」时这一行的样子 → 同文件
     `test_each_component_shows_its_own_installing_row`（已装好的快照出发）与本轮新增的
     `test_each_component_installs_from_missing_without_showing_missing_blocks`（从「没装」
     出发：断言「没装」块不显示、进度区说正在安装；去掉任一侧「没装」块显示条件里的
     !installing，它就红，第一条失败断言是「安装中的××不能显示成没装」）。
  3. 后端给「检查中」时两行都不显示成「没装」且进度块要显示 → 同文件
     `test_checking_state_is_not_missing_on_both_rows`（本轮加强：新增两边进度块是显示的
     断言；把任一侧 loading 里认 checking 的那一项换成 false，它就红，第一条失败断言是
     「检查中的××进度块要显示」）；另有两批更早的按路径加载的用例分别守两行
     （`test_phone_ui.py` 的 `test_checking_component_is_not_missing_and_offers_no_install_or_enable`
     与 `test_checking_ocr_component_is_not_missing_in_settings_or_login_line`）。
- **契约测试逐条分类**：`contract-tests.md`——15 条逐条归类（照原型逐字的文案、无障碍
  名称、页面元素、源码形状），行为侧已有用例守着的指名（3 条），第一批补出行为用例的
  4 条（每条都做了对应变异验证、红在用户看得到的断言），只能保留字面断言的 8 条各写明
  为什么行为化不了。
- **搬家事实表**：`move-facts.md`——表一名字引用（本轮把经 `window.PhonePanel` 的访问与
  typeof 判断算进来重出：PhonePanel 被 app.js、plan-panel.js、settings.js、status-cards.js、
  help.js 引用）、表一·面板成员与反向表（本轮新增，均由脚本出）、表二成员归属（本轮
  改正 clearConfirm 一行的读写说明并补 saveCredentials 入口的已知事实）、表三按路径加载
  的测试、表四两段绘制的逐阶段对照（本轮按代码改正「检查中」一行：检查中两边的主按钮
  都收在各自块里看不到，不存在要裁决的不一致）。
- **现有测试的用例数**：两批开工与收工一致——第一批 `test_ui_*.py` 开工 570 例、收工
  591 例；本轮开工 591 例、收工 608 例，多出的全部来自两个新文件（它们也匹配
  `test_ui_*` 通配）。第一批之前就存在的测试文件用例数与通过数零变化；
  `test_prerefactor_fixes.py` 27 例、`test_phone_ui.py` 210 例，前后一致。
- **复跑命令**（仓库根，Python 一律带 `-B`；临时目录一律在 tempfile 的默认位置，不写死
  盘符）：

  ```bash
  # 定位核对（不变异）
  python -B design/evidence/2026-11-14/components-net/scripts/mutate_reads.py --verify
  # 未变异基线（必须 0 失败）
  python -B design/evidence/2026-11-14/components-net/scripts/mutate_reads.py --baseline
  # 全部行（认阶段 + 读标志 + 使用点 + 探针，83 行），可加 --shard i --shards 4 并行
  python -B design/evidence/2026-11-14/components-net/scripts/mutate_reads.py \
      --phase 补测试之前 --out before.md
  # 只跑某一组或指定行（核对单条用例的「变异变红」），分片跑完用 --merge 合成一张表
  python -B design/evidence/2026-11-14/components-net/scripts/mutate_reads.py \
      --ids busy-installBtn,installing-missingShow --save-output <结果目录>
  python -B design/evidence/2026-11-14/components-net/scripts/mutate_reads.py \
      --merge s0.json s1.json s2.json s3.json --phase 补测试之后 --title 使用点变异结论表 \
      --out uses-after.md
  # 事实清点（表一、面板成员、反向表、表三，打印到标准输出）
  python -B design/evidence/2026-11-14/components-net/scripts/move_facts.py
  # 新用例
  python -B -m unittest discover -s local/tests -p "test_ui_component_rows.py" -v
  python -B -m unittest discover -s local/tests -p "test_ui_phone_access_rows.py" -v
  ```
- **注意**：变异脚本按「那一行的文字」定位——这两个文件里那 83 行的文字改了，要先改
  `mutate_rows.py` 的清单再跑，定位不到会整体停下报告，不猜。
- 本批只加测试与证据：产品代码、现有测试、夹具、工具零改动；逐条变异的原始输出在结果
  目录（不入库，收工提醒跑净化脚本）。
