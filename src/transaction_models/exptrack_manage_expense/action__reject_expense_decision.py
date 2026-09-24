# project: Expense_Management
# object_type: T
# object_name: exptrack_manage_expense
# event_type: action
# function_name: reject_expense_decision
# action_name: Reject
# language: python
# description: Reject the expense and its linked report, and propagate the rejection
# functional_specification: Payload is the FLAT EXPTRACK_EXPENSE row. (1) Verify APPROVER_COMMENTS is not blank, EMPLOYEE is not the logged-in approver, and STATUS is not already 'Approved'/'Rejected'; otherwise return {"error": "..."}. (2) UPDATE EXPTRACK_EXPENSE SET STATUS='Rejected', APPROVAL_STATUS='Rejected', APPROVER = logged-in user, APPROVAL_DATE = current timestamp, APPROVER_COMMENTS = the payload comments, CHG_DATE = current timestamp WHERE EXPENSE_ID = the payload id. (3) When EXPENSE_REPORT is not blank, propagate to EVERY expense of that report: UPDATE EXPTRACK_EXPENSE SET STATUS='Rejected', APPROVAL_STATUS='Rejected', CHG_DATE = current timestamp WHERE EXPENSE_REPORT = that report id. (4) UPDATE EXPTRACK_EXPENSE_REPORT SET STATUS='Rejected', APPROVER = logged-in user, APPROVAL_DATE = current timestamp, APPROVER_COMMENTS = the payload comments, CHG_DATE = current timestamp WHERE REPORT_ID = that report id. Leave PAYMENT_STATUS untouched - rejected reports are never released to Finance. (5) Write an Activity Log entry capturing the actor, the action 'Rejected' and the affected REPORT_ID / EXPENSE_ID. (6) Return {"message": "Expense <id> rejected."}.
# business_logic: Reject the expense and its linked report, and propagate the rejection


def _val(args, name):
    """Case-insensitive payload read."""
    if name in args:
        return args[name]
    return args.get(name.lower())


def _txt(v):
    return '' if v is None else str(v).strip()


def _actor(args):
    return _txt(coalesce(_val(args, 'CHG_USER'), _val(args, 'ADD_USER'), _val(args, 'APPROVER')))[:10]


def _actor_name(args, actor):
    """Display/full name of the logged-in user; falls back to the short user id."""
    name = _txt(coalesce(
        _val(args, 'USER_NAME'),
        _val(args, 'USER_FULL_NAME'),
        _val(args, 'LOGIN_USER_NAME'),
        _val(args, 'CHG_USER_NAME'),
        _val(args, 'ADD_USER_NAME'),
    ))
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
    if not comments:
        return {'error': 'Approver Comments are mandatory when rejecting an expense.'}
    if actor and employee and employee.upper() == actor.upper():
        return {'error': 'You cannot reject your own expense.'}
    if status in ('Approved', 'Rejected'):
        return {'error': 'Expense ' + expense_id + ' is already ' + status + '.'}

    stamp = now()
    comments = comments[:500]

    # (2) The expense itself
    db.execute(
        'UPDATE ' + db.t('EXPTRACK_EXPENSE') + ' SET STATUS = :st, APPROVAL_STATUS = :ast,'
        ' APPROVER = :apr, APPROVAL_DATE = :adt, APPROVER_COMMENTS = :cmt,'
        ' CHG_DATE = :cdt WHERE EXPENSE_ID = :eid',
        {'st': 'Rejected', 'ast': 'Rejected', 'apr': actor_name or None, 'adt': stamp,
         'cmt': comments, 'cdt': stamp, 'eid': expense_id})

    if report_id:
        # (3) Propagate to every expense on the same report
        db.execute(
            'UPDATE ' + db.t('EXPTRACK_EXPENSE') + ' SET STATUS = :st, APPROVAL_STATUS = :ast,'
            ' CHG_DATE = :cdt WHERE EXPENSE_REPORT = :rid',
            {'st': 'Rejected', 'ast': 'Rejected', 'cdt': stamp, 'rid': report_id})

        # (4) Reject the report - PAYMENT_STATUS deliberately untouched
        db.execute(
            'UPDATE ' + db.t('EXPTRACK_EXPENSE_REPORT') + ' SET STATUS = :st, APPROVER = :apr,'
            ' APPROVAL_DATE = :adt, APPROVER_COMMENTS = :cmt, CHG_DATE = :cdt'
            ' WHERE REPORT_ID = :rid',
            {'st': 'Rejected', 'apr': actor_name or None, 'adt': stamp, 'cmt': comments,
             'cdt': stamp, 'rid': report_id})

    # (5) Activity Log
    narrative = 'Approver ' + (actor or 'system') + ' rejected Expense ' + expense_id
    if report_id:
        narrative = narrative + ' (Report ' + report_id + ')'
    narrative = narrative + ': ' + comments
    _log_activity(actor, 'Rejected', expense_id, report_id or None, narrative)

    # (6)
    return {'message': 'Expense ' + expense_id + ' rejected.'}
