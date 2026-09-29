# Viva — 方案细化（Airwallex PS1 "Getting Good"）

> 状态：**主方案 v3**（29 Sep 2026 下午）。本文件是方案的单一事实来源，幻灯片与 demo 以此为准。版本记录见 docs/README.md。
> 一句话（pitch line）：**"AI took the reps. Viva gives them back — inside the work you already do."**
> 副标题：**"AI can do the work. Only you can defend it."**
> 定位：**不是又一道 PR 测验关，而是一台"练习引擎"。** 每一次用 AI 完成的任务都变成一次"先做、做砸、被纠正"的练习：先预测、由真实运行结果揭晓，senior 花 30 秒纠正，几天后换个任务再问一次，能力画像随时间上升。答辩记录自动变成团队本来就要写的文档。
> 对比竞品的一句话：**"Other tools ask: did you read this PR? We ask: are you getting better?"**
>
> **v3 相对 v2 的变化：** 采用团队提出的主干流程（风险 × 新颖度 × 熟练度决定是否答辩，答辩聚焦决策，通过就减少人工审核）；触发改为三因素评分加硬规则，分四档（4.3）；答辩定名为 **Decision Defense**，每次 2–3 道题：解释决策、选择证据、应对一个条件变化（4.2 ③④）；未通过先让本人重答一次，再把具体风险交给 senior（4.4）；demo、数据模型、评委问答同步更新。
>
> **v2 相对 v1 的变化：** 在第 1 节末加入竞品与定位；流程从直线改为四个循环（4.1、4.5–4.7）；demo 脚本按"先预测再揭晓"和"senior 纠正"重写（第 9 节）；补充语音、录音与数据安全（4.2 ④、8、13）；新增待拍板项（14）。详细调研见 docs/research/viva-competitors-voice-privacy.md。

---

## 1. 问题

**官方书面题目（原文）：** "Every expert got good the same way: doing small, low-stakes work badly, over and over, with someone correcting them. Those are precisely the tasks that are being automated first… Design how a person becomes genuinely good at something when the beginner version of their work is already solved."

**我们对问题的界定：**
- 入门级工作（小 bug 修复、初稿、手搭模型）原本是"判断力被安装进人脑"的地方（briefing: "it was where judgment got installed"）。AI 接管后，新人**交付得更多，理解得更少**，也就是 briefing 说的 "You've shipped something you didn't fully understand"。
- 5 年后的风险：AI 写的东西出了问题（讲者举例：每天损失上百万的 bug），团队里没人能讲清它为什么这样工作、错在哪、怎么修。
- 这种"已上线但没有任何人能解释的产出"，业界已有人称为 **comprehension debt（理解负债）**（Addy Osmani，O'Reilly Radar；引用时注明出处，不要说是我们提出的）。它和技术债一样会积累，而且出事时才暴露。
- 招聘端的佐证：Stanford Digital Economy Lab（2026 年 8 月更新，美国 ADP 薪资数据）显示，22–25 岁、处在 AI 高暴露职业的员工，就业水平比同龄低暴露职业的趋势**低约 19%**（2022.11–2026.06），主要通过**减少招聘年轻人**实现，而不是裁员。作者强调这是描述性结果，不是因果结论。
- 健身房类比（Airwallex 讲者认可）：AI 替你举铁，任务完成了，肌肉没长。

**现有做法为什么不够：**
- 课程、导师：题目明确不要，而且脱离真实工作。
- 少用 AI、禁用 AI：题目明确不要，也违背公司的效率动机。
- Code review：审的是代码，不是人有没有懂；AI 让 PR 数量暴涨，reviewer 只能粗看。
- 高校的书面考试：一样可以被 AI 代写。

### 竞品与定位（v2 新增）

**"用测验拦住没看懂的 AI 代码"已经有现成产品**，这不是我们的创新点：
- **PR 理解测验**（SlopBlock、Gater、Reviewsaur、Commit Comprehension Gate、PR Quiz）：面向开发团队，读 PR diff，由 LLM 出题（多为选择题），每个 PR 都拦。只管代码，只做一次性验证。
- **AI 口试**（vivaproof 的 **Viva** ⚠️ 同名、Viva Vocina、Integrevise 等）：面向学校，读学生作业，语音口试，验证"是不是本人、懂不懂"。也是一次性验证。
- **邻近**：AI 代码审查（CodeRabbit 等）检查的是代码，不是人；练习和教练类工具（Yoodli 等）不在工作流里；AI 导师是题目明确排除的。

**定位图（幻灯片用 2×2）：**
- 横轴：一次性验证 ↔ 长期成长
- 纵轴：只管代码或作业 ↔ 多种能力（代码、决策、合规、分析）
- PR 测验类在"一次性 + 代码"；教育口试在"一次性 + 作业"；**Viva 在"长期成长 + 多种能力"**。

**我们的差异点（按重要性）：**
1. **把"底层台阶"还回来**：先预测，再由真实运行结果揭晓（4.2 ④），相当于"做砸了、被纠正"。竞品只检查，不形成练习。
2. **标准答案靠执行，不靠 LLM 意见**：沙箱实际运行得出标准答案。已查到的竞品都是 LLM 出题、LLM 判分。
3. **有人纠正**：senior 花 30 秒复核标出的片段并写一句纠正（4.5）。竞品全自动，题目里的 "someone correcting them" 缺位。
4. **学会的东西留得住**：几天后换个任务再问同一个概念（4.6）。竞品只查一次。
5. **不止代码**：决策、合规、分析各有追问招式；决策类用 7 项逻辑闭环。
6. **懂 = 更快**：L 牌到 P 牌，越懂抽查越少；答辩记录直接变成 PR 描述。竞品是每个 PR 都拦，纯增加负担。

详细竞品表见 docs/research/viva-competitors-voice-privacy.md。

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
| 拖慢学习者就有代价（grade / deadline / output） | **分档触发**（4.3）：熟练员工做低风险的熟悉改动基本不被打扰；轻量档只有 1 道题；标准档 2–5 分钟。**答辩记录自动生成 PR 描述、决策记录或审计备注**，替代原本要手写的文档；通过后还能**减少人工审核**，整体上反而更快（v3） |
| 只有自律的人才接受的麻烦是筛子（filters for people who could already afford to go slower） | 这是**交付关卡**，由团队统一设置，人人适用，不靠个人自觉；支持母语和文字作答，不偏向口才好或英语好的人 |
| 不要课程、不要导师 | Viva 不教任何东西，只是一道关加一面镜子；学习发生在准备答辩的过程中，用什么工具准备都行。senior 纠正（4.5）只是针对一个具体缺口写一句话、约 30 秒，不是导师制度，也不需要额外排时间（v2） |
| 不要"少用 AI"的理由 | 任务阶段随便用 AI，准备答辩时也可以让 AI 给你讲懂；我们只要求你**最终自己懂** |
| 让捷径感觉像损失（make the shortcut feel like the loss） | 没搞懂就过不了关，交不了付；反过来，越懂的人被抽到答辩的频率越低（类似学车从 L 牌到 P 牌），**懂 = 更快** |
| 书面题：doing it badly, with someone correcting them | 三层纠正：① **先预测，再由真实运行结果揭晓**，现实当场纠正你；② 答不上来不扣分，拿到具体的"理解缺口报告"，搞懂后重答；③ **senior 花 30 秒**复核 AI 标出的片段，写一句纠正（v2） |
| 书面题：over and over | **间隔复查**：几天后在另一个任务里换个说法再问同一个概念，答对了缺口才算"关闭"（v2） |

---

## 4. 产品如何运作

### 4.1 总流程（v3：分档触发 + Decision Defense）

v3 采用团队提出的主干（按"风险 × 新颖度 × 熟练度"决定要不要答辩，答辩聚焦决策，通过就减少人工审核，未通过就把具体风险交给资深人员），并补上两处：**触发分档**（4.3）和**未通过时先让本人重答一次**（4.4）。v2 的四个循环保留在后台。

```
员工使用任意 AI 完成任务
        ↓
系统读取：工单、产出（diff / 决策）、测试结果、变更范围（可选：AI 对话记录）
        ↓
豁免检查：纯文档、格式化、重命名、依赖小版本升级且测试全过 → 直接提交
        ↓
触发评分 S = 风险 R × 新颖度 N × 熟练度缺口 G（各 1–3 分）+ 硬规则
并告诉员工"为什么触发、还差多少能降档"
        ↓
 ┌────────────┬──────────────┬─────────────────────┬──────────────────────────┐
免答辩 S≤3      轻量 4–8        标准 9–17               完整 18–27
正常提交        1 道题          Decision Defense         Decision Defense
（5% 随机抽查）  PR 评论里异步    2–3 道题，2–5 分钟        + senior 必看审核摘要
                 └──────────────┴──────────┬──────────┘
                                           ↓
               Decision Defense：① 解释决策 ② 选择证据 ③ 应对一个条件变化
               （③ 先预测，再由测试 / 沙箱揭晓）
                                           ↓
               系统运行测试，生成审核摘要（= PR 描述 / 决策记录）
                                           ↓
              ┌────────────────────────────┴────────────────────────────┐
            通过                                                     未通过
              │                                                         │
   减少人工审核（按风险分级，见 4.4）                   缺口报告 → 本人搞懂后重答 1 次
   更新该项能力记录 → 下次更可能降档                                   │ 重答仍未通过
                                                                        ↓
                                            具体风险点（题目、原话、代码行、录音片段）交 senior
                                            senior：写一句纠正（回到本人能力记录）
                                                    + 决定结对修改 / 担保放行 / 打回

后台循环：间隔复查（到期的概念加进下次答辩）· 能力画像 · 理解负债地图 · 事故回放（路线图）
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
- 题量按档位定（v3）：轻量 1 题；标准和完整 2–3 题，控制在 2–5 分钟。每题最多追问 1 次。

**④ 答辩：Decision Defense（Interview agent）**
- **三类题（v3）**：任何任务都被当成一组决策来答辩，代码任务也一样（例如"为什么在这一步舍入"）。
  1. **解释决策**（必有）："你为什么这样处理 X？"员工用自己的话回答。
  2. **选择证据**（必有）：系统列出 4–6 条候选证据（测试用例、日志、代码行、文档或监管条款），其中混入无关或不支持结论的。员工点选能支持自己结论的 1–2 条，并说一句为什么。好处：不依赖口才和英语；有标准答案，可以自动判分；也能看出这个人有没有真看过测试。
  3. **应对一个条件变化**（标准档和完整档必有）：条件变了（例如币种换成 JPY），**先写预测和信心，再由测试或沙箱揭晓**。
  - 轻量档只出 1 题：可执行的产出优先出第 3 类，否则出第 2 类。
- **先预测，再揭晓（v2 核心交互）**：预测题和反事实题一律是"你先说结果（加一个信心值），再点运行"。沙箱跑出真实结果后，和你的预测并排显示。这一刻就是"做砸了、被现实纠正"。纠正来自真实运行，不是 LLM 的意见。
- 文字或语音都可以，两者地位相同。语音为加分项：
  - STT（语音转文字）：按住说话 → 浏览器 `MediaRecorder` 录音 → 后端**本地** faster-whisper 转写（音频不交给第三方；用 `initial_prompt` 提示 JPY、KWD、ISO 4217 等专有词）。不用 Chrome 默认的 Web Speech，因为它会把音频发到云端。
  - TTS（文字转语音）：浏览器自带 `speechSynthesis`，只读问题文本；**问题文字同时显示在屏幕上**。
  - **一次只问一个问题，在代码里强制检查**，不只靠 prompt（NYU 语音口试研究的教训）。
- **自适应**：回答太浅就往下追一层（v3 起每题最多追 1 次，保证 2–5 分钟）；回答已经很深就跳到下一题。
- 不给提示，不教学。允许说"我不知道"，诚实作答比瞎编得分高。
- 每题请作答者报一个信心值（低/中/高），用来做校准。

**⑤ 评分（Grader）**
- 评分器和提问器使用不同的 prompt，互相隔离；每个评分结论都要引用作答原文作为证据。
- 具体规则见第 5 节。

**⑥ 输出**
- **给个人**：理解缺口报告（哪里没懂，指向产出里的具体位置），加上能力画像的变化，以及待复查的缺口列表。
- **给 senior**：需要复核的片段（带录音时间戳），见 4.5。
- **给团队**：自动生成的 PR 描述、决策记录或审计备注，内容就是作答者自己的解释。
- **给组织**：理解负债地图，显示哪些模块、哪些决策目前没有人能讲清；以及团队层面的能力分布。

### 4.3 触发策略 v3：三因素评分 + 硬规则（L 牌 → P 牌）

团队的原始想法：任务简单、风险低、员工熟练，就省略答辩；任务大而复杂、风险高、员工不熟练，就触发答辩。v3 把它做成一套**能自动计算、能向员工解释**的规则。

**第 0 步：豁免（不计分）**
纯文档、格式化、重命名、锁文件或依赖小版本升级且测试全过：直接提交。竞品也这样处理，否则会被当成噪音。

**第 1 步：三个因素，各 1–3 分，系统自动算，并附上理由**

| 因素 | 1 分 | 2 分 | 3 分 | 数据来源 |
|---|---|---|---|---|
| **风险 R**：错了代价多大 | 内部工具、文案；有功能开关可以随时关掉 | 一般业务逻辑；公开接口变更；跨多个模块 | **资金流**（汇率、手续费、清结算、账本）；鉴权和权限；个人信息；合规规则；不可逆的数据迁移 | 团队配置的**风险地图**（目录或文件 → 等级，写法类似 CODEOWNERS）；变更范围；改动行有没有测试覆盖 |
| **新颖度 N**：对这个人、这份代码有多新 | 这个人改过这个模块，同类改动通过过答辩 | 模块熟、改法新，或者反过来 | 第一次碰这个模块；引入新依赖、新外部接口、新写法 | git 历史；能力记录 |
| **熟练度缺口 G**：熟练度反过来算 | 在**这个能力 × 这个领域**近期稳定达到 L3 以上 | 有记录但只到 L2，或记录已经过期 | 没有记录，或最近在这里没通过 | 答辩记录。**按领域分开算**；太久没有新记录会自动降一级 |

G 按领域算的原因：前端老手第一次改清结算代码，在支付领域仍然按新手处理。

**第 2 步：分数 S = R × N × G（1–27），分四档**

| S | 档位 | 做什么 | 时间 |
|---|---|---|---|
| 1–3 | **免答辩** | 正常提交；其中约 5% 随机抽一道轻量题（防止钻空子，也用来校准评分） | 0 |
| 4–8 | **轻量** | 1 道题，在 PR 评论里异步作答 | 约 1 分钟 |
| 9–17 | **标准** | Decision Defense，2–3 道题 | 2–5 分钟 |
| 18–27 | **完整** | 标准 + senior **无论通过与否**都看一眼审核摘要 | 2–5 分钟，senior 另加 1–2 分钟 |

用乘法而不是加法：任何一个因素很低都会把分数拉下来（熟练员工做低风险的熟悉改动几乎不会被打扰）；三个都高时分数急剧上升。

| 例子 | R × N × G | S | 档位 |
|---|---|---|---|
| 熟练员工改内部工具文案 | 1 × 1 × 1 | 1 | 免答辩 |
| 熟练员工改自己熟悉的手续费逻辑 | 3 × 1 × 1 | 3 | 分数是免答辩，但硬规则要求至少**轻量**（见下） |
| 中等熟练员工用新写法改一般业务 | 2 × 2 × 2 | 8 | 轻量 |
| 前端老手第一次改清结算 | 3 × 3 × 3 | 27 | 完整 |
| Mia（入职 4 个月）第一次改手续费函数 | 3 × 3 × 3 | 27 | 完整 |

**第 3 步：硬规则（覆盖分数）**
- **R = 3**（资金流、安全、不可逆）：至少轻量。它既是检查，也是审计证据。
- **有到期的间隔复查概念**：在本次答辩里加 1 题；本次免答辩时，单独推 1 道轻量题。
- **团队手动指定**：例如上线前夜，某些改动一律要答辩。
- **防止拆分规避**：把大改动拆成很多小 PR 来压低分数？R 和 N 按这个人最近几天在同一模块的**累计改动**计算。

**第 4 步：对员工透明**
触发时告诉员工原因，以及离降档还差多少。例如："本次触发：settlement/ 属于高风险路径（R3）；你第一次改这个模块（N3）；你在'构建 · 支付'上还没有记录（G3）。在这个领域再通过 2 次，同类改动会降到轻量档。"这样"懂 = 更快"是看得见的，捷径的代价也看得见。

**刻意不放进公式的：AI 写了多少。** 检测不可靠，还会鼓励员工隐瞒自己用了 AI；题目也明确不要"少用 AI"。我们只看风险、新颖度和这个人是否已经证明过自己懂。

**非代码任务（例如 AML 告警）同样适用：** R 看金额、客户风险等级、是否涉及上报期限；N 看这个人有没有处理过这种类型（typology）；G 看他在"审核 · 合规"上的记录。

### 4.4 结果处理（v3）

**通过：减少人工审核，按风险分级**
- **R1–R2**：reviewer 只看审核摘要里标出的风险点（轻审）；团队也可以配置为不需要人工复核。
- **R3**：**保留人工审核**。支付和合规通常要求双人复核（四眼原则），Viva 不取代它，而是让 reviewer 拿到一份带证据的审核摘要，审得更快、更准。
- 两种情况都会更新该项能力记录，下次同类改动更可能降档。

**未通过：先让本人再试一次，再交给 senior**
1. 第一次未通过：拿到缺口报告（哪道题、哪句回答、对应哪行代码），去搞懂（查文档、问 AI、问同事都可以），然后**重答一次**。
2. 重答仍未通过：把**具体风险点**交给 senior，包括题目、作答原话、对应代码行和录音片段（4.5）。senior 做两件事：
   - 写一句纠正，回到本人的缺口报告和能力记录，形成学习闭环；
   - 决定下一步：结对修改、senior 担保放行，或者打回。
3. 完整档另有一条：无论通过与否，senior 都会看一眼审核摘要（4.3）。
4. 不做任何额外惩罚。作答者可以对评分提出申诉，由人工复核。

**为什么不一失败就直接交给 senior：** 否则 senior 会变成瓶颈，而员工也跳过了"自己搞懂"这一步，等于又失去了一次练习。

### 4.5 循环 A：senior 30 秒纠正（v2 新增）

- 缺口报告同时推给指定的 senior。AI 在每个缺口上标出**作答原文和录音时间戳**，senior 点一下就跳到那一段（Whisper 自带分段时间戳）。
- senior 写一句纠正或补充，例如"舍入位数要按币种查 ISO 4217，不能写死"。这句话：
  - 进入作答者的缺口报告和能力画像；
  - 沉淀进该领域的题库，下次 Planner 出题时可以用上。
- 这补上了题目里的 "someone correcting them"，而且只占用 senior 很少的时间。
- **录音和录像的定位：** 只作为给人看的证据，不进入 AI 评分。senior 只在四种情况下能打开：重答仍未通过、完整档、作答者申诉、随机抽样做评分校准。每次查看都记日志，作答者本人能看到。录像默认关闭（见第 8 节隐私一行）。

### 4.6 循环 B：间隔复查（v2 新增）

- 每个缺口关闭时，系统记下对应的**概念**（例如"币种小数位"），而不只是这道题。
- 几天后，当这个人提交另一个涉及同一概念的任务时，触发判断会优先抽中它，并换一种问法追问（例如这次换成 KWD 的 3 位小数）。
- 答对了，这个缺口才算"真正关闭"；答错了，重新进入缺口报告。
- 依据：间隔效应（spacing effect）；以及高信心错误被纠正后记得更牢（hypercorrection effect），见第 7 节。

### 4.7 循环 D：事故回放（路线图，不在黑客松实现）

- 线上出事时，调出相关改动的答辩记录：当时谁答了什么、哪里答对了、哪里没问到。
- 事故本身变成一道答辩题，推给团队里所有碰过这个模块的人。

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
- **不评什么（v2）**：不从表情、语气、语速推断"自信、紧张、是否说谎"，也不评口音和流利度。只评内容。原因：欧盟 AI Act 第 5(1)(f) 条已禁止在职场和教育场景用 AI 从面部或声音推断情绪；而且按表现评分会偏向口才好、英语好的人，违背第 3 节的承诺。

---

## 6. 防 AI 代答（诚实版）

1. **锚定具体细节**：问题指向这一份产出的具体行和具体结论，通用答案答不上。
2. **现场反事实**：反事实输入是答辩时临时生成的，标准答案由沙箱实时算出，没有可背的答案。
3. **自适应追问**：浅答会触发下一层追问，照念的答案很难一路撑下去。
4. **一致性和信心校准**：代答往往前后不一致，或者信心和正确率对不上。
5. **间隔复查（v2）**：蒙过一次没用，几天后同一个概念会在另一个任务里换个问法再出现。
6. **激励兜底**：侥幸蒙过的人，下一次同类任务还会被抽到；能力画像的波动会暴露问题；出事时答辩记录可以追溯。

**要承认的局限：** 实时提词类作弊工具已经存在，我们无法百分之百杜绝。Viva 的目标是**让作弊变得不划算**，而不是不可能。准备答辩时尽管用 AI 帮你讲懂，那本身就是学习。

---

## 7. 学习科学依据

- **自我解释效应（self-explanation effect）**：让学习者解释给自己或别人听，能显著提升理解（Chi et al., 1989）。
- **检索练习或测试效应（testing effect）**：被提问、需要主动回忆，比重读更能巩固记忆（Roediger & Karpicke, 2006）。
- **SOLO 理解层级**：从复述到迁移，用于给理解深度定级（Biggs & Collis, 1982）。
- **间隔效应（spacing effect，v2）**：同样的练习量，分散在不同时间比集中在一次记得更牢（Cepeda et al., 2006 元分析）。对应循环 B。
- **高信心错误的纠正效应（hypercorrection effect，v2）**：人们以高信心答错、随后被纠正的内容，反而更容易记住（Butterfield & Metcalfe, 2001）。对应"先报信心、先预测、再揭晓"。
- **AI 语音口试的可行性和坑（v2）**：NYU 的研究用 AI 给 36 名本科生做语音口试，每人成本约 0.42 美元；三家模型讨论后评分一致性 α=0.86。但 83% 的学生觉得压力比笔试大，国际学生反映限时下表达困难，一次问多个问题负担过重（Ipeirotis & Rizakos, 2026）。所以我们让文字和语音地位相同，一次只问一个问题。
- **高校已经在往口试走**：悉尼大学的 "two-lane approach" 把口试这类有监督的评估列为 secure lane；TEQSA 的 *Assessment reform for the age of artificial intelligence*（2023）也建议在课程层面设置能确认"学生真的学会"的评估。
- Viva 相当于把高校正在采用的做法，搬进职场的日常交付流程。

---

## 8. 技术架构

| 层 | 选型（黑客松版） | 说明 |
|---|---|---|
| 前端 | Next.js / React | 任务页、答辩对话页（文字 + 麦克风，含"先预测再揭晓"组件）、结果与缺口报告页、senior 复核页、经理仪表盘 |
| 后端 | FastAPI（Python） | 编排整条流程 |
| LLM | Claude API（4 个角色分别用独立 prompt） | Classifier → Planner → Interviewer → Grader，评分器看不到提问器的内部提示 |
| 执行沙箱 | Python 子进程 + 超时 + 白名单（生产环境换容器） | 对产出函数跑反事实输入，得到标准答案 |
| 语音（加分项） | 浏览器 `MediaRecorder` 录音 + 后端本地 faster-whisper 转写；浏览器 `speechSynthesis` 朗读问题 | 团队已有 Whisper 转写经验。不用 Chrome 默认 Web Speech（音频会发到云端） |
| 录音与复核 | 录音文件存本地；Whisper 分段时间戳和作答原文对齐 | senior 复核页点击缺口即跳到对应时间点。录像默认关闭 |
| 触发引擎（v3） | 规则引擎，不用 LLM：风险地图（YAML，目录或文件 → R）+ git 历史（N）+ 能力记录（G） | 输出分数、档位和一句可读的理由；阈值和硬规则都可配置 |
| 存储 | SQLite / JSON | Task、Artifact、Viva、Question、Answer、Score、Profile、**Gap（概念、状态、下次复查）**、**Correction（senior 纠正）**、**AccessLog**、**RiskMap**、**TriggerDecision（R、N、G、分数、档位、理由、命中的硬规则）** |
| 隐私（黑客松） | 全部合成数据；API key 放 `.env`；实验参与者签知情同意，活动后删除原始录音 | 产品版设计（最少读取、脱敏、区域存储、零留存、访问日志、自动删除）见 docs/research/viva-competitors-voice-privacy.md 第 4 节 |
| 集成（路线图） | GitHub App（PR status check：答辩通过前不能合并）、Jira、Slack | 黑客松阶段用模拟 PR 页面演示 |

**Question 对象示例：**
```json
{
  "capability": "build",
  "move": "predict",
  "anchor": "fx.py:L14-L22",
  "prompt": "A payout of 1,234.56 AUD to a JPY account at rate 97.3 — what exact amount does the recipient get?",
  "truth": {"type": "exec", "value": "<sandbox result>"},
  "follow_ups_max": 1
}
```

---

## 9. Demo 脚本（决赛约 3 分钟）

**任务 1（构建类，主线）：跨境付款手续费函数**
- 工单："给跨境付款加上手续费并换汇。"Mia 用 AI 几秒钟生成 `convert_with_fee()`。
- 埋下的真实问题：函数对所有币种统一保留 2 位小数，但 **JPY 在 ISO 4217 中没有小数位**（KWD 则有 3 位）；手续费先扣还是先换汇，结果也会不同；用 float 存金额，存在精度问题。

**第一幕：走捷径，被现实纠正（高潮）**
1. Mia 直接点"提交"。先弹出**触发卡片**："settlement/ 属于高风险路径（R3）× 你第一次改这个模块（N3）× 你在'构建 · 支付'上还没有记录（G3）= 27，完整档。"
2. 题一（解释决策）："手续费为什么在换汇之前扣？"她答得含糊。
3. 题二（选择证据）：系统列出 5 条候选证据，让她选能证明"各币种金额都正确"的那条。她选了 `test_fee_aud_to_usd`，但这个测试只覆盖美元，证据不支持她的结论。
4. 题三（条件变化，**先预测，再揭晓**）："同样的 1,234.56 AUD 付到日元账户，收款人拿到的确切金额是多少？先写答案和信心。"她写了一个数，信心"高"。点"运行"：沙箱的真实输出和她的预测并排出现，输出是一个带两位小数的日元金额，这本身就是 bug。高信心答错被标红。
5. 结果：未通过。缺口报告指出："没有意识到函数对所有币种统一保留 2 位小数，JPY 没有小数位；现有测试只覆盖美元。"合并被拦下。

**第二幕：自己搞懂，再由 senior 把关**
1. Mia 去弄懂（可以问 AI、查 ISO 4217），修好函数，补上 JPY 和 KWD 的测试。
2. 重答：先预测、再揭晓，这次对了；还主动说出"KWD 有 3 位小数也要处理"，达到 L4 迁移。通过。
3. 因为是完整档，senior 仍要看一眼**审核摘要**：改了什么、她的原话、她选的证据、条件变化题的对错、测试结果。senior 约 30 秒看完，只补一句"清结算日志里也要按币种格式化"。这句话进入 Mia 的能力记录。
4. 审核摘要同时就是**自动生成的 PR 描述**，展示出来。

**第三幕：决策类（快速展示）**
- 一条 AML 告警（合成数据）：学生账户短时间内收到多笔小额入账，随后一笔跨境转出。要上报还是关闭？
- 题二"选择证据"：从交易记录里点出支持决定的几笔；题三"条件变化"："如果转出账户是本人在海外的账户，你的决定会变吗？"逻辑闭环清单逐项点亮。

**第四幕：懂 = 更快**
- 对比：熟练的同事 Leo 改内部工具文案，1 × 1 × 1 = 1，免答辩，直接提交。
- 几周后（模拟数据），Mia 再改手续费逻辑：3 × 1 × 1 = 3，只剩硬规则要求的 1 道轻量题；到期的间隔复查概念（KWD）也顺带出现在这道题里。她的能力画像时间线在上升。
- 经理仪表盘：理解负债地图（哪些模块目前没人能讲清）。

**收尾一句：** "Other tools ask: did you read this PR? Viva asks: are you getting better?"

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
- **知情同意（v2）**：开始前请参与者签一页简单的同意书（录什么、用途、谁能看、活动结束后删除原始录音）；结果只保留匿名化的分数。

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
| **周二 29 下午（今天）** | 锁定概念和定位（v2）；完成 3 页 pre-screen 幻灯片（第 2 页放竞品 2×2）；决定是否改名；准备两个任务素材（手续费函数 + AML 告警）；写 4 个角色的 prompt 草稿；搭后端骨架 |
| **周三 30 上午** | Pre-screen。**不等结果**，直接开发 |
| **周三 30 白天到晚上** | **触发引擎和触发卡片**；打通核心闭环：读入 → Decision Defense 三类题 → 文字作答 → 评分 → 缺口报告 → 重答；接上沙箱，做成**先预测再揭晓**；生成审核摘要（兼 PR 描述） |
| **周四 1 上午** | 跑验证实验，收集数据（先签知情同意） |
| **周四 1 下午** | 语音和录音（加分项）；**senior 复核页（简版）**；能力画像时间线和经理仪表盘（模拟数据）；把真实实验数据放进决赛幻灯片；排练 |

**四个循环在黑客松里的取舍：**

| 循环 | 黑客松做到什么程度 |
|---|---|
| 先预测再揭晓 | **必做**，demo 高潮 |
| A：senior 30 秒纠正 | 简版：一个页面，能按时间戳回放录音片段、写一句纠正 |
| B：间隔复查 | 数据模型里有 Gap 表；仪表盘用模拟数据展示 |
| C：L 牌 → P 牌 | 仪表盘展示抽查比例变化（模拟数据） |
| D：事故回放 | 只写进路线图 |

**建议分工（5 人，按各自擅长认领）：**
- R1 LLM 负责人：4 个角色的 prompt、自适应追问逻辑、评分细则。
- R2 后端：FastAPI、触发引擎（风险地图 + 评分）、执行沙箱、数据模型。
- R3 前端：答辩界面（含先预测再揭晓）、结果页、senior 复核页、仪表盘。
- R4 内容与实验：任务素材、标准答案、招募参与者、知情同意书、组织 mentor 校准。
- R5 Pitch：幻灯片、demo 旁白、评委问答准备、证据资料。

---

## 12. 规模化与愿景（回应"能否走出墨尔本"）

- **不依赖本地**：纯软件，接入的是全球通用的开发和工作工具（GitHub、Jira、Slack）；支持多语言答辩，适合跨国和移民员工众多的团队。
- **领域包（domain packs）**：能力 × 追问矩阵可以按行业扩展，例如支付工程、合规运营、数据分析、法律起草、咨询建模。换一个行业只需要换领域包。
- **路线图：**
  - Phase 0（黑客松）：MVP，两个任务类型。
  - Phase 1：做成 GitHub App，在一个团队试点，作为 PR status check。
  - Phase 2：领域包 + 经理仪表盘 + 可导出的审计证据（面向受监管行业）+ **事故回放**（循环 D）。
  - Phase 3：**Understanding Passport**。答辩记录沉淀成可验证、可以带走的能力证明，让雇主重新敢招新人，回应题目里"公司不招毕业生就能省工资"那一环。
  - 并行：高校版，作为口试式评估工具。
- **5 年后的逻辑**：AI 做的越多，没人懂的产出就越多，理解负债越积越大。Viva 的价值随 AI 变强而**上升**，就像财务越复杂，审计越重要。
- **商业模式**：团队按席位收费的 SaaS；合规版（导出审计证据）；高校授权。

---

## 13. 评委可能的问题（English answers for the pitch）

1. **"Isn't this just more friction?"** — The viva *is* the documentation: it writes the PR description / decision record you'd otherwise write by hand. It's risk-triggered, and the more you prove you understand, the less often you're asked.
2. **"Can't people just use AI to answer?"** — Questions are anchored to your specific artifact, counterfactuals are generated live with sandbox-computed answers, and follow-ups adapt. We don't claim it's cheat-proof; we make cheating not worth it — and preparing with AI is itself learning.
3. **"Isn't this a tutor — or a mentor programme?"** — It never teaches. It's a gate and a mirror: reality corrects you when the code runs, and a senior adds one line on one specific gap, about 30 seconds, no scheduled mentoring. The learning happens when you prepare, with any tool you like.
4. **"Why trust LLM grading?"** — Executable questions are graded by running the code, not by opinion. Every grade cites the answer as evidence; we calibrate against human mentors (target ≥80% agreement); humans handle appeals.
5. **"Why would a company pay?"** — Comprehension debt is an incident waiting to happen, especially where money moves. Viva gives faster onboarding, audit evidence that humans in the loop really understand, and a map of what nobody on the team can explain.
6. **"How is this different from code review?"** — Review checks the code; Viva checks the person. Reviewers are drowning in AI-generated PRs.
7. **"Doesn't it favour confident English speakers?"** — Scoring is on content, not fluency; text mode and multilingual answers are supported. This directly addresses the brief's "friction is a filter" warning.
8. **"Privacy / surveillance?"** — The capability profile belongs to the employee; managers see gate outcomes and team-level aggregates. We recommend it not be used for performance ranking. Recordings are evidence for humans only: a senior can open one only after a failed retry, for the highest-risk tier, on appeal, or in a calibration sample, and every view is logged where the employee can see it. We never score faces, tone or emotions. It's a real tension, and we'd rather name it.
9. **"What about work you can't execute, like decisions?"** — The 7-point decision-closure checklist plus consistency checks; the ground truth is the logic chain, not a single right answer.
10. **"Can it scale beyond Melbourne?"** — It plugs into global tools, domain packs extend it to other professions, and the passport becomes a portable signal across employers and countries.
11. **"Tools like SlopBlock and Gater already quiz people on their PRs. What's new?"** (v2) — They check once: did you read this PR? We build the reps: predict first and let the real run correct you, a senior adds a 30-second correction, and the same concept comes back days later on a different task. Ground truth comes from executing the code, not from an LLM's opinion. And it covers decisions and compliance, not only code.
12. **"Isn't there already a product called Viva?"** (v2) — Yes, an oral-exam tool for schools that checks authorship of assignments. We're in the workplace, embedded in delivery, and focused on growth over time rather than one-off verification. *(Drop this answer if the team renames.)*
13. **"How do you keep private code and data safe?"** (v2) — We collect the minimum (the diff and the ticket, not the repo), redact before any model sees it, keep voice transcription in-house, store data in-region, and auto-delete raw recordings. For the hackathon, everything is synthetic.
14. **"Won't this slow everyone down?"** (v3) — Routine work by people who've already proven themselves rarely triggers it. The trigger is risk × novelty × proficiency: a proficient engineer making a familiar, low-risk change skips it entirely. When it does trigger, it's one async question or a 2–5 minute defense, and passing it cuts human review. The employee always sees why it triggered and how close they are to the next tier down.
15. **"Why not just measure how much of the work AI wrote?"** (v3) — Detection is unreliable, and it would push people to hide their AI use — the brief explicitly doesn't want a reason to use AI less. We only ask: how risky is this, how new is it to you, and have you already shown you understand it?
16. **"Can people game the trigger by splitting PRs?"** (v3) — Risk and novelty are computed over a person's recent cumulative changes to a module, and 5% of skipped changes are randomly sampled.

---

## 14. 待团队拍板
- [ ] **产品名**：vivaproof.com 已有同名产品 "Viva — AI Oral Assessment"（面向学校）。改名，还是保留并在 pitch 里主动说明区别（见 13 #12）？（备选：Defend Your Work / Walkthrough）
- [ ] **定位改口径**：从"答辩关"改成"练习引擎"，pitch line 用 "AI took the reps. Viva gives them back."（v2 建议）
- [ ] **触发阈值（v3）**：四档分界 3 / 8 / 17、随机抽查 5%、R3 至少轻量档。demo 先用这组，团队确认或调整。
- [ ] **R3 通过后是否保留人工审核**：v3 建议保留（四眼原则），只是 reviewer 改看审核摘要。
- [ ] **循环取舍**：按第 11 节表格，先预测再揭晓必做，senior 复核做简版，间隔复查和 P 牌用模拟数据？
- [ ] **摄像头**：录像默认关闭、只给人看、不进入 AI 评分（v2 建议）；还是黑客松里完全不做录像？
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
- Cepeda, N. J. et al. (2006). Distributed practice in verbal recall tasks: A review and quantitative synthesis. *Psychological Bulletin*.
- Butterfield, B. & Metcalfe, J. (2001). Errors committed with high confidence are hypercorrected. *Journal of Experimental Psychology: Learning, Memory, and Cognition*.
- Ipeirotis, P. & Rizakos, K. (2026). Scalable and Personalized Oral Assessments Using Voice AI — https://arxiv.org/abs/2603.18221
- Addy Osmani, *Comprehension Debt: The Hidden Cost of AI-Generated Code* — https://addyosmani.com/blog/comprehension-debt/
- 竞品、语音、隐私调研：docs/research/viva-competitors-voice-privacy.md
- 项目文档：docs/briefing/problem-statements.md、docs/briefing/airwallex-qa.md、docs/briefing/judge-qa.md
