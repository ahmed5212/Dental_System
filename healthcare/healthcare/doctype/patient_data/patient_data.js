// Copyright (c) 2023, healthcare and contributors
// For license information, please see license.txt

frappe.ui.form.on('Patient data', {
	refresh: function(frm) {
        frm.add_custom_button('التحاليل', () => {
            frappe.new_doc('Laboratory', {
                patient_data: frm.doc.name
            })
        })
        frm.add_custom_button('التحاليل', () => {
            frappe.new_doc('Laboratory', {
				patient_data: frm.doc.name
            })
        })
    }
});
