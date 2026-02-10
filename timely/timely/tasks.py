# Copyright (c) 2026, Digital Consulting Service LLC and contributors
# For license information, please see license.txt

"""Scheduled tasks for Timely integration.

Called by Frappe's scheduler via hooks.py scheduler_events.
"""

import frappe


def daily_attendance_sync():
	"""Daily scheduler task: sync yesterday's attendance from Timely.

	Only runs if Timely Settings is enabled and sync_interval is 'Daily' or 'Hourly'.
	"""
	settings = frappe.get_single("Timely Settings")
	if not settings.enabled:
		return

	if settings.sync_interval == "Manual":
		return

	from timely.timely.sync import run_daily_sync

	frappe.enqueue(
		run_daily_sync,
		queue="long",
		timeout=1800,
		job_name="timely_daily_attendance_sync",
		deduplicate=True,
	)
