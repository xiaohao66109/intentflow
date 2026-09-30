export type Lesson = {
  question:string; minutes:string; concept:string; deliverable:string
  steps:string[]; ownSteps:string[]; materials:string[]; hints:string[]
  bad:string; good:string; checks:string[]; reflection:string
}
export type QuestionGrade={id:'attempt'|'evidence'|'reflection';title:string;score:number;maximum:number;status:'达到要求'|'需要补充';comment:string}
export type LearningGrade={score:number;level:string;questions:QuestionGrade[];dimensions:{name:string;score:number;comment:string}[];next:string;sourceHint:string;referencePoints:string[]}
export type LearningSample={attempt:string;evidence:string;reflection:string}
export type LearningAnswerGuide={attempt:[string,string,string];evidence:[string,string,string];reflection:[string,string,string]}
type CaseGuidance={evidenceTerms:string[];reasonTerms:string[];scopeTerms:string[];testTerms:string[];sourceHint:string;referencePoints:string[]}
export const caseGuidance:Record<string,CaseGuidance>={
 'project-context':{evidenceTerms:['居民','客服','维修人员','访谈','项目背景'],reasonTerms:['因为','因此','说明','导致'],scopeTerms:['本轮','范围','不增加','不负责','不能保证'],testTerms:['查看','显示','待确认','本人'],sourceHint:'先查看“项目背景与本轮目标”“角色职责与用户旅程”和“居民访谈记录”。',referencePoints:['识别居民、客服和维修人员的职责','指出居民看不到预计联系时间的信息缺口','区分线上信息展示与线下维修履约','明确短信、自动派单等不进入本轮','保留至少一个待确认问题']},
 'problem-evidence':{evidenceTerms:['访谈','日志','问题单','工单','测试'],reasonTerms:['因为','对照','表明','尚不能证明'],scopeTerms:['实际','期望','假设','原因'],testTerms:['复现','失败','观察','验证'],sourceHint:'先查看“问题单与复现步骤”“模拟运行日志”和“居民访谈记录”。',referencePoints:['写清当前结果与期望结果','引用访谈、日志或测试中的具体事实','把展示遗漏与未填写区分开','将未经验证的原因标为假设']},
 specification:{evidenceTerms:['业务规则','验收清单','访谈','工单'],reasonTerms:['因为','所以','对应','依据'],scopeTerms:['已填写','未填写','本人','其他居民','不增加'],testTerms:['当','如果','应','显示','不得'],sourceHint:'先查看“业务规则与状态约定”“需求分歧与优先级”和“验收清单与测试映射”。',referencePoints:['写出条件、操作和可观察结果','覆盖已填写与未填写两种情况','保留本人访问限制','说明本轮方案取舍']},
 'engineering-intent':{evidenceTerms:['模块职责','验收清单','业务规则','测试'],reasonTerms:['因为','所以','对应','避免'],scopeTerms:['只修改','保持','不得','兼容','权限'],testTerms:['文件','测试','验证','断言'],sourceHint:'先查看“模块职责与修改边界”和“验收清单与测试映射”。',referencePoints:['把需求对应到居民详情读取位置','说明为什么只修改展示模块','列出权限、状态和旧数据保护行为','给出对应测试方法']},
 'software-change':{evidenceTerms:['代码差异','测试','提交','设计'],reasonTerms:['因为','对应','实现','保持'],scopeTerms:['只修改','未修改','范围','无关'],testTerms:['测试','断言','提交','版本'],sourceHint:'对照代码差异、工程设计和验收测试再作答。',referencePoints:['解释关键代码变化','确认修改没有越过设计范围','说明新增或更新的测试','固定可复验的代码版本']},
 verification:{evidenceTerms:['测试','断言','输出','提交'],reasonTerms:['因为','失败','原因','定位'],scopeTerms:['已覆盖','未覆盖','风险','环境'],testTerms:['预期','实际','通过','复验'],sourceHint:'查看逐项测试结果，并把失败位置对应到验收标准。',referencePoints:['说明测试对应的代码版本','区分未运行、失败和通过','解释至少一个失败的预期与实际','指出尚未覆盖的风险']},
 'runtime-outcome':{evidenceTerms:['指标','工单','回放','观察'],reasonTerms:['因为','相比','说明','不能证明'],scopeTerms:['口径','样本','周期','限制'],testTerms:['变更前','变更后','分母','数据来源'],sourceHint:'查看“效果评估口径与后续观察”和前后工单回放结果。',referencePoints:['定义指标口径和数据来源','用相同样本比较前后结果','区分测试通过与真实使用效果','根据证据强度选择下一步']},
 'next-change':{evidenceTerms:['访谈','需求','修改','测试','回放'],reasonTerms:['因为','改变','修正','下一轮'],scopeTerms:['新问题','未知','风险','不直接套用'],testTerms:['计划','收集','验证','验收'],sourceHint:'回看本轮追溯记录和“下一轮变更请求”。',referencePoints:['串联问题到效果的证据链','解释一次判断修正','指出仍未知的内容','为下一轮制定独立验证计划']},
}
export const studentLessons:Record<string,Lesson> = {
 'project-context':{
  question:'谁在什么场景下遇到了问题？本轮不解决什么？',minutes:'15–25 分钟',
  concept:'系统边界是本轮承担的责任范围。先理解使用者与业务，再讨论功能。',
  deliverable:'用户、现有流程、本轮范围，以及至少一个待确认问题。',
  steps:['先读项目背景，再读角色职责与居民访谈。','用自己的话记录用户、困扰和本轮边界。','打开项目理解草稿，对照材料修改并逐项核对。'],
  ownSteps:['选择一个能接触到真实使用者的小问题；第一轮只做一条业务流程。','整理一次访谈或一条实际记录，通过“添加原始证据”保存来源。','写明用户、现有流程、要改什么和暂不改什么，再填写项目理解。'],
  materials:['项目背景与本轮目标','角色职责与用户旅程','居民访谈记录'],
  hints:['先找出“谁、何时、做什么、卡在哪里”，不要急着列功能。','分别写“系统负责……”和“本轮不负责……”，检查是否混入未经确认的承诺。'],
  bad:'做一个功能齐全的物业平台，让大家满意。',good:'本轮让居民查看自己报修单的联系安排；不增加短信，也不保证维修人员一小时内上门。',
  checks:['能指出主要使用者和材料来源','能说明本轮包含与不包含的范围','能区分已知事实和待确认问题'],reflection:'为什么不能把用户提出的所有愿望都直接列入本轮范围？'
 },
 'problem-evidence':{
  question:'这是有证据的问题，还是我们对原因的猜测？',minutes:'20–30 分钟',
  concept:'事实是可核对的观察，观点是人的判断，推断需要进一步验证。',deliverable:'问题陈述、支持证据、影响，以及尚未证实的原因。',
  steps:['阅读问题单、日志和访谈，分别找出事实与推断。','预测初始测试会在哪里失败，再运行初始版本测试。','比较输出与预测，形成有来源的问题分析。'],
  ownSteps:['收集可复现步骤、日志、截图说明或访谈原话，注明时间和来源。','写出当前结果与期望结果；列一个原因假设和验证方法。','先复现或补充证据，再确认问题，不把猜测写成事实。'],
  materials:['问题单与复现步骤','模拟运行日志','居民访谈记录'],hints:['“居民说不知道何时联系”不等于“维修人员没有填写”。','对照填写记录与居民详情，判断问题发生在采集、保存还是展示环节。'],
  bad:'维修人员效率低，所以要自动承诺一小时上门。',good:'访谈反映居民看不到联系安排；需对照已填写工单与详情输出，确认是否为展示遗漏。',
  checks:['每个关键判断能对应具体证据','写清实际与期望的差距','未验证的原因已标为假设'],reflection:'哪一条新证据会让你改变当前的问题判断？'
 },
 specification:{
  question:'别人怎样判断这个需求确实实现了？',minutes:'25–40 分钟',
  concept:'验收标准必须包含条件、操作和可观察结果；原型用于澄清需求，不证明代码正确。',deliverable:'可验收需求、正常与例外场景，以及范围取舍理由。',
  steps:['先写一条验收标准，再核对并确认需求草稿。','按报修带练逐步切换居民、客服、维修人员，比较预测与结果。','补充越权和漏填场景，记录方案取舍，再进入工程设计。'],
  ownSteps:['用“在……条件下，用户……，系统应……”写一条核心需求。','为同一需求设计正常、边界、非法输入或越权场景；可以使用纸面原型或实际应用。','记录预期与实际的差异，修改含糊规则并说明本轮不做的内容。'],
  materials:['业务规则与状态约定','需求分歧与优先级','验收清单与测试映射'],hints:['把“更方便”“更快”“更安全”换成可以观察或测量的行为。','分别考虑已填写、未填写、无权查看、工单已结束这四种条件。'],
  bad:'报修详情应友好地显示联系时间。',good:'已派单且填写了联系时间时，本人查看详情可见预计时间；未填写时显示“待填写”，其他居民不可读取。',
  checks:['验收结果可以明确判定','体验了正常与至少一种例外','范围冲突有明确取舍及理由'],reflection:'原型符合需求，为什么仍然需要测试实际代码？'
 },
 'engineering-intent':{
  question:'怎样用尽量小的修改实现需求，同时保护已有行为？',minutes:'20–30 分钟',
  concept:'设计把需求连接到模块责任与实现位置。保护行为是这次修改不能破坏的约定。',deliverable:'需求到模块、修改位置和测试的对应关系，以及设计取舍。',
  steps:['对照模块职责，定位居民详情展示的实现位置。','解释为什么只修改 readmodel.py，并列出必须保留的权限和状态行为。','核对设计草稿中的文件范围、测试命令和验收依据。'],
  ownSteps:['找到承载核心业务的入口、数据处理和展示模块，画出一条调用路径。','把每条需求对应到拟修改的位置、理由和验证方法。','比较至少两个实现方案，写清允许范围、保护范围和风险。'],
  materials:['模块职责与修改边界','业务规则与状态约定','验收清单与测试映射'],hints:['先问“这个信息已经保存了吗”，再决定改数据层还是展示层。','逐项检查身份权限、状态流转、旧数据兼容，说明为什么不能改变。'],
  bad:'重写整个模块，测试以后再考虑。',good:'在居民详情读取处补充联系时间；保持本人访问限制和终态逻辑，用权限、状态与展示验收测试复验。',
  checks:['每项修改能追溯到需求','保护行为有业务理由','解释了所选方案与替代方案的取舍'],reflection:'如果把修改放到另一个模块，会增加什么耦合或风险？'
 },
 'software-change':{
  question:'这次代码差异是否只实现了约定的需求？',minutes:'25–45 分钟',
  concept:'先记录修改前可比较的版本；提交记录把实现与验证固定在同一份代码上。',deliverable:'可审阅的代码差异、对应测试，以及修改前后的代码版本。',
  steps:['先记录修改前版本，再查看参考修改。','逐行解释状态判断、字段读取和旧数据处理，不直接跳过审阅。','应用已审阅修改或自行实现；随后进入验证检查实际结果。'],
  ownSteps:['连接本地版本库，提交一个可运行的初始版本，再记录修改前的代码版本。','在开发工具中按设计实现最小修改，同时补充验收测试。','检查代码变化，提交修改与测试，然后回到平台验证该版本。'],
  materials:['模块职责与修改边界','验收清单与测试映射'],hints:['先用自己的话解释新增条件会允许和阻止哪些情况。','代码能运行不代表差异正确：检查是否误改权限、测试断言或无关文件。'],
  bad:'顺手修改多个无关模块，最后只提交了业务代码。',good:'提交展示逻辑和验收测试；对照差异确认未改权限与流转规则，记录提交编号供复验。',
  checks:['能解释关键代码差异','修改没有越过设计范围','代码与测试已一起提交'],reflection:'为什么验证未提交的工作目录，不能替代验证一个确定的提交？'
 },
 verification:{
  question:'失败是实现错误、需求含糊，还是测试假设不成立？',minutes:'20–35 分钟',
  concept:'测试通过只支持已测试的行为。失败、未运行、未知和旧版本结果必须分别处理。',deliverable:'当前提交的测试结果、失败原因分析与修复后的复验。',
  steps:['确保参考修改已应用并提交，再执行确定性验证。','逐项核对展示、权限和状态测试；对照初始失败说明修复依据。','有失败时记录预期、实际和原因假设，修复后重新验证。'],
  ownSteps:['为需求选择正常、边界、异常和回归测试，检查测试真的断言了验收标准。','提交代码后执行验证；失败时读第一处有效错误并定位关联需求。','区分环境错误与业务失败，修正代码或测试后重新提交、复验。'],
  materials:['验收清单与测试映射','问题单与复现步骤'],hints:['先看测试有没有运行，再看断言失败的位置和实际值。','不要删掉失败断言来获得绿色结果；检查它是否表达了已确认的需求。'],
  bad:'全部显示绿色，所以系统没有任何缺陷。',good:'本提交的展示、权限和状态测试通过；这支持已列场景，尚不能证明真实使用效果或未覆盖场景。',
  checks:['知道验证对应哪个提交','能解释一个失败及其定位方法','能指出尚未覆盖的风险'],reflection:'如果需求变了，为什么之前通过的测试结果可能不能继续使用？'
 },
 'runtime-outcome':{
  question:'代码正确之后，用户遇到的问题真的减少了吗？',minutes:'15–25 分钟',
  concept:'工程验证与使用效果是两种证据。指标比较需要相同口径、样本与观察条件。',deliverable:'指标定义、前后结果、证据限制和下一步决策。',
  steps:['通过验证后，回放同一批工单并保存运行证据。','比较前后联系时间可见数、越权读取数和终态承诺数。','解释模拟结果不能证明真实催办减少，再核对效果评估草稿。'],
  ownSteps:['选择一个直接对应用户问题的指标，并定义口径、观察周期和数据来源。','保存变更前后同口径结果；不足时明确选择继续观察。','同时查看副作用指标，基于证据选择结束、观察、调整或回退到上一版本。'],
  materials:['效果评估口径与后续观察','12 条模拟工单与字段样本'],hints:['指标要反映问题改善，例如重复询问率，而不只是新增页面数量。','明确分母、时间段和数据来源；模拟回放只证明模拟场景内的变化。'],
  bad:'测试通过，所以居民满意度提高了。',good:'同批模拟工单的联系时间展示改善；真实催办率仍需按相同口径观察，暂不声称满意度提高。',
  checks:['指标有口径和来源','区分测试结果与实际效果','下一步决策与证据强度一致'],reflection:'样本量不足或观察时间太短时，你为什么可能选择继续观察？'
 },
 'next-change':{
  question:'换一个问题，不看参考答案，你能独立完成吗？',minutes:'20–30 分钟',
  concept:'复盘要解释决策如何被证据改变；迁移练习检验能否把方法用到新情境。',deliverable:'一条完整证据链、一个判断修正，以及下一轮独立计划。',
  steps:['串联访谈、需求、修改、测试和回放，指出每个结论的依据。','回顾一次预测不符，解释如何修改自己的判断。','独立调查“预计时间已过仍未联系”的新问题，先写证据需求与验收标准。'],
  ownSteps:['整理本轮“问题 → 需求 → 设计 → 修改 → 测试 → 效果”证据链。','记录一个有效决策、一个错误假设和下轮改进。','选择相似但不同的问题，独立制定收集证据、实现和验证计划。'],
  materials:['下一轮变更请求'],hints:['不要只写“我学会了”，请引用一项实际成果解释你会怎样判断。','下一轮先调查，不把案例中的答案直接套到新问题上。'],
  bad:'我完成了所有按钮，已经掌握软件工程。',good:'我能用访谈与测试区分展示缺陷和履约问题；下一轮先调查超时联系，再决定提醒机制是否必要。',
  checks:['能说明完整证据链','能解释一次判断修正','已制定不同问题的独立练习计划'],reflection:'如果没有本案例草稿，你最不确定哪一步？下一次如何补足？'
 }
}

const answerGuides:Record<string,LearningAnswerGuide>={
 'project-context':{
  attempt:['写出主要使用者，以及问题发生的业务场景。','说明当前流程中的具体困扰或信息缺口。','划定本轮负责与暂不负责的范围。'],
  evidence:['注明项目背景、角色说明或访谈材料的名称。','摘出能够直接确认的用户、流程或困扰事实。','说明这些事实如何支持本轮边界判断。'],
  reflection:['指出目前仍不清楚的角色需求或系统边界。','说明准备访谈谁或核对哪项流程。','写明什么新事实会让你调整本轮范围。'],
 },
 'problem-evidence':{
  attempt:['写出可复现条件和实际观察到的结果。','写出期望结果及其业务依据。','说明实际与期望的差距，并把原因保留为待验证假设。'],
  evidence:['注明问题单、日志、访谈或测试场景。','记录其中可直接核对的原文、数值或测试结果。','说明证据支持的是问题事实还是原因假设。'],
  reflection:['指出当前最关键但尚未证实的原因假设。','说明下一步如何对照数据、接口或页面验证。','写明哪种结果会推翻或改写当前问题判断。'],
 },
 specification:{
  attempt:['写出角色、前置状态和触发操作。','写出系统必须产生的可观察结果。','补充未填写、越权或终态等例外及本轮取舍。'],
  evidence:['注明业务规则、访谈或验收清单来源。','写出材料中与条件、权限或状态有关的明确规则。','说明该规则对应哪条验收标准。'],
  reflection:['指出仍可能产生两种理解的需求规则。','说明准备用原型或具体场景怎样澄清。','写明什么体验或测试结果会促使你修改规格。'],
 },
 'engineering-intent':{
  attempt:['把已确认需求对应到承担责任的模块或调用路径。','说明允许修改的位置及选择该方案的理由。','列出必须保护的权限、状态、兼容行为和禁止修改范围。'],
  evidence:['注明模块职责、业务规则或验收映射材料。','写出代码当前由哪个模块读取、处理或展示数据。','说明这些事实为什么支持当前修改边界。'],
  reflection:['指出设计中尚未确认的技术风险或兼容问题。','说明准备运行哪些测试或检查哪条调用路径。','写明什么结果会要求扩大范围或重新设计。'],
 },
 'software-change':{
  attempt:['指出本次实际修改的文件和关键代码位置。','说明代码变化分别实现了哪条需求与测试。','确认没有修改哪些受保护行为或无关文件。'],
  evidence:['注明代码差异、提交编号和相关测试。','写出差异中可直接看到的条件、字段或断言变化。','说明这些变化如何证明实现没有越过设计范围。'],
  reflection:['指出当前差异中仍未审清或未固定的内容。','说明准备怎样检查差异、提交和测试对应关系。','写明什么发现会要求拆分、撤回或重新修改代码。'],
 },
 verification:{
  attempt:['写出被验证的提交、测试场景和验收目标。','对照记录预期结果与实际输出。','判断结果是通过、实现错误、需求含糊还是测试假设错误。'],
  evidence:['注明测试命令、测试报告或失败断言。','写出退出状态、通过数量或首个有效错误等事实。','说明该结果支持或不支持哪条验收结论。'],
  reflection:['指出当前验证尚未覆盖的场景或风险。','说明准备补充什么测试并在哪个提交上复验。','写明什么结果会改变当前通过或失败结论。'],
 },
 'runtime-outcome':{
  attempt:['定义对应用户问题的指标、样本和观察周期。','用同一口径写出变更前后的结果。','说明可以得出的效果结论及暂时不能声称的内容。'],
  evidence:['注明工单回放、运行记录或现场数据来源。','写出样本量、分母和前后数值等可核对事实。','说明这些数据支持改善、继续观察还是回退。'],
  reflection:['指出当前数据在样本、周期或真实性方面的限制。','说明下一步准备怎样收集同口径真实数据。','写明达到什么结果才会改变继续观察的决定。'],
 },
 'next-change':{
  attempt:['串联本轮问题、需求、设计、修改、测试和效果证据。','写出一次被证据纠正的判断及纠正原因。','提出下一轮新问题，并说明先调查什么、暂不直接做什么。'],
  evidence:['注明本轮追溯记录和下一轮变更请求。','各举一项能够证明判断变化与交付结果的事实。','说明这些事实如何支持你独立处理下一轮问题。'],
  reflection:['指出脱离案例后自己最不确定的工程步骤。','为该步骤安排一次独立收集证据、实现或验证练习。','写明什么成果表示已经掌握，什么结果表示需要调整计划。'],
 },
}

export function learningAnswerGuide(stage:string):LearningAnswerGuide{
 return answerGuides[stage]||answerGuides['project-context']
}

const sampleAttempts:Record<string,string>={
 'project-context':'1. 使用者与场景：居民查看本人已经派单的报修单时，想知道维修人员何时联系。\n2. 当前困扰：联系时间已经填写，但居民详情中看不到，因此居民会重复询问。\n3. 本轮边界：解决本人查看联系安排的问题；暂不增加短信，也不承诺一小时内上门。',
 'problem-evidence':'1. 实际结果：居民查看已填写联系时间的工单时，详情仍未显示该时间。\n2. 期望及依据：业务规则要求本人能看到已填写的联系安排。\n3. 差距与假设：差距是已保存信息未显示；原因可能在接口读取或页面展示，尚不能认定维修人员未填写。',
 specification:'1. 条件与操作：本人查看已派单或处理中的报修单。\n2. 可观察结果：已填写时显示具体时间，未填写时显示“待填写”。\n3. 例外与取舍：其他居民不得读取，终态不显示联系承诺；本轮不增加短信和自动派单。',
 'engineering-intent':'1. 需求与模块：联系时间已保存，居民详情读取由 readmodel.py 负责。\n2. 修改方案：在居民详情组装处补充 contact_time，因为不需要改变数据写入。\n3. 保护边界：保持本人访问、状态流转和旧工单兼容；不修改数据库结构和派单逻辑。',
 'software-change':'1. 文件与位置：修改 readmodel.py 的居民详情返回逻辑，并更新联系时间验收测试。\n2. 需求与测试：新增状态条件和 contact_time 返回值，对应已填写、未填写及终态断言。\n3. 未改内容：没有改变访问权限、工单流转和无关模块。',
 verification:'1. 验证对象：在已提交版本上运行展示、权限、状态和旧数据测试。\n2. 预期与实际：预期十四项测试全部通过，实际输出也为十四项通过且退出状态为零。\n3. 结果判断：当前提交通过已列验收场景；这不是需求含糊或测试失败，但不能证明未覆盖场景。',
 'runtime-outcome':'1. 指标口径：用同一批十二条模拟工单，统计应显示联系时间的工单中正确显示的数量。\n2. 前后结果：变更前为零条，变更后为六条；越权读取和终态错误均为零。\n3. 结论边界：模拟场景内展示改善；暂不能声称真实催办率或满意度已经改善。',
 'next-change':'1. 本轮证据链：访谈指出信息缺口，规格定义展示规则，代码补充字段，测试与回放确认模拟场景改善。\n2. 判断修正：最初怀疑维修人员未填写，工单记录证明时间已存在，因此改判为读取展示问题。\n3. 下一轮计划：调查“预计时间已过仍未联系”的新问题，先收集超时记录，暂不直接增加提醒功能。',
}

const sampleEvidence:Record<string,string>={
 'project-context':'1. 材料来源：《项目背景与本轮目标》《角色职责与用户旅程》《居民访谈记录》。\n2. 可核对事实：居民负责提交并查看本人报修，访谈中明确表示看不到预计联系时间。\n3. 支持的判断：这些事实支持把“本人查看联系安排”列入本轮，同时不能据此承诺线下上门时间。',
 'problem-evidence':'1. 证据来源：《问题单与复现步骤》、模拟运行日志和初始版本测试。\n2. 可核对事实：工单 BX-001 已保存联系时间，但居民详情输出没有 contact_time，初始测试因此失败。\n3. 支持的判断：证据支持“已保存信息未展示”的问题事实；接口或页面谁负责遗漏仍需继续验证。',
 specification:'1. 规则来源：《业务规则与状态约定》、居民访谈和验收清单。\n2. 可核对规则：本人可以查看自己的工单，未填写时间时不得伪造具体时间，其他居民不得读取。\n3. 对应验收：这些规则分别支持已填写显示、未填写显示待填写和越权拒绝三类标准。',
 'engineering-intent':'1. 设计来源：《模块职责与修改边界》、业务规则和验收映射。\n2. 可核对事实：expected_contact 已由工单流程保存，readmodel.py 负责组装居民详情返回。\n3. 支持的边界：因此只需修改读取展示模块，并用权限、状态和旧数据测试保护现有行为。',
 'software-change':'1. 实现记录：代码差异、当前提交编号和新增的联系时间验收测试。\n2. 可核对事实：差异只在 readmodel.py 增加状态判断与 contact_time 字段，并增加对应断言。\n3. 支持的判断：这证明实现对应已确认需求，且没有修改权限、写入结构或工单流转。',
 verification:'1. 验证记录：当前提交编号、测试命令和测试报告。\n2. 可核对事实：命令退出状态为零，十四项展示、权限、状态和兼容测试全部通过。\n3. 支持的结论：结果支持当前提交满足已列验收标准，但不支持“所有未知场景都正确”。',
 'runtime-outcome':'1. 数据来源：十二条模拟工单的变更前后回放记录。\n2. 可核对事实：同一批样本中正确显示联系时间从零条变为六条，越权读取保持零次。\n3. 支持的决策：数据支持模拟场景内改善并继续观察，不足以直接宣称真实催办率下降。',
 'next-change':'1. 追溯来源：本轮访谈、规格、设计、提交、测试、回放记录和《下一轮变更请求》。\n2. 可核对事实：已保存时间未展示的判断被测试证实；真实催办改善仍没有现场数据。\n3. 支持的迁移判断：我能用证据修正判断，所以下一轮应先调查超时联系，而不是套用本轮答案直接开发。',
}

const sampleReflections:Record<string,string>={
 'project-context':'1. 目前不确定：不同角色对联系提醒的优先级是否一致。\n2. 验证方法：下一步分别访谈居民、客服和维修人员，并记录他们的实际流程。\n3. 改变判断的结果：如果实际流程与当前系统边界冲突，就重新调整本轮范围。',
 'problem-evidence':'1. 目前不确定：遗漏发生在数据保存还是详情展示。\n2. 验证方法：下一步对照已填写工单、接口返回和居民页面。\n3. 改变判断的结果：如果接口已经返回联系时间，就把问题改为前端展示缺陷。',
 specification:'1. 目前不确定：原型中的规则是否已被真实代码正确实现。\n2. 验证方法：下一步运行正常、未填写、越权和终态场景测试。\n3. 改变判断的结果：任何场景与验收标准不一致，都要修改实现或重新澄清需求。',
 'engineering-intent':'1. 目前不确定：只修改读取展示是否能够兼容旧工单。\n2. 验证方法：下一步运行权限、状态和旧数据兼容测试。\n3. 改变判断的结果：如果必须改变写入结构，就暂停实现并重新评审设计范围。',
 'software-change':'1. 目前不确定：当前差异是否只包含本次需求和对应测试。\n2. 验证方法：下一步检查提交差异、文件范围和测试对应关系，再记录提交编号。\n3. 改变判断的结果：如果差异包含无关文件，就先拆分修改再提交验证。',
 verification:'1. 目前不确定：现有测试是否覆盖全部已确认条件。\n2. 验证方法：下一步把每条验收标准逐项对应到具体测试断言。\n3. 改变判断的结果：如果需求或断言发生变化，就废弃旧结论并重新验证。',
 'runtime-outcome':'1. 目前不确定：真实催办率是否随展示改善而下降。\n2. 验证方法：下一步按统一口径和观察周期统计真实工单。\n3. 改变判断的结果：如果催办率没有下降，就不能把模拟回放改善解释为真实业务效果。',
 'next-change':'1. 目前不确定：超时联系问题是否真的需要新增提醒机制。\n2. 验证方法：下一步收集超时联系记录，并比较实际结果与期望结果。\n3. 改变判断的结果：如果证据不支持提醒机制，就不进入实现，改为继续分析其他原因。',
}

export function learningSample(stage:string):LearningSample{
 return{
  attempt:sampleAttempts[stage]||sampleAttempts['project-context'],
  evidence:sampleEvidence[stage]||sampleEvidence['project-context'],
  reflection:sampleReflections[stage]||sampleReflections['project-context'],
 }
}

export function reflectionFeedback(attempt:string,evidence:string,reflection:string):string[]{
 const feedback:string[]=[]
 if(!attempt.trim())feedback.push('先写自己的判断或操作预测，再查看提示。')
 if(/提升体验|更加友好|功能齐全|提高效率/.test(attempt)&&!/[0-9]|条件|当|如果|显示|不得|应/.test(attempt))feedback.push('目标仍较笼统，请补充条件、操作和可观察结果。')
 if(!evidence.trim())feedback.push('补充材料名称、原文或测试的预期与实际结果，让判断有依据。')
 if(!reflection.trim())feedback.push('解释结果为何符合或不符合预测，并写一个尚未确定的问题。')
 return feedback.length?feedback:['已记录判断、依据和反思。请按自查标准核对内容；系统不自动判定答案正确或已经掌握。']
}

export function gradeLearningRecord(stage:string,attempt:string,evidence:string,reflection:string,checked:number,totalChecks:number):LearningGrade{
 const guide=caseGuidance[stage]||caseGuidance['project-context']
 const combined=`${attempt} ${evidence} ${reflection}`
 const matches=(terms:string[])=>terms.filter(term=>combined.includes(term)).length
 const dimensions:LearningGrade['dimensions']=[]
 const evidenceHits=matches(guide.evidenceTerms)
 const evidenceScore=!evidence.trim()?0:Math.min(25,8+(evidence.length>=20?5:0)+Math.min(12,evidenceHits*4))
 dimensions.push({name:'证据一致性',score:evidenceScore,comment:evidenceScore>=20?'回答使用了本阶段可核对的材料证据。':`目前只匹配到 ${evidenceHits} 个案例证据点，请注明材料及其支持的判断。`})
 const reasonHits=matches(guide.reasonTerms)
 const reasonScore=!attempt.trim()||!reflection.trim()?0:Math.min(25,8+(attempt.length+reflection.length>=45?5:0)+Math.min(12,reasonHits*4))
 dimensions.push({name:'推理完整性',score:reasonScore,comment:reasonScore>=20?'说明了证据、判断和下一步之间的关系。':'不要只写结论，请说明证据为什么支持判断以及仍有哪些未知。'})
 const scopeHits=matches(guide.scopeTerms)
 const scopeScore=!attempt.trim()?0:Math.min(25,8+Math.min(17,scopeHits*5))
 dimensions.push({name:'范围控制',score:scopeScore,comment:scopeScore>=20?'回答覆盖了本阶段边界和限制。':'补充本轮包含、不包含或尚未确认的范围。'})
 const testHits=matches(guide.testTerms)
 const testScore=!attempt.trim()?0:Math.min(25,8+Math.min(17,testHits*5))
 dimensions.push({name:'可验证性',score:testScore,comment:testScore>=20?'判断包含可观察或可复验的内容。':'把抽象判断改成包含条件、操作和可观察结果的表述。'})
 const attemptObservable=[...guide.testTerms,'条件','对象','范围','显示','不得','应当'].filter(term=>attempt.includes(term)).length
 const attemptScore=!attempt.trim()?0:Math.min(35,10+(attempt.length>=30?6:0)+Math.min(12,scopeHits*3)+Math.min(7,attemptObservable*3))
 const evidenceLinks=['支持','对应','说明','表明','因此'].filter(term=>evidence.includes(term)).length
 const evidenceQuestionHits=guide.evidenceTerms.filter(term=>evidence.includes(term)).length
 const evidenceQuestionScore=!evidence.trim()?0:Math.min(30,10+(evidence.length>=25?6:0)+Math.min(10,evidenceQuestionHits*3)+Math.min(4,evidenceLinks*4))
 const reflectionSignals=['下一步','验证','观察','复验','仍不确定','如果'].filter(term=>reflection.includes(term)).length
 const reflectionReasonHits=guide.reasonTerms.filter(term=>reflection.includes(term)).length
 const reflectionScore=!reflection.trim()?0:Math.min(35,10+(reflection.length>=25?7:0)+Math.min(8,reflectionReasonHits*4)+Math.min(10,reflectionSignals*5))
 const questions:LearningGrade['questions']=[
  {id:'attempt',title:'问题一：我的判断',score:attemptScore,maximum:35,status:attemptScore>=28?'达到要求':'需要补充',comment:attemptScore>=28?'写明了对象、范围和可观察结果。':'补充发生条件、涉及对象、本轮范围和可以观察到的结果。'},
  {id:'evidence',title:'问题二：证据与判断',score:evidenceQuestionScore,maximum:30,status:evidenceQuestionScore>=24?'达到要求':'需要补充',comment:evidenceQuestionScore>=24?'材料、事实和判断之间的对应关系较清楚。':'注明材料或测试名称、看到的事实，以及它具体支持哪个判断。'},
  {id:'reflection',title:'问题三：反思与下一步',score:reflectionScore,maximum:35,status:reflectionScore>=28?'达到要求':'需要补充',comment:reflectionScore>=28?'说明了未知内容和下一步验证方法。':'写出仍不确定的内容、下一步验证方法，以及什么结果会改变判断。'},
 ]
 const score=questions.reduce((sum,item)=>sum+item.score,0)
 const level=score>=85?'优秀':score>=70?'达到要求':score>=55?'基本完成':'需要修改'
 const weakest=[...dimensions].sort((a,b)=>a.score-b.score)[0]
 const weakestQuestion=[...questions].sort((a,b)=>a.score/a.maximum-b.score/b.maximum)[0]
 const unchecked=Math.max(0,totalChecks-checked)
 const next=unchecked?`${weakestQuestion.comment} 完成后再核对剩余 ${unchecked} 项自查。`:score>=85?'记录完整。可进入下一阶段，并保留一个待验证问题。':`${weakestQuestion.title}：${weakestQuestion.comment} ${weakest.comment}`
 return{score,level,questions,dimensions,next,sourceHint:guide.sourceHint,referencePoints:guide.referencePoints}
}
