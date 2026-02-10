# Copyright (c) 2026, Digital Consulting Service LLC and contributors
# For license information, please see license.txt

"""Post-install setup for Timely app.

Creates custom fields on Employee for Timely integration.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
	"""Create custom fields on Employee doctype."""
	custom_fields = {
		"Employee": [
			{
				"fieldname": "register_number",
				"label": "Register Number",
				"fieldtype": "Data",
				"insert_after": "attendance_device_id",
				"unique": 1,
				"description": "Mongolian national registration number (Регистрийн дугаар)",
				"module": "Timely",
			},
		]
	}

	create_custom_fields(custom_fields, update=True)
	frappe.db.commit()
