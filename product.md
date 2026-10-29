# Mentor AI — Product Design Doc

**Status:** Ready for Coding Jam (v1.0)
**Last updated:** October 28, 2026
**One-liner:** A multimodal AI agent that reads your resume, finds live job posts that fit you, builds a study plan,
and interviews you out loud as a senior employee of the company — then grades every answer.

---

## 1. The user & the moment

- **Who:** A student or early-career job seeker (the Handshake and LinkedIn crowd) with a resume PDF and too many
  tabs open.
- **When:** Sunday evening. They know roughly what they want but searching, deciding what to study, and practicing
  interviews are three separate, lonely chores.
- **Why now:** Gemini can read a PDF, search the live web, and hold a real-time voice conversation. One agent team can
  cover the whole path from "what should I apply to?" to "how did my interview go?".

## 2. The contract (I/O)

- **Input:** Resume (PDF / PNG / JPG / TXT), a typed job request, a 1–5 self-rating per topic, and spoken answers.
- **Output:** 5 job posts per round with links and reasons, a prioritized study plan, a 7-question voice interview,
  and a per-question review (rubric scores, strengths, what to prepare, what a senior interviewer listens for).
- **The loops:**
  1. Request → Mentor restates → you correct → **Yes, search** → 5 posts → feedback → 5 new posts → **Save**.
  2. Saved job → topics → self-ratings → study plan → **I'm done studying** → research + interview written →
     voice interview → review.

## 3. The magical moment

> "It found a real posting I'd missed, then a 'senior engineer' from that company interviewed me out loud with a
> question people actually got asked there — and told me exactly what I fumbled."

## 4. Scope: what we ARE building (v1)

- Resume upload (or a one-click sample resume) read natively by Gemini.
- Job search chat with a confirmation loop and a feedback loop; save the posts you choose.
- Saved Jobs tab with study and interview status per job.
- Topic list → self-ratings → study plan with study-first / review-later and per-topic done checkboxes.
- Interview research (reported questions with sources) → 7-question interview (configurable 5–10).
- Voice mock interview: Gemini Live API, with a turn-by-turn fallback.
- Review with a 4-criterion rubric and an overall 1–10 score per question, plus "prepare next".
- Everything stored locally in SQLite.
- **Workshop mechanics:** four agents ship with empty prompts; the app unlocks features as each prompt is pasted.

## 5. Scope: what we are NOT building

- **No accounts or auth** — one local user, zero onboarding.
- **No cloud database** — resumes are personal data; they stay in `data/` on the participant's machine.
- **No scraping behind logins** — public pages via Google Search grounding only.
- **No sample job dataset** — job data is live search only (decided); the fallback for missing descriptions is paste.
- **No comparison across interview attempts** — each review stands alone.
- **No video / body-language analysis, no resume rewriting, no cover letters, no auto-apply.**
- **No code-writing for participants** — the session teaches agent design, not plumbing.

## 6. The signature detail

**The agent rail.** Four chips (🧭 Summary, 🔎 Web Search, 🎙️ Mock Interview, 📝 Review) show *locked → ready →
working*. It makes the invisible multi-agent orchestration visible and is the progress bar for the workshop.

## 7. Success: how we know it worked

- **Primary:** ≥70% of participants finish one voice interview and see a review during the 2-hour session.
- **Secondary:** ≥80% of job search rounds return at least 3 posts with working links.
- **Not measuring:** retention, number of saved jobs.

## 8. Risks

- **Live search variance** — posts close, LinkedIn/Handshake limit public pages, dates are missing. Mitigation: show
  "date unknown", keep only links from real search results, paste-the-description fallback, round-by-round feedback.
- **API quota in a full room** — every participant brings their own key; the README has a pre-session checklist.
- **Room noise and echo** — headphones required; turn-by-turn fallback.

## 9. Handoff

- **For UX:** three tabs, one chat, and a prep page that reads top to bottom as the steps unlock (`ui.md`).
- **For Eng:** code owns status transitions; agents are stateless functions; background agents never block a request
  (`engineering.md`, `db.md`).
