# project: Expense_Management
# object_type: T
# object_name: exptrack_manage_expense
# event_type: action
# function_name: approve_expense_decision
# action_name: Approve
# language: python
# description: Approve the expense and its linked report, and release it to Finance
# functional_specification: Payload is the FLAT EXPTRACK_EXPENSE row. (1) Verify EMPLOYEE is not the logged-in approver (defence in depth) and that STATUS is not already 'Approved'/'Rejected'; otherwise return {"error": "..."}. (2) UPDATE EXPTRACK_EXPENSE SET STATUS='Approved', APPROVAL_STATUS='Approved', APPROVER = logged-in user, APPROVAL_DATE = current timestamp, CHG_DATE = current timestamp WHERE EXPENSE_ID = the payload id. (3) When EXPENSE_REPORT is not blank, propagate to EVERY expense of that report: UPDATE EXPTRACK_EXPENSE SET STATUS='Approved', APPROVAL_STATUS='Approved', CHG_DATE = current timestamp WHERE EXPENSE_REPORT = that report id. (4) UPDATE EXPTRACK_EXPENSE_REPORT SET STATUS='Approved', APPROVER = logged-in user, APPROVAL_DATE = current timestamp, PAYMENT_STATUS='Pending', APPROVER_COMMENTS = the expense's APPROVER_COMMENTS when present, CHG_DATE = current timestamp WHERE REPORT_ID = that report id, so the report appears on Finance Payment Processing (exptrack_finance_payment). (5) Write an Activity Log entry capturing the actor (logged-in user), the action 'Approved' and the affected REPORT_ID / EXPENSE_ID. (6) Return {"message": "Expense <id> approved."}.
# business_logic: Approve the expense and its linked report, and release it to Finance


def _val(args, name):
    """Case-insensitive payload read."""
    if name in args:
        return args[name]
    return args.get(name.lower())


def _txt(v):
    return '' if v is None else str(v).strip()


def _actor(args):
    """Best available identity of the acting user on this payload."""
    return _txt(coalesce(_val(args, 'CHG_USER'), _val(args, 'ADD_USER'), _val(args, 'APPROVER')))[:10]


def _actor_name(args, actor):
    """Display/full name of the logged-in user; falls back to the short user id."""
    name = _txt(coalesce(
        _val(args, '_USER_NAME'), _val(args, 'USER_NAME'), _val(args, 'USER_FULL_NAME'),
        _val(args, '_USER_FULL_NAME'), _val(args, 'LOGIN_USER_NAME')))
    return (name or actor)[:100]


def _log_activity(actor, action, expense_id, report_id, narrative):
    """Activity Log is an integration-side sink; never let it break the action."""
    try:
        api.emit_event('expense_activity_log', {
            'ACTIVITY_DATE': now().strftime('%Y-%m-%d %H:%M:%S'),
            'ACTOR': actor,
            'ACTIVITY_TYPE': action,
            'EXPENSE_ID': expense_id,
            'REPORT_ID': report_id,
            'DESCRIPTION': narrative,
        })
    except Exception:
        pass


def run(args):
    expense_id = _txt(_val(args, 'EXPENSE_ID'))
    if not expense_id:
        return {'error': 'Expense Id is missing.'}

    employee = _txt(_val(args, 'EMPLOYEE'))
    status = _txt(_val(args, 'STATUS'))
    comments = _txt(_val(args, 'APPROVER_COMMENTS'))
    report_id = _txt(_val(args, 'EXPENSE_REPORT'))
    actor = _actor(args)
    actor_name = _actor_name(args, actor)

    # (1) Guard rails
    if actor and employee and employee.upper() == actor.upper():
        return {'error': 'You cannot approve your own expense.'}
    if status in ('Approved', 'Rejected'):
        return {'error': 'Expense ' + expense_id + ' is already ' + status + '.'}

    stamp = now()

    # (2) The expense itself
    db.execute(
        'UPDATE ' + db.t('EXPTRACK_EXPENSE') + ' SET STATUS = :st, APPROVAL_STATUS = :ast,'
        ' APPROVER = :apr, APPROVAL_DATE = :adt, CHG_DATE = :cdt WHERE EXPENSE_ID = :eid',
        {'st': 'Approved', 'ast': 'Approved', 'apr': actor_name or None,
         'adt': stamp, 'cdt': stamp, 'eid': expense_id})

    if report_id:
        # (3) Propagate to every expense on the same report
        db.execute(
            'UPDATE ' + db.t('EXPTRACK_EXPENSE') + ' SET STATUS = :st, APPROVAL_STATUS = :ast,'
            ' CHG_DATE = :cdt WHERE EXPENSE_REPORT = :rid',
            {'st': 'Approved', 'ast': 'Approved', 'cdt': stamp, 'rid': report_id})

        # (4) Release the report to Finance
        sets = ('STATUS = :st, APPROVER = :apr, APPROVAL_DATE = :adt,'
                ' PAYMENT_STATUS = :pst, CHG_DATE = :cdt')
        params = {'st': 'Approved', 'apr': actor_name or None, 'adt': stamp,
                  'pst': 'Pending', 'cdt': stamp, 'rid': report_id}
        if comments:
            sets = sets + ', APPROVER_COMMENTS = :cmt'
            params['cmt'] = comments[:500]
        db.execute(
            'UPDATE ' + db.t('EXPTRACK_EXPENSE_REPORT') + ' SET ' + sets + ' WHERE REPORT_ID = :rid',
            params)

    # (5) Activity Log
    narrative = 'Approver ' + (actor or 'system') + ' approved Expense ' + expense_id
    if report_id:
        narrative = narrative + ' (Report ' + report_id + ')'
    _log_activity(actor, 'Approved', expense_id, report_id or None, narrative)

    # (6)
    return {'message': 'Expense ' + expense_id + ' approved.'}
