# Resume Tailor — Product Design Doc

**Author:** Staff Product Manager
**Status:** Ready for Review (v1.0)
**Last updated:** October 16, 2026
**One-liner:** Turn raw resume bullets and a target job description into tailored, high-impact bullet points in under three seconds.

---

## 1. The user & the moment

Who is this for, and what are they doing/feeling **right before** they open the app?

- **Who:** An active job applicant (developer, designer, or knowledge worker) who has a master resume and is applying to multiple roles each week.
- **When:** 10:30 PM on a Tuesday. They just found a job posting they actually want on LinkedIn. They know their generic resume bullets won't make it past recruiter screening, but they dread spending 45 minutes manually rewriting bullet points for the fifth time today.
- **Why now:** Recruiters spend ~6 seconds scanning resumes and modern ATS filters discard mismatched keyword applications instantly. Manually tailoring bullet points is the highest-leverage, most tedious step in job applications.

## 2. The contract (I/O)

What does the user give, and what do they get back?

- **Input:** Two clean text boxes on a single screen:
  1. Pasted existing resume bullet points (or raw experience text).
  2. Pasted job posting text (job description / requirements).
- **Output:** 3–5 tailored, high-impact resume bullets rewritten using the Google X-Y-Z formula ("Accomplished [X], as measured by [Y], by doing [Z]"), specifically incorporating the job description's critical keywords and skills.
- **The loop:** Paste raw bullets + job description → Click "Tailor Bullets" → Receive upgraded bullets with keyword badges → Click "Copy All" (or copy individual bullets) → Paste directly into their resume document.

## 3. The magical moment

The single sentence the user would say to a friend after using this for the first time:

> "This turned my sloppy bullet point into something that sounds like a senior staff engineer wrote it, and it matched the exact keywords from the job post in two seconds."

## 4. Scope: what we ARE building (v1)

The minimum surface area that delivers the magic:

- Single-page application with side-by-side (or stacked) dual inputs: Resume text and Job Description text.
- One-click sample loader ("Load Example") so any user can experience the magic in 2 seconds without searching for their resume.
- "Tailor Bullets" action button with immediate, smooth loading feedback.
- Tailored results list displaying 3–5 polished bullet points with action verbs and quantifiable impact placeholders.
- Keyword match indicator tags highlighting which skills from the job description were infused into each bullet.
- 1-click "Copy All" and individual "Copy" buttons with instant visual confirmation ("Copied!").

## 5. Scope: what we are NOT building

The cuts are the product. Everything below is explicitly excluded to preserve a tight 45-minute build and zero-friction user experience:

- **No PDF or Word document uploading/parsing** — Text parsing libraries add failure modes, parsing errors, and heavy dependencies. Paste-only is bulletproof.
- **No full resume layout editor or template builder** — Users already have their resume document in Google Docs or Word. We polish the highest-stakes text, not the margins.
- **No cover letter generation** — A distraction from the core value proposition of bullet-point optimization.
- **No user authentication, logins, or cloud accounts** — Zero friction; opens instantly and works on first visit.
- **No cloud database storage** — No server-side persistence of personal resumes or job descriptions. Completely private.
- **No PDF/DOCX export** — Copy-to-clipboard is faster, more reliable, and fits existing jobseeker workflows.
- **No interview prep or mock questions** — Phase 2 feature; out of scope for v1.

## 6. The signature detail

**The Keyword & Impact Badges.** Alongside each upgraded bullet, the UI displays subtle pill tags showing the exact match to the job description (e.g., `Matched: Distributed Systems`, `Metric: Latency Reduction`). This immediately proves to the jobseeker *why* the bullet is better and builds immediate trust that the AI didn't just hallucinate generic buzzwords.

## 7. Success: how we know it worked

- **Primary:** ≥75% of users who generate tailored bullets click "Copy" (or "Copy All") to take the bullets into their resume.
- **Secondary:** Median end-to-end time from clicking "Tailor Bullets" to render is < 3.0 seconds.
- **What we're NOT measuring:** Total session duration, bounce rates, or recurring account signups.

## 8. Open questions

- [ ] Does `gemini-2.5-flash` produce better quantified bullets with few-shot examples or direct structured output schemas?
- [ ] What is the optimal fallback behavior if the user provides very sparse input (e.g., only 1 sentence)?

## 9. Handoff

- **For UX:** The dual text inputs and the resulting tailored cards must fit naturally on a single viewport without feeling crowded, with the "Copy" action being effortless and unmistakable.
- **For Eng:** Gemini latency under 2.5 seconds using structured JSON output is the critical requirement; anything longer degrades the perceived "instant upgrade" feeling.
