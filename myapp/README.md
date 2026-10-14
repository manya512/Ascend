# Ascend — Digital Credential Registry & Verification Platform

Ascend is an institutional digital credential issuance and verification platform built with Flask and PostgreSQL. Designed for collegiate faculties, universities, accredited institutions, and recipient members, Ascend provides tamper-evident credential issuing, bulk batch workflows, live verification, and automated notification ecosystems.

---

## 🏛️ Key Features & Modules

### 1. Unified Multi-Role Architecture
Ascend provides tailored experiences based on four core organizational roles:
- **Platform Administrator (`admin`)**: Platform-wide oversight and review/approval workflow for registering institutions.
- **Institution Head (`institution`)**: Comprehensive institutional dashboard, department and club structure management, staff issuer verification, and aggregate issuance analytics.
- **Staff Issuer (`staff`)**: Department-affiliated instructors and faculty authorized to design templates and issue credentials.
- **Recipient Member (`member`)**: Students and credential holders who receive credentials, claim verified records to their portfolio, and share credentials publicly.

### 2. Institution Management Dashboard (`/institution/dashboard`)
A dedicated tabbed workspace for institution administrators:
- **Overview Analytics**: Real-time stats for enrolled students, verified vs. pending staff, department counts, club counts, and total vs. claimed issuance rates. Includes a per-department analytics table and a feed of recent issuances.
- **Department Management**: Add, rename, or delete academic departments. Features guarded deletion rules to prevent removing departments that have active staff or students assigned.
- **Club Management**: Add and delete affiliated student clubs and societies.
- **Staff Verification Center**: Review pending staff applications, verify or reject faculty issuers with automatic notification triggers, and revoke staff affiliations.
- **Student Roster**: Filter and view affiliated students with administrative options to manage institution links.

### 3. Certificate Studio & Interactive Specimen Canvas
- **Two-Column Live Studio**: Real-time two-way synchronization between template form fields and a collegiate parchment canvas.
- **Parchment Aesthetics**: Official institution seals, Latin mottoes, vector guilloche security borders, and authentic typography.
- **Dynamic Preview**: Instant visual preview before finalizing template creation.

### 4. Single & Bulk Credential Issuance
- **Dual Recipient Targeting**: Issue credentials by either **Email Address** or **Phone Number**.
- **Excel Spreadsheet Bulk Issuance (`/certificates/<id>/bulk-issue`)**:
  - Upload `.xlsx` spreadsheets (supporting up to 500 recipients per batch).
  - Downloadable standardized template (`/certificates/bulk-template.xlsx`).
  - Pre-issuance validation and duplicate filtering (within the uploaded spreadsheet and against prior issuances in the database).
  - Comprehensive results reporting detailing issued credentials, duplicates skipped, and invalid rows with specific error explanations.

### 5. Automated Background Email Delivery (`mail_utils.py`)
- **Branded HTML Emails**: Responsive email styling with Ascend's signature indigo header (`#26215C`), gold action buttons (`#EF9F27`), and plain-text fallbacks.
- **Key Email Triggers**:
  - **Certificate Issuance**: Direct "View Certificate" action link (`/verify/<code >`). For unregistered recipients, includes a pre-filled "Register to Claim" button linking to `/register?email=...`.
  - **Institution Approval & Rejection**: Official onboarding notices triggered by administrator reviews.
  - **Staff Issuer Verification**: Status updates sent upon approval or rejection by institution heads.
- **Non-Blocking Daemon Threads**: All SMTP network interactions run in daemon background threads, ensuring web requests never block or lag.
- **Throttled Bulk Sending**: Bulk issuance emails process sequentially through a background worker with a 0.5-second inter-message delay to avoid SMTP rate limiting.
- **Graceful Fallbacks & Demo Protection**: Automatic console logging when mail credentials are unset, and automatic email suppression for demo addresses ending in `.ascend.demo` or `@example.com`.

### 6. In-App Notification Hub (`/notifications`)
- **Real-Time Alerts**: Receive immediate notifications upon credential issuance, claiming, or institutional approval changes.
- **Click-Through Routing**: One-click navigation that automatically marks the notification as read and forwards to the underlying credential or dashboard.
- **Bulk Operations**: "Mark all as read" capability and dynamic unread badge counts in the navigation bar.
- **Retroactive Notification Linking**: Automatically associates pre-existing pending credentials to newly registered users matching email or phone.

### 7. Instant Cryptographic Verification & Public Portfolios
- **Public Verification (`/verify/<verification_code>`)**: Zero-login verification screen displaying credential status, recipient identifier, issuing college, department, and issue timestamp.
- **In-Memory QR Code Rendering**: Dynamic QR code generation powered by `qrcode` and `Pillow` operating directly in memory (`io.BytesIO`) without persistent disk storage requirements.
- **Print & Export Support**: Printable certificate layout optimized for print dialogues and PDF export.

---

## 🛠️ Tech Stack

- **Backend Framework**: Python 3.10+, Flask, Flask-SQLAlchemy, Flask-Login, Werkzeug
- **Spreadsheet Processing**: `openpyxl`
- **Email Delivery**: Python `smtplib` (STARTTLS, MIMEMultipart, background daemon threads)
- **Database**: PostgreSQL (hosted on Supabase via Session Pooler)
- **Database Driver**: `psycopg2-binary`
- **Frontend / UI**: Jinja2 Templates, Tailwind CSS (custom collegiate theme), Material Symbols Outlined, Google Fonts (Newsreader, Fraunces, and Inter)
- **Image & QR Rendering**: `qrcode`, `pillow`
- **Environment Management**: `python-dotenv`

---

## 🗄️ Database Architecture

```mermaid
erDiagram
    users ||--o{ departments : "institution owns"
    users ||--o{ clubs : "institution owns"
    users ||--o{ certificates : "institution/staff creates"
    users ||--o{ issued_certificates : "claims"
    users ||--o{ notifications : "receives"
    departments ||--o{ users : "staff/members belong to"
    certificates ||--o{ issued_certificates : "instantiates"

    users {
        int id PK
        string name
        string email UK
        string phone
        string password_hash
        string role "admin | institution | staff | member"
        int institution_id FK
        int department_id FK
        string staff_status "pending | verified | rejected"
        string approval_status "pending | approved | rejected"
        string job_title
        string location
        string alumni
        string portfolio_url
        boolean is_profile_setup
        datetime created_at
    }

    departments {
        int id PK
        int institution_id FK
        string name
        datetime created_at
    }

    clubs {
        int id PK
        int institution_id FK
        string name
        datetime created_at
    }

    certificates {
        int id PK
        int institution_id FK
        string title
        text description
        datetime created_at
    }

    issued_certificates {
        int id PK
        int certificate_id FK
        int institution_id FK
        string recipient_email
        string recipient_phone
        string verification_code UK
        string status "issued | claimed"
        datetime claimed_at
        int claimed_by_id FK
        datetime issued_at
    }

    notifications {
        int id PK
        int user_id FK
        string recipient_email
        string recipient_phone
        text message
        string link
        boolean is_read
        datetime created_at
    }
```

---

## 🚀 Setup & Local Run Instructions

### 1. Prerequisites
- Python 3.10+
- PostgreSQL database instance or Supabase project URL

### 2. Environment Setup
Clone the repository and enter the application directory:
```bash
cd myapp
```

Create and activate a virtual environment:
```bash
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On macOS / Linux:
source venv/bin/activate
```

Install all required dependencies:
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in `myapp/` (a template is available in `.env.example`):
```env
# Database
DATABASE_URL=postgresql://user:password@host:port/dbname

# Flask Security
SECRET_KEY=your_secret_key_here

# SMTP Email Configuration (Optional - falls back to console logging)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_FROM=your_email@gmail.com
APP_BASE_URL=http://localhost:5000
```

> [!NOTE]
> If `MAIL_USERNAME` or `MAIL_PASSWORD` are left empty, the application will not crash; all outgoing emails will be logged to the console.

### 4. Database Schema Migration & Seeding
Initialize or update the database schema:
```bash
python alter_db.py
python migrate_institutions.py
```

*(Optional)* Seed demo accounts (22 student members and 5 colleges):
```bash
python seed_demo_users.py
```

### 5. Run the Application
Launch the Flask development server:
```bash
python app.py
```

The application will be accessible at:
- **Homepage**: `http://127.0.0.1:5000`
- **Sign In / Registration**: `http://127.0.0.1:5000/login`
- **Public Verification**: `http://127.0.0.1:5000/verify`

---

## 🧪 Testing & Quality Assurance

Ascend contains automated test suites covering core functionality:

```bash
# Test notifications, click-through routing, and badge counts
python test_notifications_feature.py

# Test institution restructuring, departments, and club associations
python test_institution_restructure.py

# Test institution head dashboard, department/club CRUD, and staff verification
python test_institution_dashboard.py

# Test SMTP mail utility, payload generation, fallback logging, and bulk delivery
python test_email_sending.py
```

---

## 🔒 Security & Deployment Rules

- **Credential Hygiene**: Sensitive credentials (`.env`, database connection strings, passwords) are strictly excluded from source control via `.gitignore`.
- **Non-Fatal Email Resilience**: Email transmission errors or misconfigurations are handled asynchronously without disrupting credential issuance or user onboarding.
- **In-Memory Rendering**: Dynamic QR codes and rendered graphics are computed entirely in memory, ensuring compatibility with containerized environments and serverless platforms without persistent disk dependencies.
