# Copyright (c) 2026, Digital Consulting Service LLC and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime


def before_tests():
	"""Set up test environment: run setup wizard to create _Test Company with all
	required ERPNext fixtures (Warehouse Types, Chart of Accounts, etc.)."""
	frappe.clear_cache()
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	year = now_datetime().year
	if not frappe.get_list("Company"):
		setup_complete(
			{
				"currency": "MNT",
				"full_name": "Test User",
				"company_name": "_Test Company",
				"timezone": "Asia/Ulaanbaatar",
				"company_abbr": "TST",
				"industry": "Services",
				"country": "Mongolia",
				"fy_start_date": f"{year}-01-01",
				"fy_end_date": f"{year}-12-31",
				"language": "english",
				"company_tagline": "Testing",
				"email": "test@timely.mn",
				"password": "test",
				"chart_of_accounts": "Standard",
			}
		)

	frappe.db.commit()
