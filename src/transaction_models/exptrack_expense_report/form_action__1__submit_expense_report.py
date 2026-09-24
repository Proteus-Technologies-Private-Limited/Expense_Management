# project: Expense_Management
# object_type: T
# object_name: exptrack_expense_report
# event_type: form_action
# function_name: submit_expense_report
# form_no: 1
# action_name: Submit for Approval
# language: python
# description: Submit the report for approval: lock its lines, set STATUS=Submitted, and log the activity
# functional_specification: Payload carries this report's REPORT_ID, STATUS, EMPLOYEE, APPROVER. Validate STATUS is 'Draft' or 'Rejected' - if not, return {"error": "Only a Draft or Rejected report can be submitted for approval."}. Validate at least one expense line exists: SELECT COUNT(*) FROM EXPTRACK_EXPENSE WHERE EXPENSE_REPORT = this REPORT_ID; if zero, return {"error": "At least one expense line is required before this report can be submitted."}. If the report's current STATUS was 'Rejected' (a resubmission), clear the prior decision: UPDATE EXPTRACK_EXPENSE_REPORT SET APPROVER_COMMENTS = NULL, APPROVAL_DATE = NULL WHERE REPORT_ID = this REPORT_ID. UPDATE EXPTRACK_EXPENSE_REPORT SET STATUS = 'Submitted' WHERE REPORT_ID = this REPORT_ID. Lock all linked lines: UPDATE EXPTRACK_EXPENSE SET STATUS = 'Submitted' WHERE EXPENSE_REPORT = this REPORT_ID. Write an Activity Log entry: DATE = current timestamp, ACTIVITY_DETAILS = this REPORT_ID, ACTION_TYPE = 'Updated', DESCRIPTION = '<EMPLOYEE> submitted Report <REPORT_ID> for approval', ACTOR = the payload's EMPLOYEE (align the insert to the Activity Log object's actual table once it is modeled in this project; never let a logging failure block the submit). Return a confirmation message 'Report <REPORT_ID> submitted for approval.'
# business_logic: Submit the report for approval: lock its lines, set STATUS=Submitted, and log the activity


def _log_activity(report_id, employee, description):
    """Best-effort Activity Log write; a logging failure never blocks the submit.
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
    report_id = args.get('REPORT_ID')
    employee = args.get('EMPLOYEE')

    if is_empty(report_id):
        return {'error': 'Report ID is missing; the report must be saved before it can be submitted.'}

    row = db.query_one(
        'SELECT status, employee FROM twasta.exptrack_expense_report'
        ' WHERE report_id = :rid', {'rid': report_id})
    if not row:
        return {'error': 'Expense report ' + str(report_id) + ' was not found.'}

    current_status = (row.get('STATUS') or '').strip() or (args.get('STATUS') or '')
    if current_status not in ('Draft', 'Rejected'):
        return {'error': 'Only a Draft or Rejected report can be submitted for approval.'}

    line_count = to_number(db.scalar(
        'SELECT COUNT(*) FROM twasta.exptrack_expense'
        ' WHERE expense_report = :rid', {'rid': report_id})) or 0
    if line_count <= 0:
        return {'error': 'At least one expense line is required before this report can be submitted.'}

    if is_empty(employee):
        employee = row.get('EMPLOYEE')

    # Resubmission of a rejected report: wipe the previous approval decision.
    if current_status == 'Rejected':
        db.execute(
            'UPDATE twasta.exptrack_expense_report'
            ' SET approver_comments = NULL, approval_date = NULL WHERE report_id = :rid',
            {'rid': report_id})

    db.execute(
        'UPDATE twasta.exptrack_expense_report'
        ' SET status = :st WHERE report_id = :rid',
        {'st': 'Submitted', 'rid': report_id})

    # Lock every linked line so it can no longer be edited or re-used.
    db.execute(
        'UPDATE twasta.exptrack_expense'
        ' SET status = :st WHERE expense_report = :rid',
        {'st': 'Submitted', 'rid': report_id})

    _log_activity(report_id, employee,
                  str(employee) + ' submitted Report ' + str(report_id) + ' for approval')

    return {'message': 'Report ' + str(report_id) + ' submitted for approval.'}
