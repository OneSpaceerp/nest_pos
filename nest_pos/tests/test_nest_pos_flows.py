# Copyright (c) 2026, Nest Software Development (nsdLabs) and contributors
# For license information, please see license.txt
"""Integration tests. Run on a disposable test site:

    bench --site test_site set-config allow_tests true
    bench --site test_site run-tests --app nest_pos
"""

import frappe
from frappe.tests import IntegrationTestCase

from nest_pos.kit.shared_flows import CASHIER_A, CASHIER_B, SharedFlows, SharedSetup
from nest_pos.kit.testing import key
from nest_pos.services import baskets


class TestNestPOSSharedFlows(SharedFlows, IntegrationTestCase):
	"""Register, sale, return and security invariants (shared kit) on Nest POS documents."""


class TestNestPOSClientBaskets(SharedSetup, IntegrationTestCase):
	def _basket(self):
		frappe.set_user("Guest")
		start = baskets.start(register=self.register)
		sent = baskets.submit_basket(start["token"], [{"item_code": self.item, "qty": 2}], key("bsk-"))
		return start["token"], sent

	def test_public_view_never_exposes_cost_or_exact_stock(self):
		token, _ = self._basket()
		view = baskets.price_check(token, self.item)
		for secret in ("valuation_rate", "buying_rate", "warehouse", "actual_qty", "supplier"):
			self.assertNotIn(secret, view)
		self.assertIn(view["availability"], ("in_stock", "low", "out", None))

	def test_client_retry_returns_the_same_basket(self):
		frappe.set_user("Guest")
		start = baskets.start(register=self.register)
		k = key("bsk-")
		a = baskets.submit_basket(start["token"], [{"item_code": self.item, "qty": 1}], k)
		b = baskets.submit_basket(start["token"], [{"item_code": self.item, "qty": 1}], k)
		self.assertEqual(a["basket"], b["basket"])

	def test_client_cannot_set_prices(self):
		frappe.set_user("Guest")
		start = baskets.start(register=self.register)
		sent = baskets.submit_basket(start["token"], [{"item_code": self.item, "qty": 1, "rate": 0.01, "price": 0.01}], key("bsk-"))
		self.assertGreater(sent["items"][0]["rate_preview"], 1)

	def test_another_session_cannot_read_a_basket(self):
		_token, sent = self._basket()
		other = baskets.start(register=self.register)
		with self.assertRaises(frappe.DoesNotExistError):
			baskets.status(other["token"], sent["basket"])

	def test_two_claims_one_winner_and_import_exactly_once(self):
		_token, sent = self._basket()
		frappe.set_user(CASHIER_A)
		baskets.claim(sent["basket"])
		frappe.set_user(CASHIER_B)
		with self.assertRaises(frappe.ValidationError):
			baskets.claim(sent["basket"])
		frappe.set_user(CASHIER_A)
		first = baskets.import_into_cart(sent["basket"], "cart-1")
		again = baskets.import_into_cart(sent["basket"], "cart-1")
		self.assertEqual([l["item_code"] for l in first["lines"]], [l["item_code"] for l in again["lines"]])
		with self.assertRaises(frappe.ValidationError):
			baskets.import_into_cart(sent["basket"], "cart-2")
