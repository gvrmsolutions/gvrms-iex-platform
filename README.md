# GVRM IEX — Institutional Excellence & Transformation Platform

This is working software: a web app plus the engine behind it (a REST API
with its own database). Every feature below has been built, installed, and
tested end-to-end — login, scoring, gap analysis, corrective actions, the
audit log, and the PDF report all work.

---

## Option 1 — Try it on your own computer (quickest)

Needs Python 3.11+. In a terminal, inside this folder:

```bash
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.quickstart-example .env
python scripts/seed.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000**. Log in with:
- **Email:** admin@gvrmsolutions.in
- **Password:** ChangeMe@123

This mode stores everything in one file (`gvrm_iex.db`) — good for a pilot
with one institution, not for many customers at once.

## Option 2 — Proper deployment (multiple institutions, production)

Uses Docker so PostgreSQL and the app come up together, nothing installed
by hand:

```bash
cp .env.example .env
# open .env and set a real, long random value for JWT_SECRET
docker compose up --build
docker compose exec api python scripts/seed.py
```

Open **http://localhost:8000**. To put this on the internet for real
clients it needs to run on a server with a domain name and HTTPS in front
of it — happy to help with that step when you're ready.

---

## What the software does

**52-domain framework, 260 indicators** — the A–Z framework, with each
letter split into two focused sub-domains (e.g. A1 Curriculum Delivery &
Teaching Quality, A2 Learning Assessment & Outcomes … through Z2), five
indicators each = 260 measurable indicators, ready to assess out of the box.

**Roles** — Admin, Principal, IQAC Coordinator, Consultant. An admin
invites teammates under Team & Roles and assigns one of these roles;
campus/department creation is restricted to Admin and Principal.

**Institution → Campus → Department** — add campuses and departments
under "Campuses & Depts"; assessments can be tied to a specific campus or
department.

**Assessment & scoring engine** — score any of the 260 indicators 0–100
with an observation note; the software auto-labels it Critical / Needs
Improvement / Good / Excellent.

**Gap analysis** — flags every domain averaging below the threshold
(default 60) plus how many open corrective actions exist against it, and
lists every domain not yet assessed at all.

**Evidence upload** — real file upload (not just a filename): attach a
document to an assessment and download it back later.

**CAPA / corrective-action tracker** — log a gap against a domain with
owner, due date and priority, and move it through Not Started → In
Progress → Completed.

**Management dashboard** — overall score, assessment count, maturity mix,
and open actions at a glance.

**Domain-wise scorecards** — every one of the 52 domains with its average
score and maturity band in one table.

**Audit logs** — every login, assessment, action, evidence upload, and
team/structure change is timestamped and recorded, viewable under Audit
Log.

**PDF institutional audit report** — one click ("Download PDF Report")
produces a formatted report: overall score, the full 52-domain scorecard
table, and every open corrective action.

**Multi-tenant SaaS foundation** — each institution that registers gets
its own account and its own private data; nothing is shared across
institutions.

**REST APIs** — every feature above is also a documented API endpoint
(see **/docs** once running) so it can be integrated elsewhere later.

## Still needed before selling this to clients

- Real cloud file storage (e.g. Amazon S3) for evidence — right now files
  save to local disk, which is fine for one server but not for scaling.
- A password-reset screen.
- HTTPS and a real domain once hosted online.
- Billing, if you want to charge per institution.
- Backups and monitoring for production use.

## Login credentials created by the seed script

- Email: `admin@gvrmsolutions.in`
- Password: `ChangeMe@123`
- Organization: GVRM Demo Institution
- Role: Admin

## Main API routes (for reference)

```
POST /api/auth/register            POST /api/auth/login       GET /api/auth/me
GET  /api/domains                  GET  /api/domains/{code}
POST /api/assessments              GET  /api/assessments
POST /api/actions                  GET  /api/actions          PATCH /api/actions/{id}/status
POST /api/evidence                 POST /api/evidence/upload  GET /api/evidence/{id}/download
GET  /api/dashboard
GET  /api/reports/scorecards       GET /api/reports/gap-analysis
GET  /api/reports/audit-logs       GET /api/reports/audit-report.pdf
GET  /api/users                    POST /api/users
GET  /api/structure/campuses       POST /api/structure/campuses
POST /api/structure/departments
```

Full interactive API reference is at **/docs** once the software is
running.
