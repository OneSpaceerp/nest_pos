# Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
# For license information, please see license.txt
"""Phone-as-scanner pairing for a desktop cashier's active cart.

The desktop opens a short-lived pairing bound to its register, shift and cart id; a signed-in staff
phone joins with the 6-character code. Scans carry a per-pairing sequence number, so a resent scan is
ignored rather than added twice, and they are delivered only to the desktop user who owns the pairing.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, now_datetime

from nest_pos.core.fsm import SCANNER_PAIRING
from nest_pos.core.tokens import hash_token, short_code
from nest_pos.kit import access, audit, catalog, realtime, register

PAIRING = "Nest POS Scanner Pairing"
PENDING_MINUTES = 5
ACTIVE_HOURS = 10


def create(register_name: str, cart_id: str) -> dict:
	session = register.require_open_session(register_name)
	if not cart_id or len(cart_id) > 64:
		frappe.throw(_("Invalid cart"))
	for old in frappe.get_all(PAIRING, {"owner_user": frappe.session.user, "status": ["in", ["Pending", "Active"]]}, pluck="name"):
		_move(frappe.get_doc(PAIRING, old), "Revoked")
	code = short_code()
	doc = frappe.get_doc(
		{
			"doctype": PAIRING,
			"register": register_name,
			"session": session.name,
			"cart_id": cart_id,
			"owner_user": frappe.session.user,
			"status": "Pending",
			"pair_code_hash": hash_token(f"{register_name}:{code}"),
			"expires_at": add_to_date(now_datetime(), minutes=PENDING_MINUTES),
		}
	)
	doc.flags.ignore_permissions = True  # created for the caller's own open shift
	doc.insert()
	return {"pairing": doc.name, "code": code, "expires_in": PENDING_MINUTES * 60}


def join(register_name: str, code: str) -> dict:
	access.require_register(register_name)
	name = frappe.db.get_value(PAIRING, {"pair_code_hash": hash_token(f"{register_name}:{(code or '').upper()}")}, "name", for_update=True)
	if not name:
		frappe.throw(_("That pairing code isn't valid."), frappe.PermissionError)
	doc = frappe.get_doc(PAIRING, name)
	if doc.status != "Pending" or doc.expires_at < now_datetime():
		frappe.throw(_("That pairing code has expired. Ask for a new one."), frappe.PermissionError)
	_move(doc, "Active", phone_user=frappe.session.user, expires_at=add_to_date(now_datetime(), hours=ACTIVE_HOURS))
	audit.log("pairing.join", PAIRING, doc.name, register=register_name, desktop=doc.owner_user)
	realtime.to_user(doc.owner_user, "pairing", {"pairing": doc.name, "status": "Active", "phone_user": frappe.session.user})
	return {"pairing": doc.name, "cart_id": doc.cart_id, "desktop_user": doc.owner_user}


def scan(pairing: str, seq: int, raw: str) -> dict:
	frappe.db.get_value(PAIRING, pairing, "name", for_update=True)
	doc = frappe.get_doc(PAIRING, pairing)
	if doc.phone_user != frappe.session.user:
		frappe.throw(_("This phone isn't paired."), frappe.PermissionError)
	if doc.status != "Active" or doc.expires_at < now_datetime():
		frappe.throw(_("Pairing ended. Pair again from the till."), frappe.PermissionError)
	if frappe.db.get_value("Nest POS Register Session", doc.session, "status") != "Open":
		_move(doc, "Expired")
		frappe.throw(_("The till's shift has closed."))
	seq = cint(seq)
	if seq <= cint(doc.last_event_seq):
		return {"duplicate": True, "seq": seq}
	profile = frappe.db.get_value("Nest POS Register", doc.register, "pos_profile")
	result = catalog.resolve_scan(profile, raw)
	frappe.db.set_value(PAIRING, doc.name, "last_event_seq", seq, update_modified=False)
	realtime.to_user(doc.owner_user, "paired_scan", {"pairing": doc.name, "cart_id": doc.cart_id, "seq": seq, "result": result})
	return {"duplicate": False, "seq": seq, "result": result}


def revoke(pairing: str) -> dict:
	doc = frappe.get_doc(PAIRING, pairing)
	if frappe.session.user not in (doc.owner_user, doc.phone_user) and not access.is_supervisor():
		frappe.throw(_("Not your pairing."), frappe.PermissionError)
	if doc.status in ("Pending", "Active"):
		_move(doc, "Revoked")
		for user in {doc.owner_user, doc.phone_user} - {None}:
			realtime.to_user(user, "pairing", {"pairing": doc.name, "status": "Revoked"})
	return {"pairing": doc.name, "status": doc.status}


def _move(doc, target: str, **values) -> None:
	SCANNER_PAIRING.assert_transition(doc.status, target)
	doc.status = target
	doc.update(values)
	doc.flags.ignore_permissions = True
	doc.save()
