# Copyright (c) 2026, Digital Consulting Service LLC and contributors
# For license information, please see license.txt

"""Timely Overtime Sync

Syncs overtime hours from Timely into HRMS Overtime Slips.
Designed to run monthly (at end of payroll period).
"""

import frappe
from frappe.utils import getdate, now_datetime


def sync_overtime(date_from, date_to):
	"""Sync overtime data from Timely for a date range.

	Creates Overtime Slip records in HRMS for each employee with overtime hours.

	Args:
		date_from: Period start (YYYY-MM-DD)
		date_to: Period end (YYYY-MM-DD)
	"""
	settings = frappe.get_single("Timely Settings")
	if not settings.enabled:
		return

	log = frappe.new_doc("Timely Sync Log")
	log.sync_type = "Overtime"
	log.status = "In Progress"
	log.date_from = date_from
	log.date_to = date_to
	log.insert(ignore_permissions=True)
	frappe.db.commit()

	try:
		from timely.timely.api_client import TimelyClient

		client = TimelyClient()
		records = list(client.get_all_overview_attd(date_from, date_to))

		log.total_records = len(records)
		synced = 0
		skipped = 0
		errors = 0
		details = []
		error_log = []

		for record in records:
			try:
				worker_id = str(record.get("workerId"))
				worker_name = record.get("workerName", "Unknown")

				# Get employee mapping
				employee = frappe.db.get_value(
					"Timely Employee Map",
					{"timely_worker_id": worker_id},
					"employee",
				)
				if not employee:
					skipped += 1
					continue

				attd = record.get("attd", {})
				request_data = record.get("request", {})

				# Aggregate overtime hours
				overtime_entries = _extract_overtime(attd, request_data, settings)

				if not overtime_entries:
					skipped += 1
					continue

				created = _create_overtime_slip(employee, date_from, date_to, overtime_entries, settings)
				if created:
					synced += 1
					details.append(f"OK: {worker_name} → {employee} ({sum(e['hours'] for e in overtime_entries):.1f}h)")
				else:
					skipped += 1
					details.append(f"SKIP: {worker_name} → {employee} (already exists)")

			except Exception as e:
				errors += 1
				error_log.append(f"ERROR [{worker_name}]: {e!s}")
				frappe.log_error(
					title=f"Timely Overtime Error: {worker_name}",
					message=frappe.get_traceback(),
				)

		log.synced = synced
		log.skipped = skipped
		log.errors = errors
		log.status = "Completed"
		log.details = "\n".join(details)
		log.error_log = "\n".join(error_log) if error_log else ""

	except Exception as e:
		log.status = "Failed"
		log.error_log = f"Fatal error: {e!s}\n\n{frappe.get_traceback()}"

	log.save(ignore_permissions=True)
	frappe.db.commit()
	return log.name


def _extract_overtime(attd, request_data, settings):
	"""Extract overtime hours from Timely attendance data.

	Returns list of dicts: [{'type': 'Regular', 'hours': 5.0, 'overtime_type': 'OT-001'}, ...]
	"""
	overtime_map = [
		("overtime_regular_time", "Regular", settings.regular_overtime_type),
		("overtime_holiday_time", "Holiday", settings.holiday_overtime_type),
		("overtime_night_time", "Night", settings.night_overtime_type),
		("overtime_vacation_time", "Weekend", settings.weekend_overtime_type),
	]

	# Also check request data for overtime totals
	request_overtime = request_data.get("overtime_total_time", 0) or 0

	entries = []
	for field, label, overtime_type in overtime_map:
		hours = attd.get(field, 0) or 0
		if hours > 0 and overtime_type:
			entries.append({
				"type": label,
				"hours": hours,
				"overtime_type": overtime_type,
			})

	return entries


def _create_overtime_slip(employee, date_from, date_to, overtime_entries, settings):
	"""Create an HRMS Overtime Slip for the employee.

	Returns True if created, False if already exists.
	"""
	# Check for existing overtime slip in the same period
	existing = frappe.db.get_value(
		"Overtime Slip",
		{
			"employee": employee,
			"start_date": date_from,
			"end_date": date_to,
			"docstatus": ["!=", 2],
		},
	)
	if existing:
		return False

	try:
		slip = frappe.new_doc("Overtime Slip")
		slip.employee = employee
		slip.posting_date = date_to
		slip.start_date = date_from
		slip.end_date = date_to
		slip.company = settings.company

		# Use the first overtime type found (primary)
		primary = overtime_entries[0]
		slip.overtime_type = primary["overtime_type"]

		# Add overtime detail rows
		for entry in overtime_entries:
			slip.append("overtime_details", {
				"date": date_to,
				"overtime_type": entry["overtime_type"],
				"overtime_duration": entry["hours"],
			})

		slip.insert(ignore_permissions=True)
		return True

	except Exception as e:
		frappe.log_error(
			title=f"Timely Overtime Slip Error: {employee}",
			message=frappe.get_traceback(),
		)
		return False
