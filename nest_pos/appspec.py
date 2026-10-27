# Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
# For license information, please see license.txt
"""Identity of this app for the vendored kit (see nest_pos/kit/VENDORED.md)."""

from nest_pos.kit.spec import AppSpec

SPEC = AppSpec(
	app="nest_pos",
	prefix="Nest POS",
	field_prefix="nest_pos",
	route="/nest-pos",
	desk_page="nest-pos",
	roles={"cashier": "Nest POS Cashier", "supervisor": "Nest POS Supervisor", "manager": "Nest POS Manager"},
	modules=("Nest POS Setup", "Nest POS Registers", "Nest POS Selling", "Nest POS Pricing"),
	extra_invoice_fields=(
		{
			"fieldname": "nest_pos_basket",
			"fieldtype": "Link",
			"label": "Nest POS client basket",
			"options": "Nest POS Client Basket",
			"insert_after": "nest_pos_request",
			"read_only": 1,
			"no_copy": 1,
		},
	),
)
