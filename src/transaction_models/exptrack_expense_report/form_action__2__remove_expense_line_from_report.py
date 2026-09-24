# project: Expense_Management
# object_type: T
# object_name: exptrack_expense_report
# event_type: form_action
# function_name: remove_expense_line_from_report
# form_no: 2
# action_name: Remove Expense Line
# language: python
# description: Unlink one expense line from this report, revert it to Draft, and recalculate the report total
# functional_specification: Payload carries this line's EXPENSE_ID and the header REPORT_ID/STATUS. Validate the header report's STATUS is 'Draft' or 'Rejected' - if not, return {"error": "Expense lines can only be removed while the report is Draft or Rejected."}. UPDATE EXPTRACK_EXPENSE SET EXPENSE_REPORT = NULL, STATUS = 'Draft' WHERE EXPENSE_ID = this line's EXPENSE_ID. UPDATE EXPTRACK_EXPENSE_REPORT SET TOTAL_AMOUNT = (SELECT COALESCE(SUM(AMOUNT),0) FROM EXPTRACK_EXPENSE WHERE EXPENSE_REPORT = <header REPORT_ID>) WHERE REPORT_ID = <header REPORT_ID>. Write an Activity Log entry describing the line being removed from the report (align to the Activity Log object's actual table once modeled). Return a confirmation message 'Expense <EXPENSE_ID> removed from report <REPORT_ID>.'
# business_logic: Unlink one expense line from this report, revert it to Draft, and recalculate the report total


def _log_activity(report_id, employee, description):
    """Best-effort Activity Log write; never blocks the removal.
    Re-point this insert at the real Activity Log table once it is modeled."""
    try:
        db.insert('exptrack_activity_log', {
            'DATE': now(),
            'ACTIVITY_DETAILS': report_id,
            'ACTION_TYPE': 'Updated',
            'DESCRIPTION': description,
            'ACTOR': employee,
        })
    except Exception:
        pass


def run(args):
    header = args.get('header') if isinstance(args.get('header'), dict) else {}
    expense_id = args.get('EXPENSE_ID')
    report_id = coalesce(args.get('REPORT_ID'), header.get('REPORT_ID'), header.get('report_id'))

    if is_empty(expense_id):
        return {'error': 'Select an expense line to remove.'}
    if is_empty(report_id):
        return {'error': 'Report ID is missing; save the report before removing lines.'}

    rpt = db.query_one(
        'SELECT STATUS, EMPLOYEE FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        ' WHERE REPORT_ID = :rid', {'rid': report_id})
    if not rpt:
        return {'error': 'Expense report ' + str(report_id) + ' was not found.'}

    if (rpt.get('STATUS') or '').strip() not in ('Draft', 'Rejected'):
        return {'error': 'Expense lines can only be removed while the report is Draft or Rejected.'}

    exp = db.query_one(
        'SELECT EXPENSE_ID, EXPENSE_REPORT FROM ' + db.t('EXPTRACK_EXPENSE') +
        ' WHERE EXPENSE_ID = :eid', {'eid': expense_id})
    if not exp:
        return {'error': 'Expense ' + str(expense_id) + ' was not found.'}
    if (exp.get('EXPENSE_REPORT') or '').strip() != str(report_id).strip():
        return {'error': 'Expense ' + str(expense_id) + ' is not linked to report ' +
                         str(report_id) + '.'}

    db.execute(
        'UPDATE ' + db.t('EXPTRACK_EXPENSE') +
        ' SET EXPENSE_REPORT = NULL, STATUS = :st WHERE EXPENSE_ID = :eid',
        {'st': 'Draft', 'eid': expense_id})

    # Recalculate the report total over the remaining linked lines.
    db.execute(
        'UPDATE ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        ' SET TOTAL_AMOUNT = (SELECT COALESCE(SUM(AMOUNT), 0) FROM ' + db.t('EXPTRACK_EXPENSE') +
        ' WHERE EXPENSE_REPORT = :rid) WHERE REPORT_ID = :rid',
        {'rid': report_id})

    employee = coalesce(header.get('EMPLOYEE'), header.get('employee'), rpt.get('EMPLOYEE'))
    _log_activity(report_id, employee,
                  str(employee) + ' removed Expense ' + str(expense_id) +
                  ' from Report ' + str(report_id))

    return {'message': 'Expense ' + str(expense_id) + ' removed from report ' +
                       str(report_id) + '.'}
