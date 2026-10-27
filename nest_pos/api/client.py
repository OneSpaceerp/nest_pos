# Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
# For license information, please see license.txt
"""Public (guest) endpoints for the shopper PWA.

Guests never touch Frappe documents directly. Each call carries an opaque session token; the server
stores only its hash. Calls are rate-limited per client IP, payloads are bounded, and responses carry
only public catalog data. Staff credentials never appear in the customer bundle.
"""

import frappe
from frappe.rate_limiter import rate_limit

from nest_pos.kit.util import obj
from nest_pos.services import baskets


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=60)
def outlets() -> list:
	return baskets.public_outlets()


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=60 * 10)
def start(register_name: str | None = None, store_code: str | None = None) -> dict:
	return baskets.start(register_name, store_code)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=120, seconds=60)
def price(token: str, code: str) -> dict:
	return baskets.price_check(token, (code or "")[:128])


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=15, seconds=60)
def submit(token: str, lines, request_key: str, note: str = "") -> dict:
	return baskets.submit_basket(token, obj(lines, []), request_key, note)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=120, seconds=60)
def status(token: str, basket: str) -> dict:
	return baskets.status(token, basket)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=60)
def cancel(token: str, basket: str) -> dict:
	return baskets.cancel_by_client(token, basket)
