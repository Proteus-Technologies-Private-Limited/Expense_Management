# project: Expense_Management
# object_type: T
# object_name: exptrack_manage_expense
# event_type: post_commit
# function_name: log_expense_approval_activity
# language: python
# description: Write an Activity Log entry for the approval decision
# functional_specification: Runs after the save commits. From the transaction payload ({action, txn_id, header, details}) read the header EXPTRACK_EXPENSE row. Insert one Activity Log entry capturing the date/time, the actor (logged-in user), the activity type derived from STATUS/APPROVAL_STATUS ('Approved' / 'Rejected', else 'Updated'), the affected EXPENSE_ID and EXPENSE_REPORT (report id), and a narrative description such as 'Manager approved Report RPT-0088 (Expense EXP-1023)'. Never block the save - log and return on any error.
# business_logic: Write an Activity Log entry for the approval decision


def _val(row, name):
    """Case-insensitive read from a row dict."""
    if not row:
        return None
    if name in row:
        return row[name]
    return row.get(name.lower())


def _txt(v):
    return '' if v is None else str(v).strip()


def run(args):
    try:
        header = args.get('header') or {}

        expense_id = _txt(_val(header, 'EXPENSE_ID')) or _txt(args.get('txn_id'))
        report_id = _txt(_val(header, 'EXPENSE_REPORT'))
        actor = _txt(coalesce(_val(header, 'CHG_USER'), _val(header, 'ADD_USER'),
                              _val(header, 'APPROVER')))[:10]

        status = _txt(_val(header, 'STATUS'))
        approval_status = _txt(_val(header, 'APPROVAL_STATUS'))
        decision = approval_status or status
        if decision == 'Reject':
            decision = 'Rejected'
        if decision in ('Approved', 'Rejected'):
            activity_type = decision
            verb = decision.lower()
        else:
            activity_type = 'Updated'
            verb = 'updated'

        narrative = (actor or 'System') + ' ' + verb + ' '
        if report_id:
            narrative = narrative + 'Report ' + report_id + ' (Expense ' + expense_id + ')'
        else:
            narrative = narrative + 'Expense ' + expense_id

        api.emit_event('expense_activity_log', {
            'ACTIVITY_DATE': now().strftime('%Y-%m-%d %H:%M:%S'),
            'ACTOR': actor,
            'ACTIVITY_TYPE': activity_type,
            'EXPENSE_ID': expense_id,
            'REPORT_ID': report_id or None,
            'TXN_ACTION': _txt(args.get('action')),
            'DESCRIPTION': narrative,
        })
    except Exception:
        # Logging must never disturb a committed save.
        pass
    return None
