import os
import sys
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from app import app
from models import db, User, Notification

DEMO_MEMBERS = [
    ("Usha", "usha@ascend.demo", "Demo@1234"),
    ("Shreenithi", "shreenithi@ascend.demo", "Demo@1234"),
    ("Sahana", "sahana@ascend.demo", "Demo@1234"),
    ("Danusha", "danusha@ascend.demo", "Demo@1234"),
    ("Srinika", "srinika@ascend.demo", "Demo@1234"),
    ("Dharshana", "dharshana@ascend.demo", "Demo@1234"),
    ("Mirthula", "mirthula@ascend.demo", "Demo@1234"),
    ("Amrita", "amrita@ascend.demo", "Demo@1234"),
    ("Hubert", "hubert@ascend.demo", "Demo@1234"),
    ("Hrishikesh", "hrishikesh@ascend.demo", "Demo@1234"),
    ("Lohith", "lohith@ascend.demo", "Demo@1234"),
    ("Aravindhan", "aravindhan@ascend.demo", "Demo@1234"),
    ("Janani", "janani@ascend.demo", "Demo@1234"),
    ("Sai Priyamvadha", "sai.priyamvadha@ascend.demo", "Demo@1234"),
    ("Angel Jeba", "angel.jeba@ascend.demo", "Demo@1234"),
    ("Anusri", "anusri@ascend.demo", "Demo@1234"),
    ("Harshitha", "harshitha@ascend.demo", "Demo@1234"),
    ("Lithusa", "lithusa@ascend.demo", "Demo@1234"),
    ("Jananee", "jananee@ascend.demo", "Demo@1234"),
    ("Udhay", "udhay@ascend.demo", "Demo@1234"),
    ("Judith", "judith@ascend.demo", "Demo@1234"),
    ("Abisha", "abisha@ascend.demo", "Demo@1234"),
]

DEMO_INSTITUTIONS = [
    ("Lakeview Institute of Technology", "admin@lakeview.ascend.demo", "Demo@1234"),
    ("Meridian College of Engineering", "admin@meridian.ascend.demo", "Demo@1234"),
    ("Crestwood University", "admin@crestwood.ascend.demo", "Demo@1234"),
    ("Silverline College of Arts and Science", "admin@silverline.ascend.demo", "Demo@1234"),
    ("Horizon Institute of Management", "admin@horizon.ascend.demo", "Demo@1234"),
]


def seed_demo_accounts():
    results = []

    with app.app_context():
        try:
            # Process members
            for name, email, password in DEMO_MEMBERS:
                clean_email = email.strip().lower()
                existing = User.query.filter(db.func.lower(User.email) == clean_email).first()
                if existing:
                    results.append((name, clean_email, "member", "skipped"))
                    continue

                new_member = User(
                    name=name.strip(),
                    email=clean_email,
                    phone=None,
                    role="member",
                    institution_id=None
                )
                new_member.set_password(password.strip())
                db.session.add(new_member)
                db.session.flush()

                # Link prior unattached notifications by lowercase email
                Notification.query.filter(
                    Notification.user_id.is_(None),
                    db.func.lower(db.func.trim(Notification.recipient_email)) == clean_email
                ).update({"user_id": new_member.id}, synchronize_session=False)

                results.append((name, clean_email, "member", "created"))

            # Process institutions
            for name, email, password in DEMO_INSTITUTIONS:
                clean_email = email.strip().lower()
                existing = User.query.filter(db.func.lower(User.email) == clean_email).first()
                if existing:
                    results.append((name, clean_email, "institution", "skipped"))
                    continue

                new_inst = User(
                    name=name.strip(),
                    email=clean_email,
                    phone=None,
                    role="institution",
                    institution_id=None
                )
                new_inst.set_password(password.strip())
                db.session.add(new_inst)
                db.session.flush()

                # Link prior unattached notifications by lowercase email
                Notification.query.filter(
                    Notification.user_id.is_(None),
                    db.func.lower(db.func.trim(Notification.recipient_email)) == clean_email
                ).update({"user_id": new_inst.id}, synchronize_session=False)

                results.append((name, clean_email, "institution", "created"))

            # Commit once at the end in a single transaction
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            print(f"Error during seeding: {e}", file=sys.stderr)
            raise e

    # Print a formatted final table
    col_name_w = 40
    col_email_w = 40
    col_role_w = 15
    col_status_w = 10

    header = f"{'Name':<{col_name_w}} | {'Email':<{col_email_w}} | {'Role':<{col_role_w}} | {'Status':<{col_status_w}}"
    sep = "-" * len(header)
    print("\n" + sep)
    print(header)
    print(sep)
    for name, email, role, status in results:
        print(f"{name:<{col_name_w}} | {email:<{col_email_w}} | {role:<{col_role_w}} | {status:<{col_status_w}}")
    print(sep + "\n")

    created_count = sum(1 for r in results if r[3] == "created")
    skipped_count = sum(1 for r in results if r[3] == "skipped")
    print(f"Seeding completed: {created_count} created, {skipped_count} skipped, {len(results)} total processed.")


if __name__ == '__main__':
    seed_demo_accounts()
