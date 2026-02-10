app_name = "timely"
app_title = "Timely"
app_publisher = "Digital Consulting Service LLC"
app_description = "Timely.mn Time & Attendance integration for ERPNext/HRMS"
app_email = "hello@frappe.mn"
app_license = "agpl-3.0"

# Apps
# ------------------

required_apps = ["frappe", "erpnext", "hrms"]

# Custom Fields
# --------------
# Add register_number to Employee for matching with Timely

fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["module", "=", "Timely"]],
	}
]

# Installation
# ------------

after_install = "timely.timely.install.after_install"

# Testing
# -------

before_tests = "timely.timely.tests.test_utils.before_tests"

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"timely.timely.tasks.daily_attendance_sync",
	],
}

# Log Clearing
# -----------

default_log_clearing_doctypes = {
	"Timely Sync Log": 90,
}

