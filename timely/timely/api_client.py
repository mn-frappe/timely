# Copyright (c) 2026, Digital Consulting Service LLC and contributors
# For license information, please see license.txt

"""Timely.mn API Client

Handles authentication, token management, and all API calls to Timely.mn.
API docs: https://developer.timely.mn/
"""

import frappe
import requests


class TimelyAPIError(Exception):
	"""Raised when Timely API returns an error response."""

	def __init__(self, message, response=None):
		self.message = message
		self.response = response
		super().__init__(self.message)


class TimelyClient:
	"""Client for Timely.mn REST API v3."""

	TOKEN_CACHE_KEY = "timely_jwt_token"
	TOKEN_TTL = 3600  # 1 hour cache

	def __init__(self):
		self.settings = frappe.get_single("Timely Settings")
		self.base_url = (self.settings.api_url or "https://api.timely.mn").rstrip("/")
		self._token = None

	@property
	def token(self):
		"""Get JWT token, from cache or fresh login."""
		if self._token:
			return self._token

		# Try cache first
		cached = frappe.cache.get_value(self.TOKEN_CACHE_KEY)
		if cached:
			self._token = cached
			return self._token

		# Fresh login
		self._token = self._login()
		frappe.cache.set_value(self.TOKEN_CACHE_KEY, self._token, expires_in_sec=self.TOKEN_TTL)
		return self._token

	def _login(self):
		"""Authenticate with Timely API and return JWT token."""
		url = f"{self.base_url}/v3/login"
		payload = {
			"name": self.settings.username,
			"password": self.settings.get_password("password"),
		}

		response = requests.post(url, json=payload, timeout=30)
		response.raise_for_status()

		data = response.json()
		token = data.get("token") or data.get("access_token") or data.get("data", {}).get("token")

		if not token:
			raise TimelyAPIError("Login succeeded but no token in response", response=data)

		return token

	def _request(self, endpoint, payload=None, retry=True):
		"""Make an authenticated POST request to Timely API.

		Args:
			endpoint: API endpoint path (e.g., '/v3/overview-attd')
			payload: JSON body dict
			retry: If True, retry once on auth failure (token refresh)

		Returns:
			dict: Parsed JSON response
		"""
		url = f"{self.base_url}{endpoint}"
		headers = {
			"Authorization": f"Bearer {self.token}",
			"Content-Type": "application/json",
		}

		response = requests.post(url, json=payload or {}, headers=headers, timeout=60)

		# Handle token expiry — retry once with fresh token
		if response.status_code == 401 and retry:
			frappe.cache.delete_value(self.TOKEN_CACHE_KEY)
			self._token = None
			return self._request(endpoint, payload, retry=False)

		response.raise_for_status()
		data = response.json()

		if data.get("success") == "0":
			raise TimelyAPIError(data.get("message", "Unknown error"), response=data)

		return data

	def get_overview_attd(self, date_from, date_to, div_id="0", page=1, limit=100):
		"""Fetch bulk attendance report for all employees.

		Args:
			date_from: Start date (YYYY-MM-DD)
			date_to: End date (YYYY-MM-DD)
			div_id: Division ID ("0" for all)
			page: Page number
			limit: Records per page

		Returns:
			dict with 'data' (list of employee attendance) and 'pagination'
		"""
		return self._request("/v3/overview-attd", {
			"company_register": self.settings.company_register,
			"div_id": str(div_id),
			"dateFrom": str(date_from),
			"dateTo": str(date_to),
			"page": page,
			"limit": limit,
		})

	def get_all_overview_attd(self, date_from, date_to, div_id="0"):
		"""Fetch all pages of attendance data.

		Yields employee attendance dicts, handling pagination automatically.
		"""
		page = 1
		while True:
			result = self.get_overview_attd(date_from, date_to, div_id, page=page, limit=100)
			data = result.get("data", [])
			if not data:
				break

			yield from data

			pagination = result.get("pagination", {})
			total_pages = pagination.get("totalPages", 1)
			if page >= total_pages:
				break
			page += 1

	def get_employee_attd(self, register, date_from, date_to, phone):
		"""Fetch individual employee attendance.

		Args:
			register: Employee register number (national ID)
			date_from: Start date (YYYY-MM-DD)
			date_to: End date (YYYY-MM-DD)
			phone: Employee phone number

		Returns:
			dict with employee attendance details
		"""
		return self._request("/v3/employee-attd", {
			"company_register": self.settings.company_register,
			"register": register,
			"dateFrom": str(date_from),
			"dateTo": str(date_to),
			"phone": str(phone),
		})

	def get_employee_info(self, tin_number, phone):
		"""Fetch employee personal info.

		Args:
			tin_number: Tax payer number
			phone: Employee phone number

		Returns:
			dict with employee info (name, bank, salary, etc.)
		"""
		return self._request("/v3/employee-info", {
			"company_register": self.settings.company_register,
			"tin_number": str(tin_number),
			"phone": str(phone),
		})

	def get_employer_info(self):
		"""Fetch company info to validate registration.

		Returns:
			dict with company name
		"""
		return self._request("/v3/employer-info", {
			"company_register": self.settings.company_register,
		})

	def invalidate_token(self):
		"""Clear cached JWT token."""
		frappe.cache.delete_value(self.TOKEN_CACHE_KEY)
		self._token = None
