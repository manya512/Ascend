import qrcode
import io
import base64
from flask import Flask, render_template, redirect, url_for, request, flash, Response, make_response, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from PIL import Image

from config import Config
from models import db, User, Certificate, IssuedCertificate, Notification

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.')

    institutions = User.query.filter_by(role='institution').order_by(User.name).all()
    return render_template('login.html', institutions=institutions)


@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'member').strip().lower()
    phone = request.form.get('phone', '').strip()
    institution_id_raw = request.form.get('institution_id')

    if not name or not email or not password:
        flash('Please fill out all required fields.')
        return redirect(url_for('login'))

    if role not in ['institution', 'staff', 'member']:
        role = 'member'

    user = User.query.filter_by(email=email).first()
    if user:
        flash('Email address already exists.')
        return redirect(url_for('login'))

    assigned_inst_id = None
    if role == 'staff':
        if not institution_id_raw:
            flash('Please select an accredited institution for your staff account.')
            return redirect(url_for('login'))
        try:
            assigned_inst_id = int(institution_id_raw)
            inst_check = User.query.filter_by(id=assigned_inst_id, role='institution').first()
            if not inst_check:
                flash('Selected institution was not found.')
                return redirect(url_for('login'))
        except (ValueError, TypeError):
            flash('Invalid institution selected.')
            return redirect(url_for('login'))

    new_user = User(
        name=name,
        email=email,
        phone=phone if phone else None,
        role=role,
        institution_id=assigned_inst_id
    )
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    # Link prior unattached notifications to the newly registered user
    conditions = [
        db.func.lower(db.func.trim(Notification.recipient_email)) == email.lower()
    ]
    if new_user.phone:
        conditions.append(Notification.recipient_phone == new_user.phone)

    Notification.query.filter(
        Notification.user_id.is_(None),
        db.or_(*conditions)
    ).update({"user_id": new_user.id}, synchronize_session=False)
    db.session.commit()

    if role == 'institution':
        flash('Institution administrator account registered successfully! Please sign in.')
    elif role == 'staff':
        flash('Staff issuer account registered successfully! Please sign in.')
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

    if current_user.role == 'admin':
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
        institution_name=get_institution_name(current_user)
    )


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

@app.route('/certificates/<int:cert_id>/issue', methods=['GET', 'POST'])
@login_required
def issue_certificate(cert_id):
    if current_user.role not in ['institution', 'staff']:
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
        
        issued_cert = IssuedCertificate(
            certificate_id=cert_id,
            institution_id=inst_id,
            recipient_email=recipient_email if recipient_email else None,
            recipient_phone=recipient_phone if recipient_phone else None,
            status='issued'
        )
        db.session.add(issued_cert)
        db.session.commit()
        
        # Find matching member user to associate notification directly if exists
        target_user = None
        if recipient_email:
            target_user = User.query.filter(db.func.lower(User.email) == recipient_email).first()
        if not target_user and recipient_phone:
            target_user = User.query.filter_by(phone=recipient_phone).first()
            
        inst_user = User.query.get(inst_id)
        issuer_name = inst_user.name if inst_user else current_user.name
        notif = Notification(
            user_id=target_user.id if target_user else None,
            recipient_email=recipient_email if recipient_email else None,
            recipient_phone=recipient_phone if recipient_phone else None,
            message=f"You received a new certificate: '{cert.title}' from {issuer_name}.",
            link=f"/verify/{issued_cert.verification_code}"
        )
        db.session.add(notif)
        db.session.commit()
        
        recipient_display = recipient_email or recipient_phone
        flash(f'Certificate successfully issued to {recipient_display}!')
        return redirect(url_for('issued_list'))
        
    return render_template('issue_certificate.html', user=current_user, certificate=cert)

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


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)