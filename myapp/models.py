from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'institution', or 'member'
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    
    job_title = db.Column(db.String(100))
    location = db.Column(db.String(100))
    alumni = db.Column(db.String(100))
    portfolio_url = db.Column(db.String(200))
    is_profile_setup = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'

class Certificate(db.Model):
    __tablename__ = 'certificates'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    institution_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<Certificate {self.title}>'

class IssuedCertificate(db.Model):
    __tablename__ = 'issued_certificates'

    id = db.Column(db.Integer, primary_key=True)
    certificate_id = db.Column(db.Integer, db.ForeignKey('certificates.id'), nullable=False)
    institution_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_email = db.Column(db.String(120), nullable=False)
    issued_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<IssuedCertificate cert={self.certificate_id} to={self.recipient_email}>'