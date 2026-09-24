# project: Expense_Management
# object_type: T
# object_name: exptrack_expense_report
# event_type: form_action
# function_name: cancel_expense_report
# form_no: 1
# action_name: Cancel
# language: python
# description: Cancel the report and release its linked expenses back to Draft
# functional_specification: Payload carries this report's REPORT_ID, STATUS, EMPLOYEE. Validate STATUS is 'Draft' or 'Submitted' - if not (e.g. Approved/Rejected/Cancelled already), return {"error": "Only a Draft or Submitted report can be cancelled."}. UPDATE EXPTRACK_EXPENSE_REPORT SET STATUS = 'Cancelled' WHERE REPORT_ID = this REPORT_ID. Release linked expenses: UPDATE EXPTRACK_EXPENSE SET STATUS = 'Draft', EXPENSE_REPORT = NULL WHERE EXPENSE_REPORT = this REPORT_ID. Write an Activity Log entry: DATE = current timestamp, ACTIVITY_DETAILS = this REPORT_ID, ACTION_TYPE = 'Updated', DESCRIPTION = '<EMPLOYEE> cancelled Report <REPORT_ID>', ACTOR = the payload's EMPLOYEE (align to the Activity Log object's actual table once modeled; never block the cancel on a logging failure). Return a confirmation message 'Report <REPORT_ID> cancelled and its expenses released to Draft.'
# business_logic: Cancel the report and release its linked expenses back to Draft


def _log_activity(report_id, employee, description):
    """Best-effort Activity Log write. The Activity Log object is not yet modeled in
    this project, so any failure here is swallowed and never blocks the action.
    Re-point this insert at the real table once it exists."""
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
    report_id = args.get('REPORT_ID')
    employee = args.get('EMPLOYEE')

    if is_empty(report_id):
        return {'error': 'Report ID is missing; the report must be saved before it can be cancelled.'}

    # Decide on committed data, not just the form's copy of STATUS.
    row = db.query_one(
        'SELECT STATUS, EMPLOYEE FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        ' WHERE REPORT_ID = :rid', {'rid': report_id})
    if not row:
        return {'error': 'Expense report ' + str(report_id) + ' was not found.'}

    current_status = (row.get('STATUS') or '').strip() or (args.get('STATUS') or '')
    if current_status not in ('Draft', 'Submitted'):
        return {'error': 'Only a Draft or Submitted report can be cancelled.'}

    if is_empty(employee):
        employee = row.get('EMPLOYEE')

    db.execute(
        'UPDATE ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        ' SET STATUS = :st WHERE REPORT_ID = :rid',
        {'st': 'Cancelled', 'rid': report_id})

    # Release every linked expense back to the employee's Draft pool.
    db.execute(
        'UPDATE ' + db.t('EXPTRACK_EXPENSE') +
        ' SET STATUS = :st, EXPENSE_REPORT = NULL WHERE EXPENSE_REPORT = :rid',
        {'st': 'Draft', 'rid': report_id})

    _log_activity(report_id, employee,
                  str(employee) + ' cancelled Report ' + str(report_id))

    return {'message': 'Report ' + str(report_id) +
                       ' cancelled and its expenses released to Draft.'}
