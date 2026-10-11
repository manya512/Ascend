from app import app, db
from sqlalchemy import text

def alter_db():
    with app.app_context():
        queries = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS job_title VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS location VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS alumni VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS portfolio_url VARCHAR(200);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_profile_setup BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE issued_certificates ADD COLUMN IF NOT EXISTS verification_code VARCHAR(36);",
            "ALTER TABLE issued_certificates ADD COLUMN IF NOT EXISTS recipient_phone VARCHAR(20);",
            "ALTER TABLE issued_certificates ALTER COLUMN recipient_email DROP NOT NULL;",
            "ALTER TABLE issued_certificates ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'issued';",
            "ALTER TABLE issued_certificates ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP;",
            "ALTER TABLE issued_certificates ADD COLUMN IF NOT EXISTS claimed_by_id INTEGER REFERENCES users(id);",
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                recipient_email VARCHAR(120),
                recipient_phone VARCHAR(20),
                message TEXT NOT NULL,
                link VARCHAR(255),
                is_read BOOLEAN DEFAULT FALSE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """
        ]
        for q in queries:
            try:
                db.session.execute(text(q))
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Query error (handled): {e}")
        print("Database schema updated successfully.")

if __name__ == '__main__':
    alter_db()

