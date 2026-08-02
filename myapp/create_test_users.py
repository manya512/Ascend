from app import app
from models import db, User

with app.app_context():
    users_to_create = [
        ('Test Institution', 'institution@ascend.com', 'institution'),
        ('Test Member', 'member@ascend.com', 'member'),
    ]

    for name, email, role in users_to_create:
        if not User.query.filter_by(email=email).first():
            u = User(name=name, email=email, role=role)
            u.set_password('password123')
            db.session.add(u)

    db.session.commit()
    print("Test users created.")