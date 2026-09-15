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
            [[RLImage(str(logo_path), width=70, height=70),
              Paragraph(f"<font color='#07152d'><b>{org.name}</b></font><br/>"
                        f"<font size=9 color='#666666'>Institutional Excellence &amp; Transformation — GVRM Solutions</font>",
                        styles["Normal"])]],
            colWidths=[85, 380]
        )
        header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        elements.append(header)
    else:
        elements.append(Paragraph(f"<font color='#07152d'><b>{org.name}</b></font>", styles["Title"]))

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Institutional Excellence — Audit Report (A-Z, 52-Domain Framework)", styles["Heading3"]))
    elements.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}", styles["Normal"]))

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
        elements.append(Paragraph(" &nbsp;|&nbsp; ".join(detail_lines), styles["Normal"]))

    elements.append(Spacer(1, 14))

    scored = [c for c in cards if c["average_score"] is not None]
    overall = round(sum(c["average_score"] for c in scored) / len(scored), 1) if scored else 0
    elements.append(Paragraph(f"<b>Overall institutional score: {overall} / 100</b>", styles["Heading2"]))
    elements.append(Paragraph(f"Domains assessed: {len(scored)} of {len(cards)} &nbsp;&nbsp; Open corrective actions: {len(open_actions)}", styles["Normal"]))
    elements.append(Spacer(1, 14))

    data = [["Code", "Domain", "Avg Score", "Maturity", "Assessed / Total"]]
    for c in cards:
        data.append([c["code"], c["name"], c["average_score"] if c["average_score"] is not None else "—",
                     c["maturity"], f"{c['assessed']}/{c['total_indicators']}"])
    tbl = Table(data, colWidths=[35, 210, 60, 100, 80])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6fa")]),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("<b>Open Corrective Actions (CAPA)</b>", styles["Heading2"]))
    if open_actions:
        adata = [["Domain", "Title", "Priority", "Due Date", "Status"]]
        for a in open_actions:
            adata.append([a.domain_code, a.title, a.priority, str(a.due_date or "—"), a.status])
        atbl = Table(adata, colWidths=[45, 220, 60, 80, 80])
        atbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), gold),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ]))
        elements.append(atbl)
    else:
        elements.append(Paragraph("No open corrective actions.", styles["Normal"]))

    # Signature block
    elements.append(Spacer(1, 40))
    sig_table = Table(
        [["_______________________________", ""],
         ["G. Veerapandian", ""],
         ["Founder | Institutional Excellence Consultant", ""],
         ["G.V.R.M. SOLUTIONS, Ramanathapuram", ""],
         ["Phone: +91 6383858318  |  Email: info.g.v.r.m.solutions.in@gmail.com", ""]],
        colWidths=[300, 200]
    )
    sig_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (0, 1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    buf.seek(0)
    filename = f"{org.code}-audit-report.pdf"
    return StreamingResponse(buf, media_type="application/pdf",
                              headers={"Content-Disposition": f"attachment; filename={filename}"})
