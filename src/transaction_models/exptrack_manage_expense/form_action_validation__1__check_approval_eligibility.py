# project: Expense_Management
# object_type: T
# object_name: exptrack_manage_expense
# event_type: form_action_validation
# function_name: check_approval_eligibility
# form_no: 1
# action_name: Submit
# language: python
# description: Guard the approve/reject decision
# functional_specification: Read the stored EXPTRACK_EXPENSE_REPORT row for REPORT_ID (the payload carries the form values including the newly chosen STATUS, so re-read the persisted row rather than trusting the payload STATUS). Return an error when: (a) the stored STATUS is not 'Submitted' — only submitted reports are actionable, and a report already decided (Approved/Rejected/Cancelled) is locked until the employee resubmits after a rejection; or (b) the stored EMPLOYEE is the logged-in user — an approver may not act on a report they own; identify the acting user from the payload's audit/user column. Return NULL/None when the decision may proceed.
# business_logic: Guard the approve/reject decision


def run(args):
    report_id = args.get('REPORT_ID')
    if is_empty(report_id):
        return {'error': 'No report selected for approval.'}

    report_id = str(report_id).strip()

    stored = db.query_one(
        'SELECT REPORT_ID, STATUS, EMPLOYEE FROM ' + db.t('EXPTRACK_EXPENSE_REPORT')
        + ' WHERE REPORT_ID = :r',
        {'r': report_id})

    if not stored:
        return {'error': 'Report ' + report_id + ' no longer exists.'}

    # Re-read persisted status; never trust the STATUS sitting in the payload.
    stored_status = '' if is_empty(stored.get('STATUS')) else str(stored.get('STATUS')).strip()

    # A report is actionable only while it is awaiting a decision. In this design the
    # awaiting state is carried as 'Submitted' (or its equivalent 'Pending').
    if not in_list(stored_status, 'Submitted,Pending'):
        return {'error': 'Report ' + report_id + ' is ' + (stored_status or 'in an unknown state')
                         + ' and is locked for approval. Only a submitted report can be approved'
                           ' or rejected; the employee must resubmit it after a rejection.'}

    stored_employee = '' if is_empty(stored.get('EMPLOYEE')) else str(stored.get('EMPLOYEE')).strip()

    # Acting user comes from the payload's audit/user columns.
    acting_user = coalesce(args.get('CHG_USER'), args.get('ADD_USER'))
    acting_user = '' if is_empty(acting_user) else str(acting_user).strip()

    if acting_user and stored_employee and acting_user.upper() == stored_employee.upper():
        return {'error': 'You cannot approve or reject report ' + report_id
                         + ' because you are the employee who raised it.'}

    return None
