# Ascend

**Ascend** is a modern digital credential platform that enables institutions to issue secure digital certificates, members to claim and showcase their achievements, and verifiers to instantly authenticate credentials through QR-based verification.

The platform streamlines the entire credential lifecycle—from certificate requests and issuance to claiming, verification, and status tracking—providing a secure, transparent, and user-friendly experience for institutions, learners, and employers alike.

---

## 🎯 Vision

Ascend aims to make digital credentials more trustworthy, accessible, and easy to verify by providing a centralized platform where achievements can be securely issued, managed, and shared.

---

## 🏛️ Features

### Implemented in the Codebase
* 🏫 **Institution Management Dashboard**: Accredited institutions can create, preview, edit, and delete certificate templates, as well as audit their complete issuance ledger.
* 📜 **Dual Issuance Mechanism**: Issue credentials directly to recipients using either an **Email Address** or a **Phone Number** (or both).
* 👤 **Member Profiles & Claim Flow**: Logged-in members can claim credentials matched to their verified email or phone in a single click, and showcase verified credentials on a shareable public portfolio (`/profile/<user_id>`).
* 🔍 **QR Code-Based Public Verification**: Standalone public verification portal (`/verify` and `/verify/<code>`) that resolves credentials by unique UUID with in-memory QR code rendering and no login required.
* 🔔 **In-App Notification Center**: Real-time notifications for credential issuance and member claim confirmations, complete with unread badges and mark-as-read controls.
* 📊 **Certificate Lifecycle Tracking**: Real-time database tracking for `Issued` and `Claimed` credential statuses.
* 📈 **System Reports & Analytics**: Dedicated reporting suite providing platform-wide statistics for administrators and template-level claim rate percentages for institutions.
* 🔒 **Secure Authentication & Identity**: Password encryption using Werkzeug hashing, Flask-Login session management, and role-based route protection.

### 📋 Planned / Future Work
* 📩 **Certificate Request and Approval Workflow**: Direct workflow allowing members to formally request certificates from institutions through the portal for registrar approval.
* 🚫 **Credential Revocation & Expiration**: Automated handling and audit logging for `Revoked` and `Expired` credential status transitions.
* 📦 **Bulk Issuance via CSV**: Uploading class rosters or CSV files to batch-issue diplomas and certificates to hundreds of students simultaneously.
* 📑 **Tamper-Evident Vector PDF Export**: Generating downloadable, print-ready PDF certificates with embedded cryptographic verification metadata and printable QR codes.

---

## 🚀 Getting Started / How to Run

Follow these step-by-step instructions to clone, configure, and run Ascend locally.

### 1. Prerequisites
Before running the application, make sure you have:
* **Python 3.10+** installed on your system
* **Git** installed
* A **PostgreSQL** database (a hosted Supabase project is recommended)

### 2. Clone the Repository
Clone the repository using Git and navigate to the application folder:

```bash
git clone https://github.com/manya512/Ascend.git
```

```bash
cd Ascend/myapp
```

### 3. Create and Activate a Virtual Environment
Create an isolated Python virtual environment to manage dependencies.

**On Windows PowerShell:**
```powershell
python -m venv venv
```

```powershell
.\venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
python3 -m venv venv
```

```bash
source venv/bin/activate
```

### 4. Install Dependencies
Install all required Python packages listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Ascend reads configuration settings from environment variables via `python-dotenv`. Create a `.env` file in the `myapp/` directory (you can copy `.env.example` as a template):

```env
SECRET_KEY=dev-secret-key-change-later
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

The application reads the following variables:
* `SECRET_KEY`: A secret string used by Flask to cryptographically sign session cookies. In production, use a long, random string.
* `DATABASE_URL`: The PostgreSQL database connection URI.
  > **Note on Supabase:** Always use the **Supabase Session Pooler** connection string (port `6543` or `5432` with IPv4 pooler mode) to ensure reliable connections with serverless and local Flask workers.

### 6. Database Setup & Initialization
Ascend uses SQLAlchemy models defined in `models.py`.

1. To run the safe, non-destructive schema migration (which adds all required columns to PostgreSQL without dropping tables):
```bash
python alter_db.py
```

2. To seed initial test accounts for testing (Admin, Institution, and Member):
```bash
python create_test_users.py
```

### 7. Run the Application
Launch the Flask development server:

```bash
python app.py
```

Open your browser and navigate to:
* **Home / Landing Page**: [http://127.0.0.1:5000](http://127.0.0.1:5000)
* **Sign In & Registration**: [http://127.0.0.1:5000/login](http://127.0.0.1:5000/login)
* **Public Certificate Verifier**: [http://127.0.0.1:5000/verify](http://127.0.0.1:5000/verify)

---

## 📁 Project Structure

```text
Ascend/
├── README.md                 # Primary project documentation and technical overview
├── .env.example              # Template environment file with variable placeholders
└── myapp/                    # Core Flask application folder
    ├── app.py                # Flask app entry point, route handlers, auth logic, and error handlers
    ├── config.py             # Configuration loader reading SECRET_KEY and DATABASE_URL from .env
    ├── models.py             # SQLAlchemy database models (User, Certificate, IssuedCertificate, Notification)
    ├── alter_db.py           # Safe, non-destructive PostgreSQL migration script for existing tables
    ├── create_test_users.py  # Seed script creating test accounts for Admin, Institution, and Member
    ├── create_user.py        # CLI helper script for creating individual admin accounts
    ├── requirements.txt      # Pinned Python package dependencies
    ├── .gitignore            # Git exclusion rules (.env, venv/, __pycache__/)
    ├── static/               # Static assets, styles, scripts, and favicon
    └── templates/            # Jinja2 HTML templates styled with Tailwind CSS
        ├── base.html         # Master layout with collegiate navigation bar, flash messages, and theme tokens
        ├── landing.html      # Public marketing landing page with feature cards and platform benefits
        ├── login.html        # Authentication gateway featuring sign-in, member registration, and SSO
        ├── dashboard.html    # Unified, role-adaptive dashboard for Admin, Institution, and Member
        ├── certificates_list.html # Institution catalog to browse, edit, and issue certificate templates
        ├── create_certificate.html # Interactive 2-column studio editor to design certificate templates
        ├── edit_certificate.html   # Studio editor to modify existing certificate templates
        ├── issue_certificate.html  # Issuance form to dispatch a certificate via Email or Phone
        ├── issued_list.html  # Registrar ledger of all issued credentials, statuses, and codes
        ├── profile.html      # Public verified member profile and credentials portfolio
        ├── member.html       # Member profile setup screen and verified achievements showcase
        ├── institution.html  # Institution workspace portal with registrar action shortcuts
        ├── admin.html        # Platform administration console and system telemetry
        ├── reports.html      # Audit reports showing institution and template claim breakdowns
        ├── notifications.html # In-app notification center with read/unread tracking
        └── verify.html       # Public verification gateway with in-memory QR code preview
```

---

## 👥 User Roles & Permissions

The application implements four distinct user personas governed by route-level checks in `app.py`:

| Role | Access Level & Route Guards | What They Can Do |
| :--- | :--- | :--- |
| **Administrator** | `current_user.role == 'admin'` | • Accesses the system-wide overview on `/dashboard`.<br>• Views total counts of users, institutions, members, templates, and issuances.<br>• Accesses `/reports` with the `institution_breakdown` view detailing template counts and total certificates issued per institution.<br>• Inspects system audit logs. |
| **Institution** | `current_user.role == 'institution'` | • Creates, edits, and deletes certificate templates (`/certificates/create`, `/certificates/<id>/edit`, `/certificates/<id>/delete`).<br>• Issues certificates to recipients by email or phone (`/certificates/<id>/issue`).<br>• Audits all issued credentials in `/issued`.<br>• Accesses `/reports` with the `template_breakdown` view showing claim rates.<br>• Receives notifications when members claim their credentials. |
| **Member** | `current_user.role == 'member'` | • Self-registers via the public sign-up form on `/login`.<br>• Views unclaimed certificates matching their email or phone in `/dashboard`.<br>• Claims credentials in 1-click via POST `/certificates/<id>/claim`.<br>• Updates profile details (job title, location, alma mater, portfolio link) on `/update-profile`.<br>• Shares a public portfolio of claimed certificates at `/profile/<user_id>`. |
| **Verifier** | Public / Unauthenticated | • No login required.<br>• Looks up any credential at `/verify` or directly via `/verify/<code>`.<br>• Views the issuer, recipient, issue date, and in-memory QR verification code.<br>• Verifies authenticity on public member profiles (`/profile/<user_id>`). |

### How to Register as an Institution
To maintain institutional accreditation and prevent unauthorized issuers, the public self-registration form (`/register`) automatically creates **Member** accounts. To register or create an **Institution** account, you can use any of the following methods:

1. **Quick Seeding via CLI (Recommended for Development)**:
   Run the included seed script to create a pre-configured institution account:
   ```bash
   python create_test_users.py
   ```
   *Default Credentials:* `institution@ascend.com` / `password123`

2. **Python Command Line**:
   Run a one-line command to register any custom institution name and credentials:
   ```bash
   python -c "from app import app, db, User; app.app_context().push(); u = User(name='Pacific Institute of Technology', email='registrar@pit.edu', role='institution'); u.set_password('securepassword'); db.session.add(u); db.session.commit(); print('Institution registered successfully!')"
   ```

3. **Institutional SSO Demo Shortcut**:
   On the login page (`/login`), click **"Institutional SSO"** to immediately sign into the registered institution account.

4. **Direct Database Role Promotion**:
   Register a normal account on `/login`, then in your Supabase SQL Editor run:
   ```sql
   UPDATE users SET role = 'institution' WHERE email = 'your_email@university.edu';
   ```

---

## ⚙️ How It Works (Implementation Logic)

### 1. Authentication
* **Session Management**: Handled via `Flask-Login` using encrypted HTTP-only session cookies. Routes requiring authentication use the `@login_required` decorator.
* **Password Hashing**: Passwords are never stored in plain text. When a user registers or updates their password, Werkzeug's `generate_password_hash()` generates a salted hash. During login, `check_password_hash()` verifies the entered password against the stored hash.

### 2. Role-Based Access Control
Routes apply role checks directly after the `@login_required` guard. If a user attempts to access an unauthorized route, they are redirected to their respective dashboard:

```python
@app.route('/certificates/create', methods=['GET', 'POST'])
@login_required
def create_certificate():
    if current_user.role != 'institution':
        return redirect(url_for('dashboard'))
    # ... institution logic continues
```

### 3. Certificate Template Creation
Institutions design templates by supplying a title and description. When saved, a new `Certificate` row is created in PostgreSQL with `institution_id` set to `current_user.id`.

### 4. Issuance Mechanism
1. An institution selects a template and provides the recipient's **email**, **phone**, or both.
2. The server instantiates an `IssuedCertificate` record.
3. A unique 36-character **UUID v4** verification code is generated (`str(uuid.uuid4())`) ensuring collision-proof, tamper-resistant identifiers.
4. An automated `Notification` record is created for the recipient matching their email or phone.

### 5. Claim Flow
1. When a member logs into `/dashboard`, the server queries `IssuedCertificate` for records where `status != 'claimed'` that match the member's registered email or phone.
2. When the member clicks **Claim Certificate**, a POST request is sent to `/certificates/<issued_id>/claim`.
3. The server validates that the logged-in user is indeed the authorized recipient.
4. The record is updated: `status = 'claimed'`, `claimed_at = datetime.utcnow()`, and `claimed_by_id = current_user.id`.
5. An automated notification is sent to the issuing institution confirming the claim.

### 6. Public Verification Logic
1. Anyone can visit `/verify/<code>` without logging in.
2. The server queries `IssuedCertificate` joined with `Certificate` and `User` (the issuing institution) by `verification_code`.
3. If valid, `generate_qr_base64()` dynamically constructs a QR code in memory using `io.BytesIO` and returns a Base64-encoded PNG image string (`data:image/png;base64,...`).
4. The page displays the official certificate preview, verification timestamp, and issuing authority.

### 7. Certificate Lifecycle
The application tracks credentials through two active states:
* `issued`: The credential has been signed and dispatched by an institution, awaiting claim by the recipient.
* `claimed`: The credential has been accepted and linked to the recipient member's verified account.

### 8. Database Design & Relational Model
* Every `Certificate` belongs to an institution (`users.id`).
* Every `IssuedCertificate` references both the original `Certificate` (`certificate_id`) and the issuing `User` (`institution_id`).
* When claimed, `IssuedCertificate.claimed_by_id` links directly to the recipient `User`.
* `Notification` records link to `User` accounts or reference recipient contact details.

---

## 🗄️ Database Schema

The database consists of four tables defined in `models.py`:

### `users`
Represents administrators, accredited institutions, and recipient members.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Primary Key | Unique user ID |
| `name` | `VARCHAR(100)` | NOT NULL | User or Institution name |
| `email` | `VARCHAR(120)` | UNIQUE, NOT NULL | Account email address |
| `phone` | `VARCHAR(20)` | NULL | Contact phone number for claim matching |
| `password_hash` | `VARCHAR(255)` | NOT NULL | Werkzeug salted password hash |
| `role` | `VARCHAR(20)` | NOT NULL | Account role (`admin`, `institution`, or `member`) |
| `created_at` | `DATETIME` | Default: `NOW()` | Registration timestamp |
| `job_title` | `VARCHAR(100)` | NULL | Professional or academic title |
| `location` | `VARCHAR(100)` | NULL | City, Country or Campus location |
| `alumni` | `VARCHAR(100)` | NULL | Alma mater or university |
| `portfolio_url` | `VARCHAR(200)` | NULL | External portfolio or registry link |
| `is_profile_setup`| `BOOLEAN` | Default: `FALSE` | Indicates whether the profile has been initialized |

### `certificates`
Templates created by institutions defining credential types (e.g., Bachelor of Science, Honors Award).

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Primary Key | Unique template ID |
| `title` | `VARCHAR(150)` | NOT NULL | Credential or diploma title |
| `description` | `TEXT` | NULL | Detailed coursework or criteria description |
| `institution_id`| `INTEGER` | Foreign Key (`users.id`), NOT NULL | Issuer institution ID |
| `created_at` | `DATETIME` | Default: `NOW()` | Creation timestamp |

### `issued_certificates`
Official issued credentials assigned to individual recipients.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Primary Key | Unique issuance ID |
| `certificate_id`| `INTEGER` | Foreign Key (`certificates.id`), NOT NULL | Reference to the certificate template |
| `institution_id`| `INTEGER` | Foreign Key (`users.id`), NOT NULL | Issuer institution ID |
| `recipient_email`| `VARCHAR(120)`| NULL | Recipient's email address |
| `recipient_phone`| `VARCHAR(20)` | NULL | Recipient's mobile phone number |
| `verification_code`| `VARCHAR(36)` | UNIQUE, NOT NULL | RFC 4122 UUID v4 verification code |
| `status` | `VARCHAR(20)` | NOT NULL, Default: `'issued'` | Status (`'issued'` or `'claimed'`) |
| `claimed_at` | `DATETIME` | NULL | Timestamp when the member claimed the credential |
| `claimed_by_id` | `INTEGER` | Foreign Key (`users.id`), NULL | Member ID who claimed the credential |
| `issued_at` | `DATETIME` | Default: `NOW()` | Issuance timestamp |

### `notifications`
In-app communication records dispatched upon issuance and claim events.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Primary Key | Unique notification ID |
| `user_id` | `INTEGER` | Foreign Key (`users.id`), NULL | Specific recipient user ID (if registered) |
| `recipient_email`| `VARCHAR(120)`| NULL | Target recipient email |
| `recipient_phone`| `VARCHAR(20)` | NULL | Target recipient phone |
| `message` | `TEXT` | NOT NULL | Notification content |
| `link` | `VARCHAR(255)` | NULL | Action URL (e.g. `/verify/<code>`) |
| `is_read` | `BOOLEAN` | NOT NULL, Default: `FALSE` | Read status |
| `created_at` | `DATETIME` | Default: `NOW()` | Dispatch timestamp |

---

## 🛠️ Tech Stack

Ascend is built using a lightweight, modern Python web architecture:

* **Backend Web Framework**: [Flask 3.1.3](https://flask.palletsprojects.com/)
* **Database ORM**: [Flask-SQLAlchemy 3.1.1](https://flask-sqlalchemy.palletsprojects.com/) & [SQLAlchemy 2.0.51](https://www.sqlalchemy.org/)
* **Database Driver**: [psycopg2-binary 2.9.12](https://www.psycopg.org/)
* **Authentication**: [Flask-Login 0.6.3](https://flask-login.readthedocs.io/)
* **Password Security**: [Werkzeug 3.1.8](https://werkzeug.palletsprojects.com/)
* **QR Code Engine**: [qrcode 8.2](https://pypi.org/project/qrcode/) & [Pillow 12.3.0](https://python-pillow.org/)
* **Environment Configuration**: [python-dotenv 1.2.2](https://pypi.org/project/python-dotenv/)
* **Database Host**: [Supabase](https://supabase.com/) (PostgreSQL with Session Pooler)
* **Frontend**: HTML5, Jinja2 (3.1.6), Tailwind CSS (embedded collegiate theme), Google Fonts (*Newsreader* & *Inter*), and Google Material Symbols Outlined

---

## 🚢 Deployment Readiness

Ascend is configured to be deployment-ready for cloud platforms such as Render, Railway, AWS, or Heroku:

* **Pinned Dependencies**: All required packages and versions are locked in `requirements.txt`.
* **Stateless Dynamic Assets**: QR codes are generated directly into memory buffers via `io.BytesIO` and streamed as Base64 strings, avoiding ephemeral filesystem write issues on serverless or container hosts.
* **Database Pooling**: Configured with `pool_pre_ping=True` and `pool_recycle=300` in `config.py` to maintain stable connections with Supabase.
* **Environment Isolation**: `.env` and `venv/` are excluded from version control in `.gitignore`. Secrets, database connection strings, and virtual environments must never be committed to Git. In production, configure environment variables directly in your hosting provider's dashboard.
