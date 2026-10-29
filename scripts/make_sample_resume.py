"""Builds samples/sample_resume.pdf — a fictional resume for following along without your own.

Organizers only (participants never need to run this):
    uv run --with fpdf2 python scripts/make_sample_resume.py
"""

from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parent.parent / "samples" / "sample_resume.pdf"

NAME = "Jordan Rivera"
CONTACT = "Brooklyn, NY  |  jordan.rivera@example.com  |  (555) 010-2468  |  github.com/jordan-rivera-example"

SECTIONS = [
    ("Education", [
        ("B.S. Computer Science  |  Kings County University (fictional), Brooklyn, NY", "Expected May 2027", [
            "Minor in Data Science. GPA 3.7/4.0. Coursework: Data Structures, Algorithms, Databases, Operating Systems, Machine Learning, Distributed Systems.",
            "Teaching assistant, Data Structures (Spring 2026): led weekly labs for 35 students.",
        ]),
    ]),
    ("Experience", [
        ("Software Engineering Intern  |  Fieldnote Health (fictional), New York, NY", "Jun 2026 - Aug 2026", [
            "Built a FastAPI service that syncs appointment data from 3 clinic systems into PostgreSQL; cut nightly sync time from 40 to 9 minutes.",
            "Added pytest coverage to a legacy billing module (12% to 71%) and caught 4 rounding bugs before release.",
            "Containerized the service with Docker and wrote the GitHub Actions pipeline that deploys it to Google Cloud Run.",
        ]),
        ("Data Engineering Intern  |  Harborline Logistics (fictional), Jersey City, NJ", "Jun 2025 - Aug 2025", [
            "Wrote Python + SQL ETL jobs feeding a BigQuery dashboard used by 20 operations managers.",
            "Replaced a manual Excel report with an automated daily job, saving the team about 5 hours per week.",
        ]),
    ]),
    ("Projects", [
        ("TransitPulse  |  real-time NYC subway delay tracker", "2026", [
            "React + TypeScript frontend and Node.js backend consuming the MTA GTFS-realtime feed; ~1,200 monthly users.",
            "Cached feed snapshots in Redis to keep p95 API latency under 150 ms.",
        ]),
        ("StudyBuddy  |  RAG study assistant (campus hackathon winner)", "2025", [
            "Python app that answers questions over lecture PDFs using Gemini and a vector index; won Best Use of AI.",
            "Designed the chunking and evaluation set (50 Q&A pairs) used to compare retrieval settings.",
        ]),
        ("Course Scheduler  |  constraint-based class planner", "2024", [
            "Java CLI that builds conflict-free semesters with backtracking search; used by 60 classmates.",
        ]),
    ]),
    ("Skills", [
        ("", "", [
            "Languages: Python, Java, TypeScript, SQL, C",
            "Backend & data: FastAPI, Node.js, PostgreSQL, Redis, BigQuery, REST APIs",
            "Cloud & tools: Docker, Google Cloud Run, GitHub Actions, Git, Linux",
            "AI/ML: scikit-learn, pandas, Gemini API, retrieval-augmented generation",
        ]),
    ]),
]


def build() -> None:
    pdf = FPDF(format="Letter")
    pdf.set_margins(18, 16, 18)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, NAME, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9.5)
    pdf.cell(0, 6, CONTACT, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, "Sample resume for the Mentor AI Coding Jam. This person and these companies are fictional.",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)

    for title, entries in SECTIONS:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 7, title.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(1.5)
        for heading, dates, bullets in entries:
            if heading:
                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(width - 40, 6, heading)
                pdf.set_font("Helvetica", "", 9.5)
                pdf.cell(40, 6, dates, align="R", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9.5)
            for bullet in bullets:
                pdf.set_x(pdf.l_margin + 3)
                pdf.multi_cell(width - 3, 5, f"- {bullet}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
