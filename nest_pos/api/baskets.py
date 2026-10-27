# Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
# For license information, please see license.txt
"""Cashier inbox for client baskets."""

import frappe

from nest_pos.core.tokens import sign_context
from nest_pos.kit import access
from nest_pos.services import baskets


@frappe.whitelist()
def inbox(register_name: str) -> list:
	return baskets.inbox(register_name)


@frappe.whitelist(methods=["POST"])
def claim(basket: str) -> dict:
	return baskets.claim(basket)


@frappe.whitelist(methods=["POST"])
def import_basket(basket: str, cart_id: str) -> dict:
	return baskets.import_into_cart(basket, cart_id)


@frappe.whitelist(methods=["POST"])
def release(basket: str) -> dict:
	return baskets.release(basket)


@frappe.whitelist(methods=["POST"])
def cancel(basket: str, reason: str) -> dict:
	return baskets.cancel_by_staff(basket, reason)


@frappe.whitelist()
def store_qr(register_name: str, days: int = 365) -> dict:
	"""Signed store link for printing at the entrance. It names the store; it grants nothing."""
	access.require("manager", "supervisor")
	access.require_register(register_name)
	secret = frappe.get_single("Nest POS Settings").get_password("signing_secret")
	code = sign_context(secret, "store", {"register": register_name}, max(1, min(int(days), 730)) * 86400)
	return {"register": register_name, "url": f"/nest-pos/customer/s/{code}"}
