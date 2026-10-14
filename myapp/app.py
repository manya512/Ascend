import qrcode
import io
import base64
import re
import uuid
import openpyxl
from flask import Flask, render_template, redirect, url_for, request, flash, Response, make_response, abort, send_file, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from PIL import Image

from config import Config
from models import db, User, Certificate, IssuedCertificate, Notification, Department, Club
from mail_utils import (
    send_email,
    send_emails_bulk,
    build_certificate_email_payload,
    email_certificate_issued,
    email_institution_approved,
    email_institution_rejected,
    email_staff_verified,
    email_staff_rejected,
)

def generate_qr_base64(url):
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#26215c", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('ascii')

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def home():
    return render_template('landing.html')


@app.route('/login/sso')
def login_sso():
    # SSO demo route: log in as institution account if available or redirect to login
    inst = User.query.filter_by(role='institution').first()
    if inst:
        login_user(inst)
        flash(f'Signed in via Institutional SSO as {inst.name}.')
        return redirect(url_for('dashboard'))
    flash('Institutional SSO is available. Please enter your institutional email to proceed.')
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        flash(f'Password reset instructions have been dispatched to {email or "your email"}.')
        return redirect(url_for('login'))
    flash('Password reset requested. Please enter your email on the login screen.')
    return redirect(url_for('login'))

@app.route('/api/institutions/<int:inst_id>/departments')
def api_institution_departments(inst_id):
    depts = Department.query.filter_by(institution_id=inst_id).order_by(Department.name).all()
    return jsonify([{'id': d.id, 'name': d.name} for d in depts])


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')

        user = User.query.filter(db.func.lower(User.email) == email).first()

        if user and user.check_password(password):
            if user.role == 'institution':
                if user.approval_status == 'pending':
                    flash("Your institution account is awaiting approval by the Ascend admin.")
                    return redirect(url_for('login'))
                elif user.approval_status == 'rejected':
                    flash("Your institution account was not approved.")
                    return redirect(url_for('login'))
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.')

    institutions = User.query.filter_by(role='institution', approval_status='approved').order_by(User.name).all()
    return render_template('login.html', institutions=institutions)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        email = request.args.get('email', '').strip()
        return redirect(url_for('login', email=email, mode='register') if email else url_for('login', mode='register'))

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'member').strip().lower()
    phone = request.form.get('phone', '').strip()
    institution_id_raw = request.form.get('institution_id', '').strip()
    department_id_raw = request.form.get('department_id', '').strip()

    if not name or not email or not password:
        flash('Please fill out all required fields.')
        return redirect(url_for('login'))

    if role not in ['institution', 'staff', 'member']:
        role = 'member'

    user = User.query.filter(db.func.lower(User.email) == email).first()
    if user:
        flash('Email address already exists.')
        return redirect(url_for('login'))

    assigned_inst_id = None
    assigned_dept_id = None
    staff_status = None
    approval_status = None

    if role == 'institution':
        approval_status = 'pending'
    elif role == 'staff':
        staff_status = 'pending'
        if not institution_id_raw or not department_id_raw:
            flash('Please select both an accredited institution and a department for your staff account.')
            return redirect(url_for('login'))
        try:
            assigned_inst_id = int(institution_id_raw)
            assigned_dept_id = int(department_id_raw)
            inst_check = User.query.filter_by(id=assigned_inst_id, role='institution', approval_status='approved').first()
            if not inst_check:
                flash('Selected institution was not found or is not currently approved.')
                return redirect(url_for('login'))
            dept_check = Department.query.filter_by(id=assigned_dept_id, institution_id=assigned_inst_id).first()
            if not dept_check:
                flash('Selected department was not found under this institution.')
                return redirect(url_for('login'))
        except (ValueError, TypeError):
            flash('Invalid institution or department selected.')
            return redirect(url_for('login'))
    elif role == 'member':
        if institution_id_raw:
            try:
                assigned_inst_id = int(institution_id_raw)
                inst_check = User.query.filter_by(id=assigned_inst_id, role='institution', approval_status='approved').first()
                if inst_check:
                    if department_id_raw:
                        try:
                            assigned_dept_id = int(department_id_raw)
                            dept_check = Department.query.filter_by(id=assigned_dept_id, institution_id=assigned_inst_id).first()
                            if not dept_check:
                                assigned_dept_id = None
                        except (ValueError, TypeError):
                            assigned_dept_id = None
                else:
                    assigned_inst_id = None
            except (ValueError, TypeError):
                assigned_inst_id = None

    new_user = User(
        name=name,
        email=email,
        phone=phone if phone else None,
        role=role,
        institution_id=assigned_inst_id,
        department_id=assigned_dept_id,
        staff_status=staff_status,
        approval_status=approval_status
    )
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    # Link prior unattached notifications to the newly registered user
    conditions = [
        db.func.lower(db.func.trim(Notification.recipient_email)) == email
    ]
    if new_user.phone:
        conditions.append(Notification.recipient_phone == new_user.phone)

    Notification.query.filter(
        Notification.user_id.is_(None),
        db.or_(*conditions)
    ).update({"user_id": new_user.id}, synchronize_session=False)
    db.session.commit()

    if role == 'institution':
        flash('Institution administrator account registered successfully! Your account is awaiting approval by the Ascend admin.')
    elif role == 'staff':
        flash('Staff account registered successfully! Your account is pending verification by your institution.')
    else:
        flash('Member account registered successfully! Please sign in.')
    return redirect(url_for('login'))


def get_effective_institution_id(user):
    if user.role == 'staff' and user.institution_id:
        return user.institution_id
    return user.id


def get_institution_name(user):
    """Return the display name of the institution this user belongs to."""
    if user.role == 'institution':
        return user.name
    elif user.role == 'staff' and user.institution_id:
        inst = User.query.get(user.institution_id)
        return inst.name if inst else 'Your Institution'
    elif user.role == 'admin':
        return 'Ascend Platform'
    else:
        return 'Ascend Credentials'

def get_user_notifications_query(user):
    """Return query for all notifications belonging to user by user_id or email/phone."""
    if not user or not user.is_authenticated:
        return Notification.query.filter(db.false())

    conditions = [
        Notification.user_id == user.id
    ]
    if user.email:
        conditions.append(db.func.lower(db.func.trim(Notification.recipient_email)) == user.email.strip().lower())
    if user.phone:
        conditions.append(Notification.recipient_phone == user.phone.strip())

    return Notification.query.filter(db.or_(*conditions))


@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        unread_count = get_user_notifications_query(current_user).filter(Notification.is_read == False).count()
    else:
        unread_count = 0
    return dict(unread_notif_count=unread_count)


@app.route('/dashboard')
@login_required
def dashboard():
    # Helper query for unread notifications count
    notif_query = Notification.query.filter(
        db.or_(
            Notification.user_id == current_user.id,
            Notification.recipient_email == current_user.email,
            (Notification.recipient_phone == current_user.phone if current_user.phone else False)
        ),
        Notification.is_read == False
    )
    unread_notif_count = notif_query.count()

    stats = {}
    unclaimed = []
    claimed = []

    templates_list = []
    recent_issued = []
    pending_institutions = []

    if current_user.role == 'admin':
        pending_institutions = User.query.filter_by(role='institution', approval_status='pending').order_by(User.created_at.desc()).all()
        stats = {
            'total_users': User.query.count(),
            'total_institutions': User.query.filter_by(role='institution').count(),
            'total_members': User.query.filter_by(role='member').count(),
            'total_templates': Certificate.query.count(),
            'total_issued': IssuedCertificate.query.count()
        }
        templates_list = Certificate.query.order_by(Certificate.created_at.desc()).all()
        recent_issued = db.session.query(IssuedCertificate, Certificate).join(
            Certificate, IssuedCertificate.certificate_id == Certificate.id
        ).order_by(IssuedCertificate.issued_at.desc()).limit(10).all()
    elif current_user.role in ['institution', 'staff']:
        inst_id = get_effective_institution_id(current_user)
        stats = {
            'templates_count': Certificate.query.filter_by(institution_id=inst_id).count(),
            'issued_count': IssuedCertificate.query.filter_by(institution_id=inst_id).count(),
            'claimed_count': IssuedCertificate.query.filter_by(institution_id=inst_id, status='claimed').count()
        }
        templates_list = Certificate.query.filter_by(institution_id=inst_id).order_by(Certificate.created_at.desc()).all()
        recent_issued = db.session.query(IssuedCertificate, Certificate).join(
            Certificate, IssuedCertificate.certificate_id == Certificate.id
        ).filter(IssuedCertificate.institution_id == inst_id).order_by(IssuedCertificate.issued_at.desc()).limit(10).all()
    elif current_user.role == 'member':
        # Unclaimed issued certificates (status != 'claimed')
        unclaimed_raw = db.session.query(IssuedCertificate, Certificate, User).join(
            Certificate, IssuedCertificate.certificate_id == Certificate.id
        ).join(
            User, Certificate.institution_id == User.id
        ).filter(
            IssuedCertificate.status != 'claimed',
            db.or_(
                IssuedCertificate.recipient_email == current_user.email,
                (IssuedCertificate.recipient_phone == current_user.phone if current_user.phone else False)
            )
        ).all()

        unclaimed = [
            {
                'issued_id': ic.id,
                'cert_title': c.title,
                'institution_name': inst.name,
                'issued_at': ic.issued_at
            }
            for ic, c, inst in unclaimed_raw
        ]

        # Claimed certificates for member
        claimed = db.session.query(IssuedCertificate, Certificate, User).join(
            Certificate, IssuedCertificate.certificate_id == Certificate.id
        ).join(
            User, Certificate.institution_id == User.id
        ).filter(
            db.or_(
                IssuedCertificate.claimed_by_id == current_user.id,
                db.and_(
                    IssuedCertificate.status == 'claimed',
                    IssuedCertificate.recipient_email == current_user.email
                )
            )
        ).order_by(IssuedCertificate.issued_at.desc()).all()

    return render_template(
        'dashboard.html',
        user=current_user,
        stats=stats,
        unclaimed=unclaimed,
        claimed=claimed,
        templates=templates_list,
        recent_issued=recent_issued,
        unread_notif_count=unread_notif_count,
        institution_name=get_institution_name(current_user),
        pending_institutions=pending_institutions
    )


@app.route('/admin')
@login_required
def admin_console():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    pending_institutions = User.query.filter_by(role='institution', approval_status='pending').order_by(User.created_at.desc()).all()
    return render_template('admin.html', user=current_user, pending_institutions=pending_institutions)


@app.route('/admin/institutions/<int:user_id>/approve', methods=['POST'])
@login_required
def admin_approve_institution(user_id):
    if current_user.role != 'admin':
        abort(403)
    inst = User.query.filter_by(id=user_id, role='institution').first_or_404()
    inst.approval_status = 'approved'
    db.session.commit()
    try:
        email_institution_approved(inst.email, inst.name)
    except Exception as exc:
        app.logger.error("Failed to send institution approved email: %s", exc)
    flash(f"Institution '{inst.name}' has been approved.")
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/admin/institutions/<int:user_id>/reject', methods=['POST'])
@login_required
def admin_reject_institution(user_id):
    if current_user.role != 'admin':
        abort(403)
    inst = User.query.filter_by(id=user_id, role='institution').first_or_404()
    inst.approval_status = 'rejected'
    db.session.commit()
    try:
        email_institution_rejected(inst.email, inst.name)
    except Exception as exc:
        app.logger.error("Failed to send institution rejected email: %s", exc)
    flash(f"Institution '{inst.name}' was not approved.")
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    if current_user.role != 'member':
        return redirect(url_for('dashboard'))
    
    current_user.job_title = request.form.get('job_title')
    current_user.location = request.form.get('location')
    current_user.phone = request.form.get('phone')
    current_user.alumni = request.form.get('alumni')
    current_user.portfolio_url = request.form.get('portfolio_url')
    current_user.is_profile_setup = True
    
    db.session.commit()
    flash('Profile updated successfully!')
    return redirect(url_for('dashboard'))


# ── Settings (all roles) ────────────────────────────────────────────────────

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        # Profile fields
        name = request.form.get('name', '').strip()
        if name:
            current_user.name = name
        current_user.phone = request.form.get('phone', '').strip() or None
        current_user.job_title = request.form.get('job_title', '').strip() or None
        current_user.location = request.form.get('location', '').strip() or None
        current_user.alumni = request.form.get('alumni', '').strip() or None
        current_user.portfolio_url = request.form.get('portfolio_url', '').strip() or None
        current_user.is_profile_setup = True
        db.session.commit()
        flash('Profile updated successfully!')
        return redirect(url_for('settings'))
    return render_template('settings.html', user=current_user)


@app.route('/settings/change-password', methods=['POST'])
@login_required
def change_password():
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    if not current_user.check_password(current_pw):
        flash('Current password is incorrect.')
        return redirect(url_for('settings'))
    if len(new_pw) < 8:
        flash('New password must be at least 8 characters.')
        return redirect(url_for('settings'))
    if new_pw != confirm_pw:
        flash('New passwords do not match.')
        return redirect(url_for('settings'))

    current_user.set_password(new_pw)
    db.session.commit()
    flash('Password changed successfully!')
    return redirect(url_for('settings'))


@app.route('/settings/photo', methods=['POST'])
@login_required
def upload_photo():
    file = request.files.get('photo')
    if not file or file.filename == '':
        flash('No file selected.')
        return redirect(url_for('settings'))

    ALLOWED_MIMETYPES = {'image/jpeg', 'image/png', 'image/webp'}
    # Read into memory first to check size
    data = file.read()
    if len(data) > 2 * 1024 * 1024:
        flash('File is too large. Maximum size is 2 MB.')
        return redirect(url_for('settings'))

    # Detect mimetype via Pillow
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format  # 'JPEG', 'PNG', 'WEBP'
        mime_map = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}
        mimetype = mime_map.get(fmt)
        if not mimetype:
            flash('Only JPG, PNG, and WEBP images are accepted.')
            return redirect(url_for('settings'))

        # Crop to square then resize to 256x256
        w, h = img.size
        min_dim = min(w, h)
        left = (w - min_dim) // 2
        top = (h - min_dim) // 2
        img = img.crop((left, top, left + min_dim, top + min_dim))
        img = img.resize((256, 256), Image.LANCZOS)
        img = img.convert('RGB')  # normalise WEBP/PNG with alpha
        mimetype = 'image/jpeg'   # always save as JPEG to save space

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=88)
        current_user.profile_photo = buf.getvalue()
        current_user.profile_photo_mimetype = 'image/jpeg'
        db.session.commit()
        flash('Profile photo updated!')
    except Exception as e:
        flash(f'Could not process image: {e}')

    return redirect(url_for('settings'))


@app.route('/settings/photo/remove', methods=['POST'])
@login_required
def remove_photo():
    current_user.profile_photo = None
    current_user.profile_photo_mimetype = None
    db.session.commit()
    flash('Profile photo removed.')
    return redirect(url_for('settings'))


@app.route('/profile-photo/<int:user_id>')
def serve_profile_photo(user_id):
    user = User.query.get_or_404(user_id)
    if not user.profile_photo:
        return redirect(url_for('static', filename='default_avatar.png'))
    resp = make_response(user.profile_photo)
    resp.headers['Content-Type'] = user.profile_photo_mimetype or 'image/jpeg'
    resp.headers['Cache-Control'] = 'public, max-age=300'
    return resp


@app.route('/certificates/<int:issued_id>/claim', methods=['POST'])
@login_required
def claim_certificate(issued_id):
    if current_user.role != 'member':
        return redirect(url_for('dashboard'))
        
    issued_cert = IssuedCertificate.query.get(issued_id)
    if not issued_cert:
        flash('Certificate not found.')
        return redirect(url_for('dashboard'))

    is_recipient = (
        issued_cert.recipient_email == current_user.email or
        (current_user.phone and issued_cert.recipient_phone == current_user.phone)
    )
    if not is_recipient:
        flash('You are not authorized to claim this certificate.')
        return redirect(url_for('dashboard'))

    from datetime import datetime
    issued_cert.status = 'claimed'
    issued_cert.claimed_at = datetime.utcnow()
    issued_cert.claimed_by_id = current_user.id

    cert = Certificate.query.get(issued_cert.certificate_id)
    if cert:
        notif = Notification(
            user_id=cert.institution_id,
            message=f"Member {current_user.name} has claimed the certificate '{cert.title}'.",
            link=f"/verify/{issued_cert.verification_code}"
        )
        db.session.add(notif)

    db.session.commit()
    flash(f"Successfully claimed certificate '{cert.title if cert else ''}'!")
    return redirect(url_for('dashboard'))


@app.route('/notifications')
@login_required
def notifications_list():
    notifications = get_user_notifications_query(current_user).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', user=current_user, notifications=notifications)


@app.route('/notifications/<int:notif_id>/open', endpoint='open_notification')
@app.route('/notifications/<int:notif_id>', endpoint='click_notification')
@login_required
def open_notification(notif_id):
    notif = get_user_notifications_query(current_user).filter(Notification.id == notif_id).first()
    if not notif:
        abort(404)

    if not notif.is_read:
        notif.is_read = True
        db.session.commit()

    target_link = notif.link
    if target_link and target_link.startswith('/') and not target_link.startswith('//'):
        return redirect(target_link)
    return redirect(url_for('notifications_list'))


@app.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = get_user_notifications_query(current_user).filter(Notification.id == notif_id).first()
    if notif and not notif.is_read:
        notif.is_read = True
        db.session.commit()
    return redirect(url_for('notifications_list'))


@app.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    unreads = get_user_notifications_query(current_user).filter(Notification.is_read == False).all()
    for notif in unreads:
        notif.is_read = True
    db.session.commit()
    flash('All notifications marked as read.')
    return redirect(url_for('notifications_list'))


@app.route('/profile/<int:user_id>')
def public_profile(user_id):
    target_user = User.query.get_or_404(user_id)
    
    certificates = db.session.query(IssuedCertificate, Certificate, User).join(
        Certificate, IssuedCertificate.certificate_id == Certificate.id
    ).join(
        User, Certificate.institution_id == User.id
    ).filter(
        db.or_(
            IssuedCertificate.claimed_by_id == target_user.id,
            IssuedCertificate.recipient_email == target_user.email
        )
    ).order_by(IssuedCertificate.issued_at.desc()).all()

    return render_template('profile.html', target_user=target_user, certificates=certificates)


@app.route('/certificates/create', methods=['GET', 'POST'])
@login_required
def create_certificate():
    if current_user.role not in ['institution', 'staff']:
        return redirect(url_for('dashboard'))
    
    inst_id = get_effective_institution_id(current_user)
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        
        new_cert = Certificate(title=title, description=description, institution_id=inst_id)
        db.session.add(new_cert)
        db.session.commit()
        flash('Certificate created successfully!')
        return redirect(url_for('certificates_list'))
        
    return render_template('create_certificate.html', user=current_user, institution_name=get_institution_name(current_user))

@app.route('/certificates')
@login_required
def certificates_list():
    if current_user.role not in ['institution', 'staff']:
        return redirect(url_for('dashboard'))
        
    inst_id = get_effective_institution_id(current_user)
    certificates = Certificate.query.filter_by(institution_id=inst_id).order_by(Certificate.created_at.desc()).all()
    return render_template('certificates_list.html', certificates=certificates, user=current_user)

@app.route('/certificates/<int:cert_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_certificate(cert_id):
    if current_user.role not in ['institution', 'staff']:
        return redirect(url_for('dashboard'))
        
    inst_id = get_effective_institution_id(current_user)
    cert = Certificate.query.get(cert_id)
    if not cert or cert.institution_id != inst_id:
        return redirect(url_for('certificates_list'))
        
    if request.method == 'POST':
        cert.title = request.form.get('title')
        cert.description = request.form.get('description')
        db.session.commit()
        flash('Certificate updated successfully!')
        return redirect(url_for('certificates_list'))
        
    return render_template('edit_certificate.html', user=current_user, certificate=cert, institution_name=get_institution_name(current_user))

@app.route('/certificates/<int:cert_id>/delete', methods=['POST'])
@login_required
def delete_certificate(cert_id):
    if current_user.role not in ['institution', 'staff']:
        return redirect(url_for('dashboard'))
        
    inst_id = get_effective_institution_id(current_user)
    cert = Certificate.query.get(cert_id)
    if not cert or cert.institution_id != inst_id:
        return redirect(url_for('certificates_list'))
        
    db.session.delete(cert)
    db.session.commit()
    flash('Certificate deleted successfully!')
    return redirect(url_for('certificates_list'))

def issue_to_recipient(cert, inst_id, email, phone):
    """
    Creates an IssuedCertificate and its associated Notification without committing.
    Returns the created IssuedCertificate.
    """
    code = str(uuid.uuid4())
    clean_email = email.strip().lower() if email else None
    clean_phone = phone.strip() if phone else None

    issued_cert = IssuedCertificate(
        certificate_id=cert.id,
        institution_id=inst_id,
        recipient_email=clean_email,
        recipient_phone=clean_phone,
        verification_code=code,
        status='issued'
    )
    db.session.add(issued_cert)

    # Find matching member user to associate notification directly if exists
    target_user = None
    if clean_email:
        target_user = User.query.filter(db.func.lower(User.email) == clean_email).first()
    if not target_user and clean_phone:
        target_user = User.query.filter_by(phone=clean_phone).first()

    inst_user = User.query.get(inst_id)
    issuer_name = inst_user.name if inst_user else (current_user.name if current_user.is_authenticated else 'Institution')
    notif = Notification(
        user_id=target_user.id if target_user else None,
        recipient_email=clean_email,
        recipient_phone=clean_phone,
        message=f"You received a new certificate: '{cert.title}' from {issuer_name}.",
        link=f"/verify/{issued_cert.verification_code}"
    )
    db.session.add(notif)
    return issued_cert

@app.route('/certificates/<int:cert_id>/issue', methods=['GET', 'POST'])
@login_required
def issue_certificate(cert_id):
    if current_user.role not in ['institution', 'staff']:
        return redirect(url_for('dashboard'))
        
    if current_user.role == 'institution' and current_user.approval_status != 'approved':
        flash('Your institution account must be approved before issuing certificates.')
        return redirect(url_for('dashboard'))

    if current_user.role == 'staff' and current_user.staff_status != 'verified':
        flash('Your staff account is pending verification and cannot issue certificates.')
        return redirect(url_for('dashboard'))

    inst_id = get_effective_institution_id(current_user)
    cert = Certificate.query.get(cert_id)
    if not cert or cert.institution_id != inst_id:
        return redirect(url_for('certificates_list'))
        
    if request.method == 'POST':
        recipient_email = request.form.get('recipient_email', '').strip().lower()
        recipient_phone = request.form.get('recipient_phone', '').strip()
        
        if not recipient_email and not recipient_phone:
            flash('Please enter at least an email or a phone number for the recipient.')
            return redirect(url_for('issue_certificate', cert_id=cert_id))
        
        issued_cert = issue_to_recipient(cert, inst_id, recipient_email, recipient_phone)
        db.session.commit()

        if recipient_email:
            try:
                has_acct = User.query.filter(db.func.lower(User.email) == recipient_email.lower()).first() is not None
                inst_user = User.query.get(inst_id)
                inst_title = inst_user.name if inst_user else 'Institution'
                email_certificate_issued(
                    recipient_email=recipient_email,
                    cert_title=cert.title,
                    institution_name=inst_title,
                    verification_code=issued_cert.verification_code,
                    has_account=has_acct
                )
            except Exception as exc:
                app.logger.error("Failed to trigger issuance email: %s", exc)

        recipient_display = recipient_email or recipient_phone
        flash(f'Certificate successfully issued to {recipient_display}!')
        return redirect(url_for('issued_list'))
        
    return render_template('issue_certificate.html', user=current_user, certificate=cert)

@app.route('/certificates/bulk-template.xlsx')
@login_required
def download_bulk_template():
    if current_user.role not in ['institution', 'staff']:
        return redirect(url_for('dashboard'))

    if current_user.role == 'institution' and current_user.approval_status != 'approved':
        return redirect(url_for('dashboard'))

    if current_user.role == 'staff' and current_user.staff_status != 'verified':
        return redirect(url_for('dashboard'))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Recipients"
    ws.append(["email", "phone"])
    ws.append(["student@example.com", "+911234567890"])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="bulk-template.xlsx"
    )

@app.route('/certificates/<int:cert_id>/bulk-issue', methods=['GET', 'POST'])
@login_required
def bulk_issue_certificate(cert_id):
    if current_user.role not in ['institution', 'staff']:
        return redirect(url_for('dashboard'))

    if current_user.role == 'institution' and current_user.approval_status != 'approved':
        flash('Your institution account must be approved before issuing certificates.')
        return redirect(url_for('dashboard'))

    if current_user.role == 'staff' and current_user.staff_status != 'verified':
        flash('Your staff account is pending verification and cannot issue certificates.')
        return redirect(url_for('dashboard'))

    inst_id = get_effective_institution_id(current_user)
    cert = Certificate.query.get(cert_id)
    if not cert or cert.institution_id != inst_id:
        return redirect(url_for('certificates_list'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file was provided in the upload request.')
            return redirect(url_for('bulk_issue_certificate', cert_id=cert_id))

        file = request.files['file']
        if not file or not file.filename:
            flash('Please select an Excel (.xlsx) file to upload.')
            return redirect(url_for('bulk_issue_certificate', cert_id=cert_id))

        if not file.filename.lower().endswith('.xlsx'):
            flash('Unsupported file format. Please upload an Excel workbook (.xlsx).')
            return redirect(url_for('bulk_issue_certificate', cert_id=cert_id))

        file_bytes = file.read()
        if len(file_bytes) > 2 * 1024 * 1024:
            flash('File size exceeds the 2 MB limit.')
            return redirect(url_for('bulk_issue_certificate', cert_id=cert_id))

        try:
            buf = io.BytesIO(file_bytes)
            wb = openpyxl.load_workbook(buf, read_only=True, data_only=True)
            sheet = wb.worksheets[0]
            rows = list(sheet.iter_rows(values_only=True))
            wb.close()
        except Exception:
            flash('Failed to read Excel file. Please ensure it is a valid, uncorrupted .xlsx workbook.')
            return redirect(url_for('bulk_issue_certificate', cert_id=cert_id))

        if not rows:
            flash('The uploaded spreadsheet contains no rows.')
            return redirect(url_for('bulk_issue_certificate', cert_id=cert_id))

        header_row = rows[0]
        email_col_idx = None
        phone_col_idx = None
        for idx, cell in enumerate(header_row):
            if cell is not None:
                col_name = str(cell).strip().lower()
                if col_name == 'email' and email_col_idx is None:
                    email_col_idx = idx
                elif col_name == 'phone' and phone_col_idx is None:
                    phone_col_idx = idx

        if email_col_idx is None and phone_col_idx is None:
            flash('Spreadsheet must include at least an "email" or "phone" column header.')
            return redirect(url_for('bulk_issue_certificate', cert_id=cert_id))

        data_rows = rows[1:]
        # Check non-empty rows limit of 500
        non_empty_count = sum(1 for r in data_rows if any(c is not None and str(c).strip() != '' for c in r))
        if non_empty_count > 500:
            flash('The uploaded spreadsheet exceeds the maximum limit of 500 data rows.')
            return redirect(url_for('bulk_issue_certificate', cert_id=cert_id))

        existing_certs = IssuedCertificate.query.filter_by(certificate_id=cert_id).all()
        existing_emails = {c.recipient_email.strip().lower() for c in existing_certs if c.recipient_email}
        existing_phones = {c.recipient_phone.strip() for c in existing_certs if c.recipient_phone}

        seen_emails = set()
        seen_phones = set()

        issued_count = 0
        skipped_count = 0
        invalid_count = 0
        row_details = []
        newly_issued_certs = []

        EMAIL_REGEX = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

        for row_idx, row in enumerate(data_rows, start=2):
            if not row or all(c is None or str(c).strip() == '' for c in row):
                continue

            # Extract and normalize email
            raw_email = row[email_col_idx] if email_col_idx is not None and email_col_idx < len(row) else None
            email = str(raw_email).strip().lower() if raw_email is not None and str(raw_email).strip() != '' else None

            # Extract and normalize phone
            raw_phone = row[phone_col_idx] if phone_col_idx is not None and phone_col_idx < len(row) else None
            phone = None
            if raw_phone is not None:
                if isinstance(raw_phone, (int,)):
                    val = str(raw_phone).strip()
                    phone = val if val else None
                elif isinstance(raw_phone, float):
                    if raw_phone.is_integer():
                        val = str(int(raw_phone)).strip()
                    else:
                        val = str(raw_phone).strip()
                        if val.endswith('.0'):
                            val = val[:-2].strip()
                    phone = val if val else None
                else:
                    val = str(raw_phone).strip()
                    if val.endswith('.0'):
                        val = val[:-2].strip()
                    phone = val if val else None

            display_val = email or phone or '(empty)'

            # Invalid: no email and no phone, or email that doesn't match basic email regex
            if not email and not phone:
                invalid_count += 1
                row_details.append({
                    'row_num': row_idx,
                    'value': display_val,
                    'status': 'invalid',
                    'reason': 'Missing both email and phone number'
                })
                continue

            if email and not EMAIL_REGEX.match(email):
                invalid_count += 1
                row_details.append({
                    'row_num': row_idx,
                    'value': display_val,
                    'status': 'invalid',
                    'reason': f"Invalid email format: '{email}'"
                })
                continue

            # Skipped as duplicate: in file or already in DB
            is_duplicate = False
            dup_reason = ""
            if email and email in seen_emails:
                is_duplicate = True
                dup_reason = 'Duplicate email earlier in file'
            elif phone and phone in seen_phones:
                is_duplicate = True
                dup_reason = 'Duplicate phone number earlier in file'
            elif email and email in existing_emails:
                is_duplicate = True
                dup_reason = 'Certificate already issued to this email'
            elif phone and phone in existing_phones:
                is_duplicate = True
                dup_reason = 'Certificate already issued to this phone number'

            if is_duplicate:
                skipped_count += 1
                row_details.append({
                    'row_num': row_idx,
                    'value': display_val,
                    'status': 'skipped',
                    'reason': dup_reason
                })
                continue

            # Valid recipient
            if email:
                seen_emails.add(email)
            if phone:
                seen_phones.add(phone)

            ic = issue_to_recipient(cert, inst_id, email, phone)
            if email:
                newly_issued_certs.append((ic, email))
            issued_count += 1

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('A database error occurred during bulk issuance. Changes have been rolled back.')
            return redirect(url_for('bulk_issue_certificate', cert_id=cert_id))

        if newly_issued_certs:
            try:
                inst_user = User.query.get(inst_id)
                inst_title = inst_user.name if inst_user else 'Institution'
                bulk_items = []
                for ic, em in newly_issued_certs:
                    has_acct = User.query.filter(db.func.lower(User.email) == em.lower()).first() is not None
                    payload = build_certificate_email_payload(
                        recipient_email=em,
                        cert_title=cert.title,
                        institution_name=inst_title,
                        verification_code=ic.verification_code,
                        has_account=has_acct
                    )
                    bulk_items.append(payload)
                if bulk_items:
                    send_emails_bulk(bulk_items, pause=0.5)
            except Exception as exc:
                app.logger.error("Failed to queue bulk issuance emails: %s", exc)

        results = {
            'issued': issued_count,
            'skipped': skipped_count,
            'invalid': invalid_count,
            'details': row_details
        }
        return render_template('bulk_issue_results.html', user=current_user, certificate=cert, results=results)

    return render_template('bulk_issue.html', user=current_user, certificate=cert)

@app.route('/issued')
@login_required
def issued_list():
    if current_user.role not in ['institution', 'staff']:
        return redirect(url_for('dashboard'))
        
    inst_id = get_effective_institution_id(current_user)
    issued = db.session.query(IssuedCertificate, Certificate).join(
        Certificate, IssuedCertificate.certificate_id == Certificate.id
    ).filter(
        IssuedCertificate.institution_id == inst_id
    ).order_by(
        IssuedCertificate.issued_at.desc()
    ).all()
    
    return render_template('issued_list.html', issued=issued, user=current_user)

@app.route('/verify', methods=['GET', 'POST'])
@app.route('/verify/<code>', methods=['GET'])
def verify_certificate(code=None):
    if request.method == 'POST':
        search_code = request.form.get('code', '').strip()
        if search_code:
            return redirect(url_for('verify_certificate', code=search_code))
            
    if not code:
        query_code = request.args.get('code', '').strip()
        if query_code:
            return redirect(url_for('verify_certificate', code=query_code))
        code = ''
        
    issued = None
    claimed_user = None
    qr_b64 = None
    share_url = None
    
    if code:
        issued = db.session.query(IssuedCertificate, Certificate, User).join(
            Certificate, IssuedCertificate.certificate_id == Certificate.id
        ).join(
            User, Certificate.institution_id == User.id
        ).filter(
            IssuedCertificate.verification_code == code
        ).first()
        
        if issued:
            if issued[0].claimed_by_id:
                claimed_user = User.query.get(issued[0].claimed_by_id)
            share_url = url_for('verify_certificate', code=code, _external=True)
            try:
                qr_b64 = generate_qr_base64(share_url)
            except Exception as e:
                qr_b64 = None

    return render_template('verify.html', result=issued, claimed_user=claimed_user, code=code, qr_b64=qr_b64, share_url=share_url)


@app.route('/certificate/<code>')
def view_certificate(code):
    issued = db.session.query(IssuedCertificate, Certificate, User).join(
        Certificate, IssuedCertificate.certificate_id == Certificate.id
    ).join(
        User, Certificate.institution_id == User.id
    ).filter(
        IssuedCertificate.verification_code == code
    ).first()

    if not issued:
        flash('Certificate not found.')
        return redirect(url_for('verify_certificate', code=code))

    issued_cert, cert, institution = issued

    # Access rules: the member who claimed it and the issuing institution can view the full certificate page
    if not current_user.is_authenticated:
        flash('Please sign in to view the official certificate document. You may also view the public verification record below.')
        return redirect(url_for('login', next=request.url))

    is_admin = (current_user.role == 'admin')
    is_issuer = False
    if current_user.role in ['institution', 'staff']:
        inst_id = get_effective_institution_id(current_user)
        is_issuer = (inst_id == issued_cert.institution_id)

    is_recipient = False
    if issued_cert.claimed_by_id and current_user.id == issued_cert.claimed_by_id:
        is_recipient = True
    elif not issued_cert.claimed_by_id:
        if current_user.email == issued_cert.recipient_email:
            is_recipient = True
        elif current_user.phone and issued_cert.recipient_phone == current_user.phone:
            is_recipient = True

    if not (is_admin or is_issuer or is_recipient):
        flash('The rendered certificate document is restricted to the recipient member and the issuing institution. Viewing the public verification record instead.')
        return redirect(url_for('verify_certificate', code=code))

    claimed_user = None
    if issued_cert.claimed_by_id:
        claimed_user = User.query.get(issued_cert.claimed_by_id)

    recipient_name = (
        claimed_user.name if claimed_user
        else (issued_cert.recipient_email or issued_cert.recipient_phone or 'Designated Recipient')
    )

    verify_url = url_for('verify_certificate', code=code, _external=True)
    qr_b64 = None
    try:
        qr_b64 = generate_qr_base64(verify_url)
    except Exception:
        qr_b64 = None

    return render_template(
        'certificate.html',
        issued_cert=issued_cert,
        cert=cert,
        institution=institution,
        claimed_user=claimed_user,
        recipient_name=recipient_name,
        verify_url=verify_url,
        qr_b64=qr_b64,
        user=current_user
    )


@app.route('/reports')
@login_required
def reports():
    if current_user.role not in ['admin', 'institution', 'staff']:
        return redirect(url_for('dashboard'))

    summary = {}
    institution_breakdown = []
    template_breakdown = []

    if current_user.role == 'admin':
        summary = {
            'total_users': User.query.count(),
            'total_institutions': User.query.filter_by(role='institution').count(),
            'total_members': User.query.filter_by(role='member').count(),
            'total_issued': IssuedCertificate.query.count()
        }

        institutions = User.query.filter_by(role='institution').all()
        for inst in institutions:
            t_count = Certificate.query.filter_by(institution_id=inst.id).count()
            i_count = IssuedCertificate.query.filter_by(institution_id=inst.id).count()
            institution_breakdown.append({
                'name': inst.name,
                'email': inst.email,
                'template_count': t_count,
                'issued_count': i_count
            })

    elif current_user.role in ['institution', 'staff']:
        inst_id = get_effective_institution_id(current_user)
        summary = {
            'templates_count': Certificate.query.filter_by(institution_id=inst_id).count(),
            'issued_count': IssuedCertificate.query.filter_by(institution_id=inst_id).count(),
            'claimed_count': IssuedCertificate.query.filter_by(institution_id=inst_id, status='claimed').count()
        }

        templates = Certificate.query.filter_by(institution_id=inst_id).all()
        for t in templates:
            i_count = IssuedCertificate.query.filter_by(certificate_id=t.id).count()
            c_count = IssuedCertificate.query.filter_by(certificate_id=t.id, status='claimed').count()
            template_breakdown.append({
                'title': t.title,
                'issued_count': i_count,
                'claimed_count': c_count
            })

    return render_template(
        'reports.html',
        user=current_user,
        summary=summary,
        institution_breakdown=institution_breakdown,
        template_breakdown=template_breakdown
    )


# ── Institution Head Dashboard ──────────────────────────────────────────────

def _require_institution_head():
    """Return (institution_user, None) or (None, redirect_response)."""
    if not current_user.is_authenticated:
        from flask_login import login_url
        return None, redirect(url_for('login'))
    if current_user.role != 'institution':
        abort(403)
    if current_user.approval_status != 'approved':
        flash('Your institution account is not approved.')
        return None, redirect(url_for('dashboard'))
    return current_user, None


@app.route('/institution/dashboard')
@login_required
def institution_dashboard():
    inst, err = _require_institution_head()
    if err:
        return err
    inst_id = inst.id

    # Overview stats
    total_students = User.query.filter_by(role='member', institution_id=inst_id).count()
    total_staff = User.query.filter_by(role='staff', institution_id=inst_id).count()
    verified_staff = User.query.filter_by(role='staff', institution_id=inst_id, staff_status='verified').count()
    pending_staff = User.query.filter_by(role='staff', institution_id=inst_id, staff_status='pending').count()
    num_departments = Department.query.filter_by(institution_id=inst_id).count()
    num_clubs = Club.query.filter_by(institution_id=inst_id).count()
    total_issued = IssuedCertificate.query.filter_by(institution_id=inst_id).count()
    claimed_issued = IssuedCertificate.query.filter_by(institution_id=inst_id, status='claimed').count()
    unclaimed_issued = total_issued - claimed_issued

    # Per-department table
    departments = Department.query.filter_by(institution_id=inst_id).order_by(Department.name).all()
    dept_rows = []
    for dept in departments:
        dept_students = User.query.filter_by(role='member', department_id=dept.id, institution_id=inst_id).count()
        dept_staff = User.query.filter_by(role='staff', department_id=dept.id, institution_id=inst_id).count()
        # issued certs to students in this dept
        student_emails = db.session.query(User.email).filter_by(
            role='member', department_id=dept.id, institution_id=inst_id
        ).all()
        email_list = [e[0].strip().lower() for e in student_emails if e[0]]
        if email_list:
            dept_certs = IssuedCertificate.query.filter(
                IssuedCertificate.institution_id == inst_id,
                db.func.lower(IssuedCertificate.recipient_email).in_(email_list)
            ).count()
        else:
            dept_certs = 0
        dept_rows.append({
            'id': dept.id,
            'name': dept.name,
            'students': dept_students,
            'staff': dept_staff,
            'certs': dept_certs
        })

    # Recent 5 issuances
    recent_issuances = db.session.query(IssuedCertificate, Certificate).join(
        Certificate, IssuedCertificate.certificate_id == Certificate.id
    ).filter(IssuedCertificate.institution_id == inst_id).order_by(
        IssuedCertificate.issued_at.desc()
    ).limit(5).all()

    stats = {
        'total_students': total_students,
        'total_staff': total_staff,
        'verified_staff': verified_staff,
        'pending_staff': pending_staff,
        'num_departments': num_departments,
        'num_clubs': num_clubs,
        'total_issued': total_issued,
        'claimed_issued': claimed_issued,
        'unclaimed_issued': unclaimed_issued,
    }

    clubs = Club.query.filter_by(institution_id=inst_id).order_by(Club.name).all()
    all_staff = User.query.filter_by(role='staff', institution_id=inst_id).order_by(
        db.case((User.staff_status == 'pending', 0), else_=1),
        User.name
    ).all()
    students = User.query.filter_by(role='member', institution_id=inst_id).order_by(User.name).all()

    return render_template(
        'institution_dashboard.html',
        user=inst,
        stats=stats,
        dept_rows=dept_rows,
        recent_issuances=recent_issuances,
        departments=departments,
        clubs=clubs,
        all_staff=all_staff,
        students=students,
        active_tab=request.args.get('tab', 'overview')
    )


@app.route('/institution/departments/add', methods=['POST'])
@login_required
def institution_add_department():
    inst, err = _require_institution_head()
    if err:
        return err
    name = request.form.get('name', '').strip()
    if not name:
        flash('Department name cannot be empty.')
        return redirect(url_for('institution_dashboard', tab='departments'))
    existing = Department.query.filter_by(institution_id=inst.id, name=name).first()
    if existing:
        flash(f'Department "{name}" already exists.')
        return redirect(url_for('institution_dashboard', tab='departments'))
    dept = Department(institution_id=inst.id, name=name)
    db.session.add(dept)
    db.session.commit()
    flash(f'Department "{name}" added.')
    return redirect(url_for('institution_dashboard', tab='departments'))


@app.route('/institution/departments/<int:dept_id>/rename', methods=['POST'])
@login_required
def institution_rename_department(dept_id):
    inst, err = _require_institution_head()
    if err:
        return err
    dept = Department.query.filter_by(id=dept_id, institution_id=inst.id).first_or_404()
    new_name = request.form.get('name', '').strip()
    if not new_name:
        flash('Department name cannot be empty.')
        return redirect(url_for('institution_dashboard', tab='departments'))
    conflict = Department.query.filter_by(institution_id=inst.id, name=new_name).first()
    if conflict and conflict.id != dept_id:
        flash(f'Department "{new_name}" already exists.')
        return redirect(url_for('institution_dashboard', tab='departments'))
    dept.name = new_name
    db.session.commit()
    flash(f'Department renamed to "{new_name}".')
    return redirect(url_for('institution_dashboard', tab='departments'))


@app.route('/institution/departments/<int:dept_id>/delete', methods=['POST'])
@login_required
def institution_delete_department(dept_id):
    inst, err = _require_institution_head()
    if err:
        return err
    dept = Department.query.filter_by(id=dept_id, institution_id=inst.id).first_or_404()
    # Block if any user is assigned
    user_count = User.query.filter_by(department_id=dept_id).count()
    if user_count > 0:
        flash(f'Cannot delete "{dept.name}": {user_count} user(s) are assigned to it. Reassign or remove them first.')
        return redirect(url_for('institution_dashboard', tab='departments'))
    db.session.delete(dept)
    db.session.commit()
    flash(f'Department "{dept.name}" deleted.')
    return redirect(url_for('institution_dashboard', tab='departments'))


@app.route('/institution/clubs/add', methods=['POST'])
@login_required
def institution_add_club():
    inst, err = _require_institution_head()
    if err:
        return err
    name = request.form.get('name', '').strip()
    if not name:
        flash('Club name cannot be empty.')
        return redirect(url_for('institution_dashboard', tab='clubs'))
    existing = Club.query.filter_by(institution_id=inst.id, name=name).first()
    if existing:
        flash(f'Club "{name}" already exists.')
        return redirect(url_for('institution_dashboard', tab='clubs'))
    club = Club(institution_id=inst.id, name=name)
    db.session.add(club)
    db.session.commit()
    flash(f'Club "{name}" added.')
    return redirect(url_for('institution_dashboard', tab='clubs'))


@app.route('/institution/clubs/<int:club_id>/delete', methods=['POST'])
@login_required
def institution_delete_club(club_id):
    inst, err = _require_institution_head()
    if err:
        return err
    club = Club.query.filter_by(id=club_id, institution_id=inst.id).first_or_404()
    name = club.name
    db.session.delete(club)
    db.session.commit()
    flash(f'Club "{name}" deleted.')
    return redirect(url_for('institution_dashboard', tab='clubs'))


@app.route('/institution/staff/<int:staff_id>/verify', methods=['POST'])
@login_required
def institution_verify_staff(staff_id):
    inst, err = _require_institution_head()
    if err:
        return err
    staff = User.query.filter_by(id=staff_id, role='staff', institution_id=inst.id).first_or_404()
    staff.staff_status = 'verified'
    notif = Notification(
        user_id=staff.id,
        recipient_email=staff.email,
        message=f"Your staff account at {inst.name} has been verified. You can now issue certificates.",
        link="/dashboard"
    )
    db.session.add(notif)
    db.session.commit()
    try:
        email_staff_verified(staff.email, staff.name, inst.name)
    except Exception as exc:
        app.logger.error("Failed to send staff verified email: %s", exc)
    flash(f'{staff.name} has been verified as staff.')
    return redirect(url_for('institution_dashboard', tab='staff'))


@app.route('/institution/staff/<int:staff_id>/reject', methods=['POST'])
@login_required
def institution_reject_staff(staff_id):
    inst, err = _require_institution_head()
    if err:
        return err
    staff = User.query.filter_by(id=staff_id, role='staff', institution_id=inst.id).first_or_404()
    staff.staff_status = 'rejected'
    notif = Notification(
        user_id=staff.id,
        recipient_email=staff.email,
        message=f"Your staff application at {inst.name} has been rejected. Please contact the institution for more information.",
        link="/dashboard"
    )
    db.session.add(notif)
    db.session.commit()
    try:
        email_staff_rejected(staff.email, staff.name, inst.name)
    except Exception as exc:
        app.logger.error("Failed to send staff rejected email: %s", exc)
    flash(f'{staff.name} staff status set to rejected.')
    return redirect(url_for('institution_dashboard', tab='staff'))


@app.route('/institution/staff/<int:staff_id>/remove', methods=['POST'])
@login_required
def institution_remove_staff(staff_id):
    inst, err = _require_institution_head()
    if err:
        return err
    staff = User.query.filter_by(id=staff_id, role='staff', institution_id=inst.id).first_or_404()
    staff.institution_id = None
    staff.department_id = None
    staff.staff_status = None
    db.session.commit()
    flash(f'{staff.name} removed from institution.')
    return redirect(url_for('institution_dashboard', tab='staff'))


@app.route('/institution/students/<int:student_id>/remove', methods=['POST'])
@login_required
def institution_remove_student(student_id):
    inst, err = _require_institution_head()
    if err:
        return err
    student = User.query.filter_by(id=student_id, role='member', institution_id=inst.id).first_or_404()
    student.institution_id = None
    student.department_id = None
    db.session.commit()
    flash(f'{student.name} removed from institution.')
    return redirect(url_for('institution_dashboard', tab='students'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)