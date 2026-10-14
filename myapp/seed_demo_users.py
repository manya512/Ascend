import os
import sys
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from app import app
from models import db, User, Department, Club, Notification

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
    ("Lakeview Institute of Technology", "admin@lakeview.ascend.demo", "Demo@1234", "lakeview"),
    ("Meridian College of Engineering", "admin@meridian.ascend.demo", "Demo@1234", "meridian"),
    ("Crestwood University", "admin@crestwood.ascend.demo", "Demo@1234", "crestwood"),
    ("Silverline College of Arts and Science", "admin@silverline.ascend.demo", "Demo@1234", "silverline"),
    ("Horizon Institute of Management", "admin@horizon.ascend.demo", "Demo@1234", "horizon"),
]

DEPARTMENTS = [
    "Computer Science",
    "Electronics",
    "Mechanical",
    "Business Administration"
]


def seed_demo_accounts():
    results = []
    admin_created = False

    with app.app_context():
        try:
            # Check admin account
            existing_admin = User.query.filter_by(role='admin').first()
            demo_admin = User.query.filter(db.func.lower(User.email) == 'admin@ascend.demo').first()
            if not existing_admin or not demo_admin:
                if not demo_admin:
                    admin_user = User(
                        name="Ascend Admin",
                        email="admin@ascend.demo",
                        phone=None,
                        role="admin"
                    )
                    admin_user.set_password("Demo@1234")
                    db.session.add(admin_user)
                    db.session.flush()
                    admin_created = True
                    results.append(("Ascend Admin", "admin@ascend.demo", "admin", "created"))

            # Process institutions
            inst_records = []
            depts_by_college = {}

            for name, email, password, slug in DEMO_INSTITUTIONS:
                clean_email = email.strip().lower()
                inst = User.query.filter(db.func.lower(User.email) == clean_email).first()
                if not inst:
                    inst = User(
                        name=name.strip(),
                        email=clean_email,
                        phone=None,
                        role="institution",
                        institution_id=None,
                        approval_status="approved"
                    )
                    inst.set_password(password.strip())
                    db.session.add(inst)
                    db.session.flush()
                    results.append((name, clean_email, "institution", "created"))
                else:
                    inst.approval_status = "approved"
                    results.append((name, clean_email, "institution", "updated"))

                inst_records.append((inst, slug))

                # Create 4 departments per institution
                depts_by_college[inst.id] = []
                for dept_name in DEPARTMENTS:
                    dept = Department.query.filter_by(institution_id=inst.id, name=dept_name).first()
                    if not dept:
                        dept = Department(institution_id=inst.id, name=dept_name)
                        db.session.add(dept)
                        db.session.flush()
                    depts_by_college[inst.id].append(dept)

            # Create 2 staff accounts per college
            for inst, slug in inst_records:
                col_depts = depts_by_college[inst.id]
                first_dept_id = col_depts[0].id if col_depts else None
                second_dept_id = col_depts[1].id if len(col_depts) > 1 else first_dept_id

                staff_specs = [
                    (f"Staff One {inst.name}", f"staff1@{slug}.ascend.demo", "verified", first_dept_id),
                    (f"Staff Two {inst.name}", f"staff2@{slug}.ascend.demo", "pending", second_dept_id),
                ]

                for s_name, s_email, s_status, s_dept_id in staff_specs:
                    clean_s_email = s_email.strip().lower()
                    existing_staff = User.query.filter(db.func.lower(User.email) == clean_s_email).first()
                    if not existing_staff:
                        staff_user = User(
                            name=s_name,
                            email=clean_s_email,
                            phone=None,
                            role="staff",
                            institution_id=inst.id,
                            department_id=s_dept_id,
                            staff_status=s_status
                        )
                        staff_user.set_password("Demo@1234")
                        db.session.add(staff_user)
                        db.session.flush()
                        results.append((s_name, clean_s_email, "staff", "created"))
                    else:
                        existing_staff.role = "staff"
                        existing_staff.institution_id = inst.id
                        existing_staff.department_id = s_dept_id
                        existing_staff.staff_status = s_status
                        results.append((s_name, clean_s_email, "staff", "updated"))

            # Process 22 demo members (round-robin assignment to college and department)
            for idx, (name, email, password) in enumerate(DEMO_MEMBERS):
                clean_email = email.strip().lower()
                member = User.query.filter(db.func.lower(User.email) == clean_email).first()

                assigned_inst, _ = inst_records[idx % len(inst_records)]
                assigned_col_depts = depts_by_college[assigned_inst.id]
                assigned_dept = assigned_col_depts[idx % len(assigned_col_depts)]

                if not member:
                    member = User(
                        name=name.strip(),
                        email=clean_email,
                        phone=None,
                        role="member",
                        institution_id=assigned_inst.id,
                        department_id=assigned_dept.id
                    )
                    member.set_password(password.strip())
                    db.session.add(member)
                    db.session.flush()

                    Notification.query.filter(
                        Notification.user_id.is_(None),
                        db.func.lower(db.func.trim(Notification.recipient_email)) == clean_email
                    ).update({"user_id": member.id}, synchronize_session=False)

                    results.append((name, clean_email, "member", "created"))
                else:
                    member.institution_id = assigned_inst.id
                    member.department_id = assigned_dept.id
                    results.append((name, clean_email, "member", "assigned"))

            # Commit once at the end in a single transaction
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            print(f"Error during seeding: {e}", file=sys.stderr)
            raise e

    # Print summary
    print(f"Admin created: {admin_created}")
    print(f"Processed {len(results)} items in seed.")
    return admin_created


if __name__ == '__main__':
    seed_demo_accounts()
