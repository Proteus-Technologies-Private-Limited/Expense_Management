# project: Expense_Management
# object_type: T
# object_name: exptrack_manage_approval_new
# event_type: followup_action
# function_name: sync_expense_status
# action_name: sync_expense_status
# condition: on-edit
# language: python
# description: Mirror the approval decision onto the expense status
# functional_specification: After the approver saves a decision on EXPTRACK_EXPENSE, if APPROVAL_STATUS is 'Approved' set STATUS='Approved'; if 'Rejected' set STATUS='Rejected'; leave STATUS='Pending' when APPROVAL_STATUS is still 'Pending'. Match the row on EXPENSE_REPORT + EXPENSE_ID and stamp CHG_DATE with the current date/time. Do not create or delete any expense record.
# business_logic: Mirror the approval decision onto the expense status


def run(args):
    report = args.get('EXPENSE_REPORT')
    expense_id = args.get('EXPENSE_ID')
    approval_status = args.get('APPROVAL_STATUS')

    if is_empty(expense_id):
        return {'error': 'Expense Id is required to sync the approval decision.'}

    if is_empty(approval_status):
        return {'error': 'Approval Status is required.'}

    approval_status = str(approval_status).strip()

    if approval_status == 'Approved':
        new_status = 'Approved'
    elif approval_status == 'Rejected':
        new_status = 'Rejected'
    elif approval_status == 'Pending':
        new_status = 'Pending'
    else:
        return {'error': 'Invalid Approval Status: ' + approval_status}

    row = db.query_one(
        'SELECT STATUS FROM ' + db.t('EXPTRACK_EXPENSE') +
        ' WHERE EXPENSE_REPORT = :rep AND EXPENSE_ID = :eid',
        {'rep': report, 'eid': expense_id}
    )

    if not row:
        return {'error': 'Expense record not found for the selected report and expense.'}

    db.update(
        'EXPTRACK_EXPENSE',
        {'STATUS': new_status, 'CHG_DATE': now()},
        {'EXPENSE_REPORT': report, 'EXPENSE_ID': expense_id}
    )

    return {
        'prompts': [{
            'code': 'SYNCEXPST1',
            'field': 'STATUS',
            'type': 'P',
            'message': 'Expense status synced to ' + new_status + '.'
        }]
    }
