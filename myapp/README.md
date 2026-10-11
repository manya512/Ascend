# Ascend — Digital Certificate Verification System

Ascend is a Flask-based digital credential issuance and verification platform (similar to Credly) built for academic institutions, organizations, and verified members.

---

## Key Features

- **Multi-Actor Access Control**: Supports Administrators, Institutions, and Members under a unified dashboard structure.
- **Certificate Template Management**: Institutions can design, edit, and manage certificate templates.
- **Dual Issuance Mechanism**: Issue certificates to recipients using either Email or Phone Number.
- **Instant Cryptographic Verification**: In-memory QR code generation and public verification pages accessible via shareable URLs with no login required.
- **Member Claim & Profile Flow**: Members can claim certificates issued to their email or phone number and showcase them on public profiles.
- **In-App Notifications**: Real-time notifications for certificate issuance and claims.
- **Reports & Analytics**: System-wide activity stats for Admins and issuance summaries for Institutions.
- **Serverless Ready**: In-memory QR rendering (`io.BytesIO`) without reliance on persistent local disk storage.

---

## Tech Stack

- **Backend**: Python 3, Flask, Flask-SQLAlchemy, Flask-Login, Werkzeug
- **Database**: PostgreSQL (Supabase / Session Pooler connection)
- **Frontend**: HTML5, Vanilla CSS / Bootstrap 5, Jinja2 Templates
- **Utilities**: `qrcode`, `pillow`, `python-dotenv`

---

## Setup & Local Run Instructions

### 1. Prerequisites
- Python 3.10+
- PostgreSQL database instance (or Supabase URL)

### 2. Environment Setup
Clone the repository and navigate into the app directory:
```bash
cd myapp
```

Create and activate a virtual environment:
```bash
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in `myapp/` (do not commit this file):
```env
SECRET_KEY=your_secret_key_here
DATABASE_URL=postgresql://user:password@host:port/dbname
```

### 4. Database Schema Migration
Run the database alter script to initialize tables and columns:
```bash
python alter_db.py
```

### 5. Run the Application
Start the Flask development server:
```bash
python app.py
```

Access the application in your browser at `http://127.0.0.1:5000`.

---

## Git & Deployment Rules

- `.env` and `venv/` are excluded via `.gitignore`.
- Database credentials and secrets are supplied strictly via environment variables.
- Serverless-compatible: no local filesystem dependencies for asset/QR generation.
