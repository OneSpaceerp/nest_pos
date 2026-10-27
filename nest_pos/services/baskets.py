# Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
# For license information, please see license.txt
"""Client baskets: a shopper builds a basket on their phone and hands it to a cashier.

A basket is a request, not a sale: it is never proof of payment, an invoice or a stock movement.
State machine: Submitted → Claimed → Imported → Completed, with Cancelled / Expired exits and
Claimed → Submitted when a cashier releases it. See docs/state-machines.md.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, now_datetime

from nest_pos.appspec import SPEC
from nest_pos.core.fingerprint import classify_replay, fingerprint, validate_key
from nest_pos.core.fsm import CLIENT_BASKET
from nest_pos.core.payloads import clean_lines, clean_note
from nest_pos.core.tokens import TokenError, hash_token, new_token, short_code, verify_context
from nest_pos.kit import access, audit, catalog, realtime

BASKET = "Nest POS Client Basket"
CLIENT_SESSION = "Nest POS Client Session"
REGISTER = "Nest POS Register"
SESSION_IDLE_MINUTES = 120
BASKET_TTL_MINUTES = 60
MAX_BASKETS_PER_SESSION = 10


# ------------------------------------------------------------------------------- client (guest) side


def public_outlets() -> list[dict]:
	return frappe.get_all(
		REGISTER,
		filters={"enabled": 1, "outlet_label": ["is", "set"]},
		fields=["name as register", "outlet_label"],
		order_by="outlet_label asc",
	)


def start(register: str | None = None, store_code: str | None = None) -> dict:
	if store_code:
		secret = frappe.get_single(SPEC.dt("Settings")).get_password("signing_secret")
		try:
			register = verify_context(secret, store_code, "store").get("register")
		except TokenError as e:
			frappe.throw(_("This store code is not valid: {0}").format(e), frappe.PermissionError)
	reg = frappe.db.get_value(REGISTER, register, ["name", "enabled", "outlet_label", "company"], as_dict=True)
	if not reg or not reg.enabled or not reg.outlet_label:
		frappe.throw(_("This store isn't taking baskets right now."), frappe.PermissionError)
	token = new_token()
	doc = frappe.get_doc(
		{
			"doctype": CLIENT_SESSION,
			"token_hash": hash_token(token),
			"register": reg.name,
			"company": reg.company,
			"status": "Active",
			"expires_at": add_to_date(now_datetime(), minutes=SESSION_IDLE_MINUTES),
			"last_seen": now_datetime(),
		}
	)
	doc.flags.ignore_permissions = True  # guest session record; only its hash is stored
	doc.insert()
	frappe.db.commit()  # the token must exist before the client's very next request  # nosemgrep
	return {"token": token, "outlet": reg.outlet_label, "register": reg.name, "expires_in": SESSION_IDLE_MINUTES * 60}


def resolve_session(token: str):
	try:
		token_hash = hash_token(token or "")
	except TokenError:
		frappe.throw(_("Your shopping session has ended. Scan the store code again."), frappe.PermissionError)
	name = frappe.db.get_value(CLIENT_SESSION, {"token_hash": token_hash, "status": "Active"}, "name")
	if not name:
		frappe.throw(_("Your shopping session has ended. Scan the store code again."), frappe.PermissionError)
	doc = frappe.get_doc(CLIENT_SESSION, name)
	if doc.expires_at and doc.expires_at < now_datetime():
		frappe.db.set_value(CLIENT_SESSION, name, "status", "Expired")
		frappe.throw(_("Your shopping session has ended. Scan the store code again."), frappe.PermissionError)
	frappe.db.set_value(
		CLIENT_SESSION, name, {"expires_at": add_to_date(now_datetime(), minutes=SESSION_IDLE_MINUTES), "last_seen": now_datetime()},
		update_modified=False,
	)
	return doc


def price_check(token: str, code: str) -> dict:
	session = resolve_session(token)
	profile = frappe.db.get_value(REGISTER, session.register, "pos_profile")
	scanned = catalog.resolve_scan(profile, code)
	if scanned.get("status") != "ok":
		return {"status": "unknown" if scanned.get("status") in ("unknown", "invalid") else "unavailable"}
	return catalog.public_view(profile, scanned["item_code"])


def _public_lines(session, raw_lines) -> tuple[list[dict], str]:
	profile = frappe.get_cached_doc("POS Profile", frappe.db.get_value(REGISTER, session.register, "pos_profile"))
	codes = {str(l.get("item_code")) for l in raw_lines or [] if isinstance(l, dict)}
	allowed = {c for c in codes if catalog.public_view(profile.name, c).get("status") == "ok"}
	weighed = {c for c in allowed if frappe.get_cached_value("Item", c, "stock_uom") in ("Kg", "Gram", "Litre")}
	lines = clean_lines(raw_lines, allowed, allow_fractional=weighed)
	return lines, profile.name


def submit_basket(token: str, raw_lines, request_key: str, note: str = "") -> dict:
	session = resolve_session(token)
	key = validate_key(request_key)
	lines, profile = _public_lines(session, raw_lines)
	fp = fingerprint({"lines": lines, "note": clean_note(note)})
	existing = frappe.db.get_value(BASKET, {"request_key": key}, ["name", "fingerprint", "client_session"], as_dict=True)
	if existing:
		if existing.client_session != session.name or classify_replay(existing.fingerprint, fp) == "conflict":
			frappe.throw(_("This basket was already sent with different items. Start a new basket."))
		return status(token, existing.name)
	if cint(session.baskets_submitted) >= MAX_BASKETS_PER_SESSION:
		frappe.throw(_("You've sent the most baskets allowed for one visit. Ask a cashier for help."))
	price_list = frappe.get_cached_value("POS Profile", profile, "selling_price_list")
	items, total = [], 0.0
	for l in lines:
		view = catalog.public_view(profile, l["item_code"])
		items.append(
			{"item_code": l["item_code"], "item_name": view["item_name"], "qty": flt(l["qty"]), "uom": view["uom"], "rate_preview": view["rate"]}
		)
		total += flt(view["rate"]) * flt(l["qty"])
	doc = frappe.get_doc(
		{
			"doctype": BASKET,
			"handoff_code": short_code(),
			"status": "Submitted",
			"register": session.register,
			"client_session": session.name,
			"request_key": key,
			"fingerprint": fp,
			"expires_at": add_to_date(now_datetime(), minutes=BASKET_TTL_MINUTES),
			"total_preview": total,
			"price_list": price_list,
			"items": items,
			"client_note": clean_note(note),
		}
	)
	doc.flags.ignore_permissions = True  # guest-created request record, scoped to a validated session
	doc.insert()
	frappe.db.set_value(CLIENT_SESSION, session.name, "baskets_submitted", cint(session.baskets_submitted) + 1)
	realtime.to_register(session.register, "basket", {"basket": doc.name, "status": "Submitted", "version": 1})
	return _client_view(doc)


def status(token: str, basket: str) -> dict:
	session = resolve_session(token)
	doc = frappe.get_doc(BASKET, basket)
	if doc.client_session != session.name:
		frappe.throw(_("Basket not found"), frappe.DoesNotExistError)
	return _client_view(doc)


def cancel_by_client(token: str, basket: str) -> dict:
	session = resolve_session(token)
	frappe.db.get_value(BASKET, basket, "name", for_update=True)
	doc = frappe.get_doc(BASKET, basket)
	if doc.client_session != session.name:
		frappe.throw(_("Basket not found"), frappe.DoesNotExistError)
	if doc.status != "Submitted":
		frappe.throw(_("A cashier is already working on this basket. Ask them to cancel it."))
	_move(doc, "Cancelled", cancel_reason=_("Cancelled by shopper"))
	return _client_view(doc)


def _client_view(doc) -> dict:
	return {
		"basket": doc.name,
		"handoff_code": doc.handoff_code,
		"status": doc.status,
		"total_preview": doc.total_preview,
		"expires_at": str(doc.expires_at),
		"items": [{"item_code": i.item_code, "item_name": i.item_name, "qty": i.qty, "rate_preview": i.rate_preview} for i in doc.items],
	}


# -------------------------------------------------------------------------------------- staff side


def _move(doc, target: str, **values) -> None:
	CLIENT_BASKET.assert_transition(doc.status, target)
	doc.status = target
	doc.update(values)
	doc.version = cint(doc.version) + 1
	doc.flags.ignore_permissions = True  # status moves are authorised by the calling service
	doc.save()
	realtime.to_register(doc.register, "basket", {"basket": doc.name, "status": doc.status, "version": doc.version})


def inbox(register: str) -> list[dict]:
	access.require_register(register)
	return frappe.get_all(
		BASKET,
		filters={"register": register, "status": ["in", ["Submitted", "Claimed"]]},
		fields=["name", "handoff_code", "status", "claimed_by", "total_preview", "creation", "expires_at", "version"],
		order_by="creation asc",
		limit_page_length=100,
	)


def _locked(basket: str):
	if not frappe.db.get_value(BASKET, basket, "name", for_update=True):
		frappe.throw(_("Basket not found"), frappe.DoesNotExistError)
	return frappe.get_doc(BASKET, basket)


def claim(basket: str) -> dict:
	"""Row lock + state check: of two simultaneous claims exactly one wins; the other sees Claimed."""
	doc = _locked(basket)
	access.require_register(doc.register)
	if doc.status == "Claimed" and doc.claimed_by == frappe.session.user:
		return {"basket": doc.name, "status": doc.status, "replay": True}
	if doc.status != "Submitted":
		frappe.throw(_("Basket {0} is {1}.").format(doc.handoff_code, _(doc.status).lower()), title=_("Already taken"))
	if doc.expires_at and doc.expires_at < now_datetime():
		_move(doc, "Expired")
		frappe.throw(_("This basket has expired."))
	_move(doc, "Claimed", claimed_by=frappe.session.user, claimed_at=now_datetime())
	return {"basket": doc.name, "status": doc.status}


def import_into_cart(basket: str, cart_id: str) -> dict:
	"""Exactly once per basket. A retry from the same cashier and cart returns the same lines."""
	doc = _locked(basket)
	if doc.claimed_by != frappe.session.user:
		frappe.throw(_("Claim the basket before importing it."), frappe.PermissionError)
	if doc.status == "Imported":
		if doc.imported_cart != cart_id:
			frappe.throw(_("This basket is already in another sale."))
	elif doc.status == "Claimed":
		_move(doc, "Imported", imported_cart=cart_id)
	else:
		frappe.throw(_("Basket {0} can't be imported while {1}.").format(doc.handoff_code, doc.status))
	profile = frappe.db.get_value(REGISTER, doc.register, "pos_profile")
	lines = []
	for i in doc.items:
		now = catalog.public_view(profile, i.item_code)
		lines.append(
			{
				"item_code": i.item_code,
				"item_name": i.item_name,
				"qty": i.qty,
				"rate_preview": i.rate_preview,
				"rate_now": now.get("rate"),
				"price_changed": now.get("status") != "ok" or flt(now.get("rate")) != flt(i.rate_preview),
				"available": now.get("status") == "ok",
			}
		)
	audit.log("basket.import", BASKET, doc.name, register=doc.register, cart=cart_id)
	return {"basket": doc.name, "handoff_code": doc.handoff_code, "lines": lines, "note": doc.client_note}


def release(basket: str) -> dict:
	doc = _locked(basket)
	if doc.claimed_by != frappe.session.user and not access.is_supervisor():
		frappe.throw(_("Only the cashier who claimed it, or a supervisor, can release it."), frappe.PermissionError)
	_move(doc, "Submitted", claimed_by=None, claimed_at=None)
	return {"basket": doc.name, "status": doc.status}


def cancel_by_staff(basket: str, reason: str) -> dict:
	doc = _locked(basket)
	access.require_register(doc.register)
	if not (reason or "").strip():
		frappe.throw(_("Give a reason."))
	_move(doc, "Cancelled", cancel_reason=reason.strip()[:200])
	audit.log("basket.cancel", BASKET, doc.name, register=doc.register, reason=reason)
	return {"basket": doc.name, "status": doc.status}


def complete(basket: str, invoice: str) -> None:
	doc = _locked(basket)
	if doc.status == "Completed":
		return
	if doc.claimed_by != frappe.session.user:
		frappe.throw(_("This basket was imported by another cashier."), frappe.PermissionError)
	_move(doc, "Completed", invoice=invoice)


def expire_stale() -> None:
	"""Scheduler (every 5 minutes)."""
	for name in frappe.get_all(BASKET, {"status": "Submitted", "expires_at": ["<", now_datetime()]}, pluck="name"):
		doc = _locked(name)
		if doc.status == "Submitted":
			_move(doc, "Expired")
	frappe.db.sql(
		f"update `tab{CLIENT_SESSION}` set status='Expired' where status='Active' and expires_at < %s", now_datetime()
	)
