from datetime import datetime
from io import BytesIO
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Domain, Indicator, Assessment, Action, AuditLog, Organization
from ..security import current_user
from ..services import maturity

router = APIRouter(prefix="/api/reports", tags=["Reports & Analytics"])

def _domain_scorecards(db: Session, org_id: int):
    domains = db.query(Domain).order_by(Domain.code).all()
    cards = []
    for d in domains:
        indicator_ids = [i.id for i in d.indicators]
        if not indicator_ids:
            cards.append({"code": d.code, "name": d.name, "average_score": None, "maturity": "Not Assessed", "assessed": 0, "total_indicators": 0})
            continue
        latest_scores = {}
        rows = (db.query(Assessment)
                .filter(Assessment.organization_id == org_id, Assessment.indicator_id.in_(indicator_ids))
                .order_by(Assessment.assessed_at.asc()).all())
        for r in rows:
            latest_scores[r.indicator_id] = r.score
        scores = list(latest_scores.values())
        avg = round(sum(scores) / len(scores), 1) if scores else None
        cards.append({
            "code": d.code, "name": d.name,
            "average_score": avg,
            "maturity": maturity(int(avg)) if avg is not None else "Not Assessed",
            "assessed": len(scores),
            "total_indicators": len(indicator_ids),
        })
    return cards

@router.get("/scorecards")
def scorecards(db: Session = Depends(get_db), user=Depends(current_user)):
    return _domain_scorecards(db, user.organization_id)

def _finding_text(c):
    if c["average_score"] is None:
        return "Not yet assessed — schedule baseline assessment"
    if c["maturity"] == "Critical / Initial":
        return "Immediate attention required — significant gaps"
    if c["maturity"] == "Needs Improvement":
        return "Below institutional standard — improvement needed"
    if c["maturity"] == "Developing":
        return "Progressing — reinforce process consistency"
    if c["maturity"] == "Proficient":
        return "Meets institutional standard"
    return "Exceeds institutional standard — sustain practice"

@router.get("/findings-register")
def findings_register(db: Session = Depends(get_db), user=Depends(current_user)):
    cards = _domain_scorecards(db, user.organization_id)
    return [{**c, "finding": _finding_text(c)} for c in cards]

@router.get("/capa-plan")
def capa_plan(db: Session = Depends(get_db), user=Depends(current_user)):
    cards = _domain_scorecards(db, user.organization_id)
    assessed_cards = [c for c in cards if c["average_score"] is not None]
    critical = [c for c in assessed_cards if c["maturity"] == "Critical / Initial"]
    needs_imp = [c for c in assessed_cards if c["maturity"] == "Needs Improvement"]

    open_actions = (db.query(Action)
                     .filter(Action.organization_id == user.organization_id, Action.status != "Completed")
                     .all())

    bucket_30, bucket_60, bucket_90 = [], [], []
    for a in open_actions:
        item = {"domain_code": a.domain_code, "title": a.title, "priority": a.priority, "status": a.status}
        if a.priority == "High":
            bucket_30.append(item)
        elif a.priority == "Medium":
            bucket_60.append(item)
        else:
            bucket_90.append(item)

    actioned_codes = {a.domain_code for a in open_actions}
    for c in critical:
        if c["code"] not in actioned_codes:
            bucket_30.append({"domain_code": c["code"], "title": f"Log corrective action for {c['name']}",
                               "priority": "High", "status": "Not Started"})
    for c in needs_imp:
        if c["code"] not in actioned_codes:
            bucket_60.append({"domain_code": c["code"], "title": f"Log corrective action for {c['name']}",
                               "priority": "Medium", "status": "Not Started"})

    return {"window_0_30": bucket_30, "window_31_60": bucket_60, "window_61_90": bucket_90}

@router.get("/gap-analysis")
def gap_analysis(threshold: int = 60, db: Session = Depends(get_db), user=Depends(current_user)):
    cards = _domain_scorecards(db, user.organization_id)
    gaps = [c for c in cards if c["average_score"] is not None and c["average_score"] < threshold]
    unassessed = [c for c in cards if c["average_score"] is None]
    open_actions_by_domain = dict(
        db.query(Action.domain_code, func.count(Action.id))
        .filter(Action.organization_id == user.organization_id, Action.status != "Completed")
        .group_by(Action.domain_code).all()
    )
    for g in gaps:
        g["open_actions"] = open_actions_by_domain.get(g["code"], 0)
    return {"threshold": threshold, "gaps": gaps, "unassessed_domains": unassessed}

@router.get("/audit-logs")
def audit_logs(limit: int = 100, db: Session = Depends(get_db), user=Depends(current_user)):
    rows = (db.query(AuditLog)
            .filter(AuditLog.organization_id == user.organization_id)
            .order_by(AuditLog.id.desc()).limit(limit).all())
    return [{
        "id": r.id, "action": r.action, "entity": r.entity, "entity_id": r.entity_id,
        "details": r.details, "user_id": r.user_id, "created_at": r.created_at
    } for r in rows]

@router.get("/audit-report.pdf")
def audit_report_pdf(db: Session = Depends(get_db), user=Depends(current_user)):
    from pathlib import Path
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.barcharts import HorizontalBarChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_CENTER

    org = db.get(Organization, user.organization_id)
    cards = _domain_scorecards(db, user.organization_id)
    open_actions = (db.query(Action)
                     .filter(Action.organization_id == user.organization_id, Action.status != "Completed")
                     .order_by(Action.priority.desc()).all())

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#07152d")
    gold = colors.HexColor("#c9a24b")

    elements = []

    logo_path = Path(__file__).resolve().parent.parent / "static" / "assets" / "gvrm_logo.png"
    if logo_path.exists():
        header = Table(
            [[
                RLImage(
                    str(logo_path),
                    width=65,
                    height=65
                ),
                Paragraph(
                    f"<font color='#07152d'><b>{org.name}</b></font><br/>"
                    f"<font size=9 color='#666666'>"
                    f"Institutional Excellence &amp; Transformation — GVRM Solutions"
                    f"</font>",
                    styles["Normal"]
                )
            ]],
            colWidths=[80, 385],
            rowHeights=[80]
        )

        header.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ])
        )

        elements.append(header)

    else:
        elements.append(
            Paragraph(
                f"<font color='#07152d'><b>{org.name}</b></font>",
                styles["Title"]
            )
        )

    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            "Institutional Excellence — Audit Report (A-Z, 52-Domain Framework)",
            styles["Heading3"]
        )
    )

    elements.append(
        Paragraph(
            f"Generated: {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}",
            styles["Normal"]
        )
    )
    detail_lines = []

    if org.address:
        detail_lines.append(org.address)

    if org.phone:
        detail_lines.append(f"Phone: {org.phone}")

    if org.principal_name:
        detail_lines.append(f"Principal: {org.principal_name}")

    if org.academic_year:
        detail_lines.append(f"Academic Year: {org.academic_year}")

    if org.student_strength:
        detail_lines.append(f"Strength: {org.student_strength}")

    if detail_lines:
        elements.append(Spacer(1, 4))
        elements.append(
            Paragraph(
                " &nbsp;|&nbsp; ".join(detail_lines),
                styles["Normal"]
            )
        )

    elements.append(Spacer(1, 14))

    scored = [
        c for c in cards
        if c["average_score"] is not None
    ]

    overall = (
        round(
            sum(c["average_score"] for c in scored) / len(scored),
            1
        )
        if scored else 0
    )

    elements.append(
        Paragraph(
            f"<b>Overall institutional score: {overall} / 5</b>",
            styles["Heading2"]
        )
    )

    elements.append(
        Paragraph(
            f"Domains assessed: {len(scored)} of {len(cards)} "
            f"&nbsp;&nbsp; Open corrective actions: {len(open_actions)}",
            styles["Normal"]
        )
    )

    elements.append(Spacer(1, 14))

    data = [
        ["Code", "Domain", "Avg Score", "Maturity", "Assessed / Total"]
    ]
    for c in cards:
        data.append([
            Paragraph(
                str(c["code"]),
                styles["Normal"]
            ),
            Paragraph(
                str(c["name"]),
                styles["Normal"]
            ),
            Paragraph(
                str(c["average_score"])
                if c["average_score"] is not None else "—",
                styles["Normal"]
            ),
            Paragraph(
                str(c["maturity"]),
                styles["Normal"]
            ),
            Paragraph(
                f"{c['assessed']}/{c['total_indicators']}",
                styles["Normal"]
            )
        ])

        maturity_colors = {
        "Critical / Initial": colors.HexColor("#f4a3a3"),
        "Needs Improvement": colors.HexColor("#ffcc99"),
        "Developing": colors.HexColor("#fff2a8"),
        "Proficient": colors.HexColor("#b9e6b9"),
        "Excellent / Advanced": colors.HexColor("#7fcf7f"),
    }
        tbl = Table(
        data,
        colWidths=[35, 190, 55, 95, 110],
        repeatRows=1,
        hAlign="LEFT"
    )
        tbl_style = [
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f5f6fa")]),
    ]

    for i, c in enumerate(cards, start=1):
        cell_color = maturity_colors.get(
            c["maturity"],
            colors.white
        )

        tbl_style.append(
            ("BACKGROUND", (3, i), (3, i), cell_color)
        )

        tbl_style.append(
            ("FONTNAME", (3, i), (3, i), "Helvetica-Bold")
        )
    tbl.setStyle(TableStyle(tbl_style))
    elements.append(tbl)
    elements.append(Spacer(1, 8))

legend_data = [[
    Paragraph(
        f"<font backColor='#f4a3a3'>&nbsp;&nbsp;&nbsp;</font> Critical/Initial",
        styles["Normal"]
    ),
    Paragraph(
        f"<font backColor='#ffcc99'>&nbsp;&nbsp;&nbsp;</font> Needs Improvement",
        styles["Normal"]
    ),
    Paragraph(
        f"<font backColor='#fff2a8'>&nbsp;&nbsp;&nbsp;</font> Developing",
        styles["Normal"]
    ),
    Paragraph(
        f"<font backColor='#b9e6b9'>&nbsp;&nbsp;&nbsp;</font> Proficient",
        styles["Normal"]
    ),
    Paragraph(
        f"<font backColor='#7fcf7f'>&nbsp;&nbsp;&nbsp;</font> Excellent/Advanced",
        styles["Normal"]
    ),
]]

legend = Table(
    legend_data,
    colWidths=[95, 105, 85, 80, 105]
)

legend.setStyle(TableStyle([
    ("FONTSIZE", (0, 0), (-1, -1), 7),
    ("TOPPADDING", (0, 0), (-1, -1), 2)
]))

elements.append(legend)
elements.append(Spacer(1, 20))

# ---- Graphical presentation: maturity distribution + domain score bar chart ----
elements.append(
        Paragraph(
            f"<b>Overall institutional score: {overall} / 5</b>",
            styles["Heading2"]
        )
    )
elements.append(Spacer(1, 6))

assessed_cards = [
    c for c in cards
    if c["average_score"] is not None
]

dist_order = [
    "Critical / Initial",
    "Needs Improvement",
    "Developing",
    "Proficient",
    "Excellent / Advanced",
    "Not Assessed"
]

dist_colors = [
    colors.HexColor("#e57373"),
    colors.HexColor("#ffb04d"),
    colors.HexColor("#f0d030"),
    colors.HexColor("#6fbf6f"),
    colors.HexColor("#3d9e3d"),
    colors.HexColor("#bbbbbb")
]

dist_counts = [
    len([c for c in cards if c["maturity"] == m])
    for m in dist_order
]

pie_drawing = Drawing(240, 170)
pie = Pie()
pie.x = 15
pie.y = 15
pie.width = 130
pie.height = 130
pie.data = [max(v, 0.0001) for v in dist_counts]
pie.labels = [
    f"{m.split(' / ')[0]} ({v})"
    for m, v in zip(dist_order, dist_counts)
]
pie.simpleLabels = 0
pie.sideLabels = 1

for i, c in enumerate(dist_colors):
    pie.slices[i].fillColor = c
    pie.slices[i].fontSize = 6

pie_drawing.add(pie)
pie_drawing.add(
    String(
        15, 158,
        "Maturity Distribution (52 Domains)",
        fontSize=8,
        fontName="Helvetica-Bold"
    )
)
elements.append(pie_drawing)
elements.append(Spacer(1, 10))

scored_sorted = sorted(
    assessed_cards,
    key=lambda c: c["average_score"]
)[:20]

if scored_sorted:
    bar_height = max(90, 16 * len(scored_sorted))
    bar_drawing = Drawing(420, bar_height + 30)

    bar_drawing.add(
        String(
            0,
            bar_height + 14,
            "Domain-wise Average Score (lowest-scoring, up to 20 shown)",
            fontSize=8,
            fontName="Helvetica-Bold"
        )
    )

    chart = HorizontalBarChart()
    chart.x = 90
    chart.y = 10
    chart.width = 300
    chart.height = bar_height
    chart.data = [[c["average_score"] for c in scored_sorted]]
    chart.categoryAxis.categoryNames = [
        f"{c['code']} {c['name'][:22]}"
        for c in scored_sorted
    ]
    chart.categoryAxis.labels.fontSize = 6
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 5
    chart.valueAxis.valueStep = 1
    chart.bars[0].fillColor = colors.HexColor("#1a2744")

    for i, c in enumerate(scored_sorted):
        chart.bars[(0, i)].fillColor = maturity_colors.get(
            c["maturity"],
            colors.HexColor("#1a2744")
        )

    bar_drawing.add(chart)
    elements.append(bar_drawing)

else:
    elements.append(
        Paragraph(
            "No domains scored yet — bar chart will appear once assessments begin.",
            styles["Normal"]
        )
    )

elements.append(Spacer(1, 20))

elements.append(
    Paragraph(
        "<b>Open Corrective Actions (CAPA)</b>",
        styles["Heading2"]
    )
)

if open_actions:
    from datetime import datetime as _dt

    sla_days_map = {
        "High": 1,
        "Medium": 30,
        "Low": 90
    }

    urgency_colors = {
        "done": colors.HexColor("#b9e6b9"),
        "ontrack": colors.HexColor("#c8e6c9"),
        "duesoon": colors.HexColor("#ffe6a8"),
        "overdue": colors.HexColor("#f4a3a3"),
    }

    def _urgency_key(a):
        if a.status == "Completed":
            return "done"

        sla = sla_days_map.get(a.priority, 30)
        elapsed = (
            (_dt.utcnow() - a.created_at).total_seconds()
            / 86400
        )

        if elapsed > sla:
            return "overdue"

        if elapsed > sla * 0.7:
            return "duesoon"

        return "ontrack"

    adata = [[
        "Domain",
        "Title",
        "Priority",
        "Due Date",
        "Status"
    ]]

    for a in open_actions:
        adata.append([
            Paragraph(str(a.domain_code), styles["Normal"]),
            Paragraph(str(a.title), styles["Normal"]),
            Paragraph(str(a.priority), styles["Normal"]),
            Paragraph(str(a.due_date or "—"), styles["Normal"]),
            Paragraph(str(a.status), styles["Normal"])
        ])

    atbl = Table(
        adata,
        colWidths=[45, 205, 65, 80, 90],
        repeatRows=1,
        hAlign="LEFT"
    )

    atbl_style = [
        ("BACKGROUND", (0, 0), (-1, 0), gold),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
    ]

    for i, a in enumerate(open_actions, start=1):
        key = _urgency_key(a)
        atbl_style.append(
            ("BACKGROUND", (4, i), (4, i), urgency_colors[key])
        )
        atbl_style.append(
            ("FONTNAME", (4, i), (4, i), "Helvetica-Bold")
        )

    atbl.setStyle(TableStyle(atbl_style))
    elements.append(atbl)
    elements.append(Spacer(1, 6))

    action_legend = Table([[
        Paragraph(
            "<font backColor='#f4a3a3'>&nbsp;&nbsp;&nbsp;</font> Overdue to start",
            styles["Normal"]
        ),
        Paragraph(
            "<font backColor='#ffe6a8'>&nbsp;&nbsp;&nbsp;</font> Due soon",
            styles["Normal"]
        ),
        Paragraph(
            "<font backColor='#c8e6c9'>&nbsp;&nbsp;&nbsp;</font> On track",
            styles["Normal"]
        ),
        Paragraph(
            "<font backColor='#b9e6b9'>&nbsp;&nbsp;&nbsp;</font> Completed",
            styles["Normal"]
        ),
    ]], colWidths=[110, 90, 90, 90])

    action_legend.setStyle(
        TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 2)
        ])
    )

    elements.append(action_legend)

else:
    elements.append(
        Paragraph(
            "No open corrective actions.",
            styles["Normal"]
        )
    )

# ---- Overall Assessment Summary / Consultant's Observations & Suggestions / Conclusion ----
elements.append(Spacer(1, 20))
elements.append(
    Paragraph(
        "<b>Overall Assessment Summary</b>",
        styles["Heading2"]
    )
)

total_domains = len(cards)
not_assessed = [
    c for c in cards
    if c["average_score"] is None
]

critical = [
    c for c in assessed_cards
    if c["maturity"] == "Critical / Initial"
]

needs_imp = [
    c for c in assessed_cards
    if c["maturity"] == "Needs Improvement"
]

strong = [
    c for c in assessed_cards
    if c["maturity"] in (
        "Proficient",
        "Excellent / Advanced"
    )
]

weakest = sorted(
    assessed_cards,
    key=lambda c: c["average_score"]
)[:3]

overall_band = (
    "an early / critical" if overall < 2 else
    "a developing" if overall < 3 else
    "a moderately mature" if overall < 3.5 else
    "a proficient" if overall < 4.5 else
    "an excellent"
)

summary_txt = (
    f"Out of the 52-domain institutional excellence framework, "
    f"{len(assessed_cards)} domain(s) have been assessed so far and "
    f"{len(not_assessed)} remain pending. The overall institutional "
    f"score stands at {overall}/5, placing the institution at "
    f"{overall_band} stage of readiness. "
    f"{len(critical)} domain(s) fall in the Critical/Initial band, "
    f"{len(needs_imp)} need improvement, and {len(strong)} are "
    f"already at a Proficient or Excellent level. There are currently "
    f"{len(open_actions)} open corrective action(s) being tracked."
)

elements.append(
    Paragraph(summary_txt, styles["Normal"])
)
elements.append(Spacer(1, 12))

elements.append(
    Paragraph(
        "<b>Consultant's Observations</b>",
        styles["Heading2"]
    )
)

if weakest:
    weak_list = ", ".join(
        f"{c['code']} ({c['name']}, {c['average_score']})"
        for c in weakest
    )

    obs_txt = (
        f"The areas needing the most immediate attention are "
        f"{weak_list}. These domains score below the institutional "
        f"average and reflect gaps in documentation, process "
        f"consistency, or review cadence rather than a single point failure."
    )

else:
    obs_txt = (
        "No domains have been scored yet; observations will populate "
        "once assessments begin."
    )

elements.append(
    Paragraph(obs_txt, styles["Normal"])
)
elements.append(Spacer(1, 12))

elements.append(
    Paragraph(
        "<b>Suggestions</b>",
        styles["Heading2"]
    )
)

suggestions = []

if not_assessed:
    suggestions.append(
        f"Prioritize assessing the {len(not_assessed)} pending domain(s) "
        f"to get a complete institutional picture."
    )

if critical:
    suggestions.append(
        f"Open corrective actions for all {len(critical)} Critical/Initial "
        f"domain(s) if not already logged, with High priority and "
        f"near-term due dates."
    )

if needs_imp:
    suggestions.append(
        f"Schedule a structured review cycle for the "
        f"{len(needs_imp)} 'Needs Improvement' domain(s) over the next quarter."
    )

if not open_actions and (critical or needs_imp):
    suggestions.append(
        "No corrective actions are currently open despite existing gaps — "
        "logging actions will help track closure."
    )

if not suggestions:
    suggestions.append(
        "Maintain the current review cadence and continue periodic "
        "re-assessment to sustain the institution's maturity level."
    )

for s in suggestions:
    elements.append(
        Paragraph(
            f"• {s}",
            styles["Normal"]
        )
    )

elements.append(Spacer(1, 12))

elements.append(
    Paragraph(
        "<b>Conclusion</b>",
        styles["Heading2"]
    )
)

conclusion_txt = (
    f"The institution is currently at {overall_band} stage of "
    f"institutional excellence ({overall}/5 overall). With focused "
    f"attention on the domains flagged above and consistent tracking "
    f"of corrective actions, measurable improvement is achievable "
    f"within the next assessment cycle."
)

elements.append(
    Paragraph(
        conclusion_txt,
        styles["Normal"]
    )
)

elements.append(Spacer(1, 20))

# ---- Consolidated Findings Register ----
elements.append(
    Paragraph(
        "<b>Consolidated Findings Register</b>",
        styles["Heading2"]
    )
)

elements.append(Spacer(1, 4))

freg_data = [[
    "Code",
    "Domain",
    "Score",
    "Maturity",
    "Finding"
]]

for c in cards:
    freg_data.append([
        Paragraph(str(c["code"]), styles["Normal"]),
        Paragraph(str(c["name"]), styles["Normal"]),
        Paragraph(
            str(c["average_score"])
            if c["average_score"] is not None else "—",
            styles["Normal"]
        ),
        Paragraph(str(c["maturity"]), styles["Normal"]),
        Paragraph(
            str(_finding_text(c)),
            styles["Normal"]
        )
    ])

freg_tbl = Table(
    freg_data,
    colWidths=[32, 110, 35, 85, 165],
    repeatRows=1
)

freg_style = [
    ("BACKGROUND", (0, 0), (-1, 0), navy),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTSIZE", (0, 0), (-1, -1), 6.5),
    ("LEADING", (0, 0), (-1, -1), 8),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
     [colors.white, colors.HexColor("#f5f6fa")]),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
]

for i, c in enumerate(cards, start=1):
    freg_style.append(
        (
            "BACKGROUND",
            (3, i),
            (3, i),
            maturity_colors.get(
                c["maturity"],
                colors.white
            )
        )
    )

freg_tbl.setStyle(TableStyle(freg_style))
elements.append(freg_tbl)
elements.append(Spacer(1, 20))

# ---- Recommendations & 90-Day CAPA Plan ----
elements.append(
    Paragraph(
        "<b>Recommendations &amp; 90-Day CAPA Plan</b>",
        styles["Heading2"]
    )
)

elements.append(Spacer(1, 4))

bucket_30, bucket_60, bucket_90 = [], [], []

for a in open_actions:
    if a.priority == "High":
        bucket_30.append(a)
    elif a.priority == "Medium":
        bucket_60.append(a)
    else:
        bucket_90.append(a)

actioned_codes = {
    a.domain_code
    for a in open_actions
}

for c in critical:
    if c["code"] not in actioned_codes:
        bucket_30.append(c)

for c in needs_imp:
    if c["code"] not in actioned_codes:
        bucket_60.append(c)

def _row_for(item):
    if hasattr(item, "priority"):
        return [
            item.domain_code,
            item.title,
            item.priority,
            item.status
        ]

    return [
        item["code"],
        f"Log corrective action for {item['name']}",
        "High" if item in critical else "Medium",
        "Not Started"
    ]

capa_data = [[
    "Window",
    "Domain",
    "Action / Title",
    "Priority",
    "Status"
]]

for label, bucket in [
    ("0–30 days", bucket_30),
    ("31–60 days", bucket_60),
    ("61–90 days", bucket_90)
]:

    if not bucket:
        capa_data.append([
            Paragraph(str(label), styles["Normal"]),
            Paragraph("—", styles["Normal"]),
            Paragraph("No items in this window", styles["Normal"]),
            Paragraph("—", styles["Normal"]),
            Paragraph("—", styles["Normal"])
        ])
        continue

    for idx, item in enumerate(bucket):
        row = _row_for(item)

        capa_data.append([
            Paragraph(
                str(label if idx == 0 else ""),
                styles["Normal"]
            ),
            Paragraph(str(row[0]), styles["Normal"]),
            Paragraph(str(row[1]), styles["Normal"]),
            Paragraph(str(row[2]), styles["Normal"]),
            Paragraph(str(row[3]), styles["Normal"])
        ])

capa_tbl = Table(
    capa_data,
    colWidths=[60, 35, 210, 55, 67],
    repeatRows=1
)

capa_tbl.setStyle(
    TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), gold),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("LEADING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
    ])
)

elements.append(capa_tbl)
