app_name = "nest_pos"
app_title = "Nest POS"
app_publisher = "Nest Software Development (nsdLabs)"
app_description = "Retail point of sale for ERPNext: fast checkout, phone scanning, client baskets and registers"
app_email = "info@nsd-eg.com"
app_license = "UNLICENSED"  # pending a publisher licensing decision; see docs/provenance.md
app_logo_url = "/assets/nest_pos/images/nest-pos-logo.png"
app_home = "/desk/nest-pos"

required_apps = ["erpnext"]

# Two-tone dock/sidebar header icons (ids prefixed nest-pos-* so they never collide)
app_include_icons = ["/assets/nest_pos/icons/nest_pos-icons.svg"]

# Apps screen tile (verified against frappe v16.52.0 hooks.py)
add_to_apps_screen = [
	{
		"name": app_name,
		"logo": app_logo_url,
		"title": app_title,
		"route": app_home,
		"has_permission": "nest_pos.kit.access.check_app_permission",
		"sequence_id": 50,
	}
]

# Staff PWA at /nest-pos/…, customer PWA at /nest-pos/customer/… (customer rules first: more specific)
website_route_rules = [
	{"from_route": "/nest-pos/customer", "to_route": "nest-pos-customer"},
	{"from_route": "/nest-pos/customer/<path:app_path>", "to_route": "nest-pos-customer"},
	{"from_route": "/nest-pos/<path:app_path>", "to_route": "nest-pos"},
]

# Serves <route>/sw.js and <route>/customer/sw.js with the right scope (see kit/sw.py)
page_renderer = ["nest_pos.kit.sw.ServiceWorkerRenderer"]

after_install = "nest_pos.kit.install.after_install"
after_migrate = "nest_pos.kit.install.after_migrate"

# Narrow hooks on core documents: guard_invoice returns immediately unless the invoice carries a
# Nest POS shift link, so every other invoice in ERPNext is untouched.
doc_events = {
	"Sales Invoice": {
		"validate": "nest_pos.kit.install.guard_invoice",
		"before_cancel": "nest_pos.kit.install.guard_invoice",
	},
	"POS Invoice": {
		"validate": "nest_pos.kit.install.guard_invoice",
		"before_cancel": "nest_pos.kit.install.guard_invoice",
	},
}

permission_query_conditions = {
	"Nest POS Register": "nest_pos.kit.access.register_query",
	"Nest POS Register Session": "nest_pos.kit.access.session_query",
	"Nest POS Sale Request": "nest_pos.kit.access.sale_request_query",
}

has_permission = {
	"Nest POS Register": "nest_pos.kit.access.register_has_permission",
}

scheduler_events = {
	"cron": {
		"*/5 * * * *": [
			"nest_pos.services.baskets.expire_stale",
			"nest_pos.kit.register.follow_up_consolidations",
		],
	},
}

export_python_type_annotations = True
