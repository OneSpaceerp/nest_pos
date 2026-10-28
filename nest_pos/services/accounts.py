# Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
# For license information, please see license.txt
"""Shopper accounts for the Nest Shop PWA.

An account is a Frappe Website User (no Desk) with ERPNext's "Customer" portal role, a new ERPNext
Customer, and a Contact that links the two. Sign-up follows the site's own switch (Website Settings →
Disable Signup) and Frappe's hourly sign-up cap and password policy; no email or SMS is sent.

A new account is never attached to an existing Customer that happens to share the phone or email:
without a verified channel that would let anyone read someone else's purchases. Staff can merge
records in Desk when a regular customer asks.

Clients only ever see invoices whose customer is their own linked Customer.
"""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, validate_email_address

from nest_pos.kit import audit

PORTAL_ROLE = "Customer"
INVOICE_DOCTYPES = ("Sales Invoice", "POS Invoice")
PHONE_RE = re.compile(r"^\+?[\d\s()-]{7,20}$")


# ------------------------------------------------------------------------------------------ who am I


def linked_customer(user: str | None = None) -> str | None:
	user = user or frappe.session.user
	if not user or user == "Guest":
		return None
	contacts = frappe.get_all("Contact", {"user": user}, pluck="name", limit=5)
	if not contacts:
		return None
	return frappe.db.get_value(
		"Dynamic Link", {"parenttype": "Contact", "parent": ["in", contacts], "link_doctype": "Customer"}, "link_name"
	)


def require_client() -> str:
	customer = linked_customer()
	if not customer:
		frappe.throw(_("Sign in to your shopping account first."), frappe.PermissionError)
	return customer


def client_boot() -> dict | None:
	"""Rendered into the shopper shell: who is signed in, if it is a shopper account."""
	customer = linked_customer()
	if not customer:
		return None
	user = frappe.db.get_value("User", frappe.session.user, ["full_name", "email", "mobile_no"], as_dict=True)
	return {"full_name": user.full_name, "email": user.email, "mobile": user.mobile_no or "", "customer": customer}


# ------------------------------------------------------------------------------------------ sign up


def _signup_allowed() -> None:
	from frappe.core.doctype.user.user import is_signup_disabled

	if is_signup_disabled():
		frappe.throw(_("New accounts can't be created here right now. Ask a member of staff."), frappe.PermissionError)
	cap = cint(frappe.get_system_settings("max_signups_allowed_per_hour") or 300)
	if frappe.db.get_creation_count("User", 60) >= cap:
		frappe.throw(_("Too many accounts were created in the last hour. Try again later."))


def _check_password(pwd: str, inputs: list[str]) -> None:
	if len(pwd or "") < 8:
		frappe.throw(_("Use at least 8 characters for your password."))
	from frappe.utils.password_strength import test_password_strength

	if test_password_strength(pwd, user_inputs=inputs).get("score", 0) < 2:
		frappe.throw(_("This password is too easy to guess. Add words, numbers or symbols."))


def _customer_group() -> str:
	g = frappe.db.get_single_value("Selling Settings", "customer_group")
	if g and not frappe.db.get_value("Customer Group", g, "is_group"):
		return g
	for name in ("Individual", _("Individual")):
		if frappe.db.exists("Customer Group", {"name": name, "is_group": 0}):
			return name
	leaf = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
	if not leaf:
		frappe.throw(_("The store hasn't finished setting up accounts. Ask a member of staff."))
	return leaf


def signup(full_name: str, email: str, password: str, mobile: str = "") -> dict:
	_signup_allowed()
	full_name = " ".join((full_name or "").split())[:140]
	email = (email or "").strip().lower()[:140]
	mobile = (mobile or "").strip()[:20]
	if len(full_name) < 2:
		frappe.throw(_("Enter your name."))
	if not email or not validate_email_address(email):
		frappe.throw(_("Enter a valid email address."))
	if mobile and not PHONE_RE.match(mobile):
		frappe.throw(_("Enter a valid mobile number."))
	if frappe.db.exists("User", email):
		frappe.throw(_("There is already an account for this email. Sign in instead."))
	_check_password(password, [full_name, email, mobile])

	first, _sp, last = full_name.partition(" ")
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": first,
			"last_name": last or None,
			"mobile_no": mobile or None,
			"user_type": "Website User",
			"enabled": 1,
			"send_welcome_email": 0,  # nothing is sent; the shopper chose their password here
			"new_password": password,
		}
	)
	user.flags.ignore_permissions = True  # guest sign-up; validated above and rate limited
	user.insert()
	if frappe.db.exists("Role", PORTAL_ROLE):
		user.add_roles(PORTAL_ROLE)

	customer = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": full_name,
			"customer_type": "Individual",
			"customer_group": _customer_group(),
			"territory": frappe.db.get_single_value("Selling Settings", "territory") or None,
		}
	)
	customer.flags.ignore_permissions = True
	customer.insert()

	contact = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": first,
			"last_name": last or None,
			"user": user.name,
			"is_primary_contact": 1,
			"email_ids": [{"email_id": email, "is_primary": 1}],
			"phone_nos": [{"phone": mobile, "is_primary_mobile_no": 1}] if mobile else [],
			"links": [{"link_doctype": "Customer", "link_name": customer.name}],
		}
	)
	contact.flags.ignore_permissions = True
	contact.insert()
	customer.db_set({"customer_primary_contact": contact.name, "mobile_no": mobile or None, "email_id": email})
	audit.log("client.signup", "Customer", customer.name, user=user.name)

	frappe.local.login_manager.login_as(user.name)
	return {"full_name": full_name, "email": email, "mobile": mobile, "customer": customer.name}


# ------------------------------------------------------------------------------------------ profile


def me() -> dict:
	require_client()
	return client_boot()


def update_profile(full_name: str, mobile: str = "") -> dict:
	customer = require_client()
	full_name = " ".join((full_name or "").split())[:140]
	mobile = (mobile or "").strip()[:20]
	if len(full_name) < 2:
		frappe.throw(_("Enter your name."))
	if mobile and not PHONE_RE.match(mobile):
		frappe.throw(_("Enter a valid mobile number."))
	first, _sp, last = full_name.partition(" ")
	user = frappe.get_doc("User", frappe.session.user)
	user.update({"first_name": first, "last_name": last or None, "mobile_no": mobile or None})
	user.flags.ignore_permissions = True
	user.save()
	contact = frappe.get_doc("Contact", frappe.db.get_value("Contact", {"user": user.name}, "name"))
	contact.update({"first_name": first, "last_name": last or None})
	if mobile:
		if contact.phone_nos:
			contact.phone_nos[0].phone = mobile
		else:
			contact.append("phone_nos", {"phone": mobile, "is_primary_mobile_no": 1})
	contact.flags.ignore_permissions = True
	contact.save()
	frappe.db.set_value("Customer", customer, {"customer_name": full_name, "mobile_no": mobile or None})
	return client_boot()


# ------------------------------------------------------------------------------------------ purchases


def purchases(limit: int = 30) -> list[dict]:
	customer = require_client()
	limit = min(max(cint(limit) or 30, 1), 100)
	rows = []
	for dt in INVOICE_DOCTYPES:
		for r in frappe.get_all(
			dt,
			{"customer": customer, "docstatus": 1},
			["name", "posting_date", "posting_time", "grand_total", "rounded_total", "currency", "is_return", "total_qty", "company"],
			order_by="posting_date desc, posting_time desc",
			limit=limit,
		):
			rows.append({**r, "doctype": dt, "total": flt(r.rounded_total or r.grand_total), "posting_date": str(r.posting_date), "posting_time": str(r.posting_time)[:5]})
	rows.sort(key=lambda r: (r["posting_date"], r["posting_time"]), reverse=True)
	return rows[:limit]


def purchase(doctype: str, name: str) -> dict:
	customer = require_client()
	if doctype not in INVOICE_DOCTYPES:
		frappe.throw(_("Receipt not found."))
	doc = frappe.get_doc(doctype, name) if frappe.db.exists(doctype, name) else None
	if not doc or doc.customer != customer or doc.docstatus != 1:
		frappe.throw(_("Receipt not found."))  # same answer whether it exists or not
	session = doc.get("nest_pos_session")
	register = frappe.db.get_value("Nest POS Register Session", session, "register") if session else None
	outlet = frappe.db.get_value("Nest POS Register", register, "outlet_label") if register else None
	return {
		"doctype": doctype,
		"name": doc.name,
		"posting_date": str(getdate(doc.posting_date)),
		"posting_time": str(doc.posting_time)[:5],
		"outlet": outlet or doc.company,
		"currency": doc.currency,
		"is_return": cint(doc.is_return),
		"items": [{"item_name": i.item_name, "qty": flt(i.qty), "uom": i.uom, "rate": flt(i.rate), "amount": flt(i.amount)} for i in doc.items],
		"net_total": flt(doc.net_total),
		"discount": flt(doc.discount_amount),
		"taxes": [{"description": t.description, "amount": flt(t.tax_amount)} for t in doc.taxes if flt(t.tax_amount)],
		"total": flt(doc.rounded_total or doc.grand_total),
		"payments": [{"mode": p.mode_of_payment, "amount": flt(p.amount)} for p in doc.payments if flt(p.amount)],
		"change": flt(doc.change_amount),
	}
