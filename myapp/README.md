# Ascend — Digital Certificate Verification System

Ascend is a Flask-based digital credential issuance and verification platform (similar to Credly) built for collegiate faculties, academic institutions, and verified members.

---

## 🏛️ Key Features & Modules

- **Unified Multi-Role Dashboard**: Single adaptive `dashboard.html` tailored for Administrators, Institutions, and Members.
- **Interactive Certificate Template Studio**: 2-column editor featuring real-time 2-way sync between form controls and an authentic parchment specimen canvas with official university seals and guilloche vector borders.
- **Dual Issuance Mechanism**: Issue credentials to recipients by either **Email Address** or **Phone Number** with automated recipient notifications.
- **Member Claim & Portfolio Flow**: Members can claim credentials issued to their contact details in a single click and showcase verified certificates on public portfolio profiles.
- **Instant Cryptographic Verification**: In-memory QR code generation (`qrcode` + `io.BytesIO`) and public verification screen accessible via shareable URLs with no login required.
- **Institutional Gateway Auth & SSO**: Clean institutional sign-in with email, member registration, password visibility toggles, and SSO integration.
- **In-App Notifications**: Real-time notifications for certificate issuance and member claims with unread count badges.
- **System Reports & Audit Analytics**: High-level platform statistics for Administrators and template issuance/claim rate breakdowns for Institutions.
- **Serverless Ready**: In-memory QR rendering and stateless architecture compatible with Vercel, Render, and other cloud providers without persistent filesystem dependencies.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, Flask, Flask-SQLAlchemy, Flask-Login, Werkzeug
- **Database**: PostgreSQL (hosted on Supabase via Session Pooler)
- **Frontend**: Tailwind CSS (custom collegiate theme), Jinja2, Material Symbols Outlined, Google Fonts (Newsreader & Inter)
- **Utilities**: `qrcode`, `pillow`, `python-dotenv`, `psycopg2-binary`

---

## 🗄️ Database Architecture

- **`users`**: `id`, `name`, `email`, `phone`, `password_hash`, `role` (`admin` / `institution` / `member`), `job_title`, `location`, `alumni`, `portfolio_url`, `is_profile_setup`, `created_at`
- **`certificates`**: `id`, `title`, `description`, `institution_id`, `created_at`
- **`issued_certificates`**: `id`, `certificate_id`, `institution_id`, `recipient_email`, `recipient_phone`, `verification_code`, `status` (`issued` / `claimed`), `claimed_at`, `claimed_by_id`, `issued_at`
- **`notifications`**: `id`, `user_id`, `recipient_email`, `recipient_phone`, `message`, `link`, `is_read`, `created_at`

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
```

Install all required dependencies:
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in `myapp/` (do not commit this file):
```env
SECRET_KEY=your_secret_key_here
DATABASE_URL=postgresql://user:password@host:port/dbname
```

### 4. Database Schema Migration
Run the non-destructive database schema migration script:
```bash
python alter_db.py
```

### 5. Run the Application
Launch the Flask development server:
```bash
python app.py
```

The application will be live at:
- **Local URL**: `http://127.0.0.1:5000`
- **Sign In**: `http://127.0.0.1:5000/login`
- **Verification Portal**: `http://127.0.0.1:5000/verify`

---

## 🔒 Security & Deployment Rules

- Sensitive credentials (`.env`, database URLs, secret keys) and virtual environment folders (`venv/`) are excluded via `.gitignore`.
- All credentials and configuration values are loaded securely from environment variables.
- Pure in-memory generation for dynamic assets (such as QR codes) guarantees seamless serverless hosting.
