import os
import io
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from app import app
from models import db, User, Department, Certificate, IssuedCertificate, Notification


def run_tests():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()

    created_user_ids = []
    created_cert_ids = []
    created_issued_ids = []
    created_notif_ids = []

    try:
        with app.app_context():
            print("--- RUNNING SELF-TESTS ---")

            # Get Lakeview college and its dept
            lakeview = User.query.filter_by(email="admin@lakeview.ascend.demo").first()
            assert lakeview is not None, "Lakeview institution not found"
            lakeview_dept = Department.query.filter_by(institution_id=lakeview.id).first()
            assert lakeview_dept is not None, "Lakeview department not found"

            # -------------------------------------------------------------
            # TEST 1: Pending institution can't log in
            # -------------------------------------------------------------
            print("\nTest 1: Pending institution registration & blocked login...")
            reg_resp = client.post('/register', data={
                'name': 'Test New College',
                'email': 'newcollege@test.demo',
                'password': 'TestPassword123',
                'role': 'institution'
            }, follow_redirects=True)
            assert reg_resp.status_code == 200

            new_inst = User.query.filter_by(email='newcollege@test.demo').first()
            assert new_inst is not None, "Institution was not created"
            created_user_ids.append(new_inst.id)
            assert new_inst.approval_status == 'pending', f"Expected pending, got {new_inst.approval_status}"

            # Attempt login as pending institution
            login_resp = client.post('/login', data={
                'email': 'newcollege@test.demo',
                'password': 'TestPassword123'
            }, follow_redirects=True)
            login_text = login_resp.get_data(as_text=True)
            assert "Your institution account is awaiting approval by the Ascend admin" in login_text, "Blocked flash not found"
            print("PASS: Pending institution login blocked.")

            # -------------------------------------------------------------
            # TEST 2: Admin approves it and it can log in
            # -------------------------------------------------------------
            print("\nTest 2: Admin approves pending institution...")
            # Login as admin
            admin_login = client.post('/login', data={
                'email': 'admin@ascend.demo',
                'password': 'Demo@1234'
            }, follow_redirects=True)
            assert admin_login.status_code == 200

            # Approve the new institution
            approve_resp = client.post(f'/admin/institutions/{new_inst.id}/approve', follow_redirects=True)
            assert approve_resp.status_code == 200

            # Refresh db object
            db.session.refresh(new_inst)
            assert new_inst.approval_status == 'approved', f"Expected approved, got {new_inst.approval_status}"

            # Logout admin
            client.get('/logout', follow_redirects=True)

            # Now log in as the approved institution
            inst_login = client.post('/login', data={
                'email': 'newcollege@test.demo',
                'password': 'TestPassword123'
            }, follow_redirects=True)
            assert inst_login.status_code == 200
            inst_text = inst_login.get_data(as_text=True)
            assert "Your institution account is awaiting approval" not in inst_text
            print("PASS: Approved institution can log in successfully.")
            client.get('/logout', follow_redirects=True)

            # -------------------------------------------------------------
            # TEST 3: Staff registration requires college and department
            # -------------------------------------------------------------
            print("\nTest 3: Staff registration requires college and department...")
            # Attempt staff registration without college/dept
            bad_staff_resp = client.post('/register', data={
                'name': 'Incomplete Staff',
                'email': 'incomplete_staff@test.demo',
                'password': 'TestPassword123',
                'role': 'staff',
                'institution_id': '',
                'department_id': ''
            }, follow_redirects=True)
            bad_staff = User.query.filter_by(email='incomplete_staff@test.demo').first()
            assert bad_staff is None, "Incomplete staff should not have been created"

            # Attempt staff registration with college and dept
            good_staff_resp = client.post('/register', data={
                'name': 'Complete Staff',
                'email': 'complete_staff@test.demo',
                'password': 'TestPassword123',
                'role': 'staff',
                'institution_id': str(lakeview.id),
                'department_id': str(lakeview_dept.id)
            }, follow_redirects=True)
            good_staff = User.query.filter_by(email='complete_staff@test.demo').first()
            assert good_staff is not None, "Complete staff should have been created"
            created_user_ids.append(good_staff.id)
            assert good_staff.staff_status == 'pending', f"Expected pending staff_status, got {good_staff.staff_status}"
            assert good_staff.institution_id == lakeview.id
            assert good_staff.department_id == lakeview_dept.id
            print("PASS: Staff registration properly validates college and department.")

            # -------------------------------------------------------------
            # TEST 4: Pending staff cannot issue; verified staff can
            # -------------------------------------------------------------
            print("\nTest 4: Issuing permissions for pending vs verified staff...")
            # Ensure a certificate exists for lakeview
            cert = Certificate.query.filter_by(institution_id=lakeview.id).first()
            if not cert:
                cert = Certificate(
                    title="Test Lakeview Certificate",
                    institution_id=lakeview.id,
                    description="Test description"
                )
                db.session.add(cert)
                db.session.commit()
                created_cert_ids.append(cert.id)

            # 4a: Pending staff (staff2@lakeview.ascend.demo) attempts to issue
            login_s2 = client.post('/login', data={
                'email': 'staff2@lakeview.ascend.demo',
                'password': 'Demo@1234'
            }, follow_redirects=True)
            assert login_s2.status_code == 200

            issue_s2 = client.post(f'/certificates/{cert.id}/issue', data={
                'recipient_name': 'Test Recipient',
                'recipient_email': 'recipient_pending@test.demo',
                'recipient_phone': ''
            }, follow_redirects=True)
            s2_text = issue_s2.get_data(as_text=True)
            assert "Your staff account is pending verification and cannot issue certificates." in s2_text, "Expected blocked notice"

            issued_pend = IssuedCertificate.query.filter_by(recipient_email='recipient_pending@test.demo').first()
            assert issued_pend is None, "Pending staff should not be able to issue certificate"

            client.get('/logout', follow_redirects=True)

            # 4b: Verified staff (staff1@lakeview.ascend.demo) attempts to issue
            login_s1 = client.post('/login', data={
                'email': 'staff1@lakeview.ascend.demo',
                'password': 'Demo@1234'
            }, follow_redirects=True)
            assert login_s1.status_code == 200

            issue_s1 = client.post(f'/certificates/{cert.id}/issue', data={
                'recipient_name': 'Test Recipient Verified',
                'recipient_email': 'recipient_verified@test.demo',
                'recipient_phone': ''
            }, follow_redirects=True)
            assert issue_s1.status_code == 200

            issued_ver = IssuedCertificate.query.filter_by(recipient_email='recipient_verified@test.demo').first()
            assert issued_ver is not None, "Verified staff should have issued certificate"
            created_issued_ids.append(issued_ver.id)
            assert issued_ver.institution_id == lakeview.id, "Should issue under staff's institution"

            # Check notification created
            notif = Notification.query.filter_by(recipient_email='recipient_verified@test.demo').first()
            if notif:
                created_notif_ids.append(notif.id)

            client.get('/logout', follow_redirects=True)
            print("PASS: Pending staff blocked from issuing, verified staff successfully issued.")

            # -------------------------------------------------------------
            # TEST 5: Member registration with and without college
            # -------------------------------------------------------------
            print("\nTest 5: Member registration with and without college...")
            # 5a: Without college
            mem_no_col_resp = client.post('/register', data={
                'name': 'Member No College',
                'email': 'member_no_col@test.demo',
                'password': 'TestPassword123',
                'role': 'member',
                'institution_id': '',
                'department_id': ''
            }, follow_redirects=True)
            assert mem_no_col_resp.status_code == 200
            mem_no_col = User.query.filter_by(email='member_no_col@test.demo').first()
            assert mem_no_col is not None
            created_user_ids.append(mem_no_col.id)
            assert mem_no_col.institution_id is None
            assert mem_no_col.department_id is None

            # 5b: With college and department
            mem_col_resp = client.post('/register', data={
                'name': 'Member With College',
                'email': 'member_with_col@test.demo',
                'password': 'TestPassword123',
                'role': 'member',
                'institution_id': str(lakeview.id),
                'department_id': str(lakeview_dept.id)
            }, follow_redirects=True)
            assert mem_col_resp.status_code == 200
            mem_col = User.query.filter_by(email='member_with_col@test.demo').first()
            assert mem_col is not None
            created_user_ids.append(mem_col.id)
            assert mem_col.institution_id == lakeview.id
            assert mem_col.department_id == lakeview_dept.id
            print("PASS: Member registration works both with and without college affiliation.")

            # -------------------------------------------------------------
            # TEST 6: Departments API endpoint
            # -------------------------------------------------------------
            print("\nTest 6: GET /api/institutions/<id>/departments...")
            api_resp = client.get(f'/api/institutions/{lakeview.id}/departments')
            assert api_resp.status_code == 200
            dept_data = api_resp.get_json()
            assert len(dept_data) == 4
            assert any(d['name'] == 'Computer Science' for d in dept_data)
            print("PASS: Department JSON API works.")

            print("\nALL TESTS PASSED!")

    finally:
        # Cleanup test rows
        with app.app_context():
            print("\nCleaning up test rows...")
            if created_notif_ids:
                Notification.query.filter(Notification.id.in_(created_notif_ids)).delete(synchronize_session=False)
            if created_issued_ids:
                IssuedCertificate.query.filter(IssuedCertificate.id.in_(created_issued_ids)).delete(synchronize_session=False)
            if created_cert_ids:
                Certificate.query.filter(Certificate.id.in_(created_cert_ids)).delete(synchronize_session=False)
            if created_user_ids:
                User.query.filter(User.id.in_(created_user_ids)).delete(synchronize_session=False)
            db.session.commit()
            print("Cleanup completed.")


if __name__ == '__main__':
    run_tests()
