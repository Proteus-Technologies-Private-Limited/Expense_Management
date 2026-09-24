# project: Expense_Management
# object_type: T
# object_name: exptrack_approve_expense_report
# event_type: action
# function_name: reject_expense_report
# action_name: Reject
# language: python
# description: Reject the report and propagate to linked expenses
# functional_specification: Given the current form payload (REPORT_ID, EMPLOYEE, STATUS, APPROVER_COMMENTS), verify STATUS = 'Submitted', EMPLOYEE is not the logged-in approver, and APPROVER_COMMENTS is not blank (defense in depth, in addition to the pre-action validations). UPDATE EXPTRACK_EXPENSE_REPORT SET STATUS='Rejected', APPROVER=logged-in user short id, APPROVER_COMMENTS=the submitted comments, APPROVAL_DATE=current timestamp WHERE REPORT_ID = the report id AND STATUS='Submitted'. If no row was updated, return {"error": "Report is no longer Submitted."}. Then UPDATE every EXPTRACK_EXPENSE row WHERE EXPENSE_REPORT = the report id SET STATUS='Rejected', APPROVAL_STATUS='Rejected', CHG_DATE=current timestamp. Insert an Activity Log entry (actor = logged-in user, action='Rejected', affected REPORT_ID) if an activity log table/mechanism exists in the project. Return {"message": "Report <REPORT_ID> rejected."}.
# business_logic: Reject the report and propagate to linked expenses


def run(args):
    report_id = args.get('REPORT_ID')
    if is_empty(report_id):
        return {'error': 'Report id is missing.'}

    status = args.get('STATUS')
    employee = args.get('EMPLOYEE')
    comments = args.get('APPROVER_COMMENTS')
    # Logged-in approver short id: the APPROVER column carries the acting user on this
    # approval form; fall back to the row's change/add user stamps.
    approver = coalesce(args.get('APPROVER'), args.get('CHG_USER'), args.get('ADD_USER'))

    if status != 'Submitted':
        return {'error': 'Only a Submitted report can be rejected.'}

    if not_empty(approver) and not_empty(employee) and str(employee).strip() == str(approver).strip():
        return {'error': 'You cannot reject your own expense report.'}

    if is_empty(comments) or not str(comments).strip():
        return {'error': 'Approver comments are required to reject a report.'}

    stamp = now()

    db.execute(
        'UPDATE ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        " SET STATUS = 'Rejected', APPROVER = :approver, APPROVER_COMMENTS = :comments,"
        ' APPROVAL_DATE = :stamp'
        " WHERE REPORT_ID = :rid AND STATUS = 'Submitted'",
        {'approver': approver, 'comments': str(comments).strip(),
         'stamp': stamp, 'rid': report_id})

    # Confirm the state transition actually happened (nothing updated -> stale form).
    current = db.query_one(
        'SELECT STATUS FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') + ' WHERE REPORT_ID = :rid',
        {'rid': report_id})
    if not current or current.get('STATUS') != 'Rejected':
        return {'error': 'Report is no longer Submitted.'}

    db.execute(
        'UPDATE ' + db.t('EXPTRACK_EXPENSE') +
        " SET STATUS = 'Rejected', APPROVAL_STATUS = 'Rejected', CHG_DATE = :stamp"
        ' WHERE EXPENSE_REPORT = :rid',
        {'stamp': stamp, 'rid': report_id})

    # No activity-log table exists in this project's schema, so nothing is logged here.
    return {'message': 'Report ' + str(report_id) + ' rejected.'}
