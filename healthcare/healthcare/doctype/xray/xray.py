# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_link_to_form, getdate, now_datetime

from healthcare.healthcare.doctype.nursing_task.nursing_task import NursingTask


class Xray(Document):
	def validate(self):
		if not self.is_new():
			self.set_secondary_uom_result()

	def on_submit(self):
		from healthcare.healthcare.utils import validate_nursing_tasks

		validate_nursing_tasks(self)
		self.validate_result_values()
		self.db_set("submitted_date", getdate())
		self.db_set("status", "Completed")

	def on_cancel(self):
		self.db_set("status", "Cancelled")
		self.reload()

	def on_update(self):
		if self.sensitivity_test_items:
			sensitivity = sorted(self.sensitivity_test_items, key=lambda x: x.antibiotic_sensitivity)
			for i, item in enumerate(sensitivity):
				item.idx = i + 1
			self.sensitivity_test_items = sensitivity

	



	def load_test_from_template(self):
		xray= self
		create_test_from_template(xray)
		self.reload()

	def set_secondary_uom_result(self):
		for item in self.normal_test_items:
			if item.result_value and item.secondary_uom and item.conversion_factor:
				try:
					item.secondary_uom_result = float(item.result_value) * float(item.conversion_factor)
				except Exception:
					item.secondary_uom_result = ""
					frappe.msgprint(
						_("Row #{0}: Result for Secondary UOM not calculated").format(item.idx), title=_("Warning")
					)

	def validate_result_values(self):
		if self.normal_test_items:
			for item in self.normal_test_items:
				if not item.result_value and not item.allow_blank and item.require_result_value:
					frappe.throw(
						_("Row #{0}: Please enter the result value for {1}").format(
							item.idx, frappe.bold(item.xray_name)
						),
						title=_("Mandatory Results"),
					)

		if self.descriptive_test_items:
			for item in self.descriptive_test_items:
				if not item.result_value and not item.allow_blank and item.require_result_value:
					frappe.throw(
						_("Row #{0}: Please enter the result value for {1}").format(
							item.idx, frappe.bold(item.xray_particulars)
						),
						title=_("Mandatory Results"),
					)


def create_test_from_template(xray):
	template = frappe.get_doc("Template Xray", lab_test.template)
	patient = frappe.get_doc("Patient", xray.patient)

	xray.xray_name = template.xray_name
	xray.result_date = getdate()
	xray.department = template.department
	xray.xray_group = template.lab_test_group
	xray.legend_print_position = template.legend_print_position
	xray.result_legend = template.result_legend
	xray.worksheet_instructions = template.worksheet_instructions

	xray = create_sample_collection(xray, template, patient, None)
	load_result_format(xray, template, None, None)


@frappe.whitelist()
def update_status(status, name):
	if name and status:
		frappe.db.set_value("xray", name, {"status": status, "approved_date": getdate()})


@frappe.whitelist()
def create_multiple(doctype, docname):
	if not doctype or not docname:
		frappe.throw(
			_("Sales Invoice or Patient Encounter is required to create Lab Tests"),
			title=_("Insufficient Data"),
		)

	xray_created = False
	if doctype == "Sales Invoice":
		xray_created = create_xray_from_invoice(docname)
	elif doctype == "Patient Encounter":
		xray_created = create_xray_from_encounter(docname)

	if xray_created:
		frappe.msgprint(
			_("Xray(s) {0} created successfully").format(xray_created), indicator="green"
		)
	else:
		frappe.msgprint(_("No Xray"))


def create_xray_from_encounter(encounter):
	xray_created = False
	encounter = frappe.get_doc("Patient Encounter", encounter)

	if encounter and encounter.xray_prescription:
		patient = frappe.get_doc("Patient", encounter.patient)
		for item in encounter.xray_prescription:
			if not item.xray_created:
				template = get_template_xray(item.xray_code)
				if template:
					xray = create_xray_doc(
						encounter.practitioner, patient, template, encounter.company, item.invoiced
					)
					xray.save(ignore_permissions=True)
					frappe.db.set_value( item.name, "xray_created", 1)
					if not xray_created:
						xray_created = xray.name
					else:
						xray_created += ", " + xray.name
	return xray_created


def create_xray_from_invoice(sales_invoice):
	xrays_created = False
	invoice = frappe.get_doc("Sales Invoice", sales_invoice)
	if invoice and invoice.patient:
		patient = frappe.get_doc("Patient", invoice.patient)
		for item in invoice.items:
			xray_created = 0
		#	if item.reference_dt == "Lab Prescription":
		#		lab_test_created = frappe.db.get_value(
		#			"Lab Prescription", item.reference_dn, "lab_test_created"
		#		)
		#	elif item.reference_dt == "Xray":
		#		xray_created = 1
			if xray_created != 1:
				template = get_xray_template(item.item_code)
				if template:
					xray = create_xray_doc(
						invoice.ref_practitioner, patient, template, invoice.company, True, item.service_unit
					)
			#		if item.reference_dt == "Lab Prescription":
			#			lab_test.prescription = item.reference_dn
					lab_test.save(ignore_permissions=True)
			#		if item.reference_dt != "Lab Prescription":
			#			frappe.db.set_value("Sales Invoice Item", item.name, "reference_dt", "Xray")
			#			frappe.db.set_value("Sales Invoice Item", item.name, "reference_dn", xray.name)
					if not xrays_created:
						xrays_created = xray.name
					else:
						xrays_created += ", " + xray.name
	return xrays_created


def get_template_xray(item):
	template_id = frappe.db.exists("Template Xray", {"item": item})
	if template_id:
		return frappe.get_doc("Template Xray", template_id)
	return False


def create_xray_doc(
	practitioner, patient, template, company, invoiced=False, service_unit=None
):
	xray = frappe.new_doc("Xray")
	xray.invoiced = invoiced
	xray.practitioner = practitioner
	xray.patient = patient.name
	xray.patient_age = patient.get_age()
	xray.patient_sex = patient.sex
	xray.email = patient.email
	xray.mobile = patient.mobile
	xray.report_preference = patient.report_preference
	xray.department = template.department
	xray.template = template.name
	xray.lab_test_group = template.xray_group
	xray.result_date = getdate()
	xray.company = company
	xray.service_unit = service_unit
	return xray















@frappe.whitelist()
def get_employee_by_user_id(user_id):
	emp_id = frappe.db.exists("Employee", {"user_id": user_id})
	if emp_id:
		return frappe.get_doc("Employee", emp_id)
	return None


@frappe.whitelist()
def get_xray_prescribed(patient):
	return frappe.db.sql(
		"""
			select
				lp.name,
				lp.lab_test_code,
				lp.parent,
				lp.invoiced,
				pe.practitioner,
				pe.practitioner_name,
				pe.encounter_date
			from
				`tabPatient Encounter` pe, `tabLab Prescription` lp
			where
				pe.patient=%s
				and lp.parent=pe.name
				and lp.lab_test_created=0
		""",
		(patient),
	)
