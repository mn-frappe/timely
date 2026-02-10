// Copyright (c) 2026, Digital Consulting Service LLC and contributors
// For license information, please see license.txt

frappe.ui.form.on("Timely Settings", {
	refresh(frm) {
		frm.trigger("set_button_handlers");
	},

	set_button_handlers(frm) {
		frm.fields_dict.test_connection.$input?.off("click").on("click", () => {
			frappe.call({
				method: "test_connection",
				doc: frm.doc,
				freeze: true,
				freeze_message: __("Testing connection..."),
			});
		});

		frm.fields_dict.sync_now.$input?.off("click").on("click", () => {
			frappe.confirm(
				__("This will sync yesterday's attendance data from Timely. Continue?"),
				() => {
					frappe.call({
						method: "sync_now",
						doc: frm.doc,
						freeze: true,
						freeze_message: __("Queuing sync..."),
					});
				}
			);
		});
	},
});
