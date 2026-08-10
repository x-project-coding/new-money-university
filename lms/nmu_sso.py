# Single sign-on bridge from the 42bucks platform (agent-app launch flow).
#
# The university agent app validates the platform's one-time launch ticket
# with x-api, then redirects the browser here with a short-lived HMAC token:
#
#   GET /api/method/lms.nmu_sso.login?token=<b64url(payload)>.<b64url(sig)>
#
#   payload JSON: {"email": ..., "full_name": ..., "iat": epoch, "exp": epoch}
#   sig = HMAC-SHA256(payload_bytes, site_config.nmu_sso_secret)
#
# On a valid token the user is created on first visit (Website User with the
# LMS Student role — everyone shares the one platform course catalog) and a
# Frappe session is opened, landing them in the LMS.

import base64
import hashlib
import hmac
import json
import time

import frappe

MAX_TOKEN_AGE_SECONDS = 300


def _b64url_decode(part: str) -> bytes:
	padding = "=" * (-len(part) % 4)
	return base64.urlsafe_b64decode(part + padding)


def _verify(token: str, secret: str) -> dict:
	try:
		payload_part, sig_part = token.split(".", 1)
		payload_bytes = _b64url_decode(payload_part)
		signature = _b64url_decode(sig_part)
	except Exception:
		frappe.throw(frappe._("Malformed SSO token"), frappe.AuthenticationError)

	expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).digest()
	if not hmac.compare_digest(signature, expected):
		frappe.throw(frappe._("Invalid SSO token signature"), frappe.AuthenticationError)

	payload = json.loads(payload_bytes)
	now = int(time.time())
	exp = int(payload.get("exp") or 0)
	iat = int(payload.get("iat") or 0)
	if not exp or now > exp or exp - iat > MAX_TOKEN_AGE_SECONDS:
		frappe.throw(frappe._("Expired SSO token"), frappe.AuthenticationError)
	if not payload.get("email"):
		frappe.throw(frappe._("SSO token has no email"), frappe.AuthenticationError)
	return payload


@frappe.whitelist(allow_guest=True, methods=["GET"])
def login(token: str, redirect: str | None = None):
	secret = frappe.conf.get("nmu_sso_secret")
	if not secret:
		frappe.throw(frappe._("SSO is not configured"), frappe.AuthenticationError)

	payload = _verify(token, secret)
	email = payload["email"].strip().lower()
	full_name = (payload.get("full_name") or "").strip() or email.split("@")[0]

	existing = frappe.db.exists("User", email)
	if existing:
		# The bridge only ever signs in Website Users. Refusing System Users
		# means a leaked/abused secret cannot take over Administrator or any
		# desk account.
		if frappe.db.get_value("User", email, "user_type") != "Website User":
			frappe.throw(frappe._("SSO cannot sign in this account"), frappe.AuthenticationError)
	else:
		# The verified token is the authorization; provisioning the Website
		# User requires elevated rights (login_as below replaces the session).
		frappe.set_user("Administrator")
		parts = full_name.split(" ", 1)
		user_doc = frappe.new_doc("User")
		user_doc.email = email
		user_doc.user_type = "Website User"
		user_doc.first_name = parts[0]
		user_doc.last_name = parts[1] if len(parts) > 1 else ""
		user_doc.full_name = full_name
		user_doc.send_welcome_email = False
		user_doc.append("roles", {"role": "LMS Student"})
		user_doc.insert(ignore_permissions=True)
		if user_doc.user_type != "Website User":
			frappe.throw(frappe._("SSO provisioning failed"), frappe.AuthenticationError)

	frappe.local.login_manager.login_as(email)

	location = "/lms"
	if (
		redirect
		and redirect.startswith("/")
		and not redirect.startswith("//")
		and "\\" not in redirect
		and not any(ord(ch) < 32 for ch in redirect)
	):
		location = redirect
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = location
