# post_commit: link_rejected_expense_to_report
# Trigger: only when the just-committed EXPTRACK_EXPENSE row has STATUS = 'Reject'.
# Mirrors the rejected expense onto EXPTRACK_EXPENSE_REPORT_NEW (update if a row
# for this EXPENSE_ID already exists, otherwise insert a new correction voucher).

def run(args):
    status = args.get('STATUS')
    if status != 'Reject':
        return None

    expense_id = args.get('EXPENSE_ID')

    trip = None
    trip_name = None
    expense_report_id = args.get('EXPENSE_REPORT')
    if not_empty(expense_report_id):
        report_row = db.get('EXPTRACK_EXPENSE_REPORT', {'REPORT_ID': expense_report_id})
        if report_row:
            trip = report_row.get('TRIP')
            if not_empty(trip):
                trip_row = db.get('EXPTRACK_TRIP', {'TRIP_ID': trip})
                if trip_row:
                    trip_name = trip_row.get('TRIP_NAME')

    payload = {
        'EMPLOYEE': args.get('EMPLOYEE'),
        'CATEGORY': args.get('CATEGORY'),
        'EXPENSE_DATE': args.get('EXPENSE_DATE'),
        'PAYMENT_METHOD': args.get('PAYMENT_METHOD'),
        'RECEIPT_ATTACHMENT': args.get('RECEIPT_ATTACHMENT'),
        'TOTAL_AMOUNT': args.get('AMOUNT'),
        'APPROVER_NAME': args.get('APPROVER'),
        'TRIP': trip,
        'TRIP_NAME': trip_name,
    }

    existing = db.get('EXPTRACK_EXPENSE_REPORT_NEW', {'EXPENSE_ID': expense_id})
    if existing:
        db.update('EXPTRACK_EXPENSE_REPORT_NEW', existing['RECORD_ID'], payload)
    else:
        insert_payload = dict(payload)
        insert_payload['EXPENSE_ID'] = expense_id
        db.insert('EXPTRACK_EXPENSE_REPORT_NEW', insert_payload)

    return None
