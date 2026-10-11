import qrcode
import io
import base64
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

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

    return render_template('login.html')


@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')

    if not name or not email or not password:
        flash('Please fill out all fields.')
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first()

    if user:
        flash('Email address already exists.')
        return redirect(url_for('login'))

    new_user = User(name=name, email=email, role='member')
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    flash('Registration successful! Please log in.')
    return redirect(url_for('login'))


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

    if current_user.role == 'admin':
        stats = {
            'total_users': User.query.count(),
            'total_institutions': User.query.filter_by(role='institution').count(),
            'total_members': User.query.filter_by(role='member').count(),
            'total_templates': Certificate.query.count(),
            'total_issued': IssuedCertificate.query.count()
        }
    elif current_user.role == 'institution':
        stats = {
            'templates_count': Certificate.query.filter_by(institution_id=current_user.id).count(),
            'issued_count': IssuedCertificate.query.filter_by(institution_id=current_user.id).count(),
            'claimed_count': IssuedCertificate.query.filter_by(institution_id=current_user.id, status='claimed').count()
        }
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
        unread_notif_count=unread_notif_count
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
    notifications = Notification.query.filter(
        db.or_(
            Notification.user_id == current_user.id,
            Notification.recipient_email == current_user.email,
            (Notification.recipient_phone == current_user.phone if current_user.phone else False)
        )
    ).order_by(Notification.created_at.desc()).all()

    return render_template('notifications.html', user=current_user, notifications=notifications)


@app.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.get(notif_id)
    if notif:
        notif.is_read = True
        db.session.commit()
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
    if current_user.role != 'institution':
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        
        new_cert = Certificate(title=title, description=description, institution_id=current_user.id)
        db.session.add(new_cert)
        db.session.commit()
        flash('Certificate created successfully!')
        return redirect(url_for('certificates_list'))
        
    return render_template('create_certificate.html', user=current_user)

@app.route('/certificates')
@login_required
def certificates_list():
    if current_user.role != 'institution':
        return redirect(url_for('dashboard'))
        
    certificates = Certificate.query.filter_by(institution_id=current_user.id).order_by(Certificate.created_at.desc()).all()
    return render_template('certificates_list.html', certificates=certificates, user=current_user)

@app.route('/certificates/<int:cert_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_certificate(cert_id):
    if current_user.role != 'institution':
        return redirect(url_for('dashboard'))
        
    cert = Certificate.query.get(cert_id)
    if not cert or cert.institution_id != current_user.id:
        return redirect(url_for('certificates_list'))
        
    if request.method == 'POST':
        cert.title = request.form.get('title')
        cert.description = request.form.get('description')
        db.session.commit()
        flash('Certificate updated successfully!')
        return redirect(url_for('certificates_list'))
        
    return render_template('edit_certificate.html', user=current_user, certificate=cert)

@app.route('/certificates/<int:cert_id>/delete', methods=['POST'])
@login_required
def delete_certificate(cert_id):
    if current_user.role != 'institution':
        return redirect(url_for('dashboard'))
        
    cert = Certificate.query.get(cert_id)
    if not cert or cert.institution_id != current_user.id:
        return redirect(url_for('certificates_list'))
        
    db.session.delete(cert)
    db.session.commit()
    flash('Certificate deleted successfully!')
    return redirect(url_for('certificates_list'))

@app.route('/certificates/<int:cert_id>/issue', methods=['GET', 'POST'])
@login_required
def issue_certificate(cert_id):
    if current_user.role != 'institution':
        return redirect(url_for('dashboard'))
        
    cert = Certificate.query.get(cert_id)
    if not cert or cert.institution_id != current_user.id:
        return redirect(url_for('certificates_list'))
        
    if request.method == 'POST':
        recipient_email = request.form.get('recipient_email', '').strip()
        recipient_phone = request.form.get('recipient_phone', '').strip()
        
        if not recipient_email and not recipient_phone:
            flash('Please enter at least an email or a phone number for the recipient.')
            return redirect(url_for('issue_certificate', cert_id=cert_id))
        
        issued_cert = IssuedCertificate(
            certificate_id=cert_id,
            institution_id=current_user.id,
            recipient_email=recipient_email if recipient_email else None,
            recipient_phone=recipient_phone if recipient_phone else None,
            status='issued'
        )
        db.session.add(issued_cert)
        db.session.commit()
        
        # Find matching member user to associate notification directly if exists
        target_user = None
        if recipient_email:
            target_user = User.query.filter_by(email=recipient_email).first()
        if not target_user and recipient_phone:
            target_user = User.query.filter_by(phone=recipient_phone).first()
            
        notif = Notification(
            user_id=target_user.id if target_user else None,
            recipient_email=recipient_email if recipient_email else None,
            recipient_phone=recipient_phone if recipient_phone else None,
            message=f"You received a new certificate: '{cert.title}' from {current_user.name}.",
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
    if current_user.role != 'institution':
        return redirect(url_for('dashboard'))
        
    issued = db.session.query(IssuedCertificate, Certificate).join(
        Certificate, IssuedCertificate.certificate_id == Certificate.id
    ).filter(
        IssuedCertificate.institution_id == current_user.id
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
        code = request.args.get('code', '').strip()
        
    issued = None
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
            share_url = url_for('verify_certificate', code=code, _external=True)
            try:
                qr_b64 = generate_qr_base64(share_url)
            except Exception as e:
                qr_b64 = None

    return render_template('verify.html', result=issued, code=code, qr_b64=qr_b64, share_url=share_url)


@app.route('/reports')
@login_required
def reports():
    if current_user.role not in ['admin', 'institution']:
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

    elif current_user.role == 'institution':
        summary = {
            'templates_count': Certificate.query.filter_by(institution_id=current_user.id).count(),
            'issued_count': IssuedCertificate.query.filter_by(institution_id=current_user.id).count(),
            'claimed_count': IssuedCertificate.query.filter_by(institution_id=current_user.id, status='claimed').count()
        }

        templates = Certificate.query.filter_by(institution_id=current_user.id).all()
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
    app.run(debug=True)