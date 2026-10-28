# Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
# For license information, please see license.txt
# Serves www/nest-pos-customer.html (the built shopper PWA shell) at /nest-pos/customer/<path>.

import frappe

from nest_pos.kit.boot import customer_context
from nest_pos.services.accounts import client_boot

no_cache = 1


def get_context(context):
	# a signed-in shopper account (never staff details: client_boot only answers for linked customers)
	extra = {"client": client_boot(), "signed_in": frappe.session.user != "Guest"}
	return customer_context(context, "/nest-pos/customer", extra)
