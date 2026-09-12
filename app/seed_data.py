from .db import SessionLocal, Base, engine
from .models import Domain, Indicator, Organization, User
from .security import hash_password

# A-Z, 52 critical-domain framework: each letter split into two focused
# sub-domains -> 52 domains x 5 indicators = 260 measurable indicators.
DOMAINS = [
("A1","Curriculum Delivery & Teaching Quality","Lesson planning, pedagogy, coverage and classroom delivery quality"),
("A2","Learning Assessment & Outcomes","Formative/summative assessment design and student learning measurement"),
("B1","Budget Planning & Fee Management","Annual budgeting, fee structure and collection efficiency"),
("B2","Expenditure Control & Resource Allocation","Spend tracking, cost control and resource allocation across departments"),
("C1","Curriculum Design & Alignment","Curriculum structure, board/university alignment and periodic review"),
("C2","Regulatory Compliance & Documentation","Statutory documentation, approvals and compliance record-keeping"),
("D1","Management Information Systems","MIS accuracy, timeliness and decision-support reporting"),
("D2","Records, Evidence & Data Integrity","Data integrity, evidence trails and records retention"),
("E1","Question Paper Quality & Exam Security","Paper setting standards, confidentiality and exam-hall security"),
("E2","Valuation, Moderation & Result Processing","Answer valuation accuracy, moderation and result declaration timelines"),
("F1","Faculty Recruitment & Workload","Faculty hiring standards, qualification norms and workload balance"),
("F2","Faculty Training & Performance Appraisal","Continuous professional development and appraisal systems"),
("G1","Organizational Structure & Delegation","Org charts, role clarity and delegation of authority"),
("G2","Decision-Making & Accountability","Decision transparency, escalation paths and accountability tracking"),
("H1","Recruitment & Onboarding","HR hiring process, induction and onboarding effectiveness"),
("H2","Appraisal, Training & Grievance Redressal","Staff appraisal cycles, training plans and grievance handling"),
("I1","Physical Infrastructure & Maintenance","Buildings, labs, sanitation and preventive maintenance"),
("I2","ICT Infrastructure & Digital Resources","Computers, network, digital classrooms and resource availability"),
("J1","Internship & Industry Exposure","Internship tie-ups, industry visits and exposure programs"),
("J2","Placement Readiness & Employer Engagement","Placement cell effectiveness and employer relationship management"),
("K1","SOPs & Process Documentation","Standard operating procedures coverage and adherence"),
("K2","Institutional Knowledge Sharing","Knowledge repositories, handover practices and institutional memory"),
("L1","CO/PO Mapping & Attainment","Course/program outcome mapping and attainment calculation"),
("L2","Remedial Action & Learning Enhancement","Remedial classes, bridge courses and learning-gap closure"),
("M1","KPI Tracking & Management Reviews","Key performance indicators and periodic management review meetings"),
("M2","Corrective & Preventive Actions","CAPA logging, closure rate and recurrence prevention"),
("N1","Criteria Readiness & SSR Preparation","NAAC/NBA criterion-wise readiness and self-study report preparation"),
("N2","Evidence Compilation & Audit Preparedness","Evidence dossiers, mock audits and peer-team readiness"),
("O1","CO-PO Design & Mapping","Outcome-based education design and CO-PO articulation matrices"),
("O2","Attainment Analysis & Improvement Tracking","Attainment gap analysis and closing-the-loop actions"),
("P1","Communication & Feedback Systems","Parent-teacher communication channels and feedback collection"),
("P2","Stakeholder Participation & Satisfaction","Stakeholder involvement in decisions and satisfaction tracking"),
("Q1","IQAC Functioning & PDCA Cycle","IQAC meeting cadence, PDCA implementation and quality culture"),
("Q2","Benchmarking & Process Quality","Benchmarking against peer institutions and process quality audits"),
("R1","Research Output & Publications","Faculty/student research output, publications and citations"),
("R2","Funding, Collaboration & Innovation","Research funding, MOUs, patents and innovation initiatives"),
("S1","Attendance, Mentoring & Counselling","Attendance monitoring, mentor-mentee system and counselling support"),
("S2","Retention & Student Support Services","Dropout prevention, scholarships and student welfare services"),
("T1","LMS & ERP Systems","Learning management and ERP system adoption and effectiveness"),
("T2","Cybersecurity & Process Automation","Data security, backups and automation of routine processes"),
("U1","Statutory Compliance & Inspections","Government/board inspections and statutory compliance closure"),
("U2","Regulatory Reporting & Filings","Timely regulatory filings, returns and affiliation renewals"),
("V1","Strategic Goal Setting","Vision/mission clarity and strategic goal cascading"),
("V2","Execution Monitoring & Sustainability","Strategic plan execution tracking and long-term sustainability"),
("W1","Manpower Planning","Staffing norms, succession planning and manpower forecasting"),
("W2","Workload Distribution & Utilization","Equitable workload distribution and utilization efficiency"),
("X1","Student & Parent Experience","End-to-end experience journey for students and parents"),
("X2","Service Quality & Grievance Handling","Service-level standards and grievance resolution turnaround"),
("Y1","Soft Skills & Leadership Development","Communication, leadership and personality-development programs"),
("Y2","Career Guidance & Entrepreneurship","Career counselling, higher-education guidance and entrepreneurship cells"),
("Z1","Root Cause Analysis & CAPA","RCA methodology and corrective-action-plan discipline"),
("Z2","Continuous Improvement Culture & Benchmarking","Kaizen culture, improvement projects and benchmarking cadence"),
]
assert len(DOMAINS) == 52

def run_seed():
    """Idempotent: safe to call on every app startup. Creates the 52-domain
    framework and a default admin login only if they don't already exist."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for code, name, desc in DOMAINS:
            d = db.query(Domain).filter_by(code=code).first()
            if not d:
                d = Domain(code=code, name=name, description=desc)
                db.add(d); db.flush()
            if not d.indicators:
                for n, title in enumerate([
                    "Policy / Process Availability",
                    "Implementation Evidence",
                    "Performance Measurement",
                    "Gap Identification",
                    "Corrective / Improvement Action"
                ], 1):
                    db.add(Indicator(
                        domain_id=d.id,
                        code=f"{code}{n:02d}",
                        title=f"{name} — {title}",
                        description=f"Assess the institution's {title.lower()} for {name}.",
                        max_score=100
                    ))

        org = db.query(Organization).filter_by(code="GVRM-DEMO").first()
        if not org:
            org = Organization(name="GVRM Demo Institution", code="GVRM-DEMO")
            db.add(org); db.flush()

        u = db.query(User).filter_by(email="admin@gvrmsolutions.in").first()
        if not u:
            db.add(User(
                organization_id=org.id,
                name="GVRM Administrator",
                email="admin@gvrmsolutions.in",
                password_hash=hash_password("ChangeMe@123"),
                role="admin"
            ))
        db.commit()
    finally:
        db.close()
