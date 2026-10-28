# Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
# For license information, please see license.txt
"""Shopper account endpoints (Nest Shop PWA). See services/accounts.py.

Sign-up is the only guest endpoint here: POST-only, rate limited per IP, and subject to the site's
own sign-up switch and hourly cap. Everything else needs a signed-in shopper and only ever returns
that shopper's own records.
"""

import frappe
from frappe.rate_limiter import rate_limit

from nest_pos.services import accounts


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=60 * 60)
def signup(full_name: str, email: str, password: str, mobile: str = "") -> dict:
	return accounts.signup(full_name, email, password, mobile)


@frappe.whitelist()
def me() -> dict:
	return accounts.me()


@frappe.whitelist(methods=["POST"])
def update_profile(full_name: str, mobile: str = "") -> dict:
	return accounts.update_profile(full_name, mobile)


@frappe.whitelist()
def purchases(limit: int = 30) -> list:
	return accounts.purchases(limit)


@frappe.whitelist()
def purchase(doctype: str, name: str) -> dict:
	return accounts.purchase(doctype, name)
