# Copyright (c) 2026, Digital Consulting Service LLC and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TimelySettings(Document):
	@frappe.whitelist()
	def test_connection(self):
		"""Test connection to Timely API."""
		from timely.timely.api_client import TimelyClient

		client = TimelyClient()
		try:
			result = client.get_employer_info()
			if result.get("success") == "1":
				company_name = result.get("data", {}).get("name", "Unknown")
				frappe.msgprint(
					f"✅ Connection successful! Company: <b>{company_name}</b>",
					title="Timely Connection Test",
					indicator="green",
				)
			else:
				frappe.msgprint(
					f"❌ API returned error: {result.get('message', 'Unknown error')}",
					title="Timely Connection Test",
					indicator="red",
				)
		except Exception as e:
			frappe.msgprint(
				f"❌ Connection failed: {e!s}",
				title="Timely Connection Test",
				indicator="red",
			)

	@frappe.whitelist()
	def sync_now(self):
		"""Trigger a manual sync for yesterday's attendance."""
		from timely.timely.sync import run_daily_sync

		frappe.enqueue(
			run_daily_sync,
			queue="long",
			timeout=600,
			now=frappe.conf.developer_mode,
		)
		frappe.msgprint(
			"Sync has been queued. Check Timely Sync Log for results.",
			title="Timely Sync",
			indicator="blue",
		)
