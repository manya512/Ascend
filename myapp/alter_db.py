from app import app, db
from sqlalchemy import text

def alter_db():
    with app.app_context():
        queries = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS job_title VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS location VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS alumni VARCHAR(100);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS portfolio_url VARCHAR(200);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_profile_setup BOOLEAN DEFAULT FALSE;"
        ]
        for q in queries:
            db.session.execute(text(q))
        db.session.commit()
        print("Database altered successfully.")

if __name__ == '__main__':
    alter_db()
