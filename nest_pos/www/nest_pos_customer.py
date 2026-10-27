# Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
# For license information, please see license.txt
# Serves www/nest-pos-customer.html (the built shopper PWA shell) at /nest-pos/customer/<path>.

from nest_pos.kit.boot import customer_context

no_cache = 1


def get_context(context):
	return customer_context(context, "/nest-pos/customer")
