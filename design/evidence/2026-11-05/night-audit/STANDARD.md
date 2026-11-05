# STANDARD — 全量标准化判据(第二轮,2026-11-05)

知识来源优先级:本文件 > 仓库既有设计文档(docs/ARCHITECTURE.md、docs/UI_SPEC.md、design/specs/*)> 判断。本文件每节给**可判定判据**(能用命令/脚本机械核验)+ **反例**;与仓库设计冲突处显式列允许清单,冲突本身记入 reports/DECISION-CHECK.md。

## §1 目录与分层

**判据**(机器可判定):
- J1.1 `local/domain/*.py` 的 import 集合 ∩ {infrastructure, application, ui, app} = ∅;`grep -n "^\s*\(from\|import\)\s\+\(infrastructure\|application\|ui\b\|app\b\)" local/domain/*.py` 必须 0 命中。
- J1.2 `local/ui/**`(.js/.html)不得出现文件系统调用:`grep -rnE "require\('fs'\)|fs\.(read|write|append|mkdir)|readFileSync|writeFileSync|\.readFile\(|\.writeFile\(" local/ui/` 必须 0 命中;持久化一律经 pywebview API(app.py)。
- J1.3 `local/application/*.py` 只被 `local/ui/**`(间接经 app.py)、`local/app.py`、`local/tests/**` 调用:`grep -rln "from application\.\|import application" local/ --include=*.py | grep -v tests` 命中文件 ∈ {local/app.py 及 application 内部}。
- J1.4 `local/domain` 内不得出现 `open(`/`Path(...).write` 等落盘动作(纯函数层):`grep -nE "\bopen\(|\.write_text\(|\.write_bytes\(|os\.replace" local/domain/*.py` 必须 0 命中(读写 JSON 的 demo 样例常量除外,常量不算 IO)。

**反例**:domain/retry_rules.py 里 `import infrastructure.prefs_store`(分层倒置);ui/views/xxx.js `writeFileSync(STATE_FILE)`(ui 越层落盘);application 被 infrastructure 反向 import。

## §2 命名

**判据**:
- J2.1 常量全大写:`grep -nE "^[A-Z_]+ = " local/**/*.py` 命中即合规;小写模块级不可变常量 = 违规(测试夹具常量 `_TMP` 类私有常量按 §2.4 处理)。
- J2.2 测试文件 `test_` 前缀:`ls local/tests/test_*.py server/tests/test_*.py`;非 test_ 前缀的 .py 不含 TestCase。
- J2.3 函数动词开头(公共 API):抽查级判据——对 `def <name>` 中名词性公共函数列表人工核定,不做全量改名(改名=破坏调用契约,见允许清单)。
- J2.4 私有 `_` 前缀:模块内辅助函数/属性以下划线开头;`grep -nE "^def [a-z]" local/app.py | grep -v test` 中被外部引用的函数才算公共。

**允许清单(保留原因=契约)**:`Api` 类公开方法名(check/list_activities/start_plan/update_download 等)是 pywebview 前后端契约 + test_ui_contract 钉住的接口名,改名=破契约,不适用 J2.3;`git ls-files` 层面文件名不动(启动器/部署脚本引用文件名)。

**反例**:模块级 `maxRetry = 3`(应 `MAX_RETRY`);`tests/foo.py` 含 TestCase(应 test_foo.py);公共函数 `def plan_of(...)` 实际做重试计算(应 `compute_...`)。

## §3 时间

**判据**:
- J3.1 业务时刻判定(开抢、截止、重试窗、预算、签到、批次)必须经 business_clock/server 端 common.business_now():`grep -nE "datetime\.now\(\)|datetime\.utcnow\(\)|datetime\.today\(\)|time\.time\(\)|time\.localtime\(" <file>` 命中行,若位于报名/重试/预算/批次判定链 = 违规。
- J3.2 允许清单(本机墙钟用途,经第一轮静态扫描分诊,保留理由=设计如此):
  a) local/business_clock.py 自身(时间源实现);
  b) 日志/展示戳:`%Y-%m-%d %H:%M:%S` 纯格式化行(grab.py:231/966/1026、app.py:157/1538/3347/3364、gui.py:701、server 各 stamp 行、tools/release.py built_at);
  c) 生命周期"本机经过时长"(lifecycle_store.py:79、app compute_lifecycle 调用点)——架构 4.5 明文本机口径;
  d) tools/ 构建元数据(release.py/split_branches.py 时间戳);
  e) 测试夹具构造相对时刻。
- J3.3 除允许清单外,生产代码中 J3.1 模式命中数 = 0(逐文件台账给证据)。

**反例**:server/scripts/watchlist.py:126 用 `datetime.now()` 判窗口超时(业务判定,应走 business_now;现状=隐式依赖部署时区,F-09);某 domain 函数内部 `time.time()` 算重试间隔(应注入 clock)。

## §4 错误处理

**判据**:
- J4.1 吞异常形态零容忍,判定用**多行正则**(单行正则会漏检,第一轮教训):`except\s*(Exception)?\s*:[^\n]*\n\s*pass\b`(含行尾 `# noqa` 注释变体——注释不能替代说明)。生产代码中命中者逐处裁决:**限窄类型+留注释说明**两条都满足才可保留(必要吞:清理路径、传输层),否则修。
- J4.2 裸 `except:` 0 命中(R2 已 0)。
- J4.3 抛出异常带上下文:自定义异常 raise 时带原因字段/消息(抽查 `raise \w+Error\(` 后跟空串或无上下文格式串的为反例)。
- J4.4 用户文案与日志分离:面向用户的中文文案出自 UI_SPEC/规格词表并经 _emit/payload 传递;运行日志(log_event/log)不夹带用户界面文案模板。抽查级:log 输出里出现「请」「您」类界面语 = 反例。

**反例**:`except Exception: pass`(静默丢错);`except:` 裸捕;`raise ValueError()` 无信息;日志里打用户界面整句文案导致 grep 双源。

## §5 日志

**判据**:
- J5.1 脱敏:`grep -rnE "token|学号|student|phone|1[3-9][0-9]{9}" --include=*.py local/ server/ | grep -E "(print|log|write)"` 命中行逐一研判,允许:指纹化(token_probe.py:194 sha1[:8])、黑名单拦截(log_events.py:25)、字段名描述;命中原值 = 违规(第一轮密钥治理已核 0)。
- J5.2 可轮转:local 主日志走 RotatingFileHandler 或等价大小上限(grab.py LOG_MAX_BYTES=5MB,第一轮已确认);server 走 systemd/journald(deploy 单元)或文件轮转。
- J5.3 结构化:log_event 带固定字段(event/source/...);server 卡片/告警字段化。抽查级。

**反例**:日志打完整 token/手机号;日志无上限增长(RotatingFileHandler 缺失,第一轮 live-check.md 曾记录此债、后已补)。

## §6 文件 IO

**判据**:
- J6.1 Python 落盘写一律原子替换:写临时文件+`os.replace`(grep `os.replace|replace\(tmp` 命中为证);直接 `open(path,"w")` 后不 replace 的写盘 = 违规(锁文件 .lock 的 a+b 句柄除外,见允许清单)。
- J6.2 读取优先 `with open(...)`;**跨函数生命周期句柄**(文件锁:a+b 打开后在临界区外层 finally close)允许非 with,但必须有 try/finally 收口:`grep -n "handle = open" local/*.py local/infrastructure/*.py server/` 命中行逐一核对 finally/收口。
- J6.3 路径来源走 runtime_paths.py(local)与部署约定(server):`grep -rnE "[CD]:\\\\|C:/Users|/Users/" --include=*.py --include=*.js local/ server/ tools/` 0 命中;`<tmp>` 字面量 0 命中(第一轮 Fix A 已清)。
- J6.4 测试夹具禁硬编码盘符与 `<tmp>`(=§7 J7.2)。

**反例**:`f = open(p,"w"); f.write(...)` 无 with 无原子替换;`open("C:/data/x.json")`;夹具 `dir="<tmp>"`。

## §7 测试

**判据**:
- J7.1 每个新增/修改断言可失败:改动必须附反向对照记录(改坏实现→该用例红)。台账里给证据链接(PATCHES 或执行记录)。
- J7.2 夹具无盘符/无 `<tmp>`:`grep -rnE '"[CD]:\\\\|<tmp>' local/tests server/tests` 0 命中(Fix A 后已 0,持续守住)。**允许清单**:负向测试输入字面量(断言拒绝该路径、从不落盘,如 test_component_builder.py:25 的 `("<tmp>", "C:/bad")` 反例)与注释中的历史路径说明(按 AGENTS.md 应改写为日期+命令口径,注释级 P3)。
- J7.3 套件门槛:批间全量 `python -X utf8 -m unittest discover -s local/tests -p "test_*.py"` 全绿 + `python -m pytest server/tests` 全绿 + node 两件套绿。

**反例**:`self.assertTrue(True)`;夹具 `os.path.join("D:\\","x")`;断言依赖固定当前日期导致明天必红。

## §8 文档

**判据**:
- J8.1 单一真源:版本号唯一出自 `VERSION`(test_lifecycle_release.py:98 钉住);活动域名唯一出自 site_target;业务口径唯一出自对应 spec——同一事实在两处手写两份 = 违规(允许:测试内的期望值拷贝,改真源时同步测试)。
- J8.2 三处一致:VERSION ↔ CHANGELOG 顶部条目 ↔ app.py TERMS_VERSION 与条款文档版本头,四点可 grep 对齐:`cat VERSION`、`head CHANGELOG.md`、`grep TERMS_VERSION local/app.py`、条款版本头。当前态:VERSION=1.2.0(待发布)、CHANGELOG 1.2.0 待发布、TERMS_VERSION=2026-11-03-r4(条款 r4 与 B9"待执行未排期"一致)——r4 与 1.2.0 候选并行不冲突,但 README.md:77/:256 的 1.1.1 口径为**违规待修**(第一轮 F-29)。
- J8.3 历史记录不追改:design/decisions/、design/evidence/、CHANGELOG 已发布段落不改写(AGENTS.md「旧记录不追改」);可改的是**活规格**(design/specs/*、docs/*、README)与实现同步。
- J8.4 规格与实现同步:spec 描述的行为与代码不符 → 修 spec(第一轮 F-20~F-24 清单);修 spec 的机械判据=grep 旧口径 0 命中。

**反例**:README 两处版本口径互相矛盾(J8.2 实例);把 2026-11-04 证据文档里的临时路径改成新路径(违反 J8.3);specs 里保留已被取代的「登录预计剩余」口径(J8.4 实例)。

## 判据与仓库文档的冲突登记(详文见 DECISION-CHECK.md 追加节)

1. §3 vs 架构 4.5(生命周期本机经过时长)与日志戳本地时区惯例 → 允许清单 J3.2。
2. §6"一律 with" vs 文件锁跨临界区句柄 → J6.2 允许非 with 但必须 finally 收口。
3. §2 命名 vs pywebview Api 契约方法名与部署脚本引用的文件名 → 允许清单,不改契约名。
4. §8"历史不追改" vs "specs 与实现同步" → 边界:decisions/evidence/CHANGELOG 已发布段不追改,活规格可改。
