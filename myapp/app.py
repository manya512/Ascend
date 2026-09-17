from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from config import Config
from models import db, User, Certificate, IssuedCertificate

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
    if current_user.role == 'member':
        return render_template('member.html', user=current_user)
    elif current_user.role == 'institution':
        return render_template('institution.html', user=current_user)
    elif current_user.role == 'admin':
        return render_template('admin.html', user=current_user)
    return redirect(url_for('login'))


@app.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    if current_user.role != 'member':
        return redirect(url_for('dashboard'))
    
    current_user.job_title = request.form.get('job_title')
    current_user.location = request.form.get('location')
    current_user.alumni = request.form.get('alumni')
    current_user.portfolio_url = request.form.get('portfolio_url')
    current_user.is_profile_setup = True
    
    db.session.commit()
    flash('Profile updated successfully!')
    return redirect(url_for('dashboard'))


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
        recipient_email = request.form.get('recipient_email')
        
        issued_cert = IssuedCertificate(
            certificate_id=cert_id,
            institution_id=current_user.id,
            recipient_email=recipient_email
        )
        db.session.add(issued_cert)
        db.session.commit()
        
        flash(f'Certificate issued to {recipient_email}!')
        return redirect(url_for('certificates_list'))
        
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


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)