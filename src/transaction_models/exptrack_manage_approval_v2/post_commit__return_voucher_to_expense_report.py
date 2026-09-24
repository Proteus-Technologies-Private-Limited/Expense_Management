# project: Expense_Management
# object_type: T
# object_name: exptrack_manage_approval_v2
# event_type: post_commit
# function_name: return_voucher_to_expense_report
# language: python
# description: Return a rejected voucher to the Expense Report transaction
# functional_specification: Fires after commit of this transaction (Manage Approval, header form EXPTRACK_EXPENSE, action 'Submit' / system_op 'save'). If the just-saved header EXPTRACK_EXPENSE.STATUS is not exactly 'Reject', return without doing anything. Otherwise upsert a row into EXPTRACK_EXPENSE_REPORT_NEW keyed on EXPENSE_ID = header EXPENSE_ID (update the existing row if one already has that EXPENSE_ID, otherwise insert a new row with RECORD_ID = auto-generated). Populate the row from the header's own real column values only: EXPENSE_ID, EMPLOYEE, CATEGORY, EXPENSE_DATE, PAYMENT_METHOD, APPROVER_NAME (from header APPROVER), RECEIPT_ATTACHMENT; TRIP/TRIP_NAME are resolved via EXPTRACK_EXPENSE_REPORT (matched by REPORT_ID = header EXPENSE_REPORT) then EXPTRACK_TRIP (matched by TRIP_ID = that TRIP value), left blank if header EXPENSE_REPORT is null. This is a side-effect update only; do not block or roll back the save on failure, but log/report any error encountered.
# business_logic: Return a rejected voucher to the Expense Report transaction


def run(args):
    header = args.get('header') or {}

    def hval(name):
        for key in (name, name.lower(), name.upper()):
            if key in header:
                return header.get(key)
        return None

    # Only a rejected voucher goes back to the Expense Report transaction.
    status = hval('STATUS')
    if is_empty(status) or str(status).strip() != 'Reject':
        return None

    expense_id = hval('EXPENSE_ID')
    if is_empty(expense_id) or not str(expense_id).strip():
        return None
    expense_id = str(expense_id).strip()

    try:
        employee = hval('EMPLOYEE')
        category = hval('CATEGORY')
        expense_date = hval('EXPENSE_DATE')
        payment_method = hval('PAYMENT_METHOD')
        approver = hval('APPROVER')
        receipt_attachment = hval('RECEIPT_ATTACHMENT')
        report_id = hval('EXPENSE_REPORT')

        trip = None
        trip_name = None
        total_amount = None
        if not_empty(report_id) and str(report_id).strip():
            report_id = str(report_id).strip()
            rep = db.query_one(
                'SELECT TRIP, TOTAL_AMOUNT FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
                ' WHERE REPORT_ID = :rid',
                {'rid': report_id}
            )
            if rep:
                trip = rep.get('TRIP') if 'TRIP' in rep else rep.get('trip')
                total_amount = (rep.get('TOTAL_AMOUNT')
                                 if 'TOTAL_AMOUNT' in rep
                                 else rep.get('total_amount'))
                if not_empty(trip):
                    trip = str(trip).strip()
                    trip_row = db.query_one(
                        'SELECT TRIP_NAME FROM ' + db.t('EXPTRACK_TRIP') +
                        ' WHERE TRIP_ID = :trip',
                        {'trip': trip}
                    )
                    if trip_row:
                        trip_name = (trip_row.get('TRIP_NAME')
                                     if 'TRIP_NAME' in trip_row
                                     else trip_row.get('trip_name'))

        # EXPENSE_ID is treated as a uniqueness key for this table: never insert
        # a second EXPTRACK_EXPENSE_REPORT_NEW row for the same EXPENSE_ID.
        existing = db.get('EXPTRACK_EXPENSE_REPORT_NEW', {'EXPENSE_ID': expense_id})
        if existing:
            # A correction voucher already exists for this expense (e.g. an
            # earlier rejection). Only refresh header-driven fields; leave the
            # employee-entered correction fields (TRIP, TRIP_NAME, CATEGORY,
            # PAYMENT_METHOD, RECEIPT_ATTACHMENT) untouched so in-progress
            # corrections are preserved.
            db.update('EXPTRACK_EXPENSE_REPORT_NEW',
                       {'EMPLOYEE': employee, 'APPROVER_NAME': approver},
                       {'EXPENSE_ID': expense_id})
        else:
            # No existing correction voucher: insert a full editable copy.
            record_id = auto_generate('EXPTRACK_EXPENSE_REPORT_NEW', 'RECORD_ID', 'ERN-')
            report_new_data = {
                'RECORD_ID': record_id,
                'EXPENSE_ID': expense_id,
                'EMPLOYEE': employee,
                'TRIP': trip,
                'TRIP_NAME': trip_name,
                'TOTAL_AMOUNT': total_amount,
                'CATEGORY': category,
                'EXPENSE_DATE': expense_date,
                'PAYMENT_METHOD': payment_method,
                'APPROVER_NAME': approver,
                'RECEIPT_ATTACHMENT': receipt_attachment,
            }
            db.insert('EXPTRACK_EXPENSE_REPORT_NEW', report_new_data)
    except Exception as exc:
        # Side-effect only: never block or roll back the already-committed
        # Manage Approval save on failure here. Just log and return normally.
        print('return_voucher_to_expense_report: failed to sync '
              'EXPTRACK_EXPENSE_REPORT_NEW for expense ' + expense_id +
              ': ' + str(exc))

    return None
