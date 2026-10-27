// Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
// For license information, please see license.txt
//
// Hosts the Nest POS till inside Desk's own shell (Dock + module Sidebar stay native). The Vue
// bundle is built by frontend/ into public/desk/ and mounted into the page body.

frappe.pages["nest-pos"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Nest POS"), single_column: true });
	page.add_inner_button(__("Full screen"), () => window.open("/nest-pos", "_self"));
	const mount = document.createElement("div");
	mount.className = "nest-desk-host";
	page.main[0].appendChild(mount);
	frappe.require(["/assets/nest_pos/desk/nest-pos-desk.css", "/assets/nest_pos/desk/nest-pos-desk.js"], () => {
		wrapper.nest_app = window["NestPosDesk"].mount(mount, {
			csrfToken: frappe.csrf_token,
			user: frappe.session.user,
			lang: frappe.boot.lang,
			embedded: true,
		});
	});
};

frappe.pages["nest-pos"].on_page_show = function (wrapper) {
	wrapper.nest_app?.resume?.();
};
