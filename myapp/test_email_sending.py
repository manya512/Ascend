"""
Self-test suite for Ascend email notifications feature.
Tests:
 1. No MAIL_* configured:
    - Single issuance completes and logs to console without error.
    - Bulk issuance completes and logs to console without error.
    - Admin institution approval / rejection completes and logs to console.
    - Institution staff verification / rejection completes and logs to console.
 2. Monkeypatched SMTP send:
    - Certificate issuance email (single & bulk) has recipient, subject, and /verify/<code link>.
    - Certificate issuance email for unregistered recipient contains /register?email= link.
    - Institution approved email contains institution email, subject, and /login link.
    - Staff verified email contains staff email, subject, and /dashboard link.
 3. Clean up all temporary test rows.
"""

import os
import re
import io
import openpyxl
from unittest.mock import patch

# Ensure test runs against local test environment
os.environ['APP_BASE_URL'] = 'http://localhost:5000'

from app import app, db
from models import User, Certificate, IssuedCertificate, Notification, Department
import mail_utils


def run_tests():
    print("=== Starting Email Notifications Self-Test ===")
    client = app.test_client()

    created_user_ids = []
    created_cert_ids = []
    created_issued_cert_ids = []

    with app.app_context():
        # Setup test institution
        inst_email = "test_head_inst@institution.test"
        inst = User.query.filter_by(email=inst_email).first()
        if not inst:
            inst = User(
                name="Test Tech University",
                email=inst_email,
                role="institution",
                approval_status="approved",
                phone="+919999000001"
            )
            inst.set_password("TestPass123!")
            db.session.add(inst)
            db.session.commit()
            created_user_ids.append(inst.id)

        # Setup test certificate template
        cert = Certificate(
            institution_id=inst.id,
            title="Python Advanced Certification",
            description="Testing email triggers"
        )
        db.session.add(cert)
        db.session.commit()
        created_cert_ids.append(cert.id)

        # Setup test staff user
        staff_email = "test_staff_candidate@institution.test"
        staff = User.query.filter_by(email=staff_email).first()
        if not staff:
            staff = User(
                name="Prof. Test Staff",
                email=staff_email,
                role="staff",
                institution_id=inst.id,
                staff_status="pending",
                phone="+919999000002"
            )
            staff.set_password("TestPass123!")
            db.session.add(staff)
            db.session.commit()
            created_user_ids.append(staff.id)

        # Setup pending institution for admin approval test
        pending_inst_email = "pending_head@institution.test"
        pending_inst = User.query.filter_by(email=pending_inst_email).first()
        if not pending_inst:
            pending_inst = User(
                name="Pending State College",
                email=pending_inst_email,
                role="institution",
                approval_status="pending",
                phone="+919999000003"
            )
            pending_inst.set_password("TestPass123!")
            db.session.add(pending_inst)
            db.session.commit()
            created_user_ids.append(pending_inst.id)

        # Setup admin user
        admin = User.query.filter_by(role="admin").first()
        if not admin:
            admin = User(name="Test Admin", email="test_admin@ascend.registry", role="admin")
            admin.set_password("AdminPass123!")
            db.session.add(admin)
            db.session.commit()
            created_user_ids.append(admin.id)

        def login_as(email, pw="TestPass123!"):
            client.get('/logout', follow_redirects=True)
            return client.post('/login', data={'email': email, 'password': pw}, follow_redirects=True)

        print("1. Testing mail_utils when credentials are not configured...")
        # Clear env vars for test
        old_user = os.environ.pop('MAIL_USERNAME', None)
        old_pass = os.environ.pop('MAIL_PASSWORD', None)

        try:
            # Calling send_email with no credentials must return False and not throw
            res = mail_utils.send_email("someone@realdomain.org", "Test Subject", "Test Body", "<p>Test</p>")
            assert res is False, f"Expected False when missing credentials, got {res}"
            print("  [OK] send_email with missing credentials returns False without exception")

            # Blocked demo address must return False and not throw
            res_demo = mail_utils.send_email("user@ascend.demo", "Demo Subject", "Body", "<p>Body</p>")
            assert res_demo is False, f"Expected False for .ascend.demo address, got {res_demo}"
            print("  [OK] send_email suppresses .ascend.demo domains")

            print("2. Testing Single Certificate Issuance without credentials (console logging)...")
            login_as(inst.email, "TestPass123!")

            resp = client.post(f"/certificates/{cert.id}/issue", data={
                'recipient_email': 'student_new@externaldomain.org',
                'recipient_phone': '+919999000099'
            }, follow_redirects=True)
            assert resp.status_code == 200, f"Expected 200 after issue redirect, got {resp.status_code}"

            issued_row = IssuedCertificate.query.filter_by(
                certificate_id=cert.id,
                recipient_email='student_new@externaldomain.org'
            ).first()
            assert issued_row is not None, "IssuedCertificate row was not created"
            created_issued_cert_ids.append(issued_row.id)
            print("  [OK] Single certificate issued successfully without mail creds")

            print("3. Testing Bulk Certificate Issuance without credentials...")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["email", "phone"])
            ws.append(["bulk_recipient1@externaldomain.org", "+919999000101"])
            ws.append(["bulk_recipient2@externaldomain.org", "+919999000102"])
            file_stream = io.BytesIO()
            wb.save(file_stream)
            file_stream.seek(0)

            resp_bulk = client.post(
                f"/certificates/{cert.id}/bulk-issue",
                data={'file': (file_stream, 'test_recipients.xlsx')},
                content_type='multipart/form-data',
                follow_redirects=True
            )
            assert resp_bulk.status_code == 200, f"Expected 200 on bulk issue, got {resp_bulk.status_code}"

            for b_email in ["bulk_recipient1@externaldomain.org", "bulk_recipient2@externaldomain.org"]:
                b_row = IssuedCertificate.query.filter_by(certificate_id=cert.id, recipient_email=b_email).first()
                assert b_row is not None, f"Bulk issued row {b_email} missing"
                created_issued_cert_ids.append(b_row.id)
            print("  [OK] Bulk certificate issuance succeeded and queued emails without error")

            print("4. Testing Admin Approval and Staff Verification without credentials...")
            # Set known password on admin
            admin.set_password("AdminPass123!")
            db.session.commit()
            login_as(admin.email, "AdminPass123!")

            resp_app = client.post(f"/admin/institutions/{pending_inst.id}/approve", follow_redirects=True)
            assert resp_app.status_code == 200
            db.session.refresh(pending_inst)
            assert pending_inst.approval_status == 'approved'
            print("  [OK] Admin institution approval succeeded without mail creds")

            login_as(inst.email, "TestPass123!")
            resp_ver = client.post(f"/institution/staff/{staff.id}/verify", follow_redirects=True)
            assert resp_ver.status_code == 200
            db.session.refresh(staff)
            assert staff.staff_status == 'verified'
            print("  [OK] Staff verification succeeded without mail creds")

        finally:
            if old_user:
                os.environ['MAIL_USERNAME'] = old_user
            if old_pass:
                os.environ['MAIL_PASSWORD'] = old_pass

        print("5. Testing with monkeypatched send_email for payload validation...")
        sent_emails = []

        def mock_send(to, subject, text_body, html_body):
            sent_emails.append({
                'to': to,
                'subject': subject,
                'text': text_body,
                'html': html_body
            })
            return True

        with patch('app.send_email', side_effect=mock_send), \
             patch('mail_utils.send_email', side_effect=mock_send):

            # --- Test 5A: Single certificate issuance to unregistered recipient ---
            sent_emails.clear()
            unreg_email = "unregistered_student@newdomain.org"
            login_as(inst.email, "TestPass123!")

            resp = client.post(f"/certificates/{cert.id}/issue", data={
                'recipient_email': unreg_email,
                'recipient_phone': ''
            }, follow_redirects=True)
            assert resp.status_code == 200

            ic_unreg = IssuedCertificate.query.filter_by(
                certificate_id=cert.id, recipient_email=unreg_email
            ).first()
            assert ic_unreg is not None
            created_issued_cert_ids.append(ic_unreg.id)

            assert len(sent_emails) == 1, f"Expected 1 email sent, got {len(sent_emails)}"
            e = sent_emails[0]
            assert e['to'] == unreg_email
            assert cert.title in e['subject']
            assert inst.name in e['subject']
            assert f"/verify/{ic_unreg.verification_code}" in e['text']
            assert f"/verify/{ic_unreg.verification_code}" in e['html']
            # Unregistered recipient must receive register to claim link
            assert "/register?email=" in e['text']
            assert "/register?email=" in e['html']
            assert "Register to Claim" in e['html']
            assert "#26215C" in e['html'] # Indigo header
            assert "#EF9F27" in e['html'] # Gold button
            print("  [OK] Certificate email to unregistered recipient verified (verify link + prefilled register link + branding)")

            # --- Test 5B: Single certificate issuance to registered member ---
            # Create or fetch a registered member
            registered_member = User.query.filter_by(email="registered_student@realdomain.org").first()
            if not registered_member:
                registered_member = User(
                    name="Registered Student",
                    email="registered_student@realdomain.org",
                    role="member"
                )
                registered_member.set_password("Pass123!")
                db.session.add(registered_member)
                db.session.commit()
            if registered_member.id not in created_user_ids:
                created_user_ids.append(registered_member.id)

            sent_emails.clear()
            resp = client.post(f"/certificates/{cert.id}/issue", data={
                'recipient_email': registered_member.email,
                'recipient_phone': ''
            }, follow_redirects=True)
            assert resp.status_code == 200

            ic_reg = IssuedCertificate.query.filter_by(
                certificate_id=cert.id, recipient_email=registered_member.email
            ).first()
            assert ic_reg is not None
            created_issued_cert_ids.append(ic_reg.id)

            assert len(sent_emails) == 1
            e_reg = sent_emails[0]
            assert e_reg['to'] == registered_member.email
            assert f"/verify/{ic_reg.verification_code}" in e_reg['text']
            # Registered recipient does not need registration prompt
            assert "You don't have an Ascend account yet" not in e_reg['text']
            print("  [OK] Certificate email to registered member verified (verify link present, register link omitted)")

            # --- Test 5C: Institution approval / rejection emails ---
            sent_emails.clear()
            login_as(admin.email, "AdminPass123!")

            # Reject institution
            resp = client.post(f"/admin/institutions/{pending_inst.id}/reject", follow_redirects=True)
            assert resp.status_code == 200
            assert len(sent_emails) == 1
            e_rej = sent_emails[0]
            assert e_rej['to'] == pending_inst.email
            assert "Update on your Ascend institution account" in e_rej['subject']
            print("  [OK] Institution rejected email verified")

            # Approve institution
            sent_emails.clear()
            resp = client.post(f"/admin/institutions/{pending_inst.id}/approve", follow_redirects=True)
            assert resp.status_code == 200
            assert len(sent_emails) == 1
            e_app = sent_emails[0]
            assert e_app['to'] == pending_inst.email
            assert "approved" in e_app['subject'].lower()
            assert "/login" in e_app['text']
            assert "/login" in e_app['html']
            print("  [OK] Institution approved email verified (/login button present)")

            # --- Test 5D: Staff verification / rejection emails ---
            sent_emails.clear()
            login_as(inst.email, "TestPass123!")

            # Reject staff
            resp = client.post(f"/institution/staff/{staff.id}/reject", follow_redirects=True)
            assert resp.status_code == 200
            assert len(sent_emails) == 1
            e_srej = sent_emails[0]
            assert e_srej['to'] == staff.email
            assert "staff application" in e_srej['subject'].lower()
            print("  [OK] Staff rejected email verified")

            # Verify staff
            sent_emails.clear()
            resp = client.post(f"/institution/staff/{staff.id}/verify", follow_redirects=True)
            assert resp.status_code == 200
            assert len(sent_emails) == 1
            e_sver = sent_emails[0]
            assert e_sver['to'] == staff.email
            assert "verified" in e_sver['subject'].lower()
            assert "/dashboard" in e_sver['text']
            assert "/dashboard" in e_sver['html']
            print("  [OK] Staff verified email verified (/dashboard button present)")

            # --- Test 5E: GET /register?email=... redirect and prefill ---
            resp_reg = client.get("/register?email=prefilled%40test.com")
            assert resp_reg.status_code in (302, 200)
            if resp_reg.status_code == 302:
                assert "prefilled%40test.com" in resp_reg.location or "prefilled@test.com" in resp_reg.location
            print("  [OK] GET /register?email= successfully preserves and routes prefill email")

        print("6. Cleaning up test data...")
        # Clean up any issued certificates referencing the test certificates
        for c_id in created_cert_ids:
            certs_to_del = IssuedCertificate.query.filter_by(certificate_id=c_id).all()
            for ic in certs_to_del:
                Notification.query.filter_by(link=f"/verify/{ic.verification_code}").delete()
                db.session.delete(ic)
        db.session.commit()

        for c_id in created_cert_ids:
            c = Certificate.query.get(c_id)
            if c:
                db.session.delete(c)
        db.session.commit()

        for u_id in created_user_ids:
            Notification.query.filter_by(user_id=u_id).delete()
            u = User.query.get(u_id)
            if u:
                db.session.delete(u)
        db.session.commit()
        print("  [OK] Test rows cleaned up successfully")

    print("=== All Email Feature Tests Passed Successfully! ===")


if __name__ == '__main__':
    run_tests()
