# Viva — 方案细化（Airwallex PS1 "Getting Good"）

> 状态：**主方案**（团队 29 Sep 2026 决定）。本文件是方案的单一事实来源，幻灯片与 demo 以此为准。
> 一句话（pitch line）：**"AI can do the work. Only you can defend it."**
> 定位：一道嵌在交付流程里的"答辩关"。用 AI 完成任务后，想交付就要能端到端讲清楚；追问按任务的能力类型定制；答辩记录自动变成团队本来就要写的文档。

---

## 1. 问题

**官方书面题目（原文）：** "Every expert got good the same way: doing small, low-stakes work badly, over and over, with someone correcting them. Those are precisely the tasks that are being automated first… Design how a person becomes genuinely good at something when the beginner version of their work is already solved."

**我们对问题的界定：**
- 入门级工作（小 bug 修复、初稿、手搭模型）原本是"判断力被安装进人脑"的地方（briefing: "it was where judgment got installed"）。AI 接管后，新人**交付得更多，理解得更少**，也就是 briefing 说的 "You've shipped something you didn't fully understand"。
- 5 年后的风险：AI 写的东西出了问题（讲者举例：每天损失上百万的 bug），团队里没人能讲清它为什么这样工作、错在哪、怎么修。
- 我们把这种"已上线但没有任何人能解释的产出"称为 **comprehension debt（理解负债）**。它和技术债一样会积累，而且出事时才暴露。
- 招聘端的佐证：Stanford Digital Economy Lab（2026 年 8 月更新，美国 ADP 薪资数据）显示，22–25 岁、处在 AI 高暴露职业的员工，就业水平比同龄低暴露职业的趋势**低约 19%**（2022.11–2026.06），主要通过**减少招聘年轻人**实现，而不是裁员。作者强调这是描述性结果，不是因果结论。
- 健身房类比（Airwallex 讲者认可）：AI 替你举铁，任务完成了，肌肉没长。

**现有做法为什么不够：**
- 课程、导师：题目明确不要，而且脱离真实工作。
- 少用 AI、禁用 AI：题目明确不要，也违背公司的效率动机。
- Code review：审的是代码，不是人有没有懂；AI 让 PR 数量暴涨，reviewer 只能粗看。
- 高校的书面考试：一样可以被 AI 代写。

---

## 2. 目标用户

| 角色 | 是谁 | 他们要什么 |
|---|---|---|
| **使用者（主）** | 入职 0–3 年、日常用 AI 干活的初级工程师和分析师 | 继续用 AI 提速；同时真的变强，不在第一次出事时露馅 |
| **买单者** | 工程经理、合规或运营负责人 | 可交付的速度；可控的风险；能证明"人在环中"是真实的 |
| **切入场景（beachhead）** | Fintech：支付工程（跨境汇率、手续费、清结算代码）和合规运营（AML 告警处置） | 涉及资金的变更要"有人真的懂"，否则出事代价极高 |
| **次要市场** | 高校（口试式评估） | 在 AI 时代"确认学生真的学会了" |

**Persona（用于 demo）：** Mia，某支付公司入职 4 个月的 graduate engineer。用 AI 一天交付的 PR 比前辈当年一周还多，但第一次值班遇到汇率舍入事故时讲不出问题出在哪。

---

## 3. 方案如何满足题目的硬约束

| 题目约束（briefing 原话） | Viva 的做法 |
|---|---|
| 拖慢学习者就有代价（grade / deadline / output） | 答辩 3–5 分钟，而且**答辩记录自动生成 PR 描述、决策记录或审计备注**，替代原本要手写的文档；按风险抽样触发，而不是每件事都答辩 |
| 只有自律的人才接受的麻烦是筛子（filters for people who could already afford to go slower） | 这是**交付关卡**，由团队统一设置，人人适用，不靠个人自觉；支持母语和文字作答，不偏向口才好或英语好的人 |
| 不要课程、不要导师 | Viva 不教任何东西，只是一道关加一面镜子；学习发生在准备答辩的过程中，用什么工具准备都行 |
| 不要"少用 AI"的理由 | 任务阶段随便用 AI，准备答辩时也可以让 AI 给你讲懂；我们只要求你**最终自己懂** |
| 让捷径感觉像损失（make the shortcut feel like the loss） | 没搞懂就过不了关，交不了付；反过来，越懂的人被抽到答辩的频率越低（类似学车从 L 牌到 P 牌），**懂 = 更快** |
| 书面题：doing it badly, with someone correcting them | 答不上来不扣分，而是得到一份具体的"理解缺口报告"，搞懂后重答，这就是新时代的"被纠正" |

---

## 4. 产品如何运作

### 4.1 总流程

```
用 AI 完成任务 ──► 提交（PR / 决策 / 报告）
                      │
                      ▼
            [触发判断] 风险 × 个人等级 × 抽样
                      │ 需要答辩
                      ▼
 ① 读入产出 ─► ② 能力分类 ─► ③ 生成追问（沙箱预算标准答案）
                                          │
                                          ▼
                           ④ 答辩 3–5 分钟（文字/语音，自适应追问）
                                          │
                                          ▼
                           ⑤ 评分（理解层级 + 执行验证 + 逻辑闭环）
                          ┌───────────────┴───────────────┐
                        通过                              有缺口
                          │                                 │
          自动生成 PR 描述 / 决策记录                  理解缺口报告
          放行交付；更新能力画像                       搞懂后重答（可用 AI 准备）
```

### 4.2 各环节细节

**① 读入（Ingest）**
- 产出本身：代码 diff、决策文档、表格或模型。
- 上下文：工单或需求描述。
- 可选：与 AI 的对话记录，用来判断哪些部分是 AI 写的，重点追问。

**② 能力分类（Capability profile）**
- 一个任务可以同时属于多种能力类型，并按权重分配，例如"构建 0.6 + 决策 0.4"。
- 分类结果决定每种能力分到几道题。

**③ 生成追问（Question planner）**
- 每道题带三个属性：考察的能力类型、追问招式、锚点（对应产出里的哪一行、哪个结论）。
- **可执行的产出（代码、模型）**：自动生成反事实输入，在沙箱里真正运行，得到标准答案。例如："目标币种换成 JPY，这个函数返回什么？"
- 不可执行的产出（决策、写作）：用逻辑闭环清单和评分细则打分（见第 5 节）。
- 每次答辩 4–6 道题，控制在 3–5 分钟。

**④ 答辩（Interview agent）**
- 文字或语音都可以（语音为加分项：STT 用 Whisper 或浏览器 Web Speech，TTS 用浏览器自带）。
- **自适应**：回答太浅就往下追一层（最多追 2 次）；回答已经很深就跳到下一题。
- 不给提示，不教学。允许说"我不知道"，诚实作答比瞎编得分高。
- 每题请作答者报一个信心值（低/中/高），用来做校准。

**⑤ 评分（Grader）**
- 评分器和提问器使用不同的 prompt，互相隔离；每个评分结论都要引用作答原文作为证据。
- 具体规则见第 5 节。

**⑥ 输出**
- **给个人**：理解缺口报告（哪里没懂，指向产出里的具体位置），加上能力画像的变化。
- **给团队**：自动生成的 PR 描述、决策记录或审计备注，内容就是作答者自己的解释。
- **给组织**：理解负债地图，显示哪些模块、哪些决策目前没有人能讲清；以及团队层面的能力分布。

### 4.3 触发策略（L 牌 → P 牌）

- **涉及资金流、高影响范围的变更**：始终需要答辩。
- **其他 AI 参与度高的变更**：按个人在该能力类型上的等级抽样。
  - 新人阶段：高比例触发。
  - 某能力类型稳定达到 L3 后：抽样比例逐级下降（具体比例由团队配置；demo 里示意为 100% → 30% → 10%）。
- 效果：证明了理解，就换来速度。不懂的人会一直被拦下来，这就是"捷径的损失"。

### 4.4 失败处理

- 第一次未通过：拿到缺口报告，去搞懂（查文档、问 AI、问同事都可以），然后重答。
- 第二次仍未通过：标记为"需要 senior 结对"，交付继续推进，但换 senior 来担保。不做任何额外惩罚。
- 作答者可以对评分提出申诉，由人工复核。

---

## 5. 能力 × 追问矩阵与评分

### 5.1 追问招式（通用）

| 招式 | 问法示例 |
|---|---|
| 复述 Walkthrough | 从输入到输出，端到端讲一遍 |
| 为什么 Justify | 为什么这样做？依据是什么？ |
| 反事实 Counterfactual | 如果 X 变了，结果会怎样？ |
| 消融 Ablation | 把这一段删掉，会发生什么？ |
| 预测 Predict | 给这个新输入，输出是什么？（可以执行验证） |
| 反驳 Challenge | AI 站在对立面："我认为方案 B 更好，因为……"你怎么回应？ |
| 迁移 Transfer | 换一个场景（另一种货币、另一类客户），还成立吗？ |

### 5.2 按能力类型的追问重点

| 能力 | 核心考察 | 典型追问 |
|---|---|---|
| **决策** | 判断依据 + 逻辑闭环 | 目标和约束是什么？考虑过哪些方案，为什么否掉？什么证据出现会让你改主意？错了最先在哪暴露？怎么回滚或止损？ |
| **构建/实现** | 端到端理解 | 数据怎么流动？删掉第 X 行会怎样？给这个输入输出是什么？边界条件在哪？ |
| **调试/诊断** | 根因 vs 症状 | 这是根因还是症状？怎么验证你的假设？日志如果是另一个样子，你下一步查什么？ |
| **分析/建模** | 假设与敏感性 | 最关键的假设是什么？哪个输入变 10% 影响最大？这个量级合理吗？ |
| **审核/合规** | 风险识别 | 为什么放行或拦截？看到了哪条风险信号？还缺什么信息？ |
| **写作/沟通** | 核心论点 | 用一句话说出结论。受众是谁？删掉哪段损失最小？对方最强的反驳是什么？ |

### 5.3 理解层级（参考 SOLO taxonomy, Biggs & Collis 1982）

| 等级 | 含义 | 判定依据 |
|---|---|---|
| L0 | 答不上或答错 | — |
| L1 复述 | 能说出做了什么 | 描述正确，但说不出原因 |
| L2 解释 | 能说出为什么、各部分如何关联 | 给出因果或依据链 |
| L3 预测 | 条件变化时能正确预测 | 反事实或预测题答对（可执行的以沙箱结果为准） |
| L4 迁移 | 能指出边界、失败模式，或迁移到新场景 | 主动说出边界，或在迁移题上正确 |

**通过线（demo 默认，可配置）：**
- 每个被考察的能力类型至少达到 L2；
- 关键路径上至少有一道题达到 L3；
- 涉及资金的变更，执行验证类题目必须答对。

### 5.4 决策类的逻辑闭环清单（7 项）

1. 目标
2. 约束
3. 备选方案
4. 取舍理由
5. 证据
6. 证伪条件（什么情况下我会改主意）
7. 回滚或止损

评分器逐项判断是否具备，并检查各项之间能否串成链：结论要能由证据推出，证伪条件要和证据对应。

### 5.5 其他信号
- **一致性**：前后回答是否自相矛盾。
- **信心校准**：高信心却答错，会单独标出来。这类人最危险，也最需要被纠正。

---

## 6. 防 AI 代答（诚实版）

1. **锚定具体细节**：问题指向这一份产出的具体行和具体结论，通用答案答不上。
2. **现场反事实**：反事实输入是答辩时临时生成的，标准答案由沙箱实时算出，没有可背的答案。
3. **自适应追问**：浅答会触发下一层追问，照念的答案很难一路撑下去。
4. **一致性和信心校准**：代答往往前后不一致，或者信心和正确率对不上。
5. **激励兜底**：侥幸蒙过的人，下一次同类任务还会被抽到；能力画像的波动会暴露问题；出事时答辩记录可以追溯。

**要承认的局限：** 实时提词类作弊工具已经存在，我们无法百分之百杜绝。Viva 的目标是**让作弊变得不划算**，而不是不可能。准备答辩时尽管用 AI 帮你讲懂，那本身就是学习。

---

## 7. 学习科学依据

- **自我解释效应（self-explanation effect）**：让学习者解释给自己或别人听，能显著提升理解（Chi et al., 1989）。
- **检索练习或测试效应（testing effect）**：被提问、需要主动回忆，比重读更能巩固记忆（Roediger & Karpicke, 2006）。
- **SOLO 理解层级**：从复述到迁移，用于给理解深度定级（Biggs & Collis, 1982）。
- **高校已经在往口试走**：悉尼大学的 "two-lane approach" 把口试这类有监督的评估列为 secure lane；TEQSA 的 *Assessment reform for the age of artificial intelligence*（2023）也建议在课程层面设置能确认"学生真的学会"的评估。
- Viva 相当于把高校正在采用的做法，搬进职场的日常交付流程。

---

## 8. 技术架构

| 层 | 选型（黑客松版） | 说明 |
|---|---|---|
| 前端 | Next.js / React | 任务页、答辩对话页（文字 + 麦克风）、结果与缺口报告页、经理仪表盘 |
| 后端 | FastAPI（Python） | 编排整条流程 |
| LLM | Claude API（4 个角色分别用独立 prompt） | Classifier → Planner → Interviewer → Grader，评分器看不到提问器的内部提示 |
| 执行沙箱 | Python 子进程 + 超时 + 白名单（生产环境换容器） | 对产出函数跑反事实输入，得到标准答案 |
| 语音（加分项） | Whisper / Web Speech API + 浏览器 TTS | 团队已有 Whisper 转写经验 |
| 存储 | SQLite / JSON | Task、Artifact、Viva、Question、Answer、Score、Profile |
| 集成（路线图） | GitHub App（PR status check：答辩通过前不能合并）、Jira、Slack | 黑客松阶段用模拟 PR 页面演示 |

**Question 对象示例：**
```json
{
  "capability": "build",
  "move": "predict",
  "anchor": "fx.py:L14-L22",
  "prompt": "A payout of 1,234.56 AUD to a JPY account at rate 97.3 — what exact amount does the recipient get?",
  "truth": {"type": "exec", "value": "<sandbox result>"},
  "follow_ups_max": 2
}
```

---

## 9. Demo 脚本（决赛约 3 分钟）

**任务 1（构建类，主线）：跨境付款手续费函数**
- 工单："给跨境付款加上手续费并换汇。"Mia 用 AI 几秒钟生成 `convert_with_fee()`。
- 埋下的真实问题：函数对所有币种统一保留 2 位小数，但 **JPY 在 ISO 4217 中没有小数位**（KWD 则有 3 位）；手续费先扣还是先换汇，结果也会不同；用 float 存金额，存在精度问题。

**第一幕：走捷径**
1. Mia 直接点"提交"，Viva 关卡弹出。
2. 追问一（复述）："手续费在哪一步扣？"她答得含糊。
3. 追问二（预测）："1,234.56 AUD 付到日元账户，收款人拿到的确切金额是多少？"她随口估了一个数；沙箱给出的真实输出是一个带两位小数的日元金额，这本身就是 bug。
4. 结果：未通过。缺口报告指出："没有意识到函数对所有币种统一保留 2 位小数；JPY 没有小数位。"合并被拦下。

**第二幕：真的搞懂**
1. Mia 去弄懂（可以问 AI、查 ISO 4217），发现问题并修好。
2. 重新答辩：答对预测题，还主动说出"KWD 有 3 位小数也要处理"，达到 L4 迁移。通过。
3. 系统用她自己的解释**自动生成 PR 描述**，展示出来。

**第三幕：决策类（快速展示）**
- 一条 AML 告警（合成数据）：学生账户短时间内收到多笔小额入账，随后一笔跨境转出。要上报还是关闭？
- 展示逻辑闭环清单逐项点亮，以及"什么证据会让你改主意"这道追问。

**第四幕：组织视角**
- 经理仪表盘：理解负债地图（哪些模块目前没人能讲清），以及 Mia 的能力画像随时间上升。

> 数值在 demo 里以沙箱的实际输出为准，幻灯片和旁白里不写死任何金额。

---

## 10. 3 天验证方案（成功标准）

**实验设计（周四上午，大约 1 小时）：**
- 参与者：8–10 名黑客松参赛者；另请 2–3 位 mentor 做人工评分校准。
- 任务：手续费函数任务（允许用 AI，限时 15 分钟）。
- 分组：
  - A 组"走捷径"：拿到 AI 输出后粗看 2 分钟内就提交；
  - B 组"弄懂再交"：同样可以随便用 AI，但要确保自己讲得清。
  - 随机分组。
- 所有人都参加 Viva，mentor 盲评其中一部分答辩记录。

**成功标准（团队自定的目标线）：**

| # | 要证明什么 | 指标与目标线 |
|---|---|---|
| 1 | **区分度**：关卡能拦住没懂的人 | B 组平均分明显高于 A 组；目标：A 组通过率 ≤30%，B 组 ≥70% |
| 2 | **评分可信** | 在约 20 个回答上，AI 和 mentor 的通过/不通过判定一致率 ≥80% |
| 3 | **问题质量** | mentor 评估 ≥80% 的问题属于"不懂就答不上" |
| 4 | **不增加负担** | 答辩中位时长 ≤5 分钟；自动生成的 PR 描述有 ≥2/3 的 mentor 认为可以直接使用 |
| 5 | **学习闭环** | 未通过者看完缺口报告、重答后，得分上升 |

> 注意：样本很小，只能提供**方向性证据**，不是统计意义上的证明。展示时要这样表述，反而显得可信。

---

## 11. 时间线与分工

| 时间 | 内容 |
|---|---|
| **周二 29 下午（今天）** | 锁定概念；完成 3 页 pre-screen 幻灯片；准备两个任务素材（手续费函数 + AML 告警）；写 4 个角色的 prompt 草稿；搭后端骨架 |
| **周三 30 上午** | Pre-screen。**不等结果**，直接开发 |
| **周三 30 白天到晚上** | 打通核心闭环：读入 → 追问 → 文字答辩 → 评分 → 缺口报告；接上沙箱反事实题；自动生成 PR 描述 |
| **周四 1 上午** | 跑验证实验，收集数据 |
| **周四 1 下午** | 经理仪表盘；语音（加分项）；把真实实验数据放进决赛幻灯片；排练 |

**建议分工（5 人，按各自擅长认领）：**
- R1 LLM 负责人：4 个角色的 prompt、自适应追问逻辑、评分细则。
- R2 后端：FastAPI、执行沙箱、数据模型。
- R3 前端：答辩界面、结果页、仪表盘。
- R4 内容与实验：任务素材、标准答案、招募参与者、组织 mentor 校准。
- R5 Pitch：幻灯片、demo 旁白、评委问答准备、证据资料。

---

## 12. 规模化与愿景（回应"能否走出墨尔本"）

- **不依赖本地**：纯软件，接入的是全球通用的开发和工作工具（GitHub、Jira、Slack）；支持多语言答辩，适合跨国和移民员工众多的团队。
- **领域包（domain packs）**：能力 × 追问矩阵可以按行业扩展，例如支付工程、合规运营、数据分析、法律起草、咨询建模。换一个行业只需要换领域包。
- **路线图：**
  - Phase 0（黑客松）：MVP，两个任务类型。
  - Phase 1：做成 GitHub App，在一个团队试点，作为 PR status check。
  - Phase 2：领域包 + 经理仪表盘 + 可导出的审计证据（面向受监管行业）。
  - Phase 3：**Understanding Passport**。答辩记录沉淀成可验证、可以带走的能力证明，让雇主重新敢招新人，回应题目里"公司不招毕业生就能省工资"那一环。
  - 并行：高校版，作为口试式评估工具。
- **5 年后的逻辑**：AI 做的越多，没人懂的产出就越多，理解负债越积越大。Viva 的价值随 AI 变强而**上升**，就像财务越复杂，审计越重要。
- **商业模式**：团队按席位收费的 SaaS；合规版（导出审计证据）；高校授权。

---

## 13. 评委可能的问题（English answers for the pitch）

1. **"Isn't this just more friction?"** — The viva *is* the documentation: it writes the PR description / decision record you'd otherwise write by hand. It's risk-triggered, and the more you prove you understand, the less often you're asked.
2. **"Can't people just use AI to answer?"** — Questions are anchored to your specific artifact, counterfactuals are generated live with sandbox-computed answers, and follow-ups adapt. We don't claim it's cheat-proof; we make cheating not worth it — and preparing with AI is itself learning.
3. **"Isn't this a tutor?"** — It never teaches. It's a gate and a mirror. The learning happens when you prepare, with any tool you like.
4. **"Why trust LLM grading?"** — Executable questions are graded by running the code, not by opinion. Every grade cites the answer as evidence; we calibrate against human mentors (target ≥80% agreement); humans handle appeals.
5. **"Why would a company pay?"** — Comprehension debt is an incident waiting to happen, especially where money moves. Viva gives faster onboarding, audit evidence that humans in the loop really understand, and a map of what nobody on the team can explain.
6. **"How is this different from code review?"** — Review checks the code; Viva checks the person. Reviewers are drowning in AI-generated PRs.
7. **"Doesn't it favour confident English speakers?"** — Scoring is on content, not fluency; text mode and multilingual answers are supported. This directly addresses the brief's "friction is a filter" warning.
8. **"Privacy / surveillance?"** — The capability profile belongs to the employee; managers see gate outcomes and team-level aggregates. We recommend it not be used for performance ranking. It's a real tension, and we'd rather name it.
9. **"What about work you can't execute, like decisions?"** — The 7-point decision-closure checklist plus consistency checks; the ground truth is the logic chain, not a single right answer.
10. **"Can it scale beyond Melbourne?"** — It plugs into global tools, domain packs extend it to other professions, and the passport becomes a portable signal across employers and countries.

---

## 14. 待团队拍板
- [ ] 产品名是否就用 "Viva"（备选：Defend Your Work / Walkthrough）
- [ ] Demo 主线用支付工程（手续费函数），决策类用 AML 告警。是否保留两个？
- [ ] 语音是否做（建议列为加分项）
- [ ] 分工认领

## 参考
- Stanford Digital Economy Lab, *Canaries in the Coal Mine?* August 2026 update — https://digitaleconomy.stanford.edu/news/canariesaug26/
- University of Sydney, two-lane approach — https://educational-innovation.sydney.edu.au/teaching@sydney/frequently-asked-questions-about-the-two-lane-approach-to-assessment-in-the-age-of-ai/
- TEQSA, *Assessment reform for the age of artificial intelligence* (2023) — https://www.teqsa.gov.au/guides-resources/resources/corporate-publications/assessment-reform-age-artificial-intelligence
- Chi, M. T. H. et al. (1989). Self-explanations: How students study and use examples in learning to solve problems. *Cognitive Science*.
- Roediger, H. L. & Karpicke, J. D. (2006). Test-enhanced learning. *Psychological Science*.
- Biggs, J. & Collis, K. (1982). *Evaluating the Quality of Learning: The SOLO Taxonomy*.
- 项目文档：problem-statements.md、claude/airwallex-qa.md、claude/judge-qa.md
