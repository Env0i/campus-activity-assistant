# 00 开工核对（zcode 第二份独立重做，20261113-zcode-full）

- 执行方：ZCode 会话（本目标的主执行方）
- 计划源：`.claude/plans/plan-20261113-refactor-audit-redo.yaml`（T0–T7 规则来源，逐条执行）；按总目标约束，本方全部产出只落 `redo/zcode/` 子目录，不写 redo/ 根（目录映射见第 6 节）
- **T0（美中时间 UTC−6）**：2026-11-12 09:05 CT（UTC 2026-11-12 15:05；本机本地时间 2026-11-12 23:05）
- 硬停线：T0+9.5h = 2026-11-12 18:35 CT；券到期 T0+10h = 19:05 CT

## 1. git 原文（开工）

`git log --oneline -3`：

```
7e2d31c fix(component): 导入装好后收掉旧的下载失败
e0054c4 docs(proposals): 前端采用 ES Modules 并留样机
5d95f34 docs(proposals): 工程化重构提案
```

`git status --short`：

```
 M design/proposals/engineering-refactor.md
?? design/evidence/2026-11-12/esm-verify/
?? design/evidence/2026-11-12/refactor-audit/
```

与计划 `known_dirty_files` 一致，无范围外改动。

## 2. 可用子代理类型清单（原文抄录）

系统给出的可用子代理类型如下。源清单每条还带「｜分区：<分区> (Tools: <工具>)」后缀，按要求只抄「名字 + 一行描述」，分区与工具后缀略。清单含两套：无前缀一套，以及内容相同、名字带 `zcode-agency:` 前缀的一套（插件命名空间），两套都全文抄录。

### 2.1 无前缀清单

- 安全工程师：专业应用安全工程师，专注于威胁建模、漏洞评估、安全代码审查、安全架构设计和事件响应，服务于现代 Web、API 和云原生应用。
- 安全架构师：资深安全架构师，专精威胁建模（threat modeling）、安全设计（secure-by-design）架构、信任边界分析、纵深防御（defense in depth），以及面向 Web、API、云原生和分布式系统的基于风险的安全评审。负责设计安全模型；把代码级 SAST/DAST 与 SDLC 工作交给 AppSec 工程师。
- 百度 SEO 专家：专注百度搜索生态的SEO优化专家，精通百度算法规则、百度生态产品矩阵、中文关键词研究、ICP备案规范、以及移动端搜索优化策略。
- 包容性视觉专家：专注于消除 AI 生成图像中的系统性偏见，确保生成的人物图像和视频在文化、肤色、体型等方面真实、有尊严、不刻板。
- 报告分发师：自动把整合好的销售报告按区域分发给对应的销售代表，支持定时和手动触发。
- 变革管理顾问：资深变革管理专家，运用 ADKAR、Kotter 和 Prosci 框架，引导组织顺利完成技术落地、组织转型与并购整合——管理阻力、推动接纳，确保变革在上线之后长久落地
- 播客内容策略师：专注中国播客市场的内容策略与运营专家，精通节目定位、音频制作、听众增长、多平台分发及商业化变现，助力播客主理人打造高粘性播客。
- 簿记与财务总监：专业簿记与财务总监，精通日常会计操作、财务预测与现金流管理，以及月末结账流程和内部控制，确保财务记录的准确性、合规性和审计就绪状态。
- 财务分析师：专业财务分析师，精通财务建模、预测分析和数据驱动的决策支持，驱动战略规划和业务决策，支撑企业全面预算管理。
- 财务预测分析师：专注企业财务预测与现金流建模的分析专家，精通收入预测、成本分析和假设驱动规划，帮助企业完成经营预测与决策支持。
- 财务追踪员：专业的财务分析与管控专家，精通财务规划、预算管理和经营绩效分析，帮助守住企业财务健康底线，优化现金流管理。
- 测试结果分析师：专注测试结果评估和质量度量分析的测试分析专家，把原始测试数据变成可执行的洞察，驱动质量决策。
- 测试自动化工程师：用 Playwright 和 Cypress 编写端到端自动化用例，处理元素定位与用例稳定性，接入 CI 并行执行，用 trace 排查失败。
- 策略对决推演师：运用 game theory（博弈论）和三十六计开展实时策略对决推演
- 产品经理（PM）：全局型产品负责人，掌控产品全生命周期——从需求发现、战略规划到路线图制定、干系人对齐、GTM 落地与结果度量。在商业目标、用户需求与技术现实之间架起桥梁，确保变革在正确的时间交付到正确的人。
- 程序化广告采买专家: 展示广告与程序化媒介采买专家，覆盖 Google Display Network、DV360、The Trade Desk 等 DSP 平台，负责采买及 ABM 展示广告策略，并对"这条要花多少钱"负责。
- 代码库入职引导工程师: 专业的开发者入职引导专家，帮助新工程师快速理解陌生代码库，通过阅读源码、追踪代码路径，只陈述基于代码的事实。
- 代码审查员: 专业代码审查专家，提供建设性、可操作的反馈，聚焦正确性、可维护性、安全性和性能，而非代码风格偏好。
- 代码执行者: 唯一的写者：按主代理指定的切片改代码、跑测试、本地提交；串行独占，不与其它子代理并行改同一文件
- 地理处理专家: 精通 ArcPy 与 Python 工具箱的自动化专家，专攻空间工作流自动化——构建 .pyt 工具箱、Model Builder 流程、批量地理处理自动化，以及为 ArcGIS Pro 编写自定义分析脚本。
- 地理学家: 自然地理与人文地理、气候系统、制图学和空间分析专家——构建地理上连贯自洽的世界，使地形、气候、资源和聚落模式在科学上合理｜分区：academic
- 地图制图设计师: 地图美学与设计专家——精通地图美学、视觉层次和排版设计，打造清晰、有效、面向打印与 Web 的地图视觉
- 电商运营师: 专注中国电商平台全链路运营的专家，精通商品上架优化、直播带货、大促策划，覆盖淘宝/天猫/拼多多/京东生态。
- 钉钉集成开发工程师: 专注钉钉开放平台全栈集成开发的工程专家，精通钉钉机器人、小程序、审批流自动化、连接器低代码应用搭建，以及企业内部应用与生态集成。
- 定价分析师: 专精定价分析与价格优化，通过市场调研、竞品分析和成本结构分析，设计定价策略，并量化价格弹性与利润影响。
- 动态定价策略师: 专注电商与零售场景的动态定价，通过供需、库存与竞对信号设计调价规则，并平衡 GMV、毛利与周转目标。
- 抖音策略师: 专注抖音平台的短视频增长策略，精通算法推荐机制、内容节奏、投放与达人合作，帮助品牌实现可持续涨粉与转化。
- 短视频剪辑指导师: 专注短视频剪辑风格与节奏的指导专家，精通脚本拆解、素材取舍、卡点与情绪曲线，输出可执行的剪辑方案。
- 多平台发布编排官: 一键中文博客发布的专家级编排官。把同一篇文章通过 Wechatsync(主通道)路由到 知乎 / 小红书 / CSDN / B站 / 公众号 / 掘金,并以 xhs-mcp 和 biliup 作为专用兜底。负责各平台内容适配、草稿优先发布、频率控制与风险规避。绝不自动发布——始终停在草稿阶段交由人工审核。
- 多智能体系统架构师: 系统架构师，专精于 multi-agent（多智能体）AI 流水线的设计、协调与治理——涵盖拓扑选型、上下文管理、智能体间信任、故障恢复、human-in-the-loop（人在环中）门控，以及面向生产级智能体系统的可观测性。
- 发票管理专家: 专注中国企业发票全生命周期管理的财税专家，精通增值税专用发票与普通发票、金税系统操作、电子发票推广、三单匹配、报销归档及涉税风险防控，帮助企业构建合规的发票管理体系。
- 法国咨询市场专家: 法国 ESN/SI 自由职业生态导航专家，精通 Malt、collective.work、freelance-informatique 等平台行情、AJ 社保与 portage salarial 机制，帮助技术顾问定位、报价与谈单。
- 法律文书审查专家: 全面的法律文书审查专家，涵盖合同、诉讼文书、监管文件的条款风险、表述歧义与程序合规审查，输出逐条修改建议。
- 法务合规员: 专业的法律合规专家，确保业务运营、数据处理和内容创作符合多个司法管辖区的相关法律法规和行业标准。
- 反馈分析师: 专注用户反馈收集与分析的专家，把碎片化的用户声音变成可执行的洞察，驱动质量决策与产品优先级。
- 房地产经纪助手: 综合房地产经纪人助手，涵盖房源管理、客户跟进、带看安排与成交谈判支持，帮助经纪人提升转化效率。
- 飞书集成开发工程师: 专注飞书开放平台全栈集成开发的工程专家，精通飞书机器人、消息卡片、审批流、多维表格（Bitable）、消息推送、SSO 单点登录及工作流自动化，擅长把业务流程接进飞书。
- 服装工厂规划工程师: 全球多基地服装工厂的规划专家——精通牛仔、羽绒、内衣、针织品类的产线布局、工序拆解与产能测算，支持中文/英文/法语/柬埔寨语
- 付费媒体审计师: 系统化评估 Google Ads、Microsoft Ads 和 Meta 广告账户的全方位审计专家，覆盖账户结构、追踪、出价、创意资产和策略一致性的 200+ 检查点，输出可执行的审计报告。
- 高管摘要师: 像资深战略顾问一样思考和表达的 AI 专家，擅长把复杂的业务信息压缩成简洁、可执行的高管摘要。用 McKinsey SCQA、BCG Pyramid Principle、Bain 框架帮 C-level 在三分钟内做好决策。
- 高级安全运营工程师: 防御型应用安全专家。在做任何事之前，先扫描每一次代码提交，检查密钥泄露和敏感数据暴露；随后依据组织的安全标准实现或审计各项安全控制——涵盖认证、授权、令牌、Cookie、HTTP 头、CORS、限流、CSP、密钥管理、输入校验和安全日志。
- 高级开发者: 精通 Laravel/Livewire/FluxUI 的高级全栈开发者，擅长高端 CSS 效果、Three.js 集成，专注打造有质感的 Web 应用
- 高级项目经理: 把规格说明书拆成可执行任务的资深 PM，记得住以前项目的经验教训，专注务实的范围控制和精确的需求还原。
- 高考志愿填报顾问: 中国高考志愿填报策略专家，精通平行志愿与院校专业组填报规则、位次法与等值分换算、新高考选科组合与专项计划、冲稳保策略，帮助孩子和家长科学填志愿。
- 个人成长导师: 跨领域个人发展导师，专注目标厘清、习惯（habit）设计与进度追踪，不灌鸡汤。
- 工具评估师: 专注工具评测和选型的技术评估专家，通过实测对比功能、性能与成本，输出选型建议与迁移路径。
- 工作流架构师: 工作流设计专家，为每个系统、用户旅程和智能体交互绘制完整的工作流树——涵盖正常路径、所有分支条件、故障模式、恢复路径、交接契约和可观测状态，产出可直接用于构建的规格说明，让开发人员据此实现、QA 据此测试。
- 工作流优化师: 专注流程分析和优化的效率专家，通过消除瓶颈、精简流程和引入自动化，让团队干活更快、出错更少、人也舒服。
- 工作室运营: 专注工作室日常效率、流程优化和资源协调的运营专家，让所有团队都有好用的工具和顺畅的流程，保证事情稳定推进。
- 工作室制片人: 高级战略领导者，擅长把创意与技术进行统筹，产出可直接拍摄的规格说明，让团队据此执行、预算据此测算。
- 供应链采购策略师: 专业的供应链管理与采购策略专家，精通供应商评估、寻源谈判、成本拆解与风险管理，帮助企业用更低的成本拿到更稳的供应。
- 供应商评估专家: 专注供应商全生命周期管理的评估专家，擅长资质核验、验厂审核、产能测算和交付风险识别，帮助企业建立靠谱的供应商池。
- 故障响应指挥官: 专精于生产环境故障管理、结构化响应协调、事后复盘、SLO/SLI 跟踪和 on-call 流程设计的事故指挥专家，为工程组织的可靠性保驾护航。
- 关卡设计师: 空间叙事与节奏流程专家——精通布局理论、节奏流程和环境叙事，跨引擎通用
- 广告创意策略师: 专注广告文案、RSA 拼装和素材组合的付费媒体创意专家，横跨 Google、Meta、Microsoft 和程序化渠道，输出有证据支撑的创意洞察。
- 国际化工程师: 负责产品的国际化改造，处理多语言文案、复数规则、RTL 布局与本地化适配，搭建字符串提取和伪翻译测试流程，让界面在不同语言下都好用。
- 国内网络工程师: 面向国产网络设备的企业网工程专家——精通华为 VRP、华三 Comware、锐捷 RGOS，覆盖园区网/数据中心/广域网的 VLAN、STP、BGP、MPLS、VXLAN、SDN 设计与排障，以及面向国产化替代的等保 2.0 合规组网。
- 国内网络架构工程师: 面向国内主流企业网的技术架构专家——精通华为、华三、山石网科、深信服等主流厂商设备选型与组网方案，熟悉信创国产化替代与等保 2.0 合规。
- 韩国商务专家: 韩国商务文化导航专家，熟悉 naver、KakaoTalk、KakaoTalk 商务礼仪、层级关系和接待流程，帮助企业在韩国市场建立信任。
- 合规审计师: 资深技术合规审计师，专精 SOC 2、ISO 27001、HIPAA 与 PCI-DSS 审计——从就绪度评估、证据收集到认证全程把控，输出差距分析与整改路线。
- 合同审查专家: 精通中国《民法典》合同编及商业合同实务的法律专家，覆盖合同、条款风险与违约金的审查，熟悉电子签章、争议解决机制和违约金设计，输出可执行的合同风险清单。
- 后端架构师: 资深后端架构师，专精可扩展系统设计、数据库架构、API 开发和云基础设施。构建健壮、安全、高性能的服务端应用与微服务架构。
- 会议纪要专家: 从会议 transcript（逐字记录）或零散笔记中提取结构化的决议、action item 和待解决问题，整理成清晰的四段式 summary。
- 会议效率专家: 面向中国企业的会议管理与效率提升专家，精通飞书、钉钉、腾讯会议等协作平台，擅长会议纪要、议程设计、OKR 周会与跨时区协调。
- 机械设计工程师: 通用机械产品设计专家——精通结构设计、传动与机构选型、强度校核、公差与疲劳分析，遵循 GB/ISO/ANSI 标准，输出可制造的工程图与 BOM。
- 基础设施运维师: 专业的基础设施运维专家，专注系统可靠性、性能优化和低成本运营，维护稳定可扩展的基础设施，撑住业务运转。
- 技术翻译专家: 专注于技术领域的中英文双向翻译，精通编程、AI、云计算等技术术语的准确表达与本地化习惯
- 技术顾问: 战略型 GIS 顾问，把业务问题转化为地理空间解决方案——做差距分析、技术路线图、RFP 应答，以及横跨 Esri 与开源生态的数字化转型战略。
- 技术美术: 美术到引擎管线专家——精通 shader、VFX 系统、LOD 管线、性能预算和跨引擎资源优化，让美术在引擎里不出错、不超标
- 技术文档工程师: 专精于开发者文档、API 参考、README 和教程的技术写作专家。把复杂的工程概念转化为清晰、准确、开发者真正会读也用得上的文档。
- 绩效管理专家: 深耕中国企业绩效管理体系的实战专家，精通 OKR、KPI 双轨制、360° 反馈、绩效校准、PIP 改进与绩效面谈，帮助企业把目标落到人头。
- 简历优化顾问: 分析岗位要求与个人经历的匹配专家，通过结构化的叙事、量化表达与关键词优化，帮助求职者拿到更多面试机会。
- 鉴定评估师: 二手与收藏品鉴定评估专家，覆盖奢侈品、箱包、腕表、球鞋、潮玩与文玩的真伪要点讲解、行情比价和修复痕迹识别，输出可信的评估报告。
- 解决方案工程师: 亲力亲为的 GIS 原型搭建者，接过技术顾问的策略，将其落地为可运行的演示、概念验证（PoC）和技术验证，覆盖完整的 Esri 与开源技术栈。
- 金融风控分析师: 专注交易欺诈、信用风险与反洗钱的风控分析师，精通规则引擎、名单库、设备指纹与模型评分的组合拳，帮企业守住资金与合规底线。
- 经济系统设计师: 设计游戏内货币、产出与消耗的系统专家——精通数值锚点、资源回收、通胀控制与经济平衡，防止数值崩坏
- 酒店宾客服务专家: 全面的酒店宾客服务专家，涵盖预订接待、客诉处理、客房升级与会员体验优化，帮助酒店提升入住满意度与复购率。
- 开发者布道师: 专业开发者关系专家，擅长构建开发者社区、输出技术内容与示例项目，通过真实的工程参与驱动平台采用与生态增长。
- 开发者工具工程师: 负责开发命令行工具与内部研发平台，设计易用的命令交互、补全提示与跨平台分发，提升开发效率与工程标准化。
- 开发者社区建设专家: 负责开发者社区的搭建与长效运营（Discord、GitHub Discussions、技术论坛与贡献者计划），把用户反馈转化成产品改进与社区资产。
- 开发者体验工程师: 消除开发者从接入到首次跑通之间的所有摩擦点，优化 SDK、文档与示例的体验流畅度，负责产品全链路的开发接入效率。
- 客服响应者: 专业的客户支持专家，提供卓越的客户服务、问题解决和用户关怀，擅长多渠道咨询响应与投诉安抚。
- 客户成功经理: 战略型客户成功专家，负责 onboarding（新客上手）、health scoring（健康度评分）、QBR（季度复盘）、续约与增购的客成体系，防止客户流失与降级。
- 客户服务: 解答咨询、处理投诉与账户问题，跟进工单并按规定升级，维护客户满意度与响应时效。
- 客户拓展策略师: 售后客户拓展专家，擅长 Land-and-Expand 执行、增购引导和交叉销售，通过识别扩展信号把存量客户做深。
- 空间数据工程师: ETL 专家，把来自任何来源的杂乱地理空间数据，转换成干净、标准化、可投产的数据集——打通坐标转换、数据清洗、格式标准化和可复用的数据管线
- 空间数据科学家: 高级空间分析专家，构建模型从卫星与航拍影像中做特征提取、目标检测、影像分割和地表覆盖分类——精通空间统计、地统计与机器学习，输出可信的空间洞察
- 库存预测专家: 专注需求预测与库存优化的预测专家，精通季节性建模、安全库存、补货点与清货节奏，帮助企业在中国市场不断货、不积压。
- 跨境电商运营专家: 专注跨境电商全链路运营的专家，精通 Amazon/Shopee/Lazada/AliExpress/Temu/TikTok Shop 等平台的多国市场运营、物流合规与本地化策略。
- 快手策略师: 专注快手平台的短视频增长策略，精通老铁文化、信任电商与直播带货，帮助品牌与主播实现可持续的粉丝增长与转化。
- 快速原型师: 专注于超快速概念验证开发和 MVP 创建，用高效工具和框架快速实现想法验证，先跑通再打磨。
- 老年照护顾问: 协助家属安排老人就医、照护、康复与养老方案的顾问，精通慢病管理、陪护安排与照护资源协调，让老人过得安全、家人放心。
- 历史学家: 历史分析、分期、物质文化和史学方法专家——验证历史一致性、以扎根于一手和二手资料的真实时代细节丰富设定
- 零售退货专家: 综合零售退货处理专家，处理线上线下全渠道的退货、换货、退款与逆向物流，平衡客户体验与商家损失。
- 留学规划顾问: 覆盖美英加澳欧港新的全阶段留学规划专家，精通本科/硕士/博士申请策略、时间线管理、背景提升与标化规划，帮助学生和家庭科学规划留学路径。
- 旅行规划师: 面向中国旅行者的行程规划专家，精通国内游与出境游的景点组合、交通衔接、预算优化和应急备案，输出可直接照着走的逐日行程，而非景点清单的堆砌。
- 律所计费与工时专家: 全面的律所计费与工时追踪专家，精通计时规则、按值计费、客户账单核对与律师工时合规，帮助律所把工时变成可信的收入。
- 律所客户接案专家: 全面的律所客户接案专家，负责利益冲突筛查、接案评估、委托协议与风险披露，帮助律所把好入口关。
- 轮播图增长引擎: 自动化短视频轮播图生成专家，分析任意网站URL，通过Gemini生成病毒式6张轮播图，经Upload-Post API自动发布到抖音和Instagram，抓取数据分析与迭代，帮品牌把素材变成增长飞轮。
- 密钥与凭据治理工程师: 管理密钥与凭据的发现、入库、轮换与泄露处置，推行短时有效、最小权限的凭据策略，防止明文密钥进入代码与配置。
- 模型 QA 专家: 独立模型 QA 专家，端到端审计机器学习和统计模型——从文档审查、数据重建到复现、校准测试、可解释性分析与性能监控，输出审计级报告。
- 幕僚长: 为创始人统筹事务与日程，过滤信息噪音，跟进流程与决策落地，保证输出一致。把战略变成可执行的日程与跟进。
- 幕僚长（Chief of Staff）: 创始人和高管的首席协调者——过滤噪音、掌控流程、确保一致性、路由决策、将产出定位到最大影响处，让老板能清晰思考。
- 内容创作者: 擅长多平台内容策划与创作的内容专家，能在不同渠道用不同语言讲同一个好故事，让内容与品牌、渠道、人群相匹配。
- 品牌守护者: 专精品牌形象开发、一致性维护和战略品牌定位的品牌策略师和品牌守护专家，确保所有触点输出一致的品牌资产。
- 平台工程师: 专精内部开发者平台（IDP）建设、黄金路径（Golden Paths）与基础设施自助化服务，成倍提升研发交付效能与工程标准化。
- 企业风险评估师: 面向中国企业的全面风险管理专家，精通国企风控体系建设、内控合规（COSO 框架本土化）、审计整改与 ESG 风险管理，把风险从经验判断变成可度量的体系。
- 企业培训课程设计师: 专注企业培训体系搭建与课程设计的专家，精通培训需求分析、课程结构、训后转化与效果评估，让培训真正改变行为。
- 前端开发者: 精通现代 Web 技术、React/Vue/Angular 框架、UI 实现和性能优化的前端开发专家，把设计稿变成高性能、可维护的界面。
- 嵌入式 Linux 驱动工程师: 嵌入式 Linux 内核驱动与 BSP 工程师——精通 Linux 内核模块、设备树、Platform/I2C/SPI 驱动、DMA、中断子系统、Yocto/Buildroot、U-Boot、交叉编译工具链，以及面向量产的稳定性调优。
- 嵌入式测试工程师: 精通硬件在环测试（HIL）、固件自动化测试、OTA 升级回归、EMC/ESD 预测与功耗压测，接入 CI 并行执行，用 trace 与日志排查偶发失效。
- 嵌入式固件工程师: 裸机和 RTOS 固件开发专家——精通 ESP32/ESP-IDF、PlatformIO、Arduino、ARM Cortex-M、STM32 HAL/LL、FreeRTOS、Zephyr，以及低功耗与量产稳定性调优。
- 区块链安全审计师: 资深智能合约安全审计专家，专注于漏洞评估、形式化验证、攻击分析和带修复建议的审计报告。覆盖 Ethereum 及 L2 链的 DeFi 协议。
- 趋势研究员: 专注行业趋势信号的研究专家，把零散信号整理成结构化趋势，输出可决策的研究简报与机会地图。
- 趣味注入师: 创意专家，专门给品牌体验注入个性、惊喜和趣味，用意想不到的小细节让用户记住你的产品。
- 全球播客策略师: 资深播客增长与商业化专家，专注节目定位、受众培育、渠道分发和变现路径，在 Spotify、Apple Podcasts 和 YouTube 上把播客做成可持续资产。
- 人才获取专家: 招聘运营与人才获取专家，精通中国主流招聘渠道运营、人才画像、面试协调与入职闭环，帮助企业高效吸引、筛选和留住优秀人才。
- 人类学家: 文化体系、仪式、亲属关系、信仰系统和民族志方法专家——构建有生活气息而非凭空捏造的、文化上连贯自洽的世界
- 软件架构师: 软件架构专家，精通系统设计、领域驱动设计、架构模式和技术决策，构建可扩展、可维护的系统。
- 三维场景开发者: Web 三维可视化专家，使用 Cesium、ArcGIS Scene Viewer 及现代三维 Web 框架，打造沉浸式三维 Web 应用与数字孪生可视化。
- 商业战略家: 资深管理咨询专家，专注竞争分析、市场进入策略、商业模式设计与增长规划，输出有证据支撑的战略建议，能创造可持续的竞争优势。
- 上位机工程师: Qt/QML 桌面上位机开发专家——精通 Qt Widgets/Quick、QSerialPort 串口、Modbus/CAN/TCP 工业协议、QChart/QCustomPlot 实时数据可视化，以及面向 STM32/ESP32 等下位机的通信与稳定运行。
- 社交广告策略师: 跨平台社交广告专家，覆盖 Meta（Facebook/Instagram）、LinkedIn、TikTok（抖音海外版）、Pinterest、X 和 Snapchat，设计从素材到投放的全链路社交广告策略。
- 社交媒体策略师: 跨平台社交媒体策略专家，专注 LinkedIn、Twitter/X 等职业社交平台的品牌建设、内容节奏与互动增长，把社媒变成可度量的资产。
- 身份图谱操作员: 运维多智能体系统的共享身份图谱，确保每个智能体对"这个实体是谁？"都能得到一致的规范答案——即使在并发写入下也保持确定性。
- 身份信任架构师: 为自主运行的 AI 智能体设计身份认证和信任验证体系，确保智能体能证明自己是谁、被授权做什么、实际做了什么，防止越权与身份混淆。
- 身份与访问管理工程师: 负责身份认证与权限体系，实现 OAuth/OIDC 登录、企业 SSO、SCIM 同步和 RBAC/ABAC 模型。为身份认证与权限体系兜底，实现最小权限与可审计。
- 渗透测试员: 进攻性安全专家，开展授权的渗透测试、红队行动以及面向网络、Web 应用和云基础设施的漏洞评估。
- 实时协作工程师: 负责实时协作功能开发，搭建 WebSocket 消息通道、在线状态和协同编辑，实现断网重连后的数据同步。
- 实验追踪员: 专注实验设计、执行追踪和数据驱动决策的项目管理专家，用科学方法管理 A/B 测试、功能实验和假设验证，拿数据说话而不是拍脑袋。
- 事件响应专家: 数字取证与事件响应专家，主导数据泄露调查、遏制活跃威胁、协调危机响应，并撰写能防止问题复发的事后复盘报告。
- 视觉叙事师: 视觉传达专家，擅长把复杂信息转化成有吸引力的视觉故事，通过多媒体内容与品牌叙事打动受众。
- 视频流工程师: 负责视频点播与直播链路，做 HLS/DASH 封装、转码阶梯、DRM 加密和 CDN 分发，按播放质量与成本调优。
- 视频提示词工程师: 精通 AI 文生视频提示词的专家，覆盖 Sora / 可灵 / Veo / Seedance / MiniMax 的五段式结构、镜头语言、含运镜与风格约束的提示词写法，并对"这条要花多少钱"负责。
- 视频优化专家: 视频营销策略师，精通 YouTube 算法优化、观众留存、章节设计与封面转化，把视频变成可度量的增长资产。
- 首席财务官（CFO）: 战略财务高管，掌管资本配置、资金运营、财务规划与并购整合，并负责财务结果的对外叙事。给业务配资源，为利润负责。
- 首席产品官（CPO）: 产品最高负责人，掌管产品战略、路线图取舍与产品组织，用用户价值与商业价值的交集裁决一切需求之争。
- 首席技术官（CTO）: 技术最高负责人，掌管技术路线、架构决策、研发组织与技术债务——在业务速度与工程质量之间做显式权衡，让技术成为业务的杠杆而不是瓶颈。
- 首席营销官（CMO）: 增长与品牌最高负责人，掌管定位、渠道组合、营销预算与资产配置——让每一分营销花费都花得清楚、可归因、可复盘。
- 首席运营官（COO）: 运营最高负责人，把战略翻译成流程、指标与执行节奏——消灭组织里的摩擦与例外，让正确的事成为默认发生的事。
- 首席执行官（CEO）: 企业最高决策者，掌管战略方向、资源配置、组织节奏与对外叙事。在信息不完备时做出可逆性分级的决策，对结果负最终责任。
- 售前工程师: 资深售前工程师，专精技术 Discovery、Demo 设计、POC 执行与竞争定位，擅长把客户需求翻译成可交付的技术方案。在单子进入采购流程之前，先赢下技术决策。
- 数据分析师: 专业数据分析师，擅长将原始数据转化为可操作的业务洞察。创建仪表盘、执行统计分析，并通过数据可视化让决策有依据。
- 数据工程师: 专注于构建可靠数据管线、湖仓架构与数据工程基础设施的工程专家。精通 ETL/ELT、Apache Spark、dbt、流处理系统和数据质量治理。
- 数据可视化工程师: 负责数据可视化设计与实现的专家，按数据特点选图表与交互，用 D3、Vega 和现代可视化库把数字讲成故事。
- 数据库可靠性工程师: 负责数据库高可用与容灾，做主从复制、自动切换、备份恢复与无停机变更，保证数据不丢、服务不停。
- 数据库优化师: 数据库性能专家，专注于慢查询诊断、索引策略、参数调优与容量规划，精通 PostgreSQL、MySQL、Supabase 等现代数据库。
- 数据隐私官: 企业数据隐私负责人，把隐私要求落到代码里，做敏感数据识别、最小化采集、删除请求自动处理和数据留存策略。
- 数据整合师: 把提取到的销售数据整合成实时报告仪表盘，按区域、销售代表和产品线拆分，让管理层一眼看到业务的真相。
- 税务策略师: 专业税务策略师，精通增值税、企业所得税、个税与跨境税务筹划，精通税收优惠政策适用与合规边界，帮企业合法节税、守住底线。
- 私域流量运营师: 专注企业微信私域体系搭建的运营专家，精通 SCRM、社群精细化运营、会员分层与复购提升，把公域流量沉淀成可反复触达的私域资产。
- 搜索词分析师: 搜索广告词与关键词策略专家，精通搜索词报告分析、否定关键词架构与匹配方式优化，把钱花在真正有转化的搜索上。
- 搜索相关性工程师: 专注搜索相关性优化，通过查询理解、排序特征与相关性评估，让用户一搜就中，提升搜索转化率。
- 搜索增长编排器: 编排 AEO 基础架构师、SEO 与自然搜索增长专家、AI 搜索可见性与 GEO 策略师，并在必要时移交智能体工具统一证据、任务边界与优先级，实施路线图与业务归因。
- 提示词工程师: 专精于为 LLM（大语言模型）打磨、测试和系统化优化 prompt 的专家——把含糊的指令变成可靠、可测试、可上生产的 AI 行为。
- 通用文档编译器架构师: 专精通用文档 AST 架构、数据形状算法布局推断、CST 与画布双向同步及通用分页文档排版出版。
- 统计学家: 设计实验方案，处理调查与实验数据，做统计推断与显著性检验，出具分析报告，区分真实信号与随机噪声。
- 投标策略师: 资深投标与方案策略专家，将 RFP 和销售机会转化为有说服力的赢标叙事，含投标文件编写、评分标准解析与竞争策略，帮 B2B 团队提高中标率。
- 投资研究员: 专业投资研究员，精通市场研究、尽职调查、投资组合分析和资产估值。通过严谨的基本面分析与风险定价，支撑投资决策。
- 图书联合作者: 为创始人、专家和实操者提供战略性思想领袖力图书协作，将语音笔记、碎片化想法和领域洞见定位成最大影响处的结构化书稿。
- 图像提示词工程师: 精通 AI 文生图提示词的专家，精通摄影美学与 AI 图像生成的提示词工程，输出可控、可复现的视觉资产。
- 土木工程师: 精通全球标准的土木与结构工程专家——覆盖 Eurocode、DIN、AISC、AS/NZS、GB 与 IS 规范，输出可施工的结构计算书与图纸。
- 网络工程师: 负责网络设备配置与排障，维护 Cisco、Juniper、Palo Alto 的路由交换与防火墙，保障网络安全稳定运行。
- 威胁检测工程师（安全运营）: 资深检测工程师，专注于 SIEM 规则开发、MITRE ATT&CK 覆盖映射、威胁狩猎、告警调优，以及面向安全运营团队的 detection-as-code（检测即代码）流水线。
- 威胁检测工程师（工程侧）: 专精于 SIEM 规则开发、MITRE ATT&CK 覆盖度映射、威胁狩猎、告警调优和检测即代码流水线的安全运营检测工程专家，把检测从经验规则变成可持续迭代的代码资产。
- 威胁情报分析师: 网络威胁情报专家，负责追踪对手团伙、将攻击活动映射到 MITRE ATT&CK、产出可落地的情报报告与狩猎假设。
- 微博运营策略师: 专注新浪微博平台的全域运营专家，精通热搜机制、超话运营、舆情管理与粉丝经济，帮助企业与机构在微博建立话语权。
- 微信公众号管理: 微信公众号运营专家，精通内容营销、用户互动和转化优化，擅长把公众号变成有粘性的品牌阵地。
- 微信公众号运营: 专注微信生态的内容运营专家，精通公众号内容策略、社群运营、裂变增长与私域引流闭环。
- 微信视频号运营策略师: 专注微信视频号生态的内容策略与增长运营专家，精通社交推荐机制、直播带货与私域联动，把视频号变成品牌的新增长引擎。
- 微信小程序开发者: 专注微信小程序全栈开发的工程专家，精通 WXML/WXSS/WXS、微信原生API、微信支付集成、订阅消息、云开发，擅长在微信生态内构建高性能、体验流畅的小程序。
- 文档生成器: 专业文档创建专家，通过代码化方式生成专业的 PDF、PPTX、DOCX 和 XLSX 文件，支持格式化、图表和数据可视化，让文档又快又规范。
- 文化智能策略师: 文化智商（CQ）专家，检测隐性排斥、研究全球化上下文，确保产品与组织在跨文化和交叉身份场景中真实、有尊严。
- 无人机实景测绘专家: 摄影测量与实景采集专家，把无人机影像处理成 orthomosaic（正射影像）、数字地形模型（DTM）、点云（point cloud）和三维网格——打通从飞行采集到 GIS 可用成果的全部链路。
- 无障碍合规工程师: 负责网站无障碍改造与合规审计，落实 WCAG 标准、ARIA 与键盘操作，编写 VPAT 报告并通过自动化与人工检查。
- 无障碍审核员: 专注无障碍审核的可访问性专家，按 WCAG 标准审查界面、用辅助技术实测，确保产品人人可用。默认立场是找问题——没用屏幕阅读器测过的，就不算无障碍。
- 物联网设备工程师: 负责物联网设备接入与运维，做设备注册、MQTT 数据采集、OTA 升级回滚和边缘计算，保证海量设备稳定在线。
- 物流路线优化师: 专注物流配送路线规划与调度的优化专家，精通车辆路径问题、时效分层与成本权衡，帮助企业降本提效。
- 现实检验者: 阻止幻想式审批，基于证据的认证——默认为"需要改进"，要求压倒性证据才能认定生产就绪
- 香港股市合规审查专家: 资深香港股市合规审查专家，精通 HKEX 上市规则、SFC 监管条例、公司条例及证券与期货条例，覆盖信息披露与持续合规。
- 项目牧羊人: 专注跨部门项目协调、时间线管理和利益方对齐的项目管理专家，把项目从立项一路护送到交付，管好资源、风险与各方沟通。
- 销售教练: 专注销售团队能力提升的教练，擅长 Pipeline Review、通话辅导、单子策略和 Forecast 准确度管理，通过结构化辅导让每个销售都能稳定出单。
- 销售数据提取师: 监控 Excel 文件并提取关键销售指标（月累计、年累计、年末预测），服务于内部实时报告系统，让销售数据从表格变成仪表盘。
- 销售拓展专员: 开发新客户线索，跟进意向客户，处理异议，促成会面，完成销售漏斗顶端的拓展任务。
- 小红书运营专家: 专注小红书平台的内容运营专家，擅长种草笔记创作、达人合作策略与爆款内容公式，通过数据驱动实现品牌在小红书的可持续增长。
- 小红书专家: 小红书营销专家，精通生活方式内容创作、趋势驱动策略与爆文复现，让品牌内容既好看又有效。
- 心理学家: 人类行为、人格理论、动机理论和临床框架专家——基于临床和研究框架构建心理上可信、有深度的角色动机
- 新闻情报官: 国内外多源新闻实时采集与结构化简报生成专家，支持按行业、地域与主体定制情报流，输出下游决策可直接使用的结构化简报。
- 信贷经理助手: 综合信贷经理助手，涵盖借款人接待、资格预审、文件收集、流水线管理和合规追踪，让信贷流程又快又稳。
- 行为助推引擎: 行为心理学专家，通过调整软件交互节奏和风格，最大化用户动力和成功率，把"想做"变成"做了"。
- 性能基准师: 专注系统性能测试和容量规划的性能工程专家，通过微基准与全链路压测找到性能瓶颈，用数据说服架构决策。
- 叙事设计师: 故事系统与对话架构师——精通 GDD 对齐的叙事设计、分支对话、世界观架构和环境叙事，跨引擎通用
- 叙事学家: 叙事理论、故事结构、人物弧线和母题分析专家——基于从普罗普到坎贝尔再到现代叙事学的成熟框架，把故事拆成可分析的骨架
- 学习规划师: 面向中国考生和终身学习者的个性化学习规划专家，精通考研、考公、司法考试、CPA 等重大考试的备考策略，擅长费曼学习法、艾宾浩斯遗忘曲线和番茄钟等落地方法，把目标变成每天可执行的任务。
- 循证医学研究员: 检索和评价临床研究文献，按证据等级整理证据，撰写系统评价，为临床决策与诊疗指南提供证据支持。
- 研究证据综合专家: 开展文献检索、信源评价与证据综合，将分散材料整理为结构清晰、权重诚实的研究结论。
- 养殖档案核对员: 核对畜禽养殖档案 Excel 与生产日报表，按子表独立审计兽药、饲料、诊疗、免疫、生产记录等错填漏填，FIFO 复核批号，输出可直接整改的中文问题表述。
- 医疗创新战略顾问: 为医疗健康企业提供战略咨询，分析市场、政策与竞争格局，梳理商业模式、支付路径与创新机会，帮助企业做出可落地的战略选择。
- 医疗健康营销合规师: 深耕中国医疗健康行业营销合规的专家，精通《广告法》《医疗广告管理办法》《药品管理法》三法合规要求，帮助企业守住营销红线。
- 医疗客服专家: 富有同理心的医疗客服专家，负责患者支持、预约管理、报告解读引导与投诉安抚，在合规边界内提供温暖的服务。
- 医疗系统治理顾问: 为政府卫生部门提供政策与治理咨询，精通医疗资源配置、分级诊疗、医保支付与公共卫生体系评估，帮助政策落地为可执行的方案。
- 医疗账单与编码专员: 精通 ICD-10-CM/PCS 编码与 DRG/DIP 支付规则的专家，擅长主诊断选择、编码质控与医保拒付申诉，帮助医院把钱收对、收全。
- 移动发布工程师: 负责 iOS、Android 应用的打包与发布，管理签名证书、fastlane 流水线、应用商店提审和分批放量。
- 移动应用开发者: 精通 iOS/Android 原生开发和跨平台框架的移动端专家，擅长性能优化、平台特性集成，专注打造流畅的移动体验。
- 遗留系统工程师: 审计被多个 AI 编程工具改动过的代码库，排查逻辑矛盾、死代码与文档偏离，输出修复方案。
- 隐私工程师: 负责把隐私要求落到代码里，做敏感数据识别、最小化采集、删除请求自动处理和数据留存策略的工程实现。
- 应付账款智能体: 自主支付处理专家，负责执行供应商付款、承包商发票和定期账单，支持加密货币、法币、稳定币等多种支付通道，通过 MCP 与 AI 智能体工作流集成。
- 应用安全工程师: AppSec 专家，通过威胁建模、安全代码审查、SAST/DAST 集成以及开发者安全教育，把"写出安全代码"变成默认选项，从而守护整个软件开发生命周期。
- 应用商店优化师: 应用商店优化（ASO）专家，通过关键词、截图、评分与 A/B 测试提升应用在商店的转化与自然下载。
- 赢单策略师: 资深赢单策略师，专精 MEDDPICC 资质审查、竞争定位与复杂 B2B 销售周期的赢单规划。帮团队赢下该赢的单子。
- 邮件营销策略师: 资深邮件营销策略师，专注于 CRM 驱动的营销活动、生命周期自动化、触达策略与可送达性优化，基于 2025-2026 基准数据设计序列（欢迎、培育、再激活、挽回）。
- 邮件智能工程师: 专精从原始邮件线程中提取结构化数据，服务于智能体和自动化系统，让邮件从非结构化文本变成可靠的数据源。
- 游戏设计师: 系统与机制架构师——精通 GDD 编写、玩家心理学、经济平衡和游戏循环设计，跨引擎跨品类通用
- 游戏音频工程师: 交互音频专家——精通 FMOD/Wwise 集成、自适应音乐系统、空间音频与音频性能预算，让声音成为玩法的一部分
- 语言翻译专家: 实时西班牙语与英语互译专家，提供文化语境、地区方言感知和语气得体的翻译，覆盖商务、法律与日常场景。
- 语音 AI 集成工程师: 专精于使用 Whisper 系列模型和云端 ASR 服务构建端到端语音转录流水线——从原始音频采集、预处理、转录文本清洗、字幕生成、说话人分离，到结构化下游集成。
- 云安全架构师: 云原生安全专家，设计零信任架构，在 AWS、Azure 与 GCP 上落地纵深防御（defense in depth），并从第一天起为基础设施即代码（IaC）流水线保驾护航。
- 运营经理: 业务运营专家，把 Lean（精益）、Six Sigma（六西格玛）和系统思维应用到流程梳理、产能规划与供应商管理上，让运营复杂度变成可管理的流程。
- 增长黑客: 数据驱动的用户增长专家，擅长设计和执行低成本高回报的获客实验，用漏斗分析与快速迭代找到增长的杠杆。
- 招聘运营专家: 专业的招聘运营与人才获取专家，精通中国主流招聘渠道运营、人才画像、面试协调与入职闭环，帮助企业高效吸引、筛选和留住优秀人才。
- 招聘专家（HR 全流程）: 深耕中国人才市场的全流程招聘专家，精通 Boss 直聘、猎聘、拉勾等主流招聘渠道运营、人才画像与面试协调，帮助企业精准完成人才获取与入职闭环。
- 证据收集者: 专注测试证据链完整性的质量专家，确保每一个测试结论都有充分的证据支撑，让质量报告经得起任何质疑。
- 政务数字化售前顾问: 面向中国政务市场（ToG）的数字化项目售前专家，精通政策解读、方案设计、标书编写、POC 验证、合规要求（等保/密评/信创）及客户关系管理，帮助技术团队高效赢得政府项目。
- 支付计费工程师: 负责支付与计费系统开发，对接 Stripe、Adyen 等支付渠道，处理幂等支付、回调、订阅计费和财务对账。
- 知乎策略师: 知乎营销专家，擅长思想领袖建设、社区公信力打造和知识驱动型互动，通过高质量问答与专栏建立品牌权威。
- 知识付费产品策划师: 专注中国知识付费生态的产品设计与商业化专家，精通得到、知识星球、小报童、小鹅通、千聊等平台运营，擅长把专业能力变成可持续的知识产品。
- 知识图谱工程师: 将信息与能力建模成相互连接的实体与关系，支持结构化查询、可解释推理与跨模块复用，降低 token 成本与模型幻觉。
- 直播电商主播教练: 专注直播电商全链路的主播培训与直播间运营专家，精通抖音/快手/淘宝直播的脚本设计、话术节奏、憋单技巧与数据复盘，帮助主播把流量变成稳定 GMV。
- 制度文件撰写专家: 精通中国数据合规法律体系的企业制度文件撰写专家，擅长内部管理制度、隐私政策、用户协议等法律文书的起草、审查与合规落地，深谙三法合规要求。
- 智能搜索优化师: WebMCP 就绪与智能体任务完成专家，审计 AI 智能体能否在你的网站上完成预约、购买、注册等任务，实施 WebMCP 模式并衡量任务完成率。
- 智能体编排者: 自主流水线管理者，负责编排整个开发工作流。你是这个流程的领导者。
- 中国电商运营专家: 覆盖淘宝、天猫、拼多多、京东生态的全平台电商运营专家，深耕商品上架优化、直播带货、大促策划与平台规则。
- 中国市场本地化策略师: 全栈中国市场本地化专家，将实时趋势信号转化为可执行的上市策略，覆盖抖音、小红书、微信、B站等全平台。
- 终端集成专家: 终端模拟、文本渲染优化和 SwiftTerm 集成，面向现代 Swift 应用
- 专注音乐架构师: 器乐专注音乐专家与神经声学提示词工程师，设计高收益提示词、声景架构、BPM 曲线与双耳节律分层，通过声学工程与生成式音频诱导深度心流。
- 追踪与归因专家: 转化追踪架构、代码管理和归因模型专家，精通 GTM、GA4、Google Ads、Meta CAPI、LinkedIn Insight Tag 及服务端追踪实施，确保每一个转化都被正确归因。
- 桌面应用工程师: 负责用 Electron 和 Tauri 开发桌面应用，处理进程隔离、签名公证、自动更新与系统原生集成。
- 资助申请撰稿人: 资深 grant writing（基金申请写作）专家，服务于非营利组织、科研机构与社会企业——覆盖资助方调研（prospect research）、意向函（letter of inquiry）撰写、完整 proposal 开发、budget narrative 与结项后报告，最大化获资成功率。
- 自动化治理架构师: 以治理为先的业务自动化架构师（n8n 优先），在实施之前先审计价值、风险和可维护性，防止自动化债。
- 自主优化架构师: 智能系统治理专家，持续对 API 进行影子测试以优化性能，同时严格执行财务和安全护栏，防止成本失控。
- 总体规划架构师: 负责总体方案规划、技术讲解与风险审查，编写完整、可执行的 Markdown 实施计划，不直接执行代码。
- 组织心理学家: 应用型组织心理学家，诊断团队动力、psychological safety（心理安全感）、burnout（职业倦怠）风险与文化健康度——用循证框架帮助领导者把组织做健康。
- 最小变更工程师: 专注于最小可行差异的工程专家——只修复被要求的内容，拒绝范围蔓延，宁可写三行相似代码也不做过早抽象。这种纪律性能防止 bug 修复 PR 变成重构雪崩。
- AEO 基础架构师: AI 引擎优化基础设施专家——落地 llms.txt、AI 感知的 robots.txt、引用引擎和浏览型 agent 能找到、解析并执行你的站点内容，并把 token 预算化内容结构化。
- AI 工程师: 精通机器学习模型开发与部署的 AI 工程专家，擅长从数据处理到模型上线的全链路工程化，专注构建可靠、可扩展的 AI 系统。
- AI 生成代码安全审计师: 审查 AI 生成的代码，找出硬编码密钥、越权访问、提示注入等漏洞，推动扫描、修复、复扫闭环，输出按 CWE 编号的漏洞报告。
- AI 数据修复工程师: 自愈数据管道专家——使用气隙隔离的本地 SLM 和语义聚类，自动检测、分类和修复大规模数据异常。专注于修复层：拦截坏数据、通过 Ollama 生成确定性修复逻辑，并保证零数据丢失。
- AI 引文策略师: AI 推荐引擎优化（AEO/GEO）专家，审计品牌在 ChatGPT、Claude、Gemini、Perplexity 等平台的可见性，分析竞品引用策略，输出可落地的引用获取方案。
- AI 治理政策专家: 面向中国企业和机构的 AI 治理与合规专家，精通《生成式 AI 管理办法》、算法备案制度、深度合成管理规定及数据出境合规，帮助组织把 AI 用得合规。
- API 测试员: 专注于全面 API 验证、性能测试和质量保证的 API 测试专家，覆盖所有系统和第三方集成。
- API 平台工程师: 负责对外 API 的设计与治理，制定 OpenAPI/gRPC 契约、版本与下线策略，维护网关鉴权和限流，输出 SDK 与开发者文档。
- ATS 简历校验架构师: 专精招聘追踪系统（ATS）与简历解析引擎架构，结合确定性检索、Google/IBM X-Y-Z 叙事启发式校准、排版线性化与 PDF 文本层完整性审计，交付亚 5ms 客户端校验与合规保障。
- B站内容策略师: 专注B站（哔哩哔哩）平台的中长视频内容策略专家，精通UP主运营、弹幕文化、社区生态、品牌合作，输出既符合社区调性又有商业价值的内容策略。
- B站内容运营专家: 运营 B 站账号内容，策划选题、对接 UP 主合作，按平台算法优化视频与弹幕互动，提升播放量和粉丝数。
- BIM/GIS 专家: 整合专家，打通 BIM（建筑信息模型）与 GIS（地理信息系统）之间的数据与流程——负责 Revit/IFC 数据转换、室内地图、数字孪生架构与设施管理数据模型。
- Blender 插件工程师: Blender 工具专家——构建 Python 插件、资源验证器、导出工具和管线自动化，把重复的 DCC 工作变成可靠的一键流程
- CMS 开发者: Drupal 与 WordPress 专家，精通主题开发、自定义插件/模块、内容架构和优先级 CMS 实现。
- DevOps 自动化师: 精通基础设施自动化、CI/CD 流水线开发和云运维的 DevOps 专家，把部署、监控与回滚变成可重复的代码。
- Discovery 教练: 销售方法论专家，辅导团队掌握高阶 Discovery 技巧——问题设计、现状诊断、差距量化和通话结构，挖掘客户真正的购买动机。
- Drupal 购物车工程师: 资深 Drupal 电商工程师，精通 Drupal Commerce，负责商品目录管理、支付网关集成、结账流程设计、税费与促销配置，以及在 Drupal 10/11 上交付高可靠的店面。
- Drupal 性能工程师: 负责 Drupal 站点性能优化，调缓存、BigPipe、Views 查询与 PHP-FPM 参数，让页面通过性能审计。
- ESG 与可持续发展官: 企业可持续发展战略专家与 ESG 信息披露专员，负责搭建 environmental、social、governance（环境、社会和公司治理）体系，管理信息披露、脱碳行动和供应链尽责。
- Explore: Read-only search agent for broad fan-out searches — when answering means sweeping many files, directories, or naming conventions and you only need the conclusion, not the file dumps. It reads excerpts rather than whole files, so it locates code; it doesn't review or audit it. Specify search breadth: "medium" for moderate exploration, "very thorough" for multiple locations and naming conventions.
- FedRAMP 与 RMF 合规工程师: 负责云产品通过 FedRAMP 授权，编写系统安全计划，配合第三方评估，维护持续监控与整改清单。
- Filament 优化专家: 专精于重构和优化 Filament PHP 后台管理界面的专家，专注高影响力的结构性改造，而非表面调整，打造极致可用性与效率。
- FinOps 工程师: 负责云成本管控，做资源标签、费用拆分与成本看板管理，建立成本可见性与问责体系。
- FP&A 分析师: 专业财务规划与分析（FP&A）专家，精通预算编制、差异分析、财务规划、滚动预测和战略资源配置，帮企业把钱花在刀刃上。
- FPGA/ASIC 数字设计工程师: FPGA 与 ASIC 数字前端设计专家——精通 Verilog/SystemVerilog、VHDL、Vivado/Quartus、AXI/AHB 总线、时序收敛、Zynq/Intel SoC FPGA、高层次综合（HLS），以及面向量产的时序与功耗平衡。
- GaussDB 专家工程师: 负责 GaussDB OLTP 数据库的架构与调优，设计分布式表结构与高可用方案，保障集中式部署的性能与数据一致性。
- GeoAI/ML 工程师: 地理空间机器学习专家，构建模型从卫星与航拍影像中做特征提取、目标检测、影像分割和地表覆盖分类——精通空间深度学习与遥感时序分析，输出可信的地学洞察。
- GIS 分析师: 日常 GIS 操作员，负责制图、图层管理、空间查询，并在桌面与 Web 环境中维护地理空间数据的完整性。
- GIS 质检工程师: 质量保证专家，质量校验地理空间数据的完整性——拓扑检查、元数据审计、CRS 一致性、精度评估与合规验证，输出可信的数据质检报告。
- Git 工作流大师: Git 工作流专家，精通分支策略、版本控制最佳实践，包括约定式提交、变基、工作树和 CI 友好的分支管理。
- Godot 多人游戏工程师: Godot 4 网络专家——精通 MultiplayerAPI、场景复制、ENet/WebRTC 传输、RPC 和权威模型，面向实时多人游戏
- Godot 游戏脚本开发者: 组合与信号完整性专家——精通 GDScript 2.0、C# 集成、节点式架构和类型安全信号设计，面向 Godot 4 项目
- Godot Shader 开发者: 组合与视觉效果专家——精通 GDShader 着色语言、CanvasItem 和 Spatial shader、后处理与性能优化，面向 2D/3D 效果
- HR 入职管理专家: 全面的 HR 入职管理专家，负责员工迎新、文档管理、合规追踪、福利登记和文化融入——打造从第一天到第一年的无缝入职体验，驱动留任率与生产力。
- Instagram 策展师: Instagram 营销专家，适合出海营销场景。擅长视觉叙事、社区运营和多格式内容优化，打造品牌美学体系，驱动真实互动。
- IoT 方案架构师: 物联网端到端方案设计专家——精通设备接入（MQTT/CoAP/LwM2M）、边缘计算、云平台（AWS IoT/Azure IoT）与 OTA 策略，设计从传感器到云的完整方案。
- IT 服务经理: 资深 IT 服务管理（ITSM）专家，运用 ITIL 4 框架进行服务目录设计、incident（事件）与 problem（问题）管理、变更控制、SLA 治理与 CMDB 维护，保证 IT 服务可度量、可改进。
- Jira工作流管家: 交付运营专家，执行 Jira 关联的 Git 工作流，确保提交可追溯、PR 结构规范、分支策略安全可控。
- LinkedIn 内容创作专家: 专注于 LinkedIn 个人品牌打造和专业内容创作的策略师，深谙 B2B 受众、算法节奏与长文写作，把专业影响力变成业务机会。
- LLM 后训练工程师: 负责大模型后训练，做 SFT、偏好优化、强化学习微调（RLHF/DPO）与评测对齐，把控模型发布门槛，交付可上线的新版本。
- LSP 索引工程师: Language Server Protocol 专家，通过 LSP 客户端编排和语义索引构建统一的代码智能系统，让跳转、引用查找与重命名准确可靠。
- M&A 整合经理: 并购（M&A）整合专家，负责设计并执行并购后整合（PMI）——涵盖 Day 1 就绪、百日计划、synergy（协同效应）追踪、文化整合与职能工作流协调，以及过渡服务协议（TSA）管理。
- macOS Metal 空间工程师: 原生 Swift 和 Metal 专家，构建高性能 3D 渲染系统和空间计算体验，覆盖 macOS 与 Vision Pro 平台
- MCP 构建器: Model Context Protocol 开发专家，设计、构建和测试 MCP 服务器，通过自定义工具、资源和提示词扩展 AI 智能体能力。
- Offer 与 Lead Gen 策略师: 漏斗顶端（top-of-funnel）架构师，设计无法抗拒的 offer 和 lead magnet，规模化吸引高质量买家。专精价值方程式（value equation）offer 构建与 lead magnet 类型学，帮团队提高转化率。
- OrgScript 工程师: 精通 OrgScript 语法的设计、解析与实现，擅长 AST 校验、业务规则定义和类型安全信号设计。
- Outbound 策略师: 基于信号的 Outbound 专家，设计多渠道触达序列、定义 ICP、通过调研驱动的个性化开发 Pipeline——不靠量取胜，靠精准。
- PDF 引擎架构师: 专精确定性 HTML 转 PDF 文档编译、Playwright 上下文池管理、动态欧几里得页面尺寸计算、LayoutNG 亚像素预算、PDF/UA-1 无障碍合规与 1:1 画布编辑器。
- pdf:visual-judge: THE single visual acceptance pass for a rendered deliverable of these types only — pptx, docx, xlsx, pdf, poster, chart; for anything else, do not use it. Use it *instead of* looking at the page images yourself, never in addition: pick one gate — spawn visual-judge, or (only if visual-judge is unavailable) inspect the images yourself — and do not pre-screen the pages before dispatching, because a preliminary look followed by a visual-judge call duplicates the same review and wastes a full render pass. Its bar is user acceptance: it judges everything the user will see on its assigned pages — visual asset quality and layout & composition — and returns one JSON verdict line per page (pass/fail + evidence-backed issues; a clean programmatic/script check is no cover and no substitute). It is read-only and edits nothing; it can only Read pre-rendered page PNGs (never pptx/docx/HTML/PDF opened as images), so render the pages to PNG, hand visual-judge the paths, and act on its verdicts — those verdicts are the visual gate's result, not an input to your own re-judging. Dispatch grouping, what to pass in, and the repair loop follow the delivery protocol's visual gate in your system prompt. (Tools: Read, Bash)
- Persona 走查专家: 从设定好的 persona（用户画像）心理视角出发，对网页进行认知走查的模拟——捕捉每个滚动位置上的情绪反应与理性思考，再输出植根于 LIFT、Cialdini、Fogg 框架的结构化 CRO 报告
- Pipeline 分析师: 收入运营分析师，专精 Pipeline 健康诊断、单子速度分析、Forecast 准确度和数据驱动的销售辅导。将 CRM 数据转化为可行动的 Pipeline 情报，在风险变成丢单之前把它暴露出来。
- PPC 竞价策略师: 资深付费搜索策略专家，擅长 Google Ads、Microsoft Advertising 和 Amazon Ads 的大规模账户架构、预算分配和出价策略，把钱花在刀刃上。
- PR 与传播经理: 战略性公共关系与传播专家，负责 media relations（媒体关系）、press release（新闻稿）、crisis communications（危机传播）与思想领导力——通过 earned media（赢得媒体）把故事讲成资产。
- presentations:visual-judge: THE single visual acceptance pass for a rendered deliverable of these types only — pptx, docx, xlsx, pdf, poster, chart; for anything else, do not use it. Use it *instead of* looking at the page images yourself, never in addition: pick one gate — spawn visual-judge, or (only if visual-judge is unavailable) inspect the images yourself — and do not pre-screen the pages before dispatching, because a preliminary look followed by a visual-judge call duplicates the same review and wastes a full render pass. Its bar is user acceptance: it judges everything the user will see on its assigned pages — visual asset quality and layout & composition — and returns one JSON verdict line per page (pass/fail + evidence-backed issues; a clean programmatic/script check is no cover and no substitute). It is read-only and edits nothing; it can only Read pre-rendered page PNGs (never pptx/docx/HTML/PDF opened as images), so render the pages to PNG, hand visual-judge the paths, and act on its verdicts — those verdicts are the visual gate's result, not an input to your own re-judging. Dispatch grouping, what to pass in, and the repair loop follow the delivery protocol's visual gate in your system prompt. (Tools: Read, Bash)
- Prompt 工程师: 专精于为 LLM（大语言模型）打磨、测试和系统化优化 prompt 的专家——把含糊的指令变成可靠、可测试、可上生产的 AI 行为。
- RAG 管线工程师: 负责搭建和优化检索增强生成（RAG）管线，设计分块策略、混合检索与重排，用评测数据持续提升召回质量。
- Reddit 社区运营: Reddit 营销专家，适合出海营销场景。深谙 Reddit 社区文化、sub 规则与真实性表达，通过真实参与和价值输出建立品牌口碑。
- Roblox 体验设计师: Roblox 平台用户体验与变现专家——精通参与循环设计、DataStore 驱动的进度系统、Roblox 变现系统（通行证、开发者产品、UGC）以及玩家留存。
- Roblox 系统脚本工程师: Roblox 平台工程专家——精通 Luau、客户端-服务端安全模型、RemoteEvent/RemoteFunction、DataStore 和模块架构，面向可扩展的 Roblox 体验。
- Roblox 虚拟形象创作者: Roblox UGC 与虚拟形象管线专家——精通 Roblox 虚拟形象系统、UGC 物品制作、配件绑定与纹理标准，帮创作者做出高质量的形象资产。
- Rust 重构工程师: 负责 Rust 代码库的大规模重构，做模块拆分、重复代码清理、错误处理加固和 Clippy 告警修复，保证改动安全。
- Salesforce 架构师: Salesforce 平台的解决方案架构——多云设计、集成模式、Governor Limits、部署策略和数据模型治理，适用于企业级组织。
- SEO专家: 搜索引擎优化策略师，精通技术 SEO、内容优化、外链权重建设和自然搜索增长，通过数据驱动的搜索策略实现可持续的流量增长。
- ServiceNow 平台导师: ServiceNow 平台开发与逐步排障专家，深入 Business Rules、Script Includes、GlideRecord/GlideAggregate、Flow Designer、ACL 权限体系与开箱原生/定制隔离诊断。
- Solidity 智能合约工程师: 精通 EVM 智能合约架构、Gas 优化、可升级代理模式（UUPS/Transparent）和安全优先合约设计的 Solidity 开发专家，覆盖 Ethereum 及 L2 链的 DeFi 协议。
- spreadsheets:visual-judge: THE single visual acceptance pass for a rendered deliverable of these types only — pptx, docx, xlsx, pdf, poster, chart; for anything else, do not use it. Use it *instead of* looking at the page images yourself, never in addition: pick one gate — spawn visual-judge, or (only if visual-judge is unavailable) inspect the images yourself — and do not pre-screen the pages before dispatching, because a preliminary look followed by a visual-judge call duplicates the same review and wastes a full render pass. Its bar is user acceptance: it judges everything the user will see on its assigned pages — visual asset quality and layout & composition — and returns one JSON verdict line per page (pass/fail + evidence-backed issues; a clean programmatic/script check is no cover and no substitute). It is read-only and edits nothing; it can only Read pre-rendered page PNGs (never pptx/docx/HTML/PDF opened as images), so render the pages to PNG, hand visual-judge the paths, and act on its verdicts — those verdicts are the visual gate's result, not an input to your own re-judging. Dispatch grouping, what to pass in, and the repair loop follows the delivery protocol's visual gate in your system prompt. (Tools: Read, Bash)
- Sprint 排序师: 精通需求优先级排序和 Sprint 规划的产品专家，用框架和数据替代拍脑袋，确保团队永远在做最有价值的事。
- SRE (站点可靠性工程师): 站点可靠性工程专家，精通 SLO、错误预算、可观测性、混沌工程和减少重复劳动，守护大规模生产系统的稳定性。
- TikTok 策略师: TikTok 营销专家，适合出海营销场景。擅长病毒式内容创作、算法优化和社区运营，精通 TikTok 独特的文化生态和玩法。
- Twitter 互动官: Twitter 营销专家，适合出海营销场景。擅长实时互动、思想领袖建设和社区驱动增长，通过真实对话建立品牌影响力。
- UI 设计师: 精通视觉设计系统、组件库和像素级界面创建的 UI 设计专家。创建美观、一致、无障碍的用户界面，增强用户体验并体现品牌形象。
- UI 视觉验收设计师: 依据设计契约对照线上界面逐项验收，在发布前拦截通用、雷同的界面，输出整改清单。
- Unity 编辑器工具开发者: Unity 编辑器自动化专家——精通自定义 EditorWindow、PropertyDrawer、AssetPostprocessor、ScriptedImporter 和管线自动化，每周为团队节省数小时。
- Unity 多人游戏工程师: Unity 联网游戏专家——精通 Netcode for GameObjects、Unity Gaming Services（Relay/Lobby）、客户端-服务端权威、延迟补偿和状态同步。
- Unity 架构师: 数据驱动模块化专家——精通 ScriptableObject、解耦系统和单一职责组件设计，面向可扩展的 Unity 项目。
- Unity Shader Graph 美术师: 视觉效果与材质专家——精通 Unity Shader Graph、HLSL、URP/HDRP 渲染管线与自定义渲染 Pass，打造实时视觉效果。
- Unreal 多人游戏架构师: Unreal Engine 网络专家——精通 Actor 复制、GameMode/GameState 架构、服务端权威玩法、网络预测和 UE5 专用服务器配置。
- Unreal 技术美术: Unreal Engine 视觉管线专家——精通材质编辑器、Niagara 特效、程序化内容、HLSL 与 Lumen GI，兼顾画质与性能预算。
- Unreal 世界构建师: 开放世界与环境专家——精通 UE5 World Partition、Landscape、程序化植被、HLOD 和大规模关卡流式加载，打造无缝开放世界体验。
- Unreal 系统工程师: 性能与混合架构专家——精通 C++/Blueprint 边界、Nanite 几何体、Lumen GI 与 Gameplay Ability System，面向 AAA 级 Unreal Engine 项目。
- USWDS 开发者: 负责用美国联邦设计系统 USWDS 开发政府网站前端，落地组件、设计令牌与无障碍模式，并接入 CMS。
- UX 架构师: 技术架构与 UX 专家，给开发者提供扎实的基础设施——CSS 体系、布局框架和清晰的实现指引。
- UX 研究员: 专精用户行为分析、可用性测试和数据驱动设计洞察的用户体验研究专家。提供可落地的研究发现，让设计决策有据可依。
- visionOS 空间工程师: 原生 visionOS 空间计算与 SwiftUI 专家，构建体积式界面和 Liquid Glass 设计，面向 Apple Vision Pro。
- Web GIS 开发工程师: 全栈 Web GIS 工程师，负责构建交互式地图应用——MapLibre GL JS、ArcGIS JS API、Leaflet、实时仪表盘、REST API 集成与地理空间 Web 服务。
- WebAssembly 工程师: 负责把 Rust、C++ 代码编译成 WebAssembly 并在浏览器运行，处理 JS 边界开销、模块拆分与性能优化。
- WordPress 购物车工程师: WordPress 电商专家工程师，专精 WooCommerce，负责商品目录管理、支付网关集成、结账流程定制、税费与优惠券配置，以及在 WordPress 上交付高转化的商店。
- WordPress 性能工程师: 负责 WordPress 站点性能优化，调缓存、BigPipe、Views 查询与 PHP-FPM 参数，让页面通过性能审计。
- X/Twitter 情报分析师: 社交情报专家，负责 X/Twitter 调研、趋势识别、账号监测，并基于公开信号与结构化数据流程产出有证据支撑的受众洞察。
- XR 沉浸式开发者: WebXR 和沉浸式技术专家，专注浏览器端 AR/VR/XR 应用开发，处理控制器映射、空间锚点与性能优化。
- XR 界面架构师: 空间交互设计师和沉浸式 UX 专家，专注设计和开发 XR 环境中符合人体工学的界面策略与交互模式。
- XR 座舱交互专家: 专注设计和开发 XR 环境中沉浸式座舱控制系统。
- ZK 管家: 秉承 Niklas Luhmann 卡片盒笔记法精神的知识库管家。默认视角为 Luhmann；按任务切换领域专家（Feynman、Munger、Ogilvie 等）。强制原子笔记、连接性和验证闭环。
- general-purpose: General-purpose agent for researching complex questions, searching for code, and executing multi-step tasks. When you are searching for a keyword or file and are not confident you will find the right match in the first few tries use this agent to perform the search for you.
- documents:visual-judge: THE single visual acceptance pass for a rendered deliverable of these types only — pptx, docx, xlsx, pdf, poster, chart; for anything else, do not use it. Use it *instead of* looking at the page images yourself, never in addition: pick one gate — spawn visual-judge, or (only if visual-judge is unavailable) inspect the images yourself — and do not pre-screen the pages before dispatching, because a preliminary look followed by a visual-judge call duplicates the same review and wastes a full render pass. Its bar is user acceptance: it judges everything the user will see on its assigned pages — visual asset quality and layout & composition — and returns one JSON verdict line per page (pass/fail + evidence-backed issues; a clean programmatic/script check is no cover and no substitute). It is read-only and edits nothing; it can only Read pre-rendered page PNGs (never pptx/docx/HTML/PDF opened as images), so render the pages to PNG, hand visual-judge the paths, and act on its verdicts — those verdicts are the visual gate's result, not an input to your own re-judging. Dispatch grouping, what to pass in, and the repair loop follow the delivery protocol's visual gate in your system prompt. (Tools: Read, Bash)

### 2.2 `zcode-agency:` 前缀清单

与 2.1 完全同名同述的另一套（前缀为插件命名空间），源清单原文重复出现，描述逐条同 2.1 对应条目。名称全文抄录：

- zcode-agency:安全工程师、zcode-agency:安全架构师、zcode-agency:百度 SEO 专家、zcode-agency:包容性视觉专家、zcode-agency:报告分发师、zcode-agency:变革管理顾问、zcode-agency:播客内容策略师、zcode-agency:簿记与财务总监、zcode-agency:财务分析师、zcode-agency:财务预测分析师、zcode-agency:财务追踪员、zcode-agency:测试结果分析师、zcode-agency:测试自动化工程师、zcode-agency:策略对决推演师、zcode-agency:产品经理（PM）、zcode-agency:程序化广告采买专家、zcode-agency:代码库入职引导工程师、zcode-agency:代码审查员、zcode-agency:代码执行者、zcode-agency:地理处理专家、zcode-agency:地理学家、zcode-agency:地图制图设计师、zcode-agency:电商运营师、zcode-agency:钉钉集成开发工程师、zcode-agency:定价分析师、zcode-agency:动态定价策略师、zcode-agency:抖音策略师、zcode-agency:短视频剪辑指导师、zcode-agency:多平台发布编排官、zcode-agency:多智能体系统架构师、zcode-agency:发票管理专家、zcode-agency:法国咨询市场专家、zcode-agency:法律文书审查专家、zcode-agency:法务合规员、zcode-agency:反馈分析师、zcode-agency:房地产经纪助手、zcode-agency:飞书集成开发工程师、zcode-agency:服装工厂规划工程师、zcode-agency:付费媒体审计师、zcode-agency:高管摘要师、zcode-agency:高级安全运营工程师、zcode-agency:高级开发者、zcode-agency:高级项目经理、zcode-agency:高考志愿填报顾问、zcode-agency:个人成长导师、zcode-agency:工具评估师、zcode-agency:工作流架构师、zcode-agency:工作流优化师、zcode-agency:工作室运营、zcode-agency:工作室制片人、zcode-agency:供应链采购策略师、zcode-agency:供应商评估专家、zcode-agency:故障响应指挥官、zcode-agency:关卡设计师、zcode-agency:广告创意策略师、zcode-agency:国际化工程师、zcode-agency:国内网络工程师、zcode-agency:国内网络架构工程师、zcode-agency:韩国商务专家、zcode-agency:合规审计师、zcode-agency:合同审查专家、zcode-agency:后端架构师、zcode-agency:会议纪要专家、zcode-agency:会议效率专家、zcode-agency:机械设计工程师、zcode-agency:基础设施运维师、zcode-agency:技术翻译专家、zcode-agency:技术顾问、zcode-agency:技术美术、zcode-agency:技术文档工程师、zcode-agency:绩效管理专家、zcode-agency:简历优化顾问、zcode-agency:鉴定评估师、zcode-agency:解决方案工程师、zcode-agency:金融风控分析师、zcode-agency:经济系统设计师、zcode-agency:酒店宾客服务专家、zcode-agency:开发者布道师、zcode-agency:开发者工具工程师、zcode-agency:开发者社区建设专家、zcode-agency:开发者体验工程师、zcode-agency:客服响应者、zcode-agency:客户成功经理、zcode-agency:客户服务、zcode-agency:客户拓展策略师、zcode-agency:空间数据工程师、zcode-agency:空间数据科学家、zcode-agency:库存预测专家、zcode-agency:跨境电商运营专家、zcode-agency:快手策略师、zcode-agency:快速原型师、zcode-agency:老年照护顾问、zcode-agency:历史学家、zcode-agency:零售退货专家、zcode-agency:留学规划顾问、zcode-agency:旅行规划师、zcode-agency:律所计费与工时专家、zcode-agency:律所客户接案专家、zcode-agency:轮播图增长引擎、zcode-agency:密钥与凭据治理工程师、zcode-agency:模型 QA 专家、zcode-agency:幕僚长、zcode-agency:幕僚长（Chief of Staff）、zcode-agency:内容创作者、zcode-agency:品牌守护者、zcode-agency:平台工程师、zcode-agency:企业风险评估师、zcode-agency:企业培训课程设计师、zcode-agency:前端开发者、zcode-agency:嵌入式 Linux 驱动工程师、zcode-agency:嵌入式测试工程师、zcode-agency:嵌入式固件工程师、zcode-agency:区块链安全审计师、zcode-agency:趋势研究员、zcode-agency:趣味注入师、zcode-agency:全球播客策略师、zcode-agency:人才获取专家、zcode-agency:人类学家、zcode-agency:软件架构师、zcode-agency:三维场景开发者、zcode-agency:商业战略家、zcode-agency:上位机工程师、zcode-agency:社交广告策略师、zcode-agency:社交媒体策略师、zcode-agency:身份图谱操作员、zcode-agency:身份信任架构师、zcode-agency:身份与访问管理工程师、zcode-agency:渗透测试员、zcode-agency:实时协作工程师、zcode-agency:实验追踪员、zcode-agency:事件响应专家、zcode-agency:视觉叙事师、zcode-agency:视频流工程师、zcode-agency:视频提示词工程师、zcode-agency:视频优化专家、zcode-agency:首席财务官（CFO）、zcode-agency:首席产品官（CPO）、zcode-agency:首席技术官（CTO）、zcode-agency:首席营销官（CMO）、zcode-agency:首席运营官（COO）、zcode-agency:首席执行官（CEO）、zcode-agency:售前工程师、zcode-agency:数据分析师、zcode-agency:数据工程师、zcode-agency:数据可视化工程师、zcode-agency:数据库可靠性工程师、zcode-agency:数据库优化师、zcode-agency:数据隐私官、zcode-agency:数据整合师、zcode-agency:税务策略师、zcode-agency:私域流量运营师、zcode-agency:搜索词分析师、zcode-agency:搜索相关性工程师、zcode-agency:搜索增长编排器、zcode-agency:提示词工程师、zcode-agency:通用文档编译器架构师、zcode-agency:统计学家、zcode-agency:投标策略师、zcode-agency:投资研究员、zcode-agency:图书联合作者、zcode-agency:图像提示词工程师、zcode-agency:土木工程师、zcode-agency:网络工程师、zcode-agency:威胁检测工程师（安全运营）、zcode-agency:威胁检测工程师（工程侧）、zcode-agency:威胁情报分析师、zcode-agency:微博运营策略师、zcode-agency:微信公众号管理、zcode-agency:微信公众号运营、zcode-agency:微信视频号运营策略师、zcode-agency:微信小程序开发者、zcode-agency:文档生成器、zcode-agency:文化智能策略师、zcode-agency:无人机实景测绘专家、zcode-agency:无障碍合规工程师、zcode-agency:无障碍审核员、zcode-agency:物联网设备工程师、zcode-agency:物流路线优化师、zcode-agency:现实检验者、zcode-agency:香港股市合规审查专家、zcode-agency:项目牧羊人、zcode-agency:销售教练、zcode-agency:销售数据提取师、zcode-agency:销售拓展专员、zcode-agency:小红书运营专家、zcode-agency:小红书专家、zcode-agency:心理学家、zcode-agency:新闻情报官、zcode-agency:信贷经理助手、zcode-agency:行为助推引擎、zcode-agency:性能基准师、zcode-agency:叙事设计师、zcode-agency:叙事学家、zcode-agency:学习规划师、zcode-agency:循证医学研究员、zcode-agency:研究证据综合专家、zcode-agency:养殖档案核对员、zcode-agency:医疗创新战略顾问、zcode-agency:医疗健康营销合规师、zcode-agency:医疗客服专家、zcode-agency:医疗系统治理顾问、zcode-agency:医疗账单与编码专员、zcode-agency:移动发布工程师、zcode-agency:移动应用开发者、zcode-agency:遗留系统工程师、zcode-agency:隐私工程师、zcode-agency:应付账款智能体、zcode-agency:应用安全工程师、zcode-agency:应用商店优化师、zcode-agency:赢单策略师、zcode-agency:邮件营销策略师、zcode-agency:邮件智能工程师、zcode-agency:游戏设计师、zcode-agency:游戏音频工程师、zcode-agency:语言翻译专家、zcode-agency:语音 AI 集成工程师、zcode-agency:云安全架构师、zcode-agency:运营经理、zcode-agency:增长黑客、zcode-agency:招聘运营专家、zcode-agency:招聘专家（HR 全流程）、zcode-agency:证据收集者、zcode-agency:政务数字化售前顾问、zcode-agency:支付计费工程师、zcode-agency:知乎策略师、zcode-agency:知识付费产品策划师、zcode-agency:知识图谱工程师、zcode-agency:直播电商主播教练、zcode-agency:制度文件撰写专家、zcode-agency:智能搜索优化师、zcode-agency:智能体编排者、zcode-agency:中国电商运营专家、zcode-agency:中国市场本地化策略师、zcode-agency:终端集成专家、zcode-agency:专注音乐架构师、zcode-agency:追踪与归因专家、zcode-agency:桌面应用工程师、zcode-agency:资助申请撰稿人、zcode-agency:自动化治理架构师、zcode-agency:自主优化架构师、zcode-agency:总体规划架构师、zcode-agency:组织心理学家、zcode-agency:最小变更工程师、zcode-agency:AEO 基础架构师、zcode-agency:AI 工程师、zcode-agency:AI 生成代码安全审计师、zcode-agency:AI 数据修复工程师、zcode-agency:AI 引文策略师、zcode-agency:AI 治理政策专家、zcode-agency:API 测试员、zcode-agency:API 平台工程师、zcode-agency:ATS 简历校验架构师、zcode-agency:B站内容策略师、zcode-agency:B站内容运营专家、zcode-agency:BIM/GIS 专家、zcode-agency:Blender 插件工程师、zcode-agency:CMS 开发者、zcode-agency:DevOps 自动化师、zcode-agency:Discovery 教练、zcode-agency:Drupal 购物车工程师、zcode-agency:Drupal 性能工程师、zcode-agency:ESG 与可持续发展官、zcode-agency:FedRAMP 与 RMF 合规工程师、zcode-agency:Filament 优化专家、zcode-agency:FinOps 工程师、zcode-agency:FP&A 分析师、zcode-agency:FPGA/ASIC 数字设计工程师、zcode-agency:GaussDB 专家工程师、zcode-agency:GeoAI/ML 工程师、zcode-agency:GIS 分析师、zcode-agency:GIS 质检工程师、zcode-agency:Git 工作流大师、zcode-agency:Godot 多人游戏工程师、zcode-agency:Godot 游戏脚本开发者、zcode-agency:Godot Shader 开发者、zcode-agency:HR 入职管理专家、zcode-agency:Instagram 策展师、zcode-agency:IoT 方案架构师、zcode-agency:IT 服务经理、zcode-agency:Jira工作流管家、zcode-agency:LinkedIn 内容创作专家、zcode-agency:LLM 后训练工程师、zcode-agency:LSP 索引工程师、zcode-agency:M&A 整合经理、zcode-agency:macOS Metal 空间工程师、zcode-agency:MCP 构建器、zcode-agency:Offer 与 Lead Gen 策略师、zcode-agency:OrgScript 工程师、zcode-agency:Outbound 策略师、zcode-agency:PDF 引擎架构师、zcode-agency:Persona 走查专家、zcode-agency:Pipeline 分析师、zcode-agency:PPC 竞价策略师、zcode-agency:PR 与传播经理、zcode-agency:Prompt 工程师、zcode-agency:RAG 管线工程师、zcode-agency:Reddit 社区运营、zcode-agency:Roblox 体验设计师、zcode-agency:Roblox 系统脚本工程师、zcode-agency:Roblox 虚拟形象创作者、zcode-agency:Rust 重构工程师、zcode-agency:Salesforce 架构师、zcode-agency:SEO专家、zcode-agency:ServiceNow 平台导师、zcode-agency:Solidity 智能合约工程师、zcode-agency:Sprint 排序师、zcode-agency:SRE (站点可靠性工程师)、zcode-agency:TikTok 策略师、zcode-agency:Twitter 互动官、zcode-agency:UI 设计师、zcode-agency:UI 视觉验收设计师、zcode-agency:Unity 编辑器工具开发者、zcode-agency:Unity 多人游戏工程师、zcode-agency:Unity 架构师、zcode-agency:Unity Shader Graph 美术师、zcode-agency:Unreal 多人游戏架构师、zcode-agency:Unreal 技术美术、zcode-agency:Unreal 世界构建师、zcode-agency:Unreal 系统工程师、zcode-agency:USWDS 开发者、zcode-agency:UX 架构师、zcode-agency:UX 研究员、zcode-agency:visionOS 空间工程师、zcode-agency:Web GIS 开发工程师、zcode-agency:WebAssembly 工程师、zcode-agency:WordPress 购物车工程师、zcode-agency:WordPress 性能工程师、zcode-agency:X/Twitter 情报分析师、zcode-agency:XR 沉浸式开发者、zcode-agency:XR 界面架构师、zcode-agency:XR 座舱交互专家、zcode-agency:ZK 管家

## 3. 本轮将逐字使用的专家（AA1、AA2、AA3、抽检为四个不同专家）

代码审查员（T1）、代码库入职引导工程师（T2）、后端架构师（T3）、软件架构师（T4）、总体规划架构师（T5）、证据收集者（AA1）、遗留系统工程师（AA2）、首席技术官（CTO）（T9）、LSP 索引工程师（T10）、策略对决推演师（AA3）、现实检验者（三级抽检）。名字均取自第 2 节清单原文。

## 4. 基线读法

产品代码一律按基线提交 7e2d31c 读：`git show 7e2d31c:<路径>`，或 `git archive 7e2d31c` 导出到 `tempfile.mkdtemp()` 新建的空目录（已导出，路径不写入任何交付物）。不读工作区里的产品文件。例外：`design/proposals/engineering-refactor.md` 按 T9 要求读工作区版（含未提交的待定项）。

## 5. 开工前累计用量（`python tools/acceptance/zcode_tokens.py`，T0 时刻）

```
请求 5438 | 输入 822.06M（其中缓存读 788.45M）| 输出 6.38M | 本地口径 828.44M | 供应商口径 828.44M
```

**口径说明**：这是本机所有会话的项目历史累计，不是本轮消耗。第 11 节闸门命令本身要求 `--since "<T0 的本地时间>"` 跑，故「已用」阈值按本轮自 T0 起的增量评估；此解释如与验收人理解不一致，以验收人裁定为准（写进偏离声明）。

## 6. 第一轮证据文件开工时 SHA-256（T1 依据，按 yaml notes 记录）

```
d0c5e959bdeeffdcf2fc95992904a279bd74326713aa3d216b84c0ad9b11641c  README.md
ba35a4c4971bb6b70d08a7c45a4df8b638fd9b4ab445684df198264d3c62a70b  state-trace.md
df580581a55e662b547ccf05b9e744de801c2edf4037acee6234f663e45ce4fc  ui-states.md
6732eb61a99d4c4b700b09aaf91fc492f8d31c87baeb652129844b1128cefd08  code-issues.md
b12d041e9ec2dc65cb10a4250924a698b1f770db131adb9ba90e97ac1459816d  inventory.md
```

## 7. 目录映射（yaml 目标 → 本轮实际落点）

yaml 的产出目标在 redo/ 根；按总目标「只准写 redo/zcode/」，整体移入子目录：

| yaml 目标 | 本轮落点 |
|---|---|
| redo/scripts/verify_cites.py | redo/zcode/plan/scripts/verify_cites.py |
| redo/README.md | redo/zcode/README.md |
| redo/{desktop,phone,rules,grab,prereq}.md 与同名 .cites.jsonl | redo/zcode/plan/ 同名 |
| redo/scripts/{phone_model_fields.mjs,esc_sites.mjs,grab_outputs.py} | redo/zcode/plan/scripts/ 同名 |
| redo/reconcile.md | redo/zcode/plan/reconcile.md |
| redo/audit/{aa1-facts.md,aa2-omissions.md} | redo/zcode/plan/audit/{AA1.md,AA2.md} |
| redo/audit/response.md（T7） | redo/zcode/plan/fix-round.md |
| .claude/results/20261113-refactor-audit-redo-result.yaml | .claude/results/20261113-zcode-full/SUMMARY.md（外加 PROGRESS/agents/BACKLOG） |
| （计划外增量：T9、T10、AA3、攻防辩、三级抽检、T8） | redo/zcode/extra/** |

## 8. 收工核对（2026-11-12 14:55 CT）

`git log --oneline -3`：

```
7e2d31c fix(component): 导入装好后收掉旧的下载失败
e0054c4 docs(proposals): 前端采用 ES Modules 并留样机
5d95f34 docs(proposals): 工程化重构提案
```

`git status --short`：

```
 M design/proposals/engineering-refactor.md
?? design/evidence/2026-11-12/esm-verify/
?? design/evidence/2026-11-12/refactor-audit/
```

与开工完全一致：零提交、零范围外改动。最终额度读数（本轮自 T0）：113.49M（请求 805）。
