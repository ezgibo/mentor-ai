# Resume Tailor — UX Design Doc

**Designer:** Senior Product Designer
**Status:** Ready for Review (v1.0)
**Last updated:** October 16, 2026

---

## 1. The design bet

We are betting that user trust in AI resume tailoring is won or lost in the **comparison clarity and copy velocity**. Rather than designing a bloated multi-step wizard or full document canvas, we invest 80% of our design effort into a lightning-fast, side-by-side workspace: frictionless dual text areas on top, leading directly into crisp, high-contrast upgraded bullet cards below with instant 1-click clipboard actions.

## 2. The defining interaction

> User pastes their existing bullets on the left, pastes the job description on the right, and clicks "Tailor Bullets ✨". The button subtly dips on click and activates a pulsing gradient border. Within 2.5 seconds, the results area smoothly slides into view with 3 to 5 tailored cards animating upward sequentially in a 60ms staggered wave. Each card displays an action-verb headline, quantifiable impact phrasing, and keyword match badges. The user clicks "Copy All" — the button transforms with a satisfying green checkmark ("Copied to clipboard!") and soundless confidence. Total elapsed time: under 3 seconds.

## 3. Screen inventory

v1 is intentionally a **single-screen web application**:

- **Tailor Workspace (Main View)** — The unified workspace containing header controls, dual input textboxes, action triggers, and the live tailored results cards.

## 4. Screen-by-screen specs

### Tailor Workspace (Main View)

**Purpose:** Provide an intuitive, distraction-free environment for users to paste raw materials and instantly inspect/copy tailored bullet points.

**Layout (Top to Bottom):**
1. **Header & Utility Bar**
   - Brand logo and title: `Resume Tailor`
   - Subtitle: "Turn raw bullets & job requirements into recruiter-ready achievements in seconds."
   - Quick Action: `Try Sample` button (prefills realistic input for immediate demonstration).
2. **Dual Input Grid (Side-by-Side on Desktop, Stacked on Mobile)**
   - **Left Panel:** "Your Current Resume / Bullets"
     - Large multiline text area with clear placeholder: *"e.g., Worked on backend services and made API faster..."*
     - Live character count and clear button.
   - **Right Panel:** "Target Job Posting"
     - Large multiline text area with placeholder: *"Paste the job requirements, responsibilities, or role description here..."*
     - Live character count and clear button.
3. **Action Bar**
   - Centered primary CTA button: `Tailor Bullets ✨` (large, high-contrast, prominent).
   - Keyboard shortcut prompt: `Cmd + Enter` / `Ctrl + Enter`.
4. **Results Section (Appears directly below inputs upon generation)**
   - Section Header: "Tailored Resume Bullets" with count tag (`3 Bullets Generated`).
   - Group Action: `Copy All` button with clipboard icon.
   - **Tailored Bullet Cards List:**
     - Each card displays:
       - Upgraded bullet text in clean, legible typography.
       - Keyword match badges (e.g., `⚡ Distributed Systems`, `🎯 Latency Optimization`).
       - Individual `Copy` button in card top-right corner.

**Key interactions:**
- Click `Try Sample` → Instantly fills both text boxes with sample data and flashes a subtle highlight.
- Press `Cmd + Enter` inside any text box → Submits the form immediately.
- Click `Copy` on an individual card → Icon morphs to a green checkmark with text "Copied!", reverting after 2 seconds.
- Click `Copy All` → Copies all generated bullets as formatted bulleted text to system clipboard.

**States:**
- **Default / Empty state:** Inputs are empty. The results pane displays a tasteful placeholder illustration or empty card with light dashed borders: *"Paste your resume and job description above to generate tailored bullets."*
- **Loading:** Primary button shows animated spinner and label *"Tailoring your bullets..."*. Results container displays 3 animated shimmer skeleton cards. Inputs are set to read-only during generation to prevent conflicting state.
- **Error:** If API call fails or input is blank, a clean inline alert banner slides down above the inputs: *"Please provide both your resume text and the job description to continue."* or *"Could not connect to AI service. Please check your connection and retry."*
- **Edge / "Too Much Text":** Inputs enforce a reasonable max limit (e.g., 10,000 characters) with a soft warning badge if exceeded. Text areas have internal scrolling so the page layout remains stable.

## 5. The user journey

User lands on the page at 10:30 PM. The screen is clean, modern, and uncluttered. There is no sign-in modal, no cookie banner, and no distraction. They see the two large text boxes: "Your Current Resume" and "Target Job Posting". 

They copy 3 rough bullets from their old resume and paste them into the left box, then copy the responsibilities section from a LinkedIn job post into the right box. They press `Cmd + Enter`. The button ripples into a loading state, and 2 seconds later three polished bullet cards glide onto the screen. 

They read the first bullet: *"Architected distributed REST endpoints using FastAPI, reducing p95 request latency by 42% across high-concurrency workloads."* Below it, they notice two green badges: `FastAPI` and `Latency Optimization` matching the job's requirements. The user smiles, clicks `Copy All`, and pastes them straight into their resume Google Doc. Total time: 35 seconds.

## 6. Component & visual notes

- **Typography:** Modern, crisp sans-serif font (Inter or Plus Jakarta Sans via Google Fonts) for high readability at small sizes. Clean monospace font (JetBrains Mono or SF Mono) for keyword badges.
- **Color Palette:** Professional dark-mode aesthetic with deep obsidian slate background (`#0B0F19`), surface card containers (`#151C2C`), crisp text (`#F8FAFC`), and subtle emerald/violet gradient accents (`#10B981` / `#6366F1`) for highlights and copy states.
- **Motion:** Subtle spring easing (`cubic-bezier(0.16, 1, 0.3, 1)`). Staggered card entrance: card 1 at 0ms, card 2 at 60ms, card 3 at 120ms. Button press depth of `transform: scale(0.98)`.
- **The Signature Visual:** The **Tailored Bullet Card** featuring a left accent border, high-contrast typography, and floating pill badges for matched keywords.
- **Microcopy Voice:** Confident, concise, and helpful:
  - "Tailor Bullets ✨"
  - "Analyzing job keywords..."
  - "Copied to clipboard!"
  - "Try Sample"

## 7. Accessibility & inclusion

- **Keyboard Navigation:** Full Tab and Shift-Tab navigation across both textareas, the sample button, the tailor button, and all copy buttons.
- **Screen Reader Support:** ARIA live regions (`aria-live="polite"`) on the results container so new bullets are announced immediately upon generation.
- **Color Contrast:** All text elements adhere to WCAG 2.1 AA standards (minimum 4.5:1 contrast against dark slate surfaces).
- **Reduced Motion:** Respects `prefers-reduced-motion` media query by disabling staggered entrance animations and shimmer effects.

## 8. What we are NOT designing

- **No multi-step wizard screens** — Everything lives on one direct workspace.
- **No drag-and-drop PDF dropzones** — Direct paste only to ensure 100% reliable input.
- **No rich-text WYSIWYG formatting toolbar** — No bold/italic/font controls; keep input clean and raw.
- **No modal settings or account profile views** — Zero configuration required.
- **No full resume layout previewer** — We focus strictly on the generated bullet points.

## 9. Open design questions

- [ ] Should "Copy All" format bullets using markdown hyphens (`- `) or standard bullet symbols (`• `)?
- [ ] On mobile devices (<640px), should the dual inputs collapse into a 2-tab segmented control ("Resume" / "Job") to preserve vertical space?

## 10. Handoff to engineering

The layout must transition smoothly between desktop (side-by-side dual textareas with equal 50/50 flex distribution) and mobile (stacked or tabbed view). The copy-to-clipboard functionality must use the modern `navigator.clipboard.writeText` API with fallback to `document.execCommand` for cross-browser safety.
