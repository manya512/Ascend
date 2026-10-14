"""
mail_utils.py  –  Branded SMTP email sending utility for Ascend Credential Registry.

Configuration (from environment / .env):
    MAIL_SERVER   – default: smtp.gmail.com
    MAIL_PORT     – default: 587 (STARTTLS)
    MAIL_USERNAME – SMTP username
    MAIL_PASSWORD – SMTP password / app password
    MAIL_FROM     – Sender address (default: MAIL_USERNAME or noreply@ascend.registry)
    APP_BASE_URL  – Web application base URL (default: http://localhost:5000)

Rules:
    - If MAIL_USERNAME or MAIL_PASSWORD is missing: do NOT crash. Print to console and return False.
    - Never send to addresses ending in '.ascend.demo' or '@example.com'; log them instead.
    - Sends run in daemon background threads; web requests never wait on SMTP.
    - Email failure never breaks application operations (issuing, approvals, verification).
    - Branded HTML template: indigo header (#26215C), gold button (#EF9F27), plain-text fallback.
"""

import os
import smtplib
import threading
import time
import logging
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# Addresses to never send real email to
BLOCKED_SUFFIXES = ('.ascend.demo', '@example.com')


def get_base_url() -> str:
    return os.environ.get('APP_BASE_URL', 'http://localhost:5000').rstrip('/')


def is_demo_address(address: str) -> bool:
    if not address:
        return True
    addr = address.strip().lower()
    return any(addr.endswith(s) or (s.startswith('@') and s in addr) for s in BLOCKED_SUFFIXES)


def render_branded_email(
    title: str,
    body_html: str,
    primary_button_text: str | None = None,
    primary_button_url: str | None = None,
    secondary_button_text: str | None = None,
    secondary_button_url: str | None = None,
) -> str:
    """
    Renders the Ascend branded HTML email with indigo header (#26215C) and gold button (#EF9F27).
    """
    buttons_html = ""
    buttons = []
    if primary_button_text and primary_button_url:
        buttons.append(
            f'''<td style="border-radius:8px; background:#EF9F27; text-align:center;">
                  <a href="{primary_button_url}"
                     style="display:inline-block; padding:12px 26px; font-family:Inter,Arial,sans-serif;
                            font-size:14px; font-weight:700; color:#26215C; text-decoration:none; border-radius:8px;">
                    {primary_button_text}
                  </a>
                </td>'''
        )
    if secondary_button_text and secondary_button_url:
        buttons.append(
            f'''<td style="border-radius:8px; background:#26215C; text-align:center;">
                  <a href="{secondary_button_url}"
                     style="display:inline-block; padding:12px 26px; font-family:Inter,Arial,sans-serif;
                            font-size:14px; font-weight:700; color:#ffffff; text-decoration:none; border-radius:8px;">
                    {secondary_button_text}
                  </a>
                </td>'''
        )

    if buttons:
        buttons_cells = "".join(f'<td style="padding:0 6px;">{b}</td>' for b in buttons)
        buttons_html = f'''
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:26px auto 10px;">
          <tr>
            {buttons_cells}
          </tr>
        </table>'''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#f5f3ff;font-family:'Inter',Arial,Helvetica,sans-serif;color:#2e2d38;-webkit-font-smoothing:antialiased;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f5f3ff;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
               style="max-width:580px;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 4px 18px rgba(38,33,92,0.08);border:1px solid #ebe7f7;">
          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg, #26215C 0%, #3C3489 100%);padding:30px 36px;text-align:center;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="center">
                    <span style="display:inline-block;font-family:Georgia,serif;font-size:24px;font-weight:700;color:#ffffff;letter-spacing:0.5px;">Ascend</span>
                    <span style="display:block;font-family:Inter,Arial,sans-serif;font-size:12px;font-weight:600;color:#c9c0ff;letter-spacing:1px;text-transform:uppercase;margin-top:4px;">Institutional Credential Registry</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body Content -->
          <tr>
            <td style="padding:34px 36px 28px;background:#ffffff;">
              <h1 style="margin:0 0 16px;font-size:20px;line-height:28px;color:#26215C;font-weight:700;font-family:Georgia,serif;">{title}</h1>
              <div style="font-size:15px;line-height:24px;color:#48464d;">
                {body_html}
              </div>
              {buttons_html}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:20px 36px;background:#f9f8fe;border-top:1px solid #ede9ff;text-align:center;">
              <p style="margin:0;font-size:12px;line-height:18px;color:#8782a0;">
                Ascend Institutional Trust & Credential Verification Registry<br>
                &copy; 2026 Ascend. Automated notification, please do not reply.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _send_smtp_sync(to: str, subject: str, text_body: str, html_body: str) -> bool:
    """Synchronous internal SMTP sender. Called inside background thread."""
    server = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    try:
        port = int(os.environ.get('MAIL_PORT', 587))
    except (ValueError, TypeError):
        port = 587
    username = os.environ.get('MAIL_USERNAME', '').strip()
    password = os.environ.get('MAIL_PASSWORD', '').strip()
    from_addr = os.environ.get('MAIL_FROM', '').strip() or username or 'noreply@ascend.registry'

    if not username or not password:
        print(f"[MAIL LOG - NO CREDS] To: {to} | Subject: {subject}\n{text_body}")
        logger.info("[MAIL LOG - NO CREDS] To: %s | Subject: %s", to, subject)
        return False

    if is_demo_address(to):
        print(f"[MAIL LOG - DEMO SKIPPED] To: {to} | Subject: {subject}")
        logger.info("[MAIL LOG - DEMO SKIPPED] To: %s | Subject: %s", to, subject)
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = to

        # Plain text fallback first, then HTML
        msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        with smtplib.SMTP(server, port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(username, password)
            smtp.sendmail(from_addr, [to], msg.as_string())

        logger.info("[MAIL SENT] To: %s | Subject: %s", to, subject)
        print(f"[MAIL SENT] To: {to} | Subject: {subject}")
        return True
    except Exception as exc:
        print(f"[MAIL ERROR] To: {to} | Subject: {subject} | Error: {exc}")
        logger.error("[MAIL ERROR] Failed sending to %s (%s): %s", to, subject, exc)
        return False


def send_email(to: str, subject: str, text_body: str, html_body: str) -> bool | threading.Thread:
    """
    Enqueue an email for delivery.
    - If MAIL_USERNAME or MAIL_PASSWORD missing: logs to console and returns False.
    - If demo address: logs to console and returns False.
    - Otherwise sends in background daemon thread (web request never waits) and returns Thread.
    """
    if not to:
        return False

    username = os.environ.get('MAIL_USERNAME', '').strip()
    password = os.environ.get('MAIL_PASSWORD', '').strip()

    # If credentials missing, log and return False immediately
    if not username or not password:
        print(f"[MAIL LOG - NO CREDS] To: {to} | Subject: {subject}\n{text_body}")
        logger.info("[MAIL LOG - NO CREDS] To: %s | Subject: %s", to, subject)
        return False

    # If demo address, log and return False immediately
    if is_demo_address(to):
        print(f"[MAIL LOG - DEMO SKIPPED] To: {to} | Subject: {subject}")
        logger.info("[MAIL LOG - DEMO SKIPPED] To: %s | Subject: %s", to, subject)
        return False

    # Spawn background daemon thread
    t = threading.Thread(
        target=_send_smtp_sync,
        args=(to, subject, text_body, html_body),
        daemon=True,
        name=f"mail-{to[:20]}"
    )
    t.start()
    return t


def send_emails_bulk(items: list[tuple[str, str, str, str]], pause: float = 0.5) -> threading.Thread:
    """
    Sends a list of (to, subject, text_body, html_body) sequentially in ONE
    background daemon worker with a pause (default 0.5s) between sends.
    """
    def _bulk_worker():
        for idx, (to, subject, text_body, html_body) in enumerate(items):
            _send_smtp_sync(to, subject, text_body, html_body)
            if idx < len(items) - 1 and pause > 0:
                time.sleep(pause)

    t = threading.Thread(target=_bulk_worker, daemon=True, name="mail-bulk-worker")
    t.start()
    return t


# ── Payload Builders & Email Triggers ─────────────────────────────────────────

def build_certificate_email_payload(
    recipient_email: str,
    cert_title: str,
    institution_name: str,
    verification_code: str,
    has_account: bool,
) -> tuple[str, str, str, str]:
    """
    Builds (to, subject, text_body, html_body) for a certificate issuance.
    """
    base_url = get_base_url()
    verify_url = f"{base_url}/verify/{verification_code}"
    register_url = f"{base_url}/register?email={urllib.parse.quote(recipient_email)}"

    subject = f"You received a certificate: '{cert_title}' from {institution_name}"

    if has_account:
        text_body = (
            f"Hello,\n\n"
            f"{institution_name} has issued you a verified credential on Ascend:\n\n"
            f"  Certificate: {cert_title}\n\n"
            f"View and verify your certificate here:\n"
            f"{verify_url}\n\n"
            f"Best regards,\n"
            f"The Ascend Team"
        )
        body_html = (
            f'<p style="margin:0 0 12px;">'
            f'  <strong>{institution_name}</strong> has issued you a new verified certificate:'
            f'</p>'
            f'<div style="margin:16px 0;padding:16px 20px;background:#f8f6ff;border-left:4px solid #EF9F27;border-radius:6px;">'
            f'  <div style="font-size:18px;font-weight:700;color:#26215C;">{cert_title}</div>'
            f'  <div style="font-size:13px;color:#6b6782;margin-top:4px;">Issued by {institution_name}</div>'
            f'</div>'
            f'<p style="margin:12px 0 0;font-size:14px;color:#5a5666;">'
            f'  Click the button below to view the official verification record.'
            f'</p>'
        )
        html_body = render_branded_email(
            title="You Received a New Certificate 🎓",
            body_html=body_html,
            primary_button_text="View Certificate",
            primary_button_url=verify_url,
        )
    else:
        text_body = (
            f"Hello,\n\n"
            f"{institution_name} has issued you a verified credential on Ascend:\n\n"
            f"  Certificate: {cert_title}\n\n"
            f"View and verify your certificate here:\n"
            f"{verify_url}\n\n"
            f"You don't have an Ascend account yet. Register to claim your certificate:\n"
            f"{register_url}\n\n"
            f"Best regards,\n"
            f"The Ascend Team"
        )
        body_html = (
            f'<p style="margin:0 0 12px;">'
            f'  <strong>{institution_name}</strong> has issued you a new verified certificate:'
            f'</p>'
            f'<div style="margin:16px 0;padding:16px 20px;background:#f8f6ff;border-left:4px solid #EF9F27;border-radius:6px;">'
            f'  <div style="font-size:18px;font-weight:700;color:#26215C;">{cert_title}</div>'
            f'  <div style="font-size:13px;color:#6b6782;margin-top:4px;">Issued by {institution_name}</div>'
            f'</div>'
            f'<p style="margin:16px 0 6px;font-size:14px;color:#26215C;font-weight:600;">'
            f'  You do not have an Ascend account yet.'
            f'</p>'
            f'<p style="margin:0 0 12px;font-size:14px;color:#5a5666;">'
            f'  Register with this email address to claim this certificate to your permanent portfolio.'
            f'</p>'
        )
        html_body = render_branded_email(
            title="You Received a New Certificate 🎓",
            body_html=body_html,
            primary_button_text="View Certificate",
            primary_button_url=verify_url,
            secondary_button_text="Register to Claim",
            secondary_button_url=register_url,
        )

    return (recipient_email, subject, text_body, html_body)


def email_certificate_issued(
    recipient_email: str,
    cert_title: str,
    institution_name: str,
    verification_code: str,
    has_account: bool,
):
    """Trigger single certificate issuance email (runs in daemon thread)."""
    to, subject, text, html = build_certificate_email_payload(
        recipient_email=recipient_email,
        cert_title=cert_title,
        institution_name=institution_name,
        verification_code=verification_code,
        has_account=has_account,
    )
    return send_email(to, subject, text, html)


def email_institution_approved(institution_email: str, institution_name: str, login_url: str | None = None):
    """Trigger email when institution account is approved by admin."""
    if not login_url:
        login_url = f"{get_base_url()}/login"

    subject = "Your Ascend institution account has been approved"
    text_body = (
        f"Hello {institution_name},\n\n"
        f"Your institution account on Ascend has been approved by the administrator.\n"
        f"You can now log in to manage departments, staff, and issue accredited certificates.\n\n"
        f"Log in here:\n"
        f"{login_url}\n\n"
        f"Best regards,\n"
        f"The Ascend Team"
    )
    body_html = (
        f'<p style="margin:0 0 12px;">'
        f'  Great news! Your institution account for <strong>{institution_name}</strong> '
        f'  has been <strong style="color:#1b5e20;">approved</strong> by the Ascend platform administrator.'
        f'</p>'
        f'<p style="margin:0 0 12px;">'
        f'  You now have full access to create certificate templates, configure departments and clubs, '
        f'  verify staff issuers, and issue verifiable credentials.'
        f'</p>'
    )
    html_body = render_branded_email(
        title="Institution Account Approved ✅",
        body_html=body_html,
        primary_button_text="Log In to Ascend",
        primary_button_url=login_url,
    )
    return send_email(institution_email, subject, text_body, html_body)


def email_institution_rejected(institution_email: str, institution_name: str, contact_url: str | None = None):
    """Trigger email when institution account application is rejected by admin."""
    if not contact_url:
        contact_url = f"{get_base_url()}/login"

    subject = "Update on your Ascend institution account application"
    text_body = (
        f"Hello {institution_name},\n\n"
        f"Thank you for your interest in Ascend. Following review, your institution application "
        f"was not approved at this time.\n\n"
        f"If you believe this was an error or would like to submit additional accreditation details, "
        f"please contact the Ascend administrative team.\n\n"
        f"Best regards,\n"
        f"The Ascend Team"
    )
    body_html = (
        f'<p style="margin:0 0 12px;">'
        f'  Thank you for applying to the Ascend Credential Registry.'
        f'</p>'
        f'<p style="margin:0 0 12px;">'
        f'  After administrative review, the institution account application for '
        f'  <strong>{institution_name}</strong> was not approved at this time.'
        f'</p>'
        f'<p style="margin:0 0 12px;">'
        f'  If you believe this decision is in error or would like to provide updated documentation, '
        f'  please reach out to our team.'
        f'</p>'
    )
    html_body = render_branded_email(
        title="Institution Application Status Update",
        body_html=body_html,
        primary_button_text="Visit Ascend",
        primary_button_url=contact_url,
    )
    return send_email(institution_email, subject, text_body, html_body)


def email_staff_verified(staff_email: str, staff_name: str, institution_name: str, dashboard_url: str | None = None):
    """Trigger email when staff member is verified by their institution head."""
    if not dashboard_url:
        dashboard_url = f"{get_base_url()}/dashboard"

    subject = f"Your staff account at {institution_name} has been verified"
    text_body = (
        f"Hello {staff_name},\n\n"
        f"Your staff issuer account at {institution_name} has been verified by the institution administrator.\n"
        f"You can now log in and issue certificates on behalf of {institution_name}.\n\n"
        f"Access your dashboard:\n"
        f"{dashboard_url}\n\n"
        f"Best regards,\n"
        f"The Ascend Team"
    )
    body_html = (
        f'<p style="margin:0 0 12px;">'
        f'  Congratulations {staff_name}! Your staff issuer account at <strong>{institution_name}</strong> '
        f'  has been <strong style="color:#1b5e20;">verified</strong>.'
        f'</p>'
        f'<p style="margin:0 0 12px;">'
        f'  You are now authorized to issue certificates to students and recipients on behalf of your institution.'
        f'</p>'
    )
    html_body = render_branded_email(
        title="Staff Issuer Account Verified ✅",
        body_html=body_html,
        primary_button_text="Go to Dashboard",
        primary_button_url=dashboard_url,
    )
    return send_email(staff_email, subject, text_body, html_body)


def email_staff_rejected(staff_email: str, staff_name: str, institution_name: str):
    """Trigger email when staff member application is rejected by institution head."""
    subject = f"Update on your staff application at {institution_name}"
    text_body = (
        f"Hello {staff_name},\n\n"
        f"Your application for a staff issuer account at {institution_name} on Ascend was not approved.\n"
        f"Please contact your institution head or academic department administrator for further information.\n\n"
        f"Best regards,\n"
        f"The Ascend Team"
    )
    body_html = (
        f'<p style="margin:0 0 12px;">'
        f'  Hello {staff_name},'
        f'</p>'
        f'<p style="margin:0 0 12px;">'
        f'  Your application for a staff issuer role at <strong>{institution_name}</strong> was not approved at this time.'
        f'</p>'
        f'<p style="margin:0 0 12px;">'
        f'  Please contact your department head or institution administrator directly if you need clarification.'
        f'</p>'
    )
    html_body = render_branded_email(
        title="Staff Application Status Update",
        body_html=body_html,
    )
    return send_email(staff_email, subject, text_body, html_body)
