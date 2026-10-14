"""
Self-test for the institution head dashboard feature.
Covers:
 1. Lakeview's head sees correct counts
 2. Add/delete a department and club
 3. Delete blocked for dept with people
 4. Verify staff2@lakeview.ascend.demo; notification created
 5. Meridian's head cannot touch Lakeview's staff
 6. Member and staff user are rejected from institution-head routes
 7. Restore data (staff2 back to pending)
"""
import os, sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from app import app
from models import db, User, Department, Club, Notification

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False
client = app.test_client()

PASS = 0
FAIL = 0

def chk(label, condition):
    global PASS, FAIL
    if condition:
        print(f"  PASS: {label}")
        PASS += 1
    else:
        print(f"  FAIL: {label}")
        FAIL += 1

created_depts = []
created_clubs = []
created_notif_ids = []

with app.app_context():
    print("\n=== Institution Dashboard Self-Test ===\n")

    # ── helpers ──────────────────────────────────────────────
    lakeview = User.query.filter_by(email='admin@lakeview.ascend.demo').first()
    meridian  = User.query.filter_by(email='admin@meridian.ascend.demo').first()
    member    = User.query.filter_by(email='usha@ascend.demo').first()
    staff2    = User.query.filter_by(email='staff2@lakeview.ascend.demo').first()
    staff1    = User.query.filter_by(email='staff1@lakeview.ascend.demo').first()

    assert lakeview, "Lakeview institution not found"
    assert meridian,  "Meridian institution not found"
    assert member,    "Demo member not found"
    assert staff2,    "staff2@lakeview not found"
    assert staff1,    "staff1@lakeview not found"

    def login_as(email, pw='Demo@1234'):
        client.get('/logout', follow_redirects=True)
        r = client.post('/login', data={'email': email, 'password': pw}, follow_redirects=True)
        return r

    # ── 1. Lakeview head sees correct counts ────────────────
    print("Test 1: Lakeview overview stats")
    login_as('admin@lakeview.ascend.demo')
    r = client.get('/institution/dashboard?tab=overview')
    chk("overview page loads (200)", r.status_code == 200)
    body = r.get_data(as_text=True)
    chk("shows student count", str(User.query.filter_by(role='member', institution_id=lakeview.id).count()) in body)
    chk("shows department count", str(Department.query.filter_by(institution_id=lakeview.id).count()) in body)

    # ── 2. Add department ────────────────────────────────────
    print("\nTest 2: Add new department")
    r = client.post('/institution/departments/add', data={'name': 'Astrophysics'}, follow_redirects=True)
    chk("add dept returns 200", r.status_code == 200)
    new_dept = Department.query.filter_by(institution_id=lakeview.id, name='Astrophysics').first()
    chk("department created in DB", new_dept is not None)
    if new_dept:
        created_depts.append(new_dept.id)

    # ── 3. Rename department ────────────────────────────────
    print("\nTest 3: Rename department")
    if new_dept:
        r = client.post(f'/institution/departments/{new_dept.id}/rename', data={'name': 'Astrophysics Renamed'}, follow_redirects=True)
        chk("rename returns 200", r.status_code == 200)
        db.session.refresh(new_dept)
        chk("dept renamed in DB", new_dept.name == 'Astrophysics Renamed')

    # ── 4. Add club ──────────────────────────────────────────
    print("\nTest 4: Add club")
    r = client.post('/institution/clubs/add', data={'name': 'Test Coding Club'}, follow_redirects=True)
    chk("add club returns 200", r.status_code == 200)
    new_club = Club.query.filter_by(institution_id=lakeview.id, name='Test Coding Club').first()
    chk("club created in DB", new_club is not None)
    if new_club:
        created_clubs.append(new_club.id)

    # ── 5. Delete club ──────────────────────────────────────
    print("\nTest 5: Delete club")
    if new_club:
        r = client.post(f'/institution/clubs/{new_club.id}/delete', follow_redirects=True)
        chk("delete club returns 200", r.status_code == 200)
        gone = Club.query.filter_by(id=new_club.id).first()
        chk("club deleted from DB", gone is None)
        if gone is None:
            created_clubs.remove(new_club.id)

    # ── 6. Delete dept that HAS people → blocked ─────────────
    print("\nTest 6: Block delete of occupied department")
    # Get a department that has users assigned
    occupied_dept = Department.query.filter_by(institution_id=lakeview.id).join(
        User, User.department_id == Department.id
    ).filter(User.role == 'member').first()
    if occupied_dept:
        r = client.post(f'/institution/departments/{occupied_dept.id}/delete', follow_redirects=True)
        chk("delete blocked (200)", r.status_code == 200)
        still_there = Department.query.filter_by(id=occupied_dept.id).first()
        chk("department still in DB", still_there is not None)
        flash_text = r.get_data(as_text=True)
        chk("flash message mentions block", "Cannot delete" in flash_text)
    else:
        print("  SKIP: No occupied department found (all empty)")

    # ── 7. Delete empty test dept ─────────────────────────────
    print("\nTest 7: Delete empty department")
    if new_dept:
        db.session.refresh(new_dept)
        r = client.post(f'/institution/departments/{new_dept.id}/delete', follow_redirects=True)
        chk("delete dept returns 200", r.status_code == 200)
        gone = Department.query.filter_by(id=new_dept.id).first()
        chk("dept deleted from DB", gone is None)
        if gone is None and new_dept.id in created_depts:
            created_depts.remove(new_dept.id)

    # ── 8. Verify staff2 → notification created ───────────────
    print("\nTest 8: Verify staff2@lakeview")
    orig_notif_count = Notification.query.filter_by(user_id=staff2.id).count()
    r = client.post(f'/institution/staff/{staff2.id}/verify', follow_redirects=True)
    chk("verify returns 200", r.status_code == 200)
    db.session.refresh(staff2)
    chk("staff2 status = verified", staff2.staff_status == 'verified')
    new_notif_count = Notification.query.filter_by(user_id=staff2.id).count()
    chk("notification created for staff2", new_notif_count > orig_notif_count)
    # collect for cleanup
    notifs = Notification.query.filter_by(user_id=staff2.id).order_by(Notification.id.desc()).limit(1).all()
    created_notif_ids.extend([n.id for n in notifs])

    # ── 9. Meridian cannot touch Lakeview's staff ─────────────
    print("\nTest 9: Cross-institution isolation")
    login_as('admin@meridian.ascend.demo')
    r = client.post(f'/institution/staff/{staff2.id}/reject', follow_redirects=True)
    chk("Meridian gets 404 on Lakeview staff action", r.status_code == 404)
    db.session.refresh(staff2)
    chk("staff2 status unchanged (verified)", staff2.staff_status == 'verified')

    # ── 10. Member rejected from institution routes ────────────
    print("\nTest 10: Member rejected from institution routes")
    login_as('usha@ascend.demo')
    r = client.get('/institution/dashboard')
    chk("member gets 403", r.status_code == 403)

    # ── 11. Staff rejected from institution routes ─────────────
    print("\nTest 11: Staff rejected from institution routes")
    login_as('staff1@lakeview.ascend.demo')
    r = client.get('/institution/dashboard')
    chk("staff gets 403", r.status_code == 403)

    # ── Restore: reset staff2 to pending ──────────────────────
    print("\nRestoring data...")
    login_as('admin@lakeview.ascend.demo')
    client.get('/logout', follow_redirects=True)

    # Restore staff2 to pending via DB
    db.session.refresh(staff2)
    staff2.staff_status = 'pending'
    # Clean up notifications we created
    if created_notif_ids:
        Notification.query.filter(Notification.id.in_(created_notif_ids)).delete(synchronize_session=False)
    # Clean up leftover test data
    for dept_id in created_depts:
        d = Department.query.filter_by(id=dept_id).first()
        if d:
            db.session.delete(d)
    for club_id in created_clubs:
        c = Club.query.filter_by(id=club_id).first()
        if c:
            db.session.delete(c)
    db.session.commit()
    db.session.refresh(staff2)
    chk("staff2 restored to pending", staff2.staff_status == 'pending')
    print("Data restored.")

    print(f"\n=== Results: {PASS} passed, {FAIL} failed ===")
    if FAIL:
        sys.exit(1)
    else:
        print("ALL TESTS PASSED!")
