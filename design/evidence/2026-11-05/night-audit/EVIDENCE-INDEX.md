# EVIDENCE-INDEX — 命令与输出摘要索引(2026-11-05 夜审计)

全部命令在仓库根(<审计副本>,MSYS 下映射 <审计副本>)执行。环境:Python 3.12.9 / Node v24.16.0 / git 2.54.0.windows.1。每条标注执行者与三态属性。

## 0. 开工三数核对(主代理,已复现)

```bash
pwd && cygpath -w "$(pwd)"        # <审计副本>
git status --porcelain | wc -l    # 27(开工时刻)
git log --oneline -1              # 4ec0b3d docs(evidence): A5 复核结论回填 + D9 新发现 N1-N3 入决策清单
git log -1 --format='%H %ci'      # 4ec0b3da… | 2026-11-04 06:46:29 -0600
```

## 1. 分母复算(主代理,已复现;脚本 reports/_tools/count.py)

```bash
git -c core.quotepath=false ls-files | wc -l                    # 469 ✓
# 分类行数:local 源码 140/65,687 ✓;server 44/12,188 ✓;tools 5/4,895 ✓;
# design 原型 100/9,165 ✓(prototype html 85 + archive 源码 12 + brand js 2 + check_refs.py 1,子集反推唯一命中)
# 文档 103/19,531(用户口径 102/19,055:文件数可按剔除 contracts md 对齐,行数差 476 无法规约,COVERAGE.md 如实记录)
# 代码总数:289/91,935 可复现,用户口径 291/92,061 余量=2 文件/126 行,有两对候选无法唯一还原,COVERAGE.md 如实记录
```

## 2. 测试基线(测试自动化工程师,已复现)

| 命令 | 退出码 | 输出摘要 |
|---|---|---|
| `python -m compileall local server` | 0 | 语法门槛通过 |
| `node --check local/ui/app.js` | 0 | 通过 |
| `python -m unittest discover -s local/tests -p "test_*.py" -v` | 1 | Ran 1696,FAILED (failures=1, errors=40, skipped=4) |
| `python -m pytest server/tests -q` | 1 | 66 failed, 56 passed(66 例全为 `<tmp>` 夹具 WinError 123,逐一核实) |
| `node server/bot/test_bot_runtime.js` | 0 | 37 项 0 败 |
| `node server/bot/test_handled_messages.js` | 0 | 8 通过 |
| `python -m unittest local.tests.test_retry_phone_policy.PlanServiceModeTests.test_backward_clock_recalibration_cannot_extend_monotonic_duration -v` | 1 | FAILED,2 != 1 |
| `python -m unittest local.tests.test_release_audit.ApiComponentCoordinationTests.test_online_download_reserves_existing_advanced_operation_guard -v` | 1 | AttributeError '_ocr_component_service'(主代理复跑复核) |

失败分类(修复前):40 errors = 39 `<tmp>` 夹具 + 1 AttributeError;1 failure = 时钟双读。skipped 4(test_lifecycle_release 三个真 git tag 用例 + test_signup_signing 非平台用例)。

**68 笔/423 文件声明核实**:滚动窗口口径——当前实测 66 笔/420 文件;`git log --since="2026-10-28 23:20:00"` 口径恰为 68 笔/423 文件(边界两笔 caa9f8c、918a2a2,2026-10-28 23:29/23:20 +0800)。声明在 2026-11-04 23:20 前测量成立。merges=0。

## 3. L1 静态扫描(L1 第三路,主代理脚本 reports/_tools/static_scan.py,已复现)

```bash
git -c core.quotepath=false ls-files -z | python -I reports/_tools/static_scan.py
# files_scanned 469
# R1_except_pass 2(均在 design/evidence 文档引用,真实代码 0)
# R2_bare_except 0 / R4_shell_true 0
# R3_eval_exec 29(归档原型 JS 正则 .exec()+测试受控片段 # noqa;生产 0)
# R5_secret_lit 4(全为测试夹具/指纹拼接,密钥治理交叉确认)
# R6_open_no_with 10(生产 4 处为锁文件句柄模式,后端深审已覆盖)
# R7_naive_dt 101(测试 55;生产 46=日志/展示戳良性+server 业务判断即 F-09+lifecycle 本机时长设计如此)
# 产物: reports/_tools/static_scan.tsv(逐文件)、static_scan_hits.txt(逐命中)
```

## 4. L1 diff 深审(代码审查员/后端架构师,证据节选)

- 27 项未提交逐文件 diff 审查 + `wc -l` 千行判定 + `grep -n "^def \|^class "` 全量函数清单(app.py 145 定义、grab.py 约 110、gui.py 37,全部"审"标记)。
- `python -c "ast.parse"` 全仓 135 个 .py 语法全过(PYTHONDONTWRITEBYTECODE=1)。
- `git show` 深读 11 笔:0cdbee4/3a563f4/00e1bce/b0e4448/6a46032/e60f878/e16d268/3706698/23b3dfc/5781bab/aa01989;66 笔全量 --stat。抽样依据:动 app.py/grab.py/server/signup/登录态/推送者深读;未抽 55 笔清单在 FINDINGS。
- `git log -S "event_now = clock_now()" -- local/application/plan_service.py` → 定位 6a46032。
- `node --check` bot.js/handled_messages.js/app.js/m/app.js/plan-panel.js/relogin.js 全过。
- 关键行号证据(摘):plan_service.py:304;test_retry_phone_policy.py:512;updater.py:33-36;app.py:1121-1124/:2688/:1701-1705;update.js:23/:30;update_check.py:219-231;relogin.js:158;app.js:173-179/:484-490;grab_signup.py:530-532/:344-350/:98-103/:764-768;watchlist.py:126;grab_card.py:64-79;auto_login.py:414-427;signup_reply.py:86-88;grab.py:2688-2692/:1610-1631/:868-886/:383-425。

## 5. L2 原型 99 处(UI 视觉验收设计师,静态比对双侧证据)

- 原型侧:`sed -n` 覆盖 Main.dc.html 490-848/855-875/1100-1290/1385-1400/1500-1560/1675-1710/1890-2183;Phone.dc.html 205-335/395-635/634-819;`grep -n "演示"` 两文件全量(19 行)。
- 实现侧:local/ui 全目录 grep/`sed`(证据逐条见 PROTOTYPE-GAP.md 表,含 grep 无匹配型证据如「上次的活动缓存」「出门前」「加密保存」「直发」计数=0)。
- `grep -c "直发" Main.dc.html` = 0(原型侧无该词,佐证 S21)。

## 6. L3 §9 63 条(技术文档工程师,已复现)

- `python -m pytest local/tests/test_ui_contract.py -q` → 286 passed, 15 subtests passed(契约主文件全绿)。
- `python -m pytest local/tests -q` → 41 failed / 1655 passed / 4 skipped / 380 subtests passed(与 unittest 基线一致)。
- 单测复现:`test_https_only`/`test_mobile_layout_statics`(Errno 22 变体)/时钟双读,均 `<tmp>` 或时钟根因。
- `python -m pytest local/tests --lf -q --co` → 37 个 last-failed id。
- spec 检索:五篇 specs 全读;`grep -n` 定位 copywriting.md:195、assistance-panels §3、versioning :12/:55-57、terms-consent r4;`grep -c 直发 local/ui/index.html` = 3(与记录吻合)。

## 7. L4 决策核对(代码审查员,静态比对+读文件已复现)

- 读 decision-agenda.md / receipt / remaining-and-template.md / architecture-revision-design.md 全文;`grep -rn` 落地点(qxbm/rjyWgzj/_join_state/_root/PRECHECK_AHEAD_S/LOG_MAX_BYTES/49 个公开方法/RISK-001/直发计数/TERMS_VERSION/TERMS_GATE/SCHOOL_TZ/BEIJING_TZ 等,命令清单见 DECISION-CHECK 附带报告)。
- `git status --porcelain design/decisions/010-…`(B1 无改动);`git ls-files design/evidence/2026-11-02/`(B2 在库);`ls local/gui.py + git log --diff-filter=D`(B7 未删)。

## 8. L5 发布口径(主代理,已复现)

```bash
cat VERSION                        # 1.2.0
head -40 CHANGELOG.md              # 1.2.0(待发布)/1.1.1(已发布)
git tag | wc -l                    # 0 → v1.1.1 本地不可追溯 → blocked
grep -n "1\.1\.1\|1\.2\.0" README.md            # :77 与 :256 矛盾
grep -n "当前正式版本\|v1.2.0" design/specs/versioning-and-release.md  # :12 基线 / :55-57 manifest
```

## 9. 密钥与凭据治理(密钥与凭据治理工程师,已复现)

- `git grep -nI` 系列 8 组模式(引号字面量/私钥块/Bearer/webhook key/长随机串/云厂商前缀/学号验证码/手机号):43 条命中全研判为占位/夹具/非密钥;历史 `git log --since=… -p` 新增行扫描 68 笔:0 真密钥。
- `git check-ignore -v local/config.json server/config.json server/data/x.json dist/x.txt local/data/x.json bot/data/x` 全命中;`git ls-files | grep -E "^(dist/|server/data/|local/data/|bot/data/)"` 为空。
- 凭据机制核对:credential_store.py:24-58(DPAPI)、auto_login.py:154(mode=0o600)、atomic_json.js:52-53、token_probe.py:194(sha1[:8] 指纹)。

## 10. 修复链(代码执行者,已复现,红→绿→反向对照)

| Fix | 关键命令与结果 |
|---|---|
| A | 改前 `unittest discover`→FAILED(f=1,e=40)/`pytest server/tests`→66 failed;改后→FAILED(f=1,e=2)/122 passed;反向 test_https_only 红(WinError 123)↔绿;`compileall -q local/tests server/tests` OK;patch 292 行 |
| B | 改前单测 2!=1;改后单测 OK+test_retry_phone_policy 25 OK+test_signup_plan+test_ui_contract 347 OK;反向撤门控红↔恢复绿;compileall OK |
| C | 改前 AttributeError e=1;改后单测 OK+test_release_audit 7 OK+`PYTHONPATH=local` test_ui_contract+test_runtime_bundle 343 OK;反向 HEAD 态红↔恢复绿;compileall OK(附:test_runtime_bundle 需 PYTHONPATH=local 调用形态,已反证与本修复无关) |
| D/E | 见 FINDINGS 修复记录表与 PATCHES/fix-D、fix-E(执行者报告附完整输出) |

## 11. 终态全量验证(主代理,FIX 全部落地后)

见 AUDIT.md「终态验证」节(修复后本机套件/server 套件/node 测试数字,覆盖账重跑 469 行核验)。

## 12. 禁止项遵守声明

全程未 push、未 commit(修复全部留在工作区,补丁存 reports/PATCHES/)、未合并、未打 tag、未装依赖、未访问学校真实接口、未读 .env/local/data/server/data/server/config.json 内容、未切模型渠道。测试运行按仓库既定命令向 gitignored 目录产生的日志/缓存属运行固有副产物,未读取其内容。

## 13. 第二轮标准化(2026-11-05)命令与证据摘要

- 分支:`git switch -c chore/standardize-20261105`(main 未动);收五修一笔 `099ded3 chore: 收第一轮五修`(选择性暂存:10 纯文件+app.py C hunk+test_ui_contract D 用例;提交树验证 1682 例 2 红均归因:1 计划内遗留 A hunk + 1 HEAD 固有矛盾 F-30,纯 HEAD 4ec0b3d worktree 单测坐实,worktree 已清)。
- 第 0 步:reports/STANDARD.md 八节可判定判据(判据升级:J4.1 改多行正则,J7.2 增负向输入豁免);冲突 C1-C8 记 DECISION-CHECK。
- 八批扫描(8 个只读子代理,并行 ≤3)+ 根级自扫;修复 14 个 patch(reports/PATCHES/std-*):批1/2/3/4a/4b/5/6/7/8a/8b/8c/8d/9a/9b,每批判据红→绿+反向对照,单批 ≤3 文件 ≤100 行。
- 批间门禁:全量 local 套件三次(批2 后/批7 后/终态)均 **1699 OK(skipped=4)**;server **122 passed**×3;node 37+8×3;compileall+node --check GATE_OK。
- J4.1 终态:local 生产代码 except-pass 65 处,BARE 16(gui.py 4=B7 待删;process_tree 5/tray_icon 6/tunnel_manager 1=批3 裁决保留),其余 49 处全带裁决注释或已窄化/留痕。
- 台账:reports/STANDARDIZATION.md 469 行(合规 156/已改 32/保留 132/N-A 149;已改数=14 patch 触及文件数)。
- 新发现登记:F-30(HEAD 固有 test/code 矛盾)、多行 except-pass 扫描缺口、application→infrastructure 口径出入(C6)、HEAD:3572 缩进事故被 compileall 拦截(执行者自曝并修正)。

## 14. 第二轮续作(批 10-17 + 质量门 + 事故记录)

- 质量门:独立质检员对 33 处吞异常批注**全查 0 不符**(26 相符/7 措辞修正,修正文本经 std-15a/15b 落地);两处「限窄裁决:不做」(app.py:1555/:3700)经类型面核验成立。
- 批 10-17:std-10(infra 12 处)/std-11(auto_login 7 处含计划外 :679)/std-12(grab_signup/login/notify 4 处)/std-13(server_refresh+bot.js:114 策略分歧注释,C9)/std-16(armedAt 死键 5 处删除,契约测试自证)/std-17(docs 三文件词汇对齐,判据驱动多修 3 处)。
- **事故记录(两起同源,已修复并机械证明归零)**:批 10 的多行 old_string 编辑两处丢失尾部代码行——process_tree.py 的 `raise`(归属失败不上抛,终态门禁 1699 例中 5 阶段红拦截)与 tray_icon.py 的 `self._icon = None`(执行者机械自查「逐 hunk 剥注释严格相等」揪出)。修复后两文件对 HEAD 差异仅剩 12 个 pass 行尾注释,全量 1699 OK 复跑通过。教训:注释批的模块测试面必须覆盖被改文件的**全部行为链**(批 10 当时的选面漏了 spawn 归属链),反向对照不能只验「注释在场」还要验「语义保持」;自查脚本已升级为剥注释严格相等校验并覆盖全部注释批文件。
- 终态:local 1699 OK/server 122/node 45/GATE_OK/tag=0;台账 469 行(合规 153/已改 45/保留 122/N-A 149);PATCHES 27 个(轮1 5 + 轮2 22)。
