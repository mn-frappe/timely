# Copyright (c) 2026, Digital Consulting Service LLC and contributors
# For license information, please see license.txt

"""Tests for Timely API Client and Sync modules.

Uses unittest.mock to test without hitting the real Timely API.
"""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

TEST_COMPANY = "_Test Company"


def _ensure_test_company():
	"""Create _Test Company if it doesn't exist (needed in CI)."""
	if not frappe.db.exists("Company", TEST_COMPANY):
		company = frappe.get_doc({
			"doctype": "Company",
			"company_name": TEST_COMPANY,
			"abbr": "TST",
			"default_currency": "MNT",
			"country": "Mongolia",
		})
		company.insert(ignore_permissions=True)
		frappe.db.commit()


# Sample API responses matching Timely.mn documentation
SAMPLE_LOGIN_RESPONSE = {
	"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-token"
}

SAMPLE_EMPLOYER_INFO = {
	"success": "1",
	"data": {
		"company_name": "Тест ХХК"
	}
}

SAMPLE_OVERVIEW_ATTD = {
	"success": "1",
	"data": [
		{
			"workerId": "1001",
			"workerName": "Бат-Эрдэнэ",
			"register": "УБ90010199",
			"division": "Санхүү",
			"position": "Нягтлан бодогч",
			"attd": {
				"worked_day": 1,
				"absent_day": 0,
				"half_day": 0,
				"remote_day": 0,
				"late_day": 0,
				"leave_day": 0,
				"worked_time": 8.5,
				"vacation_day": 0,
				"sick_day": 0,
				"overtime_regular_time": 1.5,
				"overtime_holiday_time": 0,
				"overtime_night_time": 0,
				"overtime_vacation_time": 0,
				"salary_leave_day": 0,
				"salary_leave_new_child_day": 0,
				"course_day": 0,
			},
			"request": {
				"app_leave_day": 0,
				"overtime_total_time": 1.5,
			},
		},
		{
			"workerId": "1002",
			"workerName": "Одон",
			"register": "УА85061234",
			"division": "ИТ",
			"position": "Программист",
			"attd": {
				"worked_day": 0,
				"absent_day": 1,
				"half_day": 0,
				"remote_day": 0,
				"late_day": 0,
				"leave_day": 0,
				"worked_time": 0,
				"vacation_day": 0,
				"sick_day": 0,
				"overtime_regular_time": 0,
				"overtime_holiday_time": 0,
				"overtime_night_time": 0,
				"overtime_vacation_time": 0,
				"salary_leave_day": 0,
				"salary_leave_new_child_day": 0,
				"course_day": 0,
			},
			"request": {
				"app_leave_day": 0,
				"overtime_total_time": 0,
			},
		},
		{
			"workerId": "1003",
			"workerName": "Сараа",
			"register": "УБ88050512",
			"division": "Санхүү",
			"position": "Менежер",
			"attd": {
				"worked_day": 0,
				"absent_day": 0,
				"half_day": 0,
				"remote_day": 0,
				"late_day": 0,
				"leave_day": 0,
				"worked_time": 0,
				"vacation_day": 1,
				"sick_day": 0,
				"overtime_regular_time": 0,
				"overtime_holiday_time": 0,
				"overtime_night_time": 0,
				"overtime_vacation_time": 0,
				"salary_leave_day": 0,
				"salary_leave_new_child_day": 0,
				"course_day": 0,
			},
			"request": {
				"app_leave_day": 0,
				"overtime_total_time": 0,
			},
		},
	],
	"pagination": {
		"page": 1,
		"totalPages": 1,
		"totalRecords": 3,
	},
}

SAMPLE_OVERVIEW_ATTD_EMPTY = {
	"success": "1",
	"data": [],
	"pagination": {
		"page": 1,
		"totalPages": 0,
		"totalRecords": 0,
	},
}

SAMPLE_LATE_WORKER = {
	"workerId": "1004",
	"workerName": "Ганаа",
	"register": "УО92030303",
	"division": "Борлуулалт",
	"position": "Борлуулагч",
	"attd": {
		"worked_day": 1,
		"absent_day": 0,
		"half_day": 0,
		"remote_day": 0,
		"late_day": 1,
		"leave_day": 1,
		"worked_time": 6.0,
		"vacation_day": 0,
		"sick_day": 0,
		"overtime_regular_time": 0,
		"overtime_holiday_time": 0,
		"overtime_night_time": 0,
		"overtime_vacation_time": 0,
		"salary_leave_day": 0,
		"salary_leave_new_child_day": 0,
		"course_day": 0,
	},
	"request": {
		"app_leave_day": 0,
		"overtime_total_time": 0,
	},
}


class TestTimelyClient(IntegrationTestCase):
	"""Test TimelyClient API methods with mocked HTTP."""

	@patch("timely.timely.api_client.requests.post")
	def test_login(self, mock_post):
		"""Test JWT login returns token."""
		mock_response = MagicMock()
		mock_response.json.return_value = SAMPLE_LOGIN_RESPONSE
		mock_response.raise_for_status = MagicMock()
		mock_post.return_value = mock_response

		from timely.timely.api_client import TimelyClient

		with patch.object(TimelyClient, "__init__", lambda self: None):
			client = TimelyClient()
			client.base_url = "https://api.timely.mn"
			client._token = None
			client.settings = MagicMock()
			client.settings.username = "testuser"
			client.settings.get_password.return_value = "testpass"

			token = client._login()
			self.assertEqual(token, SAMPLE_LOGIN_RESPONSE["token"])

	@patch("timely.timely.api_client.requests.post")
	def test_get_employer_info(self, mock_post):
		"""Test employer info endpoint."""
		# Login response
		login_resp = MagicMock()
		login_resp.json.return_value = SAMPLE_LOGIN_RESPONSE
		login_resp.raise_for_status = MagicMock()

		# Employer info response
		info_resp = MagicMock()
		info_resp.json.return_value = SAMPLE_EMPLOYER_INFO
		info_resp.raise_for_status = MagicMock()
		info_resp.status_code = 200

		mock_post.side_effect = [login_resp, info_resp]

		from timely.timely.api_client import TimelyClient

		with patch.object(TimelyClient, "__init__", lambda self: None):
			client = TimelyClient()
			client.base_url = "https://api.timely.mn"
			client._token = None
			client.settings = MagicMock()
			client.settings.username = "testuser"
			client.settings.get_password.return_value = "testpass"
			client.settings.company_register = "1234567"

			# Clear cache
			frappe.cache.delete_value("timely_jwt_token")

			result = client.get_employer_info()
			self.assertEqual(result["success"], "1")

	@patch("timely.timely.api_client.requests.post")
	def test_get_all_overview_attd_pagination(self, mock_post):
		"""Test paginated overview attendance fetches all pages."""
		# Already have token
		page1 = MagicMock()
		page1.json.return_value = {
			"success": "1",
			"data": [{"workerId": "1"}, {"workerId": "2"}],
			"pagination": {"page": 1, "totalPages": 2, "totalRecords": 3},
		}
		page1.raise_for_status = MagicMock()
		page1.status_code = 200

		page2 = MagicMock()
		page2.json.return_value = {
			"success": "1",
			"data": [{"workerId": "3"}],
			"pagination": {"page": 2, "totalPages": 2, "totalRecords": 3},
		}
		page2.raise_for_status = MagicMock()
		page2.status_code = 200

		mock_post.side_effect = [page1, page2]

		from timely.timely.api_client import TimelyClient

		with patch.object(TimelyClient, "__init__", lambda self: None):
			client = TimelyClient()
			client.base_url = "https://api.timely.mn"
			client._token = "existing-token"
			client.settings = MagicMock()
			client.settings.company_register = "1234567"

			records = list(client.get_all_overview_attd("2025-01-01", "2025-01-01"))
			self.assertEqual(len(records), 3)
			self.assertEqual(records[2]["workerId"], "3")


class TestAttendanceSync(IntegrationTestCase):
	"""Test attendance sync logic."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure_test_company()

	def _get_company(self):
		return frappe.db.get_single_value("Global Defaults", "default_company") or TEST_COMPANY

	def test_sync_attendance_present(self):
		"""Test present employee creates Present attendance."""
		from timely.timely.sync import _sync_attendance

		# Create a test employee
		if frappe.db.exists("Employee", {"employee_name": "Test Timely Worker"}):
			emp = frappe.get_doc("Employee", {"employee_name": "Test Timely Worker"})
		else:
			emp = frappe.get_doc({
				"doctype": "Employee",
				"first_name": "Test Timely Worker",
				"company": self._get_company(),
				"status": "Active",
			})
			emp.insert(ignore_permissions=True)

		target_date = "2099-01-15"
		attd = {
			"worked_day": 1,
			"absent_day": 0,
			"half_day": 0,
			"remote_day": 0,
			"late_day": 0,
			"leave_day": 0,
			"worked_time": 8.0,
			"vacation_day": 0,
			"sick_day": 0,
		}
		request_data = {"app_leave_day": 0}
		settings = MagicMock()
		settings.default_shift = None

		result = _sync_attendance(emp.name, target_date, attd, request_data, settings)
		self.assertEqual(result, "created")

		# Verify attendance was created
		att = frappe.get_value(
			"Attendance",
			{"employee": emp.name, "attendance_date": target_date},
			["status", "working_hours"],
			as_dict=True,
		)
		self.assertIsNotNone(att)
		self.assertEqual(att.status, "Present")
		self.assertEqual(att.working_hours, 8.0)

		# Cleanup
		att_name = frappe.get_value("Attendance", {"employee": emp.name, "attendance_date": target_date})
		if att_name:
			frappe.get_doc("Attendance", att_name).cancel()
			frappe.delete_doc("Attendance", att_name, force=True)

	def test_sync_attendance_absent(self):
		"""Test absent employee creates Absent attendance."""
		from timely.timely.sync import _sync_attendance

		if frappe.db.exists("Employee", {"employee_name": "Test Timely Worker2"}):
			emp = frappe.get_doc("Employee", {"employee_name": "Test Timely Worker2"})
		else:
			emp = frappe.get_doc({
				"doctype": "Employee",
				"first_name": "Test Timely Worker2",
				"company": self._get_company(),
				"status": "Active",
			})
			emp.insert(ignore_permissions=True)

		target_date = "2099-02-15"
		attd = {
			"worked_day": 0,
			"absent_day": 1,
			"half_day": 0,
			"remote_day": 0,
			"late_day": 0,
			"leave_day": 0,
			"worked_time": 0,
			"vacation_day": 0,
			"sick_day": 0,
		}
		request_data = {"app_leave_day": 0}
		settings = MagicMock()
		settings.default_shift = None

		result = _sync_attendance(emp.name, target_date, attd, request_data, settings)
		self.assertEqual(result, "created")

		att = frappe.get_value(
			"Attendance",
			{"employee": emp.name, "attendance_date": target_date},
			["status"],
			as_dict=True,
		)
		self.assertEqual(att.status, "Absent")

		# Cleanup
		att_name = frappe.get_value("Attendance", {"employee": emp.name, "attendance_date": target_date})
		if att_name:
			frappe.get_doc("Attendance", att_name).cancel()
			frappe.delete_doc("Attendance", att_name, force=True)

	def test_sync_attendance_on_leave_skips(self):
		"""Test that vacation/sick day returns on_leave (no attendance created)."""
		from timely.timely.sync import _sync_attendance

		settings = MagicMock()
		settings.default_shift = None

		attd = {
			"worked_day": 0,
			"absent_day": 0,
			"half_day": 0,
			"remote_day": 0,
			"late_day": 0,
			"leave_day": 0,
			"worked_time": 0,
			"vacation_day": 1,
			"sick_day": 0,
		}
		request_data = {"app_leave_day": 0}

		result = _sync_attendance("HR-EMP-00001", "2099-03-15", attd, request_data, settings)
		self.assertEqual(result, "on_leave")

	def test_sync_attendance_duplicate_skips(self):
		"""Test that duplicate sync returns 'exists'."""
		from timely.timely.sync import _sync_attendance

		if frappe.db.exists("Employee", {"employee_name": "Test Timely Dup"}):
			emp = frappe.get_doc("Employee", {"employee_name": "Test Timely Dup"})
		else:
			emp = frappe.get_doc({
				"doctype": "Employee",
				"first_name": "Test Timely Dup",
				"company": self._get_company(),
				"status": "Active",
			})
			emp.insert(ignore_permissions=True)

		target_date = "2099-04-15"
		attd = {
			"worked_day": 1, "absent_day": 0, "half_day": 0,
			"remote_day": 0, "late_day": 0, "leave_day": 0,
			"worked_time": 8.0, "vacation_day": 0, "sick_day": 0,
		}
		request_data = {"app_leave_day": 0}
		settings = MagicMock()
		settings.default_shift = None

		# First sync
		result1 = _sync_attendance(emp.name, target_date, attd, request_data, settings)
		self.assertEqual(result1, "created")

		# Second sync — should skip
		result2 = _sync_attendance(emp.name, target_date, attd, request_data, settings)
		self.assertEqual(result2, "exists")

		# Cleanup
		att_name = frappe.get_value("Attendance", {"employee": emp.name, "attendance_date": target_date})
		if att_name:
			frappe.get_doc("Attendance", att_name).cancel()
			frappe.delete_doc("Attendance", att_name, force=True)

	def test_sync_attendance_late_entry(self):
		"""Test late_day sets late_entry flag."""
		from timely.timely.sync import _sync_attendance

		if frappe.db.exists("Employee", {"employee_name": "Test Timely Late"}):
			emp = frappe.get_doc("Employee", {"employee_name": "Test Timely Late"})
		else:
			emp = frappe.get_doc({
				"doctype": "Employee",
				"first_name": "Test Timely Late",
				"company": self._get_company(),
				"status": "Active",
			})
			emp.insert(ignore_permissions=True)

		target_date = "2099-05-15"
		attd = {
			"worked_day": 1, "absent_day": 0, "half_day": 0,
			"remote_day": 0, "late_day": 1, "leave_day": 1,
			"worked_time": 6.0, "vacation_day": 0, "sick_day": 0,
		}
		request_data = {"app_leave_day": 0}
		settings = MagicMock()
		settings.default_shift = None

		result = _sync_attendance(emp.name, target_date, attd, request_data, settings)
		self.assertEqual(result, "created")

		att = frappe.get_value(
			"Attendance",
			{"employee": emp.name, "attendance_date": target_date},
			["late_entry", "early_exit"],
			as_dict=True,
		)
		self.assertEqual(att.late_entry, 1)
		self.assertEqual(att.early_exit, 1)

		# Cleanup
		att_name = frappe.get_value("Attendance", {"employee": emp.name, "attendance_date": target_date})
		if att_name:
			frappe.get_doc("Attendance", att_name).cancel()
			frappe.delete_doc("Attendance", att_name, force=True)


class TestEmployeeMapping(IntegrationTestCase):
	"""Test employee resolution logic."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure_test_company()

	def test_resolve_by_attendance_device_id(self):
		"""Test matching via attendance_device_id."""
		from timely.timely.sync import _resolve_employee

		if frappe.db.exists("Employee", {"employee_name": "Test Timely DevID"}):
			emp = frappe.get_doc("Employee", {"employee_name": "Test Timely DevID"})
		else:
			emp = frappe.get_doc({
				"doctype": "Employee",
				"first_name": "Test Timely DevID",
				"company": frappe.db.get_single_value("Global Defaults", "default_company") or TEST_COMPANY,
				"status": "Active",
				"attendance_device_id": "TM-9999",
			})
			emp.insert(ignore_permissions=True)

		settings = MagicMock()
		settings.auto_create_employee = False
		record = {"division": "ИТ", "position": "Dev"}

		result = _resolve_employee("TM-9999", "Test Worker", "УА00000000", record, settings)
		self.assertEqual(result, emp.name)

		# Cleanup mapping if created
		if frappe.db.exists("Timely Employee Map", {"timely_worker_id": "TM-9999"}):
			frappe.delete_doc("Timely Employee Map", {"timely_worker_id": "TM-9999"}, force=True)

	def test_unmapped_employee_creates_map(self):
		"""Test unmapped worker creates Unmapped map entry."""
		from timely.timely.sync import _resolve_employee

		settings = MagicMock()
		settings.auto_create_employee = False
		record = {"division": "HR", "position": "Manager"}

		# Use a worker ID that definitely doesn't exist
		result = _resolve_employee("TM-NONEXIST-001", "Ghost Worker", "", record, settings)
		self.assertIsNone(result)

		# Should have created an unmapped entry
		exists = frappe.db.exists("Timely Employee Map", {"timely_worker_id": "TM-NONEXIST-001"})
		self.assertTrue(exists)

		# Cleanup
		if exists:
			frappe.delete_doc("Timely Employee Map", exists, force=True)


class TestOvertimeSync(IntegrationTestCase):
	"""Test overtime extraction logic."""

	def test_extract_overtime(self):
		"""Test overtime hours extraction from attd data."""
		from timely.timely.overtime import _extract_overtime

		settings = MagicMock()
		settings.regular_overtime_type = "OT-Regular"
		settings.holiday_overtime_type = "OT-Holiday"
		settings.night_overtime_type = None  # not configured
		settings.weekend_overtime_type = None

		attd = {
			"overtime_regular_time": 2.5,
			"overtime_holiday_time": 4.0,
			"overtime_night_time": 0,
			"overtime_vacation_time": 0,
		}
		request_data = {"overtime_total_time": 6.5}

		entries = _extract_overtime(attd, request_data, settings)
		self.assertEqual(len(entries), 2)
		self.assertEqual(entries[0]["hours"], 2.5)
		self.assertEqual(entries[0]["overtime_type"], "OT-Regular")
		self.assertEqual(entries[1]["hours"], 4.0)

	def test_no_overtime(self):
		"""Test no overtime returns empty list."""
		from timely.timely.overtime import _extract_overtime

		settings = MagicMock()
		settings.regular_overtime_type = "OT-Regular"
		settings.holiday_overtime_type = None
		settings.night_overtime_type = None
		settings.weekend_overtime_type = None

		attd = {
			"overtime_regular_time": 0,
			"overtime_holiday_time": 0,
			"overtime_night_time": 0,
			"overtime_vacation_time": 0,
		}
		request_data = {"overtime_total_time": 0}

		entries = _extract_overtime(attd, request_data, settings)
		self.assertEqual(len(entries), 0)
