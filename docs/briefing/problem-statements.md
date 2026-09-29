# FEIT Hackathon 2026 — Problem Statements

Extracted from the sponsor briefing recordings (29 Sep 2026). The full transcripts follow below.

## Airwallex — official written text (handout, verbatim)

> **Problem statement 1 - Future Work - Skill Development / AI in the workplace**
>
> **Getting good: If AI does the beginner work, where does expertise come from?**
>
> Every expert got good the same way: doing small, low-stakes work badly, over and over, with someone correcting them. Those are precisely the tasks that are being automated first — so the ladder into skilled work is losing its bottom rungs, not by decision, but because skipping them is rational for everyone involved.
>
> Design how a person becomes genuinely good at something when the beginner version of their work is already solved.

> **Problem statement 2 - Future Work - The future workforce**
>
> **Income without a payslip: What does financial infrastructure look like when irregular income is the default?**
>
> Shift work, multiple casual jobs, gig apps, freelance income, a visa cap on your hours, money sent home. For most students this is simply what earning looks like — and almost every system that matters still asks for three recent payslips and proof of stable income.
>
> People are shut out not for earning too little, but for earning illegibly. Design financial infrastructure that treats irregular income as normal.

**Written vs spoken:** The summaries in sections 1 and 2 below come mainly from the spoken briefing. Everything in them is backed by the transcript, but the following appear **only in the spoken briefing, not the written text**: PS1's "make that path so good that taking the shortcut feels like the loss / Show us how the next person gets good", the concrete examples (bug fix, first draft, rebuilding a model; student marks; company saves a salary), and all the hard constraints (slowing down costs something; friction is a filter; no course / tutor / reason to use AI less). The same goes for PS2's wage-theft figures, the 48-hour visa cap detail, the "smooths the edges" warning and "Build for who's actually in this room". In slides, quote the written text as the official ask and cite the rest as "from the Airwallex briefing".

**Worth quoting that the summaries below miss:**
- PS1 (written): work done "**badly**, over and over": expertise comes from making mistakes and being corrected.
- PS1 (spoken [04:04]): the boring first tier "was where **judgment got installed**".
- PS1 (spoken [05:14]): friction "filters for people who could already afford to go slower".
- PS1 (spoken [04:43]): "You've shipped something you didn't fully understand… Hold on to that feeling. That's the most important data in the room."
- PS2 (written): "People are shut out not for earning too little, but for **earning illegibly**."

## 1. Airwallex · PS1 "Getting Good"
- **Ask:** "Design how a person becomes genuinely good at something when the beginner version of that work is already solved — and make that path so good that taking the shortcut feels like the loss. Show us how the next person gets good."
- **Background:** Expertise has always been built through repetition on low-stakes work, with someone correcting you. That entry-level work (small bug fixes, rough first drafts, rebuilding a model by hand) is boring and well-defined, which is exactly what got automated first. The career ladder is losing its bottom rungs. Each individual choice to skip them is rational (a student using AI gets the mark; a company using AI instead of a graduate saves a salary), but together these choices dismantle the machine that produces expertise.
- **Hard constraints / traps:** Anything that slows a learner down costs something (a grade, a deadline, an output). Friction that only disciplined people accept is a filter, not a solution. **They do not want a course, a tutor, or a reason to use AI less.**

## 2. Airwallex · PS2 Irregular income (financial infrastructure)
- **Ask:** "Design financial infrastructure that assumes irregular income is normal, not the edge case — and default. Build for who's actually in this room."
- **Background:**
  - The casual minimum wage from 1 Jul 2026 is $26.44/hr plus casual loading. A survey of about 10,000 migrant workers (80% international students) found two-thirds were paid below the minimum, and one in four were underpaid by at least $10/hr. Estimated total wage theft: **$61M per week**.
  - This is a systems problem, not just bad employers. Student visas cap work at **48 hours per fortnight**, but rosters are unpredictable. Students either turn down shifts or quietly go over the cap, and once over it they are afraid of losing their visa, so they don't speak up. Irregular hours + a hard limit + fear = leverage for someone else.
  - Renting, loans, tax, super and proof of income all assume one employer, one country and the same amount every month.
- **Explicit warning:** It is possible to make insecure work more comfortable without making it less insecure. If a solution only smooths the edges and lets the structure off the hook, judges will question it.

## 3. Cremorne Digital Hub · "The One-Square-Kilometre Problem"
- **Ask:** Use technology (software or hardware) to **measurably improve the working day** in Cremorne, practically enough to pitch to the wider Cremorne ecosystem.
- **Background:** Cremorne packs a very high density of economic activity into roughly 1–2 km². On a good day the companies there (MYOB, Carsales, REA Group and others) represent about **$6B** in market cap. It has the least public space per resident in Victoria, around **2 m² per person**, not counting about **10,000 daily commuters**. The area was built for manufacturing and never planned for tech companies. It is a tech hub but **data-dark**.
- **Example pain points:** Which walking route from the station is best (sunny narrow streets vs. a cooler river path). Crowding and hotspots (the City has already tried occupancy/hotspot tech). Meeting rooms and building capacity.
- **Constraints:** **Assume no new land, no new station and no new buildings.** Physical and policy change takes 5–20 years; they want something measurable with near-immediate impact and a fast go-to-market.
- **Bonus:** Strong teams may be invited to work from CDH and get founder support.

## 4. SMEC AI · Sovereign AI for Australian SMEs ($1,000 SMEC AI Sovereign AI Award)
- **Ask:** "Build AI that a real Australian small business would actually use", using sovereign AI to solve SMEs' everyday problems. Framing: "AI makers, not AI takers" (Dr Andrew Charlton, Assistant Minister for the Digital Economy).
- **Background:** Over 97% of Australian businesses are small businesses. Almost all their tools are rented from overseas, and data can go offshore with them. Real pain points: paperwork and documentation eating hours; bookings, email and social media; no dedicated IT person, so owners do it themselves.
- **Hard rules:**
  - All inference and processing of business data must run on **hardware you control** (in the room, on your own computer) or **Australian-hosted infrastructure**.
  - Open-weight models are fine wherever they were trained. Sovereignty means who operates the model and where the data lives.
  - **No calls to offshore APIs with business data.**
- **Judging criteria:**
  1. A real business owner can use it **straight away on Monday**: high value, low effort, minimal setup.
  2. How sovereign it is (data flow, who operates the stack). **Have a data-flow diagram ready.**
  3. Affordability: must be more cost-effective than renting overseas tech.
  4. Build quality: pace and judgement in the engineering.

---

# Transcripts

Auto-transcribed (Whisper small.en) and lightly corrected by hand. `[?]` = low-confidence guess; `[unclear]` = inaudible/garbled. Timestamps are mm:ss.

## Airwallex (headline sponsor)

[00:00] And it's my pleasure to welcome you here today.  
[00:03] We're very proud to be the headline sponsor for the hackathon,  
[00:08] and I'm very excited as well to see what we  
[00:11] build over the coming days.  
[00:13] For those who may not know us, Airwallex  
[00:15] is a global financial technology company,  
[00:19] began in Melbourne, and founded by a University of Melbourne  
[00:22] alumna, international students as well.  
[00:26] We build the financial infrastructure  
[00:29] that enables businesses to operate, grow,  
[00:31] and connect across borders.  
[00:33] Our ambition is grounded in very real world impact.  
[00:37] Recent analysis by Mandala Partners,  
[00:41] just published a couple of weeks ago,  
[00:43] estimated that Airwallex supported roughly $3.6 billion  
[00:48] in benefits to the Australian economy in 2025,  
[00:52] including around 29,000 jobs.  
[00:55] That is a powerful reminder of what  
[00:57] can happen with technology, removes barriers,  
[01:01] and gives businesses the tools to think bigger, move faster,  
[01:04] and grow globally.  
[01:06] It is also why supporting the next generation of talent,  
[01:09] builders, engineers, and problem solvers  
[01:11] matters so much to us.  
[01:13] Our partnership with the University of Melbourne  
[01:15] and the Faculty of Engineering and IT reflects that belief.  
[01:18] We want to create opportunities for students  
[01:20] to test their skills, develop new skills,  
[01:24] test their ideas, collaborate with industry,  
[01:27] and experience what it means to build something that  
[01:29] has real world impact.  
[01:31] A hackathon is much more than a competition.  
[01:35] It's an opportunity to take an ambitious idea  
[01:37] and turn it into something tangible.  
[01:39] You'll need to collaborate, adapt when things  
[01:43] don't go to plan, make decisions  
[01:45] with very incomplete information,  
[01:48] and keep moving when the problem becomes too difficult.  
[01:52] These are the same qualities that  
[01:55] matter when building products and companies.  
[01:57] Curiosity, resilience, creativity, and the courage  
[02:01] to challenge what already exists.  
[02:03] As you hear the problem statements very shortly,  
[02:07] this morning, don't focus only on producing something perfect.  
[02:12] Focus on understanding the problem,  
[02:14] listen to the people that you're trying to solve for,  
[02:18] and do something that creates genuine value.  
[02:21] Be bold with your ideas, generous with your teammates,  
[02:27] and open to learning through every iteration.  
[02:29] The strongest teams are not always  
[02:31] the ones with the most experience.  
[02:33] They are the ones with the ambition and the drive  
[02:36] to keep pushing forward, to keep going.  
[02:39] At Airwallex, we believe ambition should not  
[02:41] be limited by borders.  
[02:43] So take risks, push beyond the obvious solution,  
[02:47] and think about how far your idea can really go.  
[02:51] Good luck, enjoy the challenge, and make the most  
[02:53] of the opportunity over the next few days.  
[02:56] And now I'll move straight into presenting  
[02:58] our first problem statement.  
[03:00] This is titled Getting Good.  
[03:05] Quick question, think of one thing you're actually good at.  
[03:13] Not something that's on your CV, something  
[03:16] that you're actually very good at.  
[03:19] Now think about how you got there.  
[03:22] I guess it wasn't a course.  
[03:28] It was doing something repeatedly.  
[03:32] So doing it over and over again until you got really good.  
[03:35] And it's usually done in front of someone  
[03:37] that's there to correct you along the way.  
[03:41] That's how every skilled person who has ever lived got good.  
[03:45] Repetition on work that didn't matter much  
[03:48] with someone correcting you.  
[03:51] So here's what's changed.  
[03:53] That first tier of work, the small bug fix,  
[03:56] the rough first draft, rebuilding the model by hand,  
[03:59] was boring, and it was where judgment got installed.  
[04:04] And boring and well-defined is exactly  
[04:06] what we automated first.  
[04:09] So the ladder is losing its bottom rungs,  
[04:11] not because anybody decided to remove them,  
[04:14] because every individual's decision leading up  
[04:18] to that point and to skip them is completely rational.  
[04:22] If you use AI to finish an assignment, you get the mark [?].  
[04:27] If a company uses AI instead of hiring a graduate,  
[04:30] they save a salary.  
[04:32] Nobody in that chain is doing anything wrong.  
[04:35] And collectively, we're dismantling the machine  
[04:37] that produces expertise.  
[04:41] Some of you already feel this.  
[04:43] You've shipped something you didn't fully understand.  
[04:45] Or you've had that quiet suspicion  
[04:48] that something that you used to be really good at,  
[04:51] you're not that sharp at it anymore.  
[04:54] Hold on to that feeling.  
[04:55] That's the most important data in the room right now.  
[04:59] The hard part.  
[05:00] Anything that slows a learner down in order  
[05:03] to make them learn costs something,  
[05:05] a grade, a deadline, an output.  
[05:09] And friction that only the disciplined accept  
[05:11] isn't a solution, it's a filter.  
[05:14] It filters for people who could already  
[05:16] afford to go slower.  
[05:18] So we're not asking you to build a course or a tutor  
[05:22] or a reason to use AI less.  
[05:25] We're asking you to design how a person becomes genuinely  
[05:29] good at something when the beginner version of that work  
[05:32] is already solved.  
[05:33] And to make that path so good that taking the shortcut  
[05:37] feels like the loss.  
[05:39] Show us how the next person gets good.  
[05:45] So that's our first problem statement.  
[05:47] It's quite fun.  
[05:49] Here's our second problem statement.  
[05:54] Show of hands, who here has worked a job where your hours  
[05:59] change week to week?  
[06:06] Keep them up if you've ever had to guess  
[06:08] what you'd earn next month.  
[06:13] So this one's for you.  
[06:16] From the 1st of July this year, the casual minimum wage  
[06:19] in Australia is $26.44 plus casual loading an hour.  
[06:24] That's the law.  
[06:26] Here's the reality.  
[06:28] A survey of nearly 10,000 migrant workers,  
[06:31] 80% of them international students,  
[06:33] found two-thirds were being paid below the legal minimum.  
[06:37] One in four were underpaid by at least $10 an hour.  
[06:41] The estimate is $61 million a week every week.  
[06:47] Here's the part that makes this a systems problem and not  
[06:50] just a bad employer problem.  
[06:52] If you're on a student visa, you  
[06:54] can work 48 hours a fortnight during semester.  
[06:56] But your roster is unpredictable.  
[06:58] So students end up turning down shifts they need  
[07:01] or quietly going over the cap.  
[07:04] And once you're over the cap, you can't [report] anything [?].  
[07:07] Because you think you'll lose your visa.  
[07:10] Irregular hours plus a hard limit plus fear  
[07:13] that equals leverage for somebody else.  
[07:16] Then separately, everything else in your life  
[07:19] asks for a payslip [?], renting, a loan, tax, super, proof  
[07:23] of income.  
[07:26] All of it designed for a person with one employer, one country,  
[07:30] and the same number landing in your bank account every month.  
[07:34] That person is getting rarer, and [unclear].  
[07:39] One honest warning, it's entirely  
[07:41] possible to make insecure work more comfortable  
[07:44] without making it any less insecure.  
[07:47] If you build something that smooths the edges  
[07:49] and quietly lets the structure off the hook,  
[07:52] we will ask you about it in judging.  
[07:54] So design financial infrastructure  
[07:58] that assumes irregular income is normal, not the edge case,  
[08:02] and default.  
[08:04] Build for who's actually in this room.  
[08:06] And that's us.  
[08:08] Thank you.  
[08:08] Thanks, Jason. [?]  
[08:09] Thank you.

## Cremorne Digital Hub (CDH)

[00:00] that we do at CDH. If you haven't heard about what we do, we are Cremorne Digital Hub.  
[00:06] We're positioned in a really interesting place in the Victorian ecosystem to connect the  
[00:12] industry with each other. So we've got some very deep connections to the teams here at  
[00:19] UniMelb, to RMIT, to La Trobe, to Kangan. We also have some funding from the government  
[00:24] as well, and some live corporates. So what we really do at CDH is be able to provide  
[00:30] that essential connection and that glue role that connects the ecosystem to each other.  
[00:35] And we do that through running lots and lots of online events, and in person as well,  
[00:40] at our office in Cremorne. So, for example, some of the events, you may or may not have  
[00:46] seen them, I don't know if anyone's been to any of our events, but we do events  
[00:50] where we feature teams. They come in from Notion, we've been planning an event with  
[00:55] the core team as well. We do some events that help founders unpack a little bit  
[01:01] about what VCs are looking for when they're trying to secure investment for their startups.  
[01:07] So, primarily, we work towards helping early-stage SaaS [?] founders build exceptional  
[01:12] businesses and helping them become the best founders that they can be. And that's  
[01:17] through a myriad of ways, like supporting them with their first pilot product,  
[01:21] speaking to their customers, closing enterprise deals, or anything in between.  
[01:26] So, the problem statement that we're presenting today is what we're calling the  
[01:31] one-square-kilometre problem, and it basically boils down to quite like a  
[01:35] physical issue that we have in Cremorne, which is, Cremorne boils down and condenses  
[01:43] a huge density of business, of economic contribution into, I believe,  
[01:48] two-square-kilometres. And on a given day, on a good day, there's probably  
[01:54] an estimation of about $6 billion worth of market cap coming out of that space  
[01:59] from large companies like MYOB, Carsales, REA Group, and I think the  
[02:07] city of Yarra actually released some stats and said that in terms of  
[02:12] public spacing per resident, Cremorne actually has the lowest in Victoria,  
[02:17] and it's only two square metres per every single person, and that's not  
[02:21] counting the 10,000 people that commute Cremorne every single day to begin  
[02:25] their work day. So, the problem that we're really faced with is being  
[02:29] able to effectively navigate and improve the work day on a practical scale  
[02:34] using technology, because despite the fact that it is such a tech hub,  
[02:38] it is quite data-dark, and it's difficult for people to understand sort of  
[02:42] more practically like which pathway is the best way to walk to get to work.  
[02:48] Like, you might be coming from a train station, you could be walking  
[02:52] 10, 15 minutes, one part is on narrow streets where the sun's hitting you  
[02:56] directly, and I'm sure everyone knows what it feels like to have a  
[03:01] day where you're just walking in sun for 15 minutes for no reason,  
[03:04] whereas there could be a much more brisk river path that's less condensed.  
[03:08] So, it's much more a very practical problem that we're facing.  
[03:12] To give you a bit more example, we also do a lot of events as well.  
[03:18] So, I think in the city, they've already tried to implement some sort  
[03:22] of technology that helps people understand more about hot spots and  
[03:25] sort of which spaces are busy and occupied, and the same technology  
[03:31] we would like to see, whether that's hardware or software, they've  
[03:34] implemented into the Cremorne area to help the residents that are  
[03:38] also operating on their own frequency to consolidate and help  
[03:43] understand each other in terms of being able to navigate, like perhaps  
[03:47] their meeting rooms or understanding which buildings have more capacity  
[03:51] for people to actually get more value every day.  
[03:55] So, what we really...  
[04:05] And some of the... because I think some of the important  
[04:09] context to know is that Cremorne itself was built for manufacturing  
[04:13] and they didn't actually see or anticipate that they would have  
[04:16] so many tech companies move in, but as it stands, people move in  
[04:20] and other tech companies follow.  
[04:22] So, now we have like a sort of misdesigned space that obviously  
[04:26] would take a tremendous amount of effort to actually transform  
[04:30] physically and, you know, mandates and, you know, government spending  
[04:34] and all this kind of stuff, right? So, we're trying to use...  
[04:37] So, we're envisioning being able to use technology meaningfully,  
[04:42] whether that's from software or hardware, to measurably  
[04:45] improve the working day and have something that can be practical  
[04:49] and pitch out to the broader Cremorne ecosystem.  
[04:54] And what's really interesting about our product is that if  
[04:57] the idea, we would love for it to be effective  
[05:00] and something that we can actually champion, not to mention  
[05:03] if it's interesting enough, please come and show us  
[05:06] and we'll even support you if you can come work out of our space  
[05:10] and we can support you like one of our founders  
[05:12] to help you get to the next level and have something really cool  
[05:15] and meaningful to be able to work on.  
[05:18] But finally, in terms of some of the more unique details,  
[05:23] assume that there's no new land, new station or no new buildings.  
[05:27] Things that are being, like I said, the things that are being argued about,  
[05:31] like construction and other sort of amendments, they can take  
[05:34] five, ten, twenty years to even action.  
[05:37] So, we're looking for something that's more measurable  
[05:39] and trying to speed up that timeline and go to market, so to speak, quickly  
[05:44] and have impact almost immediately.  
[05:50] And like I said, I think like Greg [?] so eloquently said,  
[05:55] please have fun with the hackathon.  
[05:57] I think it's a really amazing opportunity to be able to  
[06:00] collaborate with your peers and have a focused time  
[06:02] to be able to work and build something really cool together.  
[06:05] I've done a few hackathons in my time  
[06:07] and they were some of the most memorable experiences that I've had.  
[06:11] I know it's daunting to be able to operate on these challenges  
[06:16] and then presenting them as a whole different ballgame  
[06:18] and a whole different challenge, but every single rep that you do  
[06:22] that helps you compound and build these really valuable skills  
[06:25] heading into the future is all worth your while.  
[06:28] And yeah, have a great hackathon.  
[06:30] Thank you, everyone.

## SMEC AI

[00:00] AI or software tools in the last week, do you know where the data went to?  
[00:09] I'm Sean from SMEC AI, stands for the Small to Medium Enterprise Centre of Artificial Intelligence  
[00:18] and we run federally funded AI Adoption Centre.  
[00:24] So that means that I'm sitting down with small businesses every week and talking with them about what their problems are.  
[00:35] So our problem statement is around what the Assistant Minister for the Digital Economy spoke of recently  
[00:50] and that is that we want to paraphrase him.  
[00:55] We want Australia as far as AI and technology to be not AI takers but AI makers.  
[01:06] Not just buying and renting the technology from overseas but creating, maintaining and developing our own.  
[01:17] And that's from Dr Andrew Charlton who as I said is the Assistant Minister for Digital Economy.  
[01:24] So you can see that Australian leadership is recognising that we need to create and not just use other technology.  
[01:35] Did you know that over 97% of Australian businesses are small businesses?  
[01:45] And almost every tool they're using is rented from overseas and data can sometimes go offshore with it.  
[01:56] So your mission, if you choose to accept it, is to build AI that a real Australian small business would actually use.  
[02:09] How do you do it? The form is yours but there are some rules I'll go through now.  
[02:16] So all inference and processing of business data must run on hardware that you control like in the room or on your computer or Australian hosted infrastructure.  
[02:38] Open weight models are welcome wherever they're trained and sovereignty is about who operates the intelligence and where the data lives.  
[02:51] There should be no calls to offshore APIs with business data.  
[03:00] Now as I said I talk with small to medium enterprises every day practically and they tell me their problems.  
[03:11] And if you're working in this area it's important I understand that all this is not about you, it's about their problems.  
[03:21] And it's about how you're going to solve them.  
[03:25] When I talk to them they talk about how paperwork and documentation eats hours of their time.  
[03:35] They could be spent on more meaningful things.  
[03:39] They might be managing bookings, emails, social media and this has taken up a lot of their time.  
[03:49] And many small to medium enterprises don't have a dedicated IT person so it's the actual business people if you like that are doing a lot of these tasks.  
[04:01] So as I said your challenge is to focus on these sorts of problems day to day using sovereign AI.  
[04:14] And how we're going to judge it is number one put a real business owner use your product or your solution straight away on Monday.  
[04:27] And what we find when we talk to business they don't want to have to spend a lot of time setting it up and configuring it and that sort of thing they want.  
[04:37] High value, low effort solutions as soon as possible because small to medium enterprises in particular time poor.  
[04:48] Next criteria we'll judge is how sovereign is it, where the data flows, who operates the stack and will need to show us that.  
[05:01] So have your data flow diagram ready and also affordability.  
[05:07] So it's not important just to have a solution but have a cost effective solution that is superior to small businesses renting technology.  
[05:22] And finally criteria is how well is it built so this is about pace and judgement in your engineering.  
[05:33] So finally the award is the one thousand dollar SMEC AI sovereign AI award and I look forward to seeing what you can get. Good luck.
