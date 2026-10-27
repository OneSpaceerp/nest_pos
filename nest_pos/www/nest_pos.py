# Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
# For license information, please see license.txt
# Serves www/nest-pos.html (the built staff PWA shell) at /nest-pos and /nest-pos/<path>.

from nest_pos.kit.boot import staff_context

no_cache = 1


def get_context(context):
	return staff_context(context, "/nest-pos")
