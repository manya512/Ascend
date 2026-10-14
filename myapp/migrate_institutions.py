import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from app import app, db
from sqlalchemy import text
from models import User

def migrate():
    with app.app_context():
        queries = [
            """
            CREATE TABLE IF NOT EXISTS departments (
                id SERIAL PRIMARY KEY,
                institution_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT uq_department_institution_name UNIQUE (institution_id, name)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS clubs (
                id SERIAL PRIMARY KEY,
                institution_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT uq_club_institution_name UNIQUE (institution_id, name)
            );
            """,
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS institution_id INTEGER REFERENCES users(id);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS department_id INTEGER REFERENCES departments(id);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS staff_status VARCHAR(20);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20);",
            """
            UPDATE users
            SET approval_status = 'approved'
            WHERE role = 'institution' AND (approval_status IS NULL OR approval_status = '');
            """
        ]

        for q in queries:
            try:
                db.session.execute(text(q))
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Migration error on query: {e}")
                raise e

        # Verify existing institutions have approval_status='approved'
        insts = User.query.filter_by(role='institution').all()
        for inst in insts:
            if not inst.approval_status:
                inst.approval_status = 'approved'
        db.session.commit()

        print(f"Migration completed successfully. {len(insts)} existing institutions verified/approved.")

if __name__ == '__main__':
    migrate()
