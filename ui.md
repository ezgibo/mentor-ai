# Mentor AI — UX Design Doc

**Status:** Ready for Coding Jam (v1.0)
**Last updated:** October 28, 2026

---

## 1. The design bet

Participants are watching a multi-agent system appear one agent at a time, so the UI makes the agents **visible**:
who is ready, who is locked, who is working in the background. Everything else is a calm, linear workspace that
reveals the next step only when the previous one is done.

## 2. The defining interaction

> The user presses **Start interview**. The 🎙️ chip pulses, the interviewer orb glows while it speaks, and a voice
> says: "Hi, I'm a senior engineer on the platform team at Northwind — thanks for joining. Let's start with your
> Fieldnote Health sync service…". The question tracker lights up **1**. The user answers out loud; their words
> stream into the transcript. Seven questions later the 📝 chip pulses, and score rings fill in one card at a time.

## 3. Screen inventory

One page, three tabs, plus a persistent header:

- **Header:** brand + **agent rail** (4 chips: locked / ready / working).
- **Resume bar:** upload, *Use sample resume*, or the current file with View / Replace.
- **1 · Find Jobs:** chat with Mentor, confirm card, search status, result cards.
- **2 · Saved Jobs:** saved job cards with study and interview status pills.
- **3 · Interview Prep:** one saved job: description → topics → study plan → interview → review.

## 4. Screen-by-screen specs

### Find Jobs
- **Chat:** Mentor bubbles (🧭, left), user bubbles (right), feedback bubbles labelled *Feedback*.
- **Confirm card** (status `collecting` with an understanding): roles, level, location, work mode, must-haves,
  avoid, matching-on — and **Yes, search ✨**. Replying in the composer corrects it instead.
- **Searching:** an inline working banner naming the Web Search Agent and the expected 20–60 s.
- **Results:** up to 5 cards — title, company · location, source / posted date / level badges, summary,
  *Why it fits you*, link (or *Search for post* when the link was not verified). Checkboxes + **Save selected (n)**.
- **Composer:** placeholder and button change with status — *Send* / *Search again* (feedback) / disabled while
  searching. *Try sample request* and *New search*.

### Saved Jobs
- Card per job: title, company, status pills (*Study: not started → Studying → Study done*,
  *Interview: not started → started → done*), *Needs job description* warning, **Prepare →**, remove (×).

### Interview Prep (one job)
1. **Header:** title, company, link, status pills; Mentor's latest message as a bubble.
2. **Job description:** collapsible; when missing, a warning box with a paste textarea (required before step 1).
3. **Know the topics:** *What do I need to know?* → topic rows with 1–5 rating buttons → *Make my study plan* →
   plan items sorted study-first, with priority pill, self-rating, actions, and a done checkbox →
   **I'm done studying →**.
4. **Mock interview:** progress list while preparing (🔎 researching → 🧭 writing → ready); then the question list
   with source badges (*Reported by candidates* / *From the job description* / *From your resume*), the voice mode
   toggle (🎙️ Live conversation / 🔁 Turn by turn), a headphones hint, and **Start interview**.
   - **Stage:** question tracker (1–7), interviewer orb (glows while speaking), mic level meter, live transcript,
     **End interview** (live) or **Record answer → Stop & submit** (turn by turn).
5. **Review:** average score ring, Mentor's summary, *Prepare next* list; per question: score ring, source badge,
   rubric bars (accuracy, depth, structure, communication), collapsible transcript, Strengths / Prepare /
   What a senior interviewer listens for. **Retake with new questions.**

### States everywhere
- **Locked:** amber notice naming the step and the file to paste into; action buttons disabled.
- **Working:** spinner in the button (foreground) or a working banner + pulsing chip (background).
- **Failed:** red inline alert with the friendly error and **Try again / Retry**.
- **Empty:** dashed empty boxes that link to the previous tab.

## 5. The user journey

Open the app → *Use sample resume* → *Try sample request* → Send → Mentor restates → *Yes, search ✨* → watch 🔎 pulse
→ tick two posts → *Save selected* → Saved Jobs → *Prepare →* → *What do I need to know?* → rate 4 topics → plan →
*I'm done studying* → research and writing (~1 min) → put on headphones → *Start interview* → 7 questions →
review appears → read *Prepare next*.

## 6. Component & visual notes

- **Type:** Inter for UI, JetBrains Mono for badges.
- **Color:** light by default, dark via `prefers-color-scheme`. Accent indigo; green = ready/done; amber =
  locked/needs action; red = errors.
- **Motion:** chip pulse while working, orb glow while speaking; all disabled under `prefers-reduced-motion`.
- **Microcopy:** Mentor speaks in first person; buttons are verbs (*Yes, search ✨*, *I'm done studying →*).

## 7. Accessibility & inclusion

- Keyboard reachable controls; `Cmd/Ctrl + Enter` sends in the composer.
- `aria-live` on the chat, resume bar, and live transcript; rating buttons expose `aria-pressed`.
- Text transcript of both sides of the interview; turn-by-turn mode for people who prefer not to be interrupted.
- Mobile: single column below 640 px.

## 8. What we are NOT designing

- No routing / deep links, no settings page (settings live in `.env`), no history of past searches beyond the latest.
- No video tile or camera — voice only.

## 9. Handoff to engineering

- The frontend renders the status it gets from the API and polls only while a background agent works.
- Never redraw the prep page while an interview is running.
- Mic → 16 kHz PCM via an AudioWorklet; playback at 24 kHz; WAV encoding in the browser for the fallback.
