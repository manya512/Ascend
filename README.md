# Ascend

**Ascend** is an institutional digital credential issuance and verification platform built with Flask and PostgreSQL. Designed for collegiate faculties, universities, accredited institutions, and recipient members, Ascend provides tamper-evident credential issuing, Excel-powered bulk batch workflows, live cryptographic QR verification, automated background email notifications, and multi-tier organizational governance.

---

## 🎯 Vision

Ascend aims to make digital credentials trustworthy, globally verifiable, and frictionless to manage. By structuring credentials around accredited institutions, academic departments, and verified staff issuers, Ascend streamlines the complete credential lifecycle—from studio design and batch issuance to member claim fulfillment and zero-login public verification.

---

## 🏛️ Features & Modules

### 1. Unified Multi-Tier Governance
Ascend provides dedicated workflows and access controls for five distinct personas:
* 🛡️ **Platform Administrator (`admin`)**: Oversees the Platform Governance Console (`/admin`), monitors system-wide telemetry, reviews and approves/rejects institutional accreditation requests, and audits ledger health.
* 🏫 **Institution Head (`institution`)**: Full institutional oversight via the tabbed Institution Management Dashboard (`/dashboard`):
  - **Overview**: Real-time KPI pods, per-department issuance metrics table, and recent activity log.
  - **Departments**: Add, rename, or delete academic departments (with safety guards preventing deletion if active staff or students are assigned).
  - **Clubs & Societies**: Register and manage official student clubs and co-curricular organizations.
  - **Staff Verification Center**: Review pending faculty/staff issuer applications with one-click verify, reject, or affiliation revocation.
  - **Student Roster**: Track enrolled students filtered by department with administrative affiliation controls.
* 🎓 **Staff Issuer (`staff`)**: Department-affiliated instructors and faculty authorized to design templates and issue official credentials stamped with institutional authority.
* 👤 **Recipient Member (`member`)**: Students, alumni, and credential holders who receive notifications, claim credentials in 1-click to their portfolio, and showcase credentials publicly at `/profile/<user_id>`.
* 🔍 **Verifier (Public)**: Zero-login public verification gateway (`/verify` and `/verify/<code>`) resolving credentials with in-memory dynamic QR codes.

### 2. Dual & Bulk Credential Issuance
* **Dual Recipient Targeting**: Dispatch individual certificates via **Email Address**, **Phone Number**, or both.
* **Excel Spreadsheet Batch Issuance (`/certificates/<id>/bulk-issue`)**:
  - Upload `.xlsx` spreadsheets supporting up to 500 recipients per batch.
  - Downloadable standardized roster template (`/certificates/bulk-template.xlsx`).
  - Pre-issuance validation, cohort snapshot preview, and safe deduplication against duplicate spreadsheet entries and prior issuances.
  - Comprehensive bulk issuance results reporting with detailed success, skip, and error breakdowns.

### 3. Automated Background Email Delivery (`mail_utils.py`)
* **Asynchronous Daemon Sending**: Uses Python's standard `smtplib` over STARTTLS in background daemon threads so web requests are never delayed.
* **Branded Responsive HTML & Plaintext**: Signature Ascend indigo header (`#26215C`) and gold action buttons (`#EF9F27`).
* **Automated Event Triggers**:
  - Certificate Issuance with direct verification link and pre-filled registration link for new recipients.
  - Institutional approval and rejection notices from administrators.
  - Staff issuer verification and status notifications from institution heads.
* **Production Resiliency**: Throttled sequential sending for bulk batches (0.5s delay), automatic console-logging fallbacks when mail settings are absent, and suppression filters for demo addresses ending in `.ascend.demo` or `@example.com`.

### 4. Interactive Certificate Studio & Canvas
* **Live Two-Column Studio**: Real-time synchronization between form parameters and collegiate parchment canvas.
* **Authentic Parchment Aesthetics**: Features guilloche security borders, institution crests, Latin mottos, authentic typography, and formal signature lines.
* **Print-to-PDF Optimization**: Tailored `@media print` CSS for pristine single-page landscape exports from any browser.

### 5. Platform Governance Console (`/admin`)
* **Real-Time System Telemetry**: Displays network verification throughput spline chart with 24h telemetry markers and latency stats (42ms edge lookup).
* **Cryptographic Security Specs**: Institutional approval ledger presenting Ed25519-Dilithium3 post-quantum ready signatures, DNS TXT validation, and AISHE identifiers.
* **Multi-Sig Consensus Status**: Visual tracking of 3-of-5 authorized registrar hardware keys (HSM).

### 6. Design System & Brand Identity
* **Curated Palette**: Deep Indigo (`#26215C`), Violet Accent (`#3C3489`), Gold/Amber CTA (`#EF9F27`), and Lavender Tint (`#f5f3ff`).
* **Typography**: Fraunces & Newsreader serif headings paired with Inter UI typography.
* **Vector Branding**: Bespoke SVG brand identity suite (`ascend-logo.svg`, `ascend-icon.svg`, and light variants) packaged in reusable Jinja template components.

---

## 🛠️ Tech Stack

* **Backend Web Framework**: [Flask 3.1.3](https://flask.palletsprojects.com/)
* **Database ORM**: [Flask-SQLAlchemy 3.1.1](https://flask-sqlalchemy.palletsprojects.com/) & [SQLAlchemy 2.0.51](https://www.sqlalchemy.org/)
* **Database Driver**: [psycopg2-binary 2.9.12](https://www.psycopg.org/)
* **Authentication**: [Flask-Login 0.6.3](https://flask-login.readthedocs.io/)
* **Security & Passwords**: [Werkzeug 3.1.8](https://werkzeug.palletsprojects.com/)
* **Spreadsheet Processing**: [openpyxl 3.1.5](https://openpyxl.readthedocs.io/)
* **QR Code Generation**: [qrcode 8.2](https://pypi.org/project/qrcode/) & [Pillow 12.3.0](https://python-pillow.org/)
* **Email Engine**: Standard library `smtplib` + `email.mime` in background daemon threads
* **Database Host**: [Supabase](https://supabase.com/) (PostgreSQL with Session Pooling)
* **Frontend**: HTML5, Jinja2, Tailwind CSS, Google Fonts (*Fraunces*, *Newsreader*, *Inter*), Google Material Symbols

---

## 🚀 Getting Started / How to Run

### 1. Prerequisites
* **Python 3.10+**
* **Git**
* A **PostgreSQL** database (Supabase Session Pooler recommended)

### 2. Clone the Repository & Navigate to the App Folder
```bash
git clone https://github.com/manya512/Ascend.git
cd Ascend/myapp
```

### 3. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in `myapp/` based on `.env.example`:

```env
SECRET_KEY=your-secure-random-secret-key
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres

# Optional SMTP Email Delivery (prints to console if omitted)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_FROM=Ascend Credentials <your-email@gmail.com>
APP_BASE_URL=http://localhost:5000
```

### 5. Database Setup & Migrations
Ascend includes a safe, non-destructive migration script that updates existing PostgreSQL schemas without dropping tables or losing data:

```bash
python alter_db.py
```

To seed initial demo accounts across all roles (Admin, Institutions, Staff, and Students):
```bash
python seed_demo_users.py
```

### 6. Run the Application
Launch the Flask development server:
```bash
python app.py
```

Open your browser at:
* **Landing Page**: [http://127.0.0.1:5000](http://127.0.0.1:5000)
* **Authentication**: [http://127.0.0.1:5000/login](http://127.0.0.1:5000/login)
* **Public Verifier**: [http://127.0.0.1:5000/verify](http://127.0.0.1:5000/verify)
* **Admin Console**: [http://127.0.0.1:5000/admin](http://127.0.0.1:5000/admin)

---

## 📁 Project Structure

```text
Ascend/
├── README.md                 # Primary project documentation and technical overview
├── .env.example              # Template environment file with variable placeholders
└── myapp/                    # Core Flask application folder
    ├── app.py                # App entry point, route endpoints, auth, and business logic
    ├── config.py             # Configuration loader reading environment variables
    ├── models.py             # Database models (User, Department, Club, Certificate, etc.)
    ├── mail_utils.py         # Asynchronous background email delivery engine
    ├── alter_db.py           # Safe, non-destructive PostgreSQL migration script
    ├── seed_demo_users.py    # Multi-role demo seed script
    ├── requirements.txt      # Pinned Python package dependencies
    ├── .env.example          # Application environment variables template
    ├── static/               # CSS styles, favicon, and bespoke SVG assets
    │   ├── style.css         # Centralized design tokens and global styles
    │   └── img/              # Ascend logo and icon vector SVGs (light/dark)
    └── templates/            # Jinja2 HTML templates styled with Tailwind CSS
        ├── _logo.html        # Reusable vector brand component
        ├── base.html         # Master layout with navigation bar and theme tokens
        ├── landing.html      # Public marketing landing page
        ├── login.html        # Authentication gateway (sign in, register, demo shortcuts)
        ├── dashboard.html    # Role-adaptive dashboard with institution tabs
        ├── certificates_list.html # Template catalog with issuance actions
        ├── create_certificate.html # Interactive 2-column live certificate studio
        ├── edit_certificate.html   # Template editor
        ├── issue_certificate.html  # Single recipient certificate issuance
        ├── bulk_issue.html   # Excel bulk batch issuance interface
        ├── bulk_issue_results.html # Detailed batch execution report
        ├── certificate.html  # Rendered formal landscape certificate with print styles
        ├── verify.html       # Public verification portal with dynamic QR code
        ├── admin.html        # Platform Governance Console & telemetry
        ├── reports.html      # Institutional audit reports & claim analytics
        ├── notifications.html # In-app notification center
        └── settings.html     # Profile settings, avatar upload, and password update
```

---

## 🗄️ Database Schema

The database consists of six relational models defined in `models.py`:

### `users`
Represents platform administrators, accredited institutions, staff issuers, and recipient members.
* `id` (`INTEGER`, PK)
* `name` (`VARCHAR(100)`, NOT NULL)
* `email` (`VARCHAR(120)`, UNIQUE, NOT NULL)
* `phone` (`VARCHAR(20)`, NULL)
* `password_hash` (`VARCHAR(255)`, NOT NULL)
* `role` (`VARCHAR(20)`, NOT NULL: `'admin'`, `'institution'`, `'staff'`, or `'member'`)
* `institution_id` (`INTEGER`, FK `users.id`, NULL): Affiliated institution for staff & members
* `department_id` (`INTEGER`, FK `departments.id`, NULL): Affiliated academic department
* `staff_status` (`VARCHAR(20)`, NULL: `'pending'`, `'verified'`, `'rejected'`)
* `approval_status` (`VARCHAR(20)`, NULL: `'pending'`, `'approved'`, `'rejected'` for institutions)
* `job_title`, `location`, `alumni`, `portfolio_url` (`VARCHAR`)
* `profile_photo` (`BYTEA`), `profile_photo_mimetype` (`VARCHAR(50)`)
* `created_at` (`DATETIME`, default: `NOW()`)

### `departments`
Academic departments operating within an accredited institution.
* `id` (`INTEGER`, PK)
* `institution_id` (`INTEGER`, FK `users.id`, NOT NULL)
* `name` (`VARCHAR(100)`, NOT NULL)
* *Constraint*: Unique `(institution_id, name)`

### `clubs`
Affiliated student clubs and co-curricular organizations within an institution.
* `id` (`INTEGER`, PK)
* `institution_id` (`INTEGER`, FK `users.id`, NOT NULL)
* `name` (`VARCHAR(100)`, NOT NULL)
* *Constraint*: Unique `(institution_id, name)`

### `certificates`
Certificate templates created by institutions defining credential types and descriptions.
* `id` (`INTEGER`, PK)
* `title` (`VARCHAR(150)`, NOT NULL)
* `description` (`TEXT`, NULL)
* `institution_id` (`INTEGER`, FK `users.id`, NOT NULL)
* `created_at` (`DATETIME`, default: `NOW()`)

### `issued_certificates`
Cryptographically identified issued credentials assigned to individual recipients.
* `id` (`INTEGER`, PK)
* `certificate_id` (`INTEGER`, FK `certificates.id`, NOT NULL)
* `institution_id` (`INTEGER`, FK `users.id`, NOT NULL)
* `recipient_email` (`VARCHAR(120)`, NULL)
* `recipient_phone` (`VARCHAR(20)`, NULL)
* `verification_code` (`VARCHAR(36)`, UNIQUE, NOT NULL, UUID v4)
* `status` (`VARCHAR(20)`, NOT NULL, `'issued'` or `'claimed'`)
* `claimed_at` (`DATETIME`, NULL)
* `claimed_by_id` (`INTEGER`, FK `users.id`, NULL)
* `issued_at` (`DATETIME`, default: `NOW()`)

### `notifications`
In-app communication alerts dispatched upon issuance, claim, and accreditation events.
* `id` (`INTEGER`, PK)
* `user_id` (`INTEGER`, FK `users.id`, NULL)
* `recipient_email` (`VARCHAR(120)`, NULL)
* `recipient_phone` (`VARCHAR(20)`, NULL)
* `message` (`TEXT`, NOT NULL)
* `link` (`VARCHAR(255)`, NULL)
* `is_read` (`BOOLEAN`, default: `FALSE`)
* `created_at` (`DATETIME`, default: `NOW()`)

---

## 👥 User Roles & Permissions

| Role | Access Level | Responsibilities & Capabilities |
| :--- | :--- | :--- |
| **Platform Administrator** | `current_user.role == 'admin'` | Full system oversight; approves or rejects registering institutions via `/admin`; views platform audit reports at `/reports`. |
| **Institution Head** | `current_user.role == 'institution'` | Manages academic departments, student clubs, and staff verification at `/dashboard`; creates certificate templates; reviews claim analytics. |
| **Staff Issuer** | `current_user.role == 'staff'` | Affiliated with an accredited institution and department; once verified, can design templates and issue credentials to recipients. |
| **Recipient Member** | `current_user.role == 'member'` | Receives certificates matched to email or phone; claims credentials in 1-click; showcases verified portfolio on `/profile/<id>`. |
| **Public Verifier** | Unauthenticated | Zero-login verification of any credential UUID at `/verify/<code>` with live dynamic QR codes. |
