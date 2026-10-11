"""Grade & CGPA Calculator with Report Card Generator (Streamlit)."""
import io
from datetime import date

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# ---------- grading rules (10-point scale; edit to match your college) ----------
GRADE_SCALE = [(90, "O", 10), (80, "A+", 9), (70, "A", 8), (60, "B+", 7),
               (50, "B", 6), (40, "C", 5), (0, "F", 0)]
MAX_SEMS = 8


def grade_for(marks):
    for cutoff, letter, points in GRADE_SCALE:
        if marks >= cutoff:
            return letter, points
    return "F", 0


def clean(df):
    """Keep only complete, valid rows."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["Subject", "Credits", "Marks"])
    df = df.dropna(subset=["Subject", "Credits", "Marks"]).copy()
    df = df[df["Subject"].astype(str).str.strip() != ""]
    df["Credits"] = df["Credits"].astype(float)
    df["Marks"] = df["Marks"].astype(float).clip(0, 100)
    return df


def grade_table(df):
    df = clean(df)
    g = df["Marks"].map(grade_for)
    df["Grade"] = [x[0] for x in g]
    df["Points"] = [x[1] for x in g]
    return df


def sgpa(df):
    return (df["Credits"] * df["Points"]).sum() / df["Credits"].sum() if len(df) else 0.0


def cgpa(sem_tables):
    allr = pd.concat(sem_tables, ignore_index=True) if sem_tables else pd.DataFrame()
    return sgpa(allr) if len(allr) else 0.0


def classification(c, backlogs):
    if backlogs:
        return "Pass with backlogs"
    if c >= 8.5:
        return "First Class with Distinction"
    if c >= 6.5:
        return "First Class"
    if c >= 5.0:
        return "Second Class"
    return "Pass Class"


def build_pdf(student, sems):
    """sems: {semester_number: graded DataFrame}. Returns PDF bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=16*mm, bottomMargin=16*mm, title="Report Card")
    ss = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=ss["Title"], textColor=colors.HexColor("#1b3a5c"), fontSize=22)
    h = ParagraphStyle("h", parent=ss["Heading3"], textColor=colors.HexColor("#1b3a5c"))
    navy, light = colors.HexColor("#1b3a5c"), colors.HexColor("#eef3f8")

    els = [Paragraph("Academic Report Card", title), Spacer(1, 4*mm)]
    info = [["Student", student["name"], "Roll No.", student["roll"]],
            ["Course", student["course"], "Date", date.today().strftime("%d %b %Y")]]
    t = Table(info, colWidths=[24*mm, 62*mm, 24*mm, 62*mm])
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                           ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                           ("BOX", (0, 0), (-1, -1), 0.6, navy), ("BACKGROUND", (0, 0), (-1, -1), light),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    els += [t, Spacer(1, 6*mm)]

    for n, df in sems.items():
        els.append(Paragraph(f"Semester {n}  -  SGPA {sgpa(df):.2f}", h))
        rows = [["Subject", "Credits", "Marks", "Grade", "Points"]]
        rows += [[r.Subject, f"{r.Credits:g}", f"{r.Marks:g}", r.Grade, r.Points] for r in df.itertuples()]
        tb = Table(rows, colWidths=[80*mm, 22*mm, 22*mm, 22*mm, 22*mm], repeatRows=1)
        style = [("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                 ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                 ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b8c6d6")),
                 ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light])]
        style += [("TEXTCOLOR", (3, i), (3, i), colors.red) for i, r in enumerate(df.itertuples(), 1) if r.Grade == "F"]
        tb.setStyle(TableStyle(style))
        els += [tb, Spacer(1, 5*mm)]

    allg = pd.concat(sems.values(), ignore_index=True)
    c = cgpa(list(sems.values()))
    backlogs = int((allg["Grade"] == "F").sum())
    summ = Table([["Overall CGPA", f"{c:.2f} / 10"],
                  ["Total credits", f"{allg['Credits'].sum():g}"],
                  ["Backlogs", str(backlogs)],
                  ["Result", classification(c, backlogs)]], colWidths=[50*mm, 70*mm])
    summ.setStyle(TableStyle([("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("BOX", (0, 0), (-1, -1), 1, navy),
                              ("BACKGROUND", (0, 0), (-1, -1), light), ("FONTSIZE", (0, 0), (-1, 0), 13),
                              ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    els += [summ, Spacer(1, 6*mm)]
    scale = "Grade scale:  " + ",  ".join(f"{g} = {m}+ marks ({p} pts)" for m, g, p in GRADE_SCALE[:-1]) + ",  F = below 40"
    els.append(Paragraph(scale, ParagraphStyle("s", parent=ss["Normal"], fontSize=8, textColor=colors.grey)))
    doc.build(els)
    return buf.getvalue()


# ---------------- UI ----------------
def main():
    st.set_page_config(page_title="CGPA Calculator", page_icon="🎓", layout="centered")
    st.title("🎓 Grade & CGPA Calculator")
    st.caption("Enter your marks, see your SGPA and CGPA, then download a report card.")

    st.subheader("1. Student details")
    name = st.text_input("Full name")
    c1, c2 = st.columns(2)
    roll = c1.text_input("Roll number")
    course = c2.text_input("Course", placeholder="B.Tech Computer Science")

    st.subheader("2. Subjects and marks")
    n = st.number_input("Number of semesters", 1, MAX_SEMS, 1)
    cfg = {"Subject": st.column_config.TextColumn("Subject", required=True),
           "Credits": st.column_config.NumberColumn("Credits", min_value=1, max_value=10, step=1, default=3),
           "Marks": st.column_config.NumberColumn("Marks /100", min_value=0, max_value=100, step=1)}
    graded = {}
    tabs = st.tabs([f"Sem {i}" for i in range(1, int(n) + 1)])
    for i, tab in enumerate(tabs, 1):
        with tab:
            start = pd.DataFrame({"Subject": ["", "", ""], "Credits": [3.0, 3.0, 3.0], "Marks": [None] * 3})
            edited = st.data_editor(start, key=f"sem{i}", num_rows="dynamic", column_config=cfg,
                                    use_container_width=True, hide_index=True)
            g = grade_table(edited)
            if len(g):
                graded[i] = g
                st.dataframe(g, hide_index=True, use_container_width=True)
                st.metric(f"Semester {i} SGPA", f"{sgpa(g):.2f}")
            else:
                st.info("Add a subject name, credits and marks to see grades.")

    st.subheader("3. Results")
    if not graded:
        st.info("Your results will appear here.")
        return
    allg = pd.concat(graded.values(), ignore_index=True)
    c = cgpa(list(graded.values()))
    backlogs = int((allg["Grade"] == "F").sum())
    a, b, d = st.columns(3)
    a.metric("CGPA", f"{c:.2f}")
    b.metric("Credits", f"{allg['Credits'].sum():g}")
    d.metric("Backlogs", backlogs)
    st.success(classification(c, backlogs))
    st.caption(f"Approx. percentage (CGPA x 9.5): {c * 9.5:.1f}%")

    if len(graded) > 1:
        st.line_chart(pd.Series({f"Sem {k}": sgpa(v) for k, v in graded.items()}, name="SGPA"))

    st.subheader("4. Report card")
    if not name.strip():
        st.warning("Enter the student name to create the report card.")
        return
    pdf = build_pdf({"name": name.strip(), "roll": roll.strip() or "-", "course": course.strip() or "-"}, graded)
    st.download_button("Download report card (PDF)", pdf, file_name=f"report_card_{name.strip().replace(' ', '_')}.pdf",
                       mime="application/pdf", type="primary")


if __name__ == "__main__":
    main()
