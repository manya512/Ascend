from app import app
from models import db, User

with app.app_context():
    db.create_all()

    existing = User.query.filter_by(email='admin@ascend.com').first()
    if existing:
        print("Test user already exists.")
    else:
        test_user = User(
            name='Test Admin',
            email='admin@ascend.com',
            role='admin'
        )
        test_user.set_password('password123')
        db.session.add(test_user)
        db.session.commit()
        print("Test user created: admin@ascend.com / password123")