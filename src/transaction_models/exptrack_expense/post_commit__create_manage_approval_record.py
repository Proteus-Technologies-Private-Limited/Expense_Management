# project: Expense_Management
# object_type: T
# object_name: exptrack_expense
# event_type: post_commit
# function_name: create_manage_approval_record
# language: python
# description: Create/sync the Manage Approval record for the just-submitted expense
# functional_specification: Runs after a save commits on exptrack_expense whenever the Submit action
#   just set EXPTRACK_EXPENSE.STATUS to 'Submitted'. From the transaction payload
#   ({action, txn_id, header, details}) read EXPENSE_ID, EMPLOYEE, TRIP, CATEGORY, EXPENSE_DATE,
#   AMOUNT, PAYMENT_METHOD and APPROVER off the header (case-insensitively). If no row exists yet in
#   EXPTRACK_MANAGE_APPROVAL_NEW_TXN for this EXPENSE_ID, auto-generate a RECORD_ID and insert a new
#   row with STATUS = 'Pending'. If a row already exists (resubmission), re-sync the copied fields
#   from the expense's current values without disturbing STATUS. Never block the expense save - log
#   and return on any error.
# business_logic: Create/sync the Manage Approval record for the just-submitted expense


def _val(row, name):
    """Case-insensitive read from a row dict."""
    if not row:
        return None
    if name in row:
        return row[name]
    return row.get(name.lower())


def run(args):
    try:
        header = args.get('header') or {}

        status = _val(header, 'STATUS')
        if status != 'Submitted':
            return None

        expense_id = _val(header, 'EXPENSE_ID')
        if is_empty(expense_id):
            return None

        employee = _val(header, 'EMPLOYEE')
        trip = _val(header, 'TRIP')
        category = _val(header, 'CATEGORY')
        expense_date = _val(header, 'EXPENSE_DATE')
        amount = to_number(_val(header, 'AMOUNT'))
        payment_method = _val(header, 'PAYMENT_METHOD')
        approver = _val(header, 'APPROVER')

        sync_data = {
            'EMPLOYEE': employee,
            'TRIP': trip,
            'CATEGORY': category,
            'EXPENSE_DATE': expense_date,
            'TOTAL_EXPENSE_AMOUNT': amount,
            'PAYMENT_METHOD': payment_method,
            'APPROVER_NAME': approver,
        }

        existing = db.get('EXPTRACK_MANAGE_APPROVAL_NEW_TXN', {'EXPENSE_ID': expense_id})
        if existing:
            db.update('EXPTRACK_MANAGE_APPROVAL_NEW_TXN', sync_data, {'EXPENSE_ID': expense_id})
        else:
            record_id = auto_generate('EXPTRACK_MANAGE_APPROVAL_NEW_TXN', 'RECORD_ID', 'APR-')
            sync_data['RECORD_ID'] = record_id
            sync_data['EXPENSE_ID'] = expense_id
            sync_data['STATUS'] = 'Pending'
            db.insert('EXPTRACK_MANAGE_APPROVAL_NEW_TXN', sync_data)
    except Exception:
        # Never disturb a committed expense save because of the approval-desk mirror.
        pass
    return None
