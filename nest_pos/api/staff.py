# Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
# For license information, please see license.txt
"""Nest POS cashier endpoints: the shared kit endpoints plus client-basket completion on sale."""

import frappe

from nest_pos.kit import invoicing
from nest_pos.kit.staff_api import (  # noqa: F401  re-exported whitelisted endpoints
	bootstrap,
	cash_movement,
	catalog_page,
	close_register,
	create_customer,
	create_return,
	held_carts,
	hold_cart,
	open_register,
	promotions,
	quote,
	recent_sales,
	request_approval,
	resolve_scan,
	resume_cart,
	search_customers,
	retry_close,
	returnable,
	set_pin,
	shift_summary,
	switch_user_check,
)
from nest_pos.kit.util import obj
from nest_pos.services import baskets


@frappe.whitelist(methods=["POST"])
def submit_sale(register_name: str, payload, request_key: str, source: str = "Online") -> dict:
	data = obj(payload)
	result = invoicing.submit(register_name, data, request_key, source=source)
	if result.get("status") == "posted" and data.get("basket") and not result.get("replayed"):
		inv = result["invoice"]
		baskets.complete(data["basket"], inv["name"])
		# provenance link only; the invoice's accounting fields are untouched
		frappe.db.set_value(inv["doctype"], inv["name"], "nest_pos_basket", data["basket"], update_modified=False)
	return result
