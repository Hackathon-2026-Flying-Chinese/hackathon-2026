# Viva front-end (demo)

Dependency-free HTML, CSS and JavaScript. No build step, no CDN, works offline. It runs against a built-in simulated
backend, so the whole demo works today and the real server can replace the simulator later.

Flow: a GitHub PR link opens the **Interview**, the interview ends in the **Results**, and the avatar at the top right opens the **Portfolio**.

## Run

```bash
cd frontend
python3 -m http.server 8790
```

Open `http://127.0.0.1:8790/?presenter=1` in Chrome. Microphone, camera and the two-window reviewer flow need an http origin.
Port 8790 avoids the backend's 8765. After an update, hard refresh with Cmd+Shift+R.

## Pages

| Page | What it does |
|---|---|
| `index.html` | **Home** (PR card and Start), **Interview** (camera gate, questions, Speak or Type), **Results** (score, marked answers, senior review, portfolio points) |
| `portfolio.html` | Points from confirmed reviews, understanding score and trend, concept level, work list, the scoring standard |
| `review.html#token` | Senior reviewer: signed video playback, transcript, decision (genuine or follow-up) and note |

A GitHub link can carry the PR: `index.html?repo=org/repo&pr=128&title=...&author=...&branch=...&sha=...`. Missing fields fall back to the sample PR.

## Interview

- Two questions per attempt: how the core logic works, and why it was built that way. Code correctness is not judged and no code is shown.
- The camera and microphone are on for the whole interview. Each answer, spoken or typed, is recorded as one clip for the senior reviewer.
- One follow-up at most, aimed at the weakest of specific, reasoning and ownership.
- The score reads the words only. It never uses face, voice tone or expressions.

## Second attempt

A first attempt that does not pass (score under 70) is feedback, not a verdict: nothing goes to a senior and the concept level stays.
**Try again with new questions** starts attempt 2 on the same PR with a different question set (`sets[1]` in `js/data.js`), so no question repeats.
A pass, or a failed second attempt, goes to a senior. A failed second attempt also lowers the concept level by one.

## Portfolio points (Viva Plan 4.3 and 4.4)

A senior-confirmed review adds **Risk x Novelty x Gap** points, each factor 1 to 3, so one change is worth 1 to 27.

| Factor | 1 | 2 | 3 |
|---|---|---|---|
| Risk | Internal tool, copy, or behind a switch | Ordinary business logic or a public API change | Money flow, sign-in, personal data, compliance |
| Novelty | Changed this module before | Familiar module with a new way, or the reverse | First time in this module, or a new dependency |
| Gap | Concept level 3 | Concept level 2 | Concept level 0 or 1 |

Bands: 1 to 3 skip, 4 to 8 light, 9 to 17 standard, 18 to 27 full. Risk 3 is never skipped. The sample PR is Risk 3, Novelty 1, so it is worth 9 at level 1 and 6 at level 2:
a small change adds fewer points than a first-time change in a risky area. The Results page shows the table, which cells this change hit and why, the product, and the next similar change.

Understanding score: average of the last ten **first** attempts, weighted by risk, and only from five attempts on ("Not enough evidence" before). A retake is never counted twice.
The dashed trend line is a fixed synthetic illustration, labelled SYNTHETIC, never stored and never counted.
The portfolio is private to the person: a reviewer token cannot read it. It shows no confidence calibration because the interview collects no confidence value.

## What is simulated

| Real in the browser | Simulated (marked in the UI) |
|---|---|
| Camera and microphone capture, waveform, 180 s clip cap, recordings in IndexedDB, playback with seek | Transcription: stand-in text per question, editable, labelled **Simulated** |
| Signed 5 minute links (HMAC, WebCrypto), expiry, renew, access log | Assessment: word patterns (numbers, names, reasons, alternatives, first-person decisions, generic phrasing) scored on the device, labelled **Simulated assessment** |
| Question sets, retake rules, concept level, points, portfolio | Reviewer identity ("Demo reviewer role. Not SSO.") and the concept "Fees and rounding" with fixed Risk and Novelty |

The header chip **Simulated backend** stays on until `js/sim.js` is replaced.

## Presenter drawer (`?presenter=1`)

Button in the header. Reviewer link, camera required (untick only if the camera hardware fails), voice stand-in Specific or Generic, fill the open question, reset all local data, and six copyable answers for the attempt on screen.
Demo: choose **Generic**, answer, fail, **Try again**, choose **Specific**, pass, open the reviewer link, confirm, watch the points arrive, open the portfolio.

## Connect the real backend

Replace `js/sim.js` with a `Viva.api` that calls the server. Suggested routes (the backend does not have them yet, so change them freely):

| `Viva.api` | Route |
|---|---|
| `start({pr})`, `session(sid)` | `POST /api/sessions`, `GET /api/sessions/{sid}` |
| `interviewNext()`, `interviewAnswer()`, `interviewFinish()` | `POST /api/sessions/{sid}/interview/next`, `/answer`, `/finish` |
| `retake(sid, {version})` | `POST /api/sessions/{sid}/retake` (only after a failed first attempt; a new question set) |
| `mediaUpload()`, `mediaDiscard()`, `mediaLink()`, `mediaFetch()` | `POST /api/sessions/{sid}/media`, `DELETE /api/media/{id}`, `POST /api/media/{id}/link`, `GET /api/media/{id}?exp=&sig=` |
| `review(token)`, `decide(token, {verdict, note})` | `GET /api/review/{token}`, `POST /api/review/{token}/decision` (the role comes from the token, never the body) |
| `portfolio()` | `GET /api/me/portfolio` (learner only) |
| `leave()`, `remove()` | `POST /api/sessions/{sid}/leave` (delete media, keep answers), `DELETE /api/sessions/{sid}` |

Rules the server must keep: a first failure does not create a reviewer token; a first failure in a Full band change (18 or more) should also go to a senior (the sample PR never reaches it);
a confirmation adds points once and a later follow-up request removes them; deleting a session removes its points and its trend point.
Shapes are in `view()`, `scoringView()`, `reviewView()` and `api.portfolio()` in `js/sim.js`.
When served by FastAPI under `/static/`, add `<base href="/static/">` to the HTML files.

## Files

| File | Job |
|---|---|
| `index.html`, `portfolio.html`, `review.html` | Learner app, portfolio, senior reviewer page |
| `js/data.js` | The person, the sample PR, two question sets with stand-in answers, the scoring standard, the synthetic trend |
| `js/sim.js` | Simulated backend: sessions, attempts, assessment, points, levels, media, reviewer |
| `js/core.js` | DOM helpers, spring and enter motion, odometer, theme, toast, dialog, avatar |
| `js/app.js` | Home, stage routing, results polling, presenter drawer |
| `js/interview.js`, `js/media.js` | Interview screen and the camera |
| `js/results.js` | Results page, the scoring table and scale, shared with the portfolio |
| `js/portfolio.js`, `js/review.js` | Portfolio page and senior reviewer page |
| `css/tokens.css` | Colour, type, radius and motion tokens, light and dark |
| `assets/avatar.jpg` | The avatar shown at the top right (replace the file to change it) |

## Design

Black and white with violet `#612fff` and blue `#3e7bff`, close to Airwallex. Violet to blue is the only gradient: the recording ring, the score ring, the rail and the points scale.
System type (SF Pro, SF Mono), hairlines, one radius scale, grain on a fixed layer. Motion carries meaning: the question types in word by word, the camera card
flies from the middle to the corner, the score ring draws and the digits roll, the marked phrases sweep in, the matching scoring cells light up, the points marker drops.
All of it honours `prefers-reduced-motion`.
