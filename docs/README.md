# 文档索引与版本记录

FEIT Hackathon 2026 · Flying Chinese · Airwallex PS1 "Getting Good"

所有方案文档都在 `plan` 分支上做版本管理。代码开发在其他分支进行，文档定稿后再合并到 `main`。

## 目录

| 路径 | 内容 |
|---|---|
| `plan/viva-plan.md` | **主方案（单一事实来源）**：问题、用户、流程、评分、demo、验证、分工、路线图、评委问答 |
| `research/viva-competitors-voice-privacy.md` | 竞品调研；STT 和 TTS 选型；摄像头与录音定位；数据安全设计 |
| `briefing/problem-statements.md` | 四个赞助方的题目摘要和 briefing 转写 |
| `briefing/airwallex-qa.md` | 与 Airwallex 讲者的答疑记录 |
| `briefing/judge-qa.md` | 与评委的答疑记录（赛制、评分偏好） |
| `briefing/problem-statements-handout.pdf` | 题目原件（PDF） |
| `briefing/airwallex-handout.jpg` | Airwallex 题目原文截图 |

## 版本记录

| 版本 | Tag | 日期 | 变化 |
|---|---|---|---|
| v1 | `plan-v1` | 29 Sep 2026 上午 | 团队确定的基线方案：交付流程里的答辩关、能力 × 追问矩阵、沙箱反事实、SOLO 评分、demo 脚本、验证实验 |
| v2 | `plan-v2` | 29 Sep 2026 下午 | 竞品调研后重新定位为"练习引擎"：新增竞品与 2×2 定位；流程从直线改为四个循环（先预测再揭晓、senior 30 秒纠正、间隔复查、L 牌到 P 牌，事故回放放进路线图）；demo 脚本重写；补充语音、录音与数据安全；标出与 vivaproof "Viva" 的重名问题 |

## 约定

- **每个定稿版本打一个 tag**：`plan-v1`、`plan-v2`……查看某一版：`git show plan-v1:docs/plan/viva-plan.md`；对比两版：`git diff plan-v1 plan-v2 -- docs/plan/viva-plan.md`。
- **提交信息**用 `docs(plan): …`、`docs(research): …`、`docs(briefing): …` 开头，写清楚改了什么、为什么改。
- **团队拍板的事项**：在 `viva-plan.md` 第 14 节勾选，并在上面的版本记录里写一行。
- **不要把真实的私人数据、录音、API key 提交进仓库。** 实验录音只存在本地，活动结束后删除。
