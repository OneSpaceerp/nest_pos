# Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
# For license information, please see license.txt

import frappe

from nest_pos.services import pairing


@frappe.whitelist(methods=["POST"])
def create(register_name: str, cart_id: str) -> dict:
	return pairing.create(register_name, cart_id)


@frappe.whitelist(methods=["POST"])
def join(register_name: str, code: str) -> dict:
	return pairing.join(register_name, code)


@frappe.whitelist(methods=["POST"])
def scan(pairing_name: str, seq: int, code: str) -> dict:
	return pairing.scan(pairing_name, seq, (code or "")[:128])


@frappe.whitelist(methods=["POST"])
def revoke(pairing_name: str) -> dict:
	return pairing.revoke(pairing_name)
