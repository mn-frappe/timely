# Copyright (c) 2026, Digital Consulting Service LLC and contributors
# For license information, please see license.txt

"""Timely → HRMS Daily Attendance Sync

Approach B: Query Timely for single-day attendance and create/update
HRMS Attendance records using built-in HRMS APIs.
"""

import frappe
from frappe.utils import add_days, getdate, now_datetime, today


def run_daily_sync(target_date=None):
	"""Run a full daily sync: attendance + leave + overtime.

	Args:
		target_date: Date to sync (default: yesterday)
	"""
	settings = frappe.get_single("Timely Settings")
	if not settings.enabled:
		return

	if not target_date:
		target_date = add_days(today(), -1)

	target_date = str(getdate(target_date))

	log = frappe.new_doc("Timely Sync Log")
	log.sync_type = "Full Sync"
	log.status = "In Progress"
	log.date_from = target_date
	log.date_to = target_date
	log.insert(ignore_permissions=True)
	frappe.db.commit()

	try:
		from timely.timely.api_client import TimelyClient

		client = TimelyClient()
		records = list(client.get_all_overview_attd(target_date, target_date))

		log.total_records = len(records)
		synced = 0
		skipped = 0
		errors = 0
		new_employees = 0
		details = []
		error_log = []

		for record in records:
			try:
				worker_id = str(record.get("workerId"))
				worker_name = record.get("workerName", "Unknown")
				register = record.get("register", "")

				# Resolve employee mapping
				employee = _resolve_employee(worker_id, worker_name, register, record, settings)

				if not employee:
					skipped += 1
					details.append(f"SKIP: {worker_name} (ID:{worker_id}) - No employee mapping")
					continue

				# Check if this is a new mapping
				mapping = frappe.db.get_value(
					"Timely Employee Map",
					{"timely_worker_id": worker_id},
					"name",
				)
				if not mapping:
					new_employees += 1

				# Sync attendance
				attd = record.get("attd", {})
				request_data = record.get("request", {})
				result = _sync_attendance(employee, target_date, attd, request_data, settings)

				if result == "created":
					synced += 1
					details.append(f"OK: {worker_name} → {employee}")
				elif result == "exists":
					skipped += 1
					details.append(f"SKIP: {worker_name} → {employee} (already marked)")
				else:
					skipped += 1
					details.append(f"SKIP: {worker_name} → {employee} ({result})")

				# Sync leave (if any leave days in the period)
				_sync_leave(employee, target_date, attd, request_data, settings)

			except Exception as e:
				errors += 1
				error_log.append(f"ERROR [{worker_name} ID:{worker_id}]: {e!s}")
				frappe.log_error(
					title=f"Timely Sync Error: {worker_name}",
					message=frappe.get_traceback(),
				)

		log.synced = synced
		log.skipped = skipped
		log.errors = errors
		log.new_employees = new_employees
		log.status = "Completed" if errors == 0 else "Completed"
		log.details = "\n".join(details)
		log.error_log = "\n".join(error_log) if error_log else ""

		# Update last_sync timestamp
		settings.last_sync = now_datetime()
		settings.save(ignore_permissions=True)

	except Exception as e:
		log.status = "Failed"
		log.error_log = f"Fatal error: {e!s}\n\n{frappe.get_traceback()}"
		frappe.log_error(title="Timely Sync Fatal Error", message=frappe.get_traceback())

	log.save(ignore_permissions=True)
	frappe.db.commit()
	return log.name


def _resolve_employee(worker_id, worker_name, register, record, settings):
	"""Resolve Timely worker to HRMS Employee.

	Matching priority:
	1. Existing Timely Employee Map by worker_id
	2. Employee.attendance_device_id matching worker_id
	3. Custom field register_number matching register
	4. Auto-create if enabled

	Returns Employee ID or None.
	"""
	# 1. Check existing mapping
	mapping = frappe.db.get_value(
		"Timely Employee Map",
		{"timely_worker_id": worker_id},
		["employee", "sync_status"],
		as_dict=True,
	)
	if mapping and mapping.employee:
		return mapping.employee

	# 2. Match by attendance_device_id
	employee = frappe.db.get_value("Employee", {"attendance_device_id": worker_id, "status": "Active"})
	if employee:
		_create_or_update_map(worker_id, employee, register, record)
		return employee

	# 3. Match by register number (if custom field exists)
	if register:
		try:
			employee = frappe.db.get_value(
				"Employee",
				{"register_number": register, "status": "Active"},
			)
			if employee:
				_create_or_update_map(worker_id, employee, register, record)
				# Also set the attendance_device_id for future matching
				frappe.db.set_value("Employee", employee, "attendance_device_id", worker_id)
				return employee
		except Exception:
			# register_number custom field may not exist yet
			pass

	# 4. Auto-create employee if configured
	if settings.auto_create_employee:
		employee = _auto_create_employee(worker_id, worker_name, register, record, settings)
		if employee:
			_create_or_update_map(worker_id, employee, register, record)
			return employee

	# Create unmapped entry for manual resolution
	if not mapping:
		_create_or_update_map(worker_id, None, register, record, status="Unmapped")

	return None


def _create_or_update_map(worker_id, employee, register, record, status=None):
	"""Create or update a Timely Employee Map record."""
	existing = frappe.db.get_value("Timely Employee Map", {"timely_worker_id": worker_id})

	if existing:
		doc = frappe.get_doc("Timely Employee Map", existing)
	else:
		doc = frappe.new_doc("Timely Employee Map")
		doc.timely_worker_id = worker_id

	if employee:
		doc.employee = employee
	doc.register_number = register or doc.register_number
	doc.timely_division = record.get("division", "")
	doc.timely_position = record.get("position", "")
	doc.last_synced = now_datetime()
	doc.sync_status = status or ("Mapped" if employee else "Unmapped")
	doc.save(ignore_permissions=True)


def _auto_create_employee(worker_id, worker_name, register, record, settings):
	"""Auto-create an Employee record from Timely data."""
	try:
		emp = frappe.new_doc("Employee")
		emp.first_name = worker_name
		emp.company = settings.company
		emp.attendance_device_id = worker_id
		emp.status = "Active"

		# Try to set department from Timely division
		division = record.get("division", "")
		if division:
			dept = frappe.db.get_value("Department", {"department_name": division, "company": settings.company})
			if dept:
				emp.department = dept

		# Try to set designation from Timely position
		position = record.get("position", "")
		if position:
			designation = frappe.db.get_value("Designation", {"name": position})
			if designation:
				emp.designation = designation

		emp.insert(ignore_permissions=True)
		frappe.db.commit()
		return emp.name
	except Exception as e:
		frappe.log_error(
			title=f"Timely Auto-Create Employee Failed: {worker_name}",
			message=frappe.get_traceback(),
		)
		return None


def _sync_attendance(employee, target_date, attd, request_data, settings):
	"""Create HRMS Attendance record from Timely data.

	Returns: 'created', 'exists', or reason string
	"""
	# Check if attendance already exists for this employee + date
	existing = frappe.db.get_value(
		"Attendance",
		{"employee": employee, "attendance_date": target_date, "docstatus": ["!=", 2]},
	)
	if existing:
		return "exists"

	# Determine attendance status from Timely data
	worked_day = attd.get("worked_day", 0) or 0
	absent_day = attd.get("absent_day", 0) or 0
	half_day = attd.get("half_day", 0) or 0
	remote_day = attd.get("remote_day", 0) or 0
	late_day = attd.get("late_day", 0) or 0
	leave_day = attd.get("leave_day", 0) or 0  # early departure
	worked_time = attd.get("worked_time", 0) or 0

	# Leave-related days from request data
	app_leave_day = request_data.get("app_leave_day", 0) or 0
	vacation_day = attd.get("vacation_day", 0) or 0
	sick_day = attd.get("sick_day", 0) or 0

	# Determine status
	if vacation_day > 0 or sick_day > 0 or app_leave_day > 0:
		# On leave — leave application will handle attendance
		return "on_leave"
	elif absent_day > 0 and worked_day == 0:
		status = "Absent"
	elif half_day > 0:
		status = "Half Day"
	elif remote_day > 0:
		status = "Work From Home"
	elif worked_day > 0:
		status = "Present"
	else:
		# No data — likely a rest day or holiday
		return "no_data"

	# Create attendance
	try:
		attendance = frappe.new_doc("Attendance")
		attendance.employee = employee
		attendance.attendance_date = target_date
		attendance.status = status
		attendance.working_hours = worked_time
		attendance.late_entry = 1 if late_day > 0 else 0
		attendance.early_exit = 1 if leave_day > 0 else 0

		if settings.default_shift:
			attendance.shift = settings.default_shift

		if status == "Half Day":
			attendance.half_day_status = "Absent"

		attendance.insert(ignore_permissions=True)
		attendance.submit()
		return "created"
	except frappe.exceptions.DuplicateEntryError:
		return "exists"
	except Exception as e:
		raise


def _sync_leave(employee, target_date, attd, request_data, settings):
	"""Create Leave Application from Timely leave data.

	Only creates if a matching Leave Type is configured in settings.
	"""
	leave_mappings = [
		("vacation_day", settings.annual_leave_type),
		("sick_day", settings.sick_leave_type),
		("app_leave_day", None),  # app_leave is in request_data, not attd
		("salary_leave_day", settings.paid_leave_type),
		("salary_leave_new_child_day", settings.parental_leave_type),
		("course_day", settings.training_leave_type),
	]

	for field, leave_type in leave_mappings:
		if not leave_type:
			continue

		# app_leave_day comes from request_data, others from attd
		if field == "app_leave_day":
			days = request_data.get("app_leave_day", 0) or 0
			if not settings.personal_leave_type:
				continue
			leave_type = settings.personal_leave_type
		else:
			days = attd.get(field, 0) or 0

		if days <= 0:
			continue

		# Check if leave application already exists
		existing = frappe.db.get_value(
			"Leave Application",
			{
				"employee": employee,
				"from_date": target_date,
				"to_date": target_date,
				"leave_type": leave_type,
				"docstatus": ["!=", 2],
			},
		)
		if existing:
			continue

		try:
			leave_app = frappe.new_doc("Leave Application")
			leave_app.employee = employee
			leave_app.leave_type = leave_type
			leave_app.from_date = target_date
			leave_app.to_date = target_date
			leave_app.total_leave_days = 1
			leave_app.status = "Approved"
			leave_app.leave_approver = frappe.db.get_value(
				"Employee", employee, "leave_approver"
			) or frappe.session.user
			leave_app.posting_date = target_date
			leave_app.description = f"Auto-synced from Timely ({field})"
			leave_app.insert(ignore_permissions=True)
			leave_app.submit()
		except Exception as e:
			frappe.log_error(
				title=f"Timely Leave Sync Error: {employee}",
				message=f"Leave type: {leave_type}\nField: {field}\n\n{frappe.get_traceback()}",
			)
