# Viva：竞品、语音与摄像头、数据安全（viva-plan 补充）

> 29 Sep 2026 调研。配合 docs/plan/viva-plan.md 使用。竞品信息来自各家官网公开描述，未实际试用。

---

## 1. 竞品

### 1.1 最直接的竞品：PR 合并前的"理解测验"（开发者向）

| 产品 | 解决什么问题 | 面向谁 | 数据来源 | 形式 |
|---|---|---|---|---|
| **SlopBlock** (slopblock.pro) | 防止没看懂的 AI 代码被橡皮图章式合并 | 个人开发者、开发团队；考 **PR 作者** | PR diff（改动行） | GitHub App + status check；**选择题**；跳过改名、文档类改动 |
| **Gater** (usegater.app) | "AI 写的代码，团队也要能 own" | 用 GitHub 的团队 | PR diff、提交、讨论 | GitHub App + Chrome 插件；简答题；个人免费 |
| **Reviewsaur** (reviewsaur.com) | 先用白话解释 PR，再让 **reviewer** 过测验才能批准 | Reviewer 和工程团队 | 只读改动和标题，不拷整个代码库；生成后删除，不用于训练 | 可选"我不知道"；Pro 版每席位每月 11 美元 |
| **Commit Comprehension Gate**（dev.to 开源） | 同上 | 开发团队 | PR diff 发给 Claude API | GitHub Action，3 道选择题；无数据库，答案藏在 PR 评论里；每个 PR 约 0.05–0.10 美元 |
| **PR Quiz**（github.com/dkamm/pr-quiz） | 同上 | 开发团队 | PR diff 发给 OpenAI | GitHub Action。HN 评论主要质疑：代码外发的隐私问题；可以让 AI 代答；LLM 出错题 |

**结论："AI 生成 PR 后用测验拦合并"这个点子已经有 4–5 个现成产品，不能再当成我们的创新点。**

### 1.2 教育向：AI 口试

| 产品 | 解决什么问题 | 面向谁 | 数据来源 | 语音、摄像头 |
|---|---|---|---|---|
| **Viva**（vivaproof.com）⚠️ **同名** | 学生交作业后做自适应语音口试，验证是不是真懂、是不是本人写的 | 中小学和大学（三大洲试点） | 学生提交的作业：essay、实验报告、代码、PPT、表格 | 语音；声纹身份验证；高风险考试可选摄像头和切屏检测；录音 30 天后自动删除；有单租户私有部署 |
| **Viva Vocina**（新西兰） | 基于提交作业的结构化口试 | 学校、职业培训、企业培训 | 学生作业 | 仅语音；给老师录音、转写和"理解分" |
| **Integrevise**（英国团队） | 书面作业加简短自适应口试，找出理解缺口 | 高校 | 书面作业 | 语音口试 |
| Rocketproof、Cadmus、OralExam.AI、FeedbackFruits 等 | 按作业生成答辩问题、录音口试、LMS 集成 | 高校 | 作业和课程材料 | 多为语音 |

**研究证据（NYU，arXiv 2603.18221）：** 36 名本科生做 AI 语音口试，成本约每人 0.42 美元；三家模型"评审团"讨论后一致性 α=0.86（讨论前只有 0.52）。但 83% 的学生觉得比笔试压力大，只有 13% 更喜欢 AI 口试；国际学生反映限时下表达困难；一次问多个问题会让人负担过重；克隆的教授声音被认为"咄咄逼人"。作者的教训："对 LLM 的行为约束要靠架构保证，不能只靠 prompt。"

**Integrevise 试点：** 7 名受访学生里只有 1 人认为口试让自己想得更深，说明"为什么要做"的沟通和融入课程比技术更关键。

### 1.3 邻近但不同类
- **AI 代码审查**（CodeRabbit、Greptile、Graphite 等）：检查代码，不检查人。
- **练习和教练**（Yoodli、InStage 等）：练表达，不是交付关卡。
- **AI 导师 / 学习模式**：题目明确排除。

### 1.4 我们还剩下的差异点（pitch 要改口径）

不要再说"我们发明了 PR 答辩关"，要说：**别人回答的是"这次你看懂了吗"，我们回答的是"你在变强吗"**（这正是 PS1 的问题）。

1. **标准答案靠执行，不靠 LLM 判断**：反事实题在沙箱里真跑出结果。已查到的竞品都是 LLM 出题、LLM 判分。
2. **不止代码**：决策、合规（AML）、分析类能力，各有追问招式和 7 项逻辑闭环。开发者工具只管代码，教育工具只管作业。
3. **开放作答加自适应追问加 SOLO 分级**，而不是选择题。选择题能蒙，也能让 agent 代答（HN 上的原话批评）。
4. **L 牌 → P 牌**：证明懂了，抽查频率就下降，懂 = 更快。竞品是每个 PR 都拦。
5. **答辩记录就是 PR 描述或审计备注**，用作者自己的话写，替代原本要手写的文档。
6. **学习闭环**：缺口报告 → 搞懂 → 重答 → 能力画像随时间上升。

**⚠️ 命名：** vivaproof.com 的产品就叫 "Viva — AI Oral Assessment"，评委一搜就能看到。建议改名，或者在 pitch 里主动说明区别（它面向学校、验证作业作者身份；我们面向职场、嵌在交付流程里、培养能力）。

---

## 2. 语音：STT 和 TTS 是什么

- **STT（speech-to-text，语音转文字）**：把作答者说的话转成文字，交给 Interviewer 和 Grader 处理。LLM 只读文字。
- **TTS（text-to-speech，文字转语音）**：把 AI 的问题读出来。

| 方案 | 是什么 | 优点 | 缺点 |
|---|---|---|---|
| **Whisper**（OpenAI 开源模型） | 可以在自己机器上跑（faster-whisper、whisper.cpp），也可以调 API | 本地跑时音频不出机器；多语言好，中文作答也能转；自带分段时间戳；可以用 `initial_prompt` 提示专有词（JPY、KWD、ISO 4217、convert_with_fee） | 不是边说边出字，要录完一段再转；大模型在 CPU 上慢，要先在自己电脑上测 |
| **Web Speech API**（浏览器自带 `SpeechRecognition`） | 浏览器内置，免费，实时出字 | 零搭建 | **Chrome 默认把音频发到云端识别**（新版有 `processLocally` 本地模式，但支持的语言和浏览器有限）；Firefox 基本不支持；口音和术语识别较差 |
| **浏览器 TTS**（`speechSynthesis`） | 浏览器内置朗读 | 免费、零延迟、零搭建 | 声音偏机械；部分"在线声音"也走网络，但读的只是问题文本，敏感度低 |

**黑客松建议：** 按住说话（push-to-talk）→ 浏览器 `MediaRecorder` 录音 → 上传后端 → 本地 faster-whisper 转写 → 文字进入 Interviewer。**同时在屏幕上显示问题文字**，一次只问一个问题，在代码里强制检查（NYU 的教训）。文字作答始终保留，作为同等选项。

---

## 3. 摄像头和录像：建议怎么定位

**可以做：** 录音（可选录像）作为 **senior 复核的证据**。
- 每道题的评分都引用作答原文；用 Whisper 的时间戳，senior 点一下就跳到那一段回放，**30 秒看完关键处，而不是看 5 分钟录像**。
- 只在这些情况下 senior 能打开录音录像：两次未通过需要 senior 担保、作答者申诉、随机抽样做评分校准。

**建议不做：** 让 AI 从画面或声音里判断"自信、紧张、是否在撒谎"并计入评分。
1. **法律**：欧盟 AI Act 第 5(1)(f) 条自 2025 年 2 月起禁止在职场和教育场景用 AI 从生物特征（面部、声音）推断情绪；压力检测不属于医疗或安全例外。面向全球（"走出墨尔本"）就绕不开这一条。
2. **和我们自己的承诺冲突**：我们说"不偏向口才好、英语好的人"，而按表现评分正好偏向这类人。NYU 研究里国际学生已经反映限时表达困难。
3. **评委问答 #8（监控）** 会更难答。

**折中写法：** 录像默认关闭；只在高风险变更时由团队开启，并告知作答者；录像只给人看，**不进入 AI 评分**；AI 只评内容。

---

## 4. 私密数据和文档：怎么上传、怎么保证安全

### 4.1 黑客松阶段（现在就要做）
- **全部用合成数据**：手续费函数是我们自己写的；AML 告警是编造的。幻灯片上写明 "synthetic data only"。
- API key 放 `.env`，不提交到 git。
- **周四的验证实验会录 8–10 人的声音**：开始前请参与者签简单的知情同意（录什么、用途、谁能看、活动后删除），活动结束后删除原始录音，只保留匿名化的分数。

### 4.2 产品设计（给评委讲）

| 层 | 做法 |
|---|---|
| **少拿数据** | GitHub App 只申请读 PR diff 和工单的最小权限，不克隆整个仓库（Reviewsaur 也是这样）。发给 LLM 之前先扫描密钥和个人信息并脱敏（如 gitleaks、Microsoft Presidio）。AML 等场景里的客户个人信息，默认脱敏后再处理 |
| **传输和存储** | 全程 TLS；音视频由浏览器通过预签名 URL 直接上传到对象存储（如 S3），使用 KMS 加密，每个租户独立密钥；数据存放在客户所在区域（如悉尼） |
| **LLM** | Anthropic 商用 API：默认不用于训练，对话内容默认不留存（Fable/Mythos 类模型除外，需留存 30 天）；可以申请 Zero Data Retention；可以用 `inference_geo` 指定数据驻留；大客户可走客户自己的云账户，或单租户私有部署 |
| **语音** | Whisper 跑在我们自己的服务器上，或客户内网，音频不交给第三方；敏感场景不用 Chrome 默认的云端 Web Speech |
| **谁能看** | 记录属于员工本人；senior 只能在前面那三种情况下打开录音录像；每次查看都记日志，**员工能看到"谁在什么时候看了我的录音"** |
| **保留期** | 原始音视频 N 天后自动删除（可配置，vivaproof 是 30 天）；长期只保留文字记录和评分，作为审计证据 |
| **合规** | 符合澳洲 Privacy Act，事先告知并取得同意。**不做声纹或人脸识别**：用于自动识别身份的生物特征属于"敏感信息"，门槛更高。不做情绪推断（见第 3 节） |

**一句话给评委（英文）：** "We collect the minimum (diff and ticket, not the repo), redact before any model sees it, keep voice transcription in-house, give recordings to humans only on appeal or failure with an access log the employee can see, and never score faces or emotions."

---

## 参考
- SlopBlock — https://slopblock.pro/
- Gater — https://usegater.app/
- Reviewsaur — https://www.reviewsaur.com/
- Commit Comprehension Gate — https://dev.to/islandbytes/i-built-a-merge-gate-that-quizzes-developers-on-their-own-code-changes-heres-why-and-how-5460
- PR Quiz（HN）— https://news.ycombinator.com/item?id=44726672
- Viva (vivaproof) — https://www.vivaproof.com/
- Viva Vocina — https://viva.vocina.ai/
- Integrevise pilot — https://www.mdpi.com/2813-4346/5/3/59
- 19 AI oral exam platforms compared — https://www.snapsdr.com/blog/ai-oral-exam-roleplay-platforms-universities-2026
- Ipeirotis & Rizakos, Scalable and Personalized Oral Assessments Using Voice AI — https://arxiv.org/abs/2603.18221
- Addy Osmani, Comprehension Debt — https://addyosmani.com/blog/comprehension-debt/
- Web Speech API on-device explainer — https://github.com/WebAudio/web-speech-api/blob/main/explainers/on-device-speech-recognition.md
- Claude API and data retention — https://platform.claude.com/docs/en/manage-claude/api-and-data-retention
- FPF on EU AI Act Art. 5(1)(f) — https://fpf.org/blog/red-lines-under-eu-ai-act-unpacking-the-prohibition-of-emotion-recognition-in-the-workplace-and-education-institutions/
