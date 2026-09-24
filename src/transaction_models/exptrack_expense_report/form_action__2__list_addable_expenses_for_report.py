# project: Expense_Management
# object_type: T
# object_name: exptrack_expense_report
# event_type: form_action
# function_name: list_addable_expenses_for_report
# form_no: 2
# action_name: Add Expense Line
# language: python
# description: List the employee's own Draft/Rejected expenses that are not yet linked to any report, as candidates to add to this report
# functional_specification: Payload carries the header report's REPORT_ID and EMPLOYEE (via header). Return the candidate rows as {"rows": [...]} where each row is one EXPTRACK_EXPENSE record with STATUS in ('Draft','Rejected'), EMPLOYEE = the header's EMPLOYEE, and EXPENSE_REPORT is NULL/blank (not already linked to any report) - i.e. SELECT EXPENSE_ID, EXPENSE_DATE, CATEGORY, AMOUNT, PAYMENT_METHOD, DESCRIPTION FROM EXPTRACK_EXPENSE WHERE EMPLOYEE = <header employee> AND STATUS IN ('Draft','Rejected') AND (EXPENSE_REPORT IS NULL OR EXPENSE_REPORT = ''). The caller presents these rows in a picker modal; when the user selects one or more and confirms, for EACH selected EXPENSE_ID run: UPDATE EXPTRACK_EXPENSE SET EXPENSE_REPORT = <header REPORT_ID>, STATUS = 'Added-to-Report' WHERE EXPENSE_ID = <selected id>. After linking, recalculate the report total: UPDATE EXPTRACK_EXPENSE_REPORT SET TOTAL_AMOUNT = (SELECT COALESCE(SUM(AMOUNT),0) FROM EXPTRACK_EXPENSE WHERE EXPENSE_REPORT = <header REPORT_ID>) WHERE REPORT_ID = <header REPORT_ID>. Write one Activity Log entry per line added (or a single combined entry) describing '<EMPLOYEE> added Expense <EXPENSE_ID> to Report <REPORT_ID>' (align to the Activity Log object's actual table once modeled).
# business_logic: List the employee's own Draft/Rejected expenses that are not yet linked to any report, as candidates to add to this report


def _log_activity(report_id, employee, description):
    """Best-effort Activity Log write; never blocks the action.
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


def _selected_ids(args):
    """The picker returns the confirmed ids on the second call. Accept the common
    carrier keys and normalise to a list of plain expense-id strings."""
    raw = coalesce(args.get('SELECTED_EXPENSE_IDS'),
                   args.get('selected_expense_ids'),
                   args.get('SELECTED_IDS'),
                   args.get('selected_ids'))
    if is_empty(raw):
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith('['):
            try:
                raw = json.loads(text)
            except Exception:
                raw = text.split(',')
        else:
            raw = text.split(',')
    if not isinstance(raw, list):
        raw = [raw]
    out = []
    for item in raw:
        if isinstance(item, dict):
            item = coalesce(item.get('EXPENSE_ID'), item.get('expense_id'))
        if not_empty(item):
            out.append(str(item).strip())
    return out


def run(args):
    header = args.get('header') if isinstance(args.get('header'), dict) else {}
    report_id = coalesce(args.get('REPORT_ID'), header.get('REPORT_ID'), header.get('report_id'))
    employee = coalesce(args.get('EMPLOYEE'), header.get('EMPLOYEE'), header.get('employee'))

    if is_empty(report_id):
        return {'error': 'Save the expense report before adding expense lines to it.'}

    rpt = db.query_one(
        'SELECT STATUS, EMPLOYEE FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        ' WHERE REPORT_ID = :rid', {'rid': report_id})
    if not rpt:
        return {'error': 'Expense report ' + str(report_id) + ' was not found.'}

    if (rpt.get('STATUS') or '').strip() not in ('Draft', 'Rejected'):
        return {'error': 'Expense lines can only be added while the report is Draft or Rejected.'}

    if is_empty(employee):
        employee = rpt.get('EMPLOYEE')

    selected = _selected_ids(args)

    # ---- Phase 1: no selection yet -> return the picker candidates -------------
    if not selected:
        rows = db.query(
            'SELECT EXPENSE_ID, EXPENSE_DATE, CATEGORY, AMOUNT, PAYMENT_METHOD, DESCRIPTION'
            ' FROM ' + db.t('EXPTRACK_EXPENSE') +
            " WHERE EMPLOYEE = :emp AND STATUS IN ('Draft','Rejected')"
            "   AND (EXPENSE_REPORT IS NULL OR EXPENSE_REPORT = '')"
            ' ORDER BY EXPENSE_DATE, EXPENSE_ID',
            {'emp': employee}) or []
        if not rows:
            return {'rows': [], 'prompts': [{
                'code': 'ERADD01',
                'type': 'P',
                'message': 'No unlinked Draft or Rejected expenses are available for this employee.'}]}
        return {'rows': rows}

    # ---- Phase 2: user confirmed a selection -> link the lines -----------------
    linked = []
    skipped = []
    for exp_id in selected:
        exp = db.query_one(
            'SELECT EXPENSE_ID, STATUS, EMPLOYEE, EXPENSE_REPORT FROM ' + db.t('EXPTRACK_EXPENSE') +
            ' WHERE EXPENSE_ID = :eid', {'eid': exp_id})
        if not exp:
            skipped.append(exp_id)
            continue
        if (exp.get('EMPLOYEE') or '').strip() != (employee or '').strip():
            skipped.append(exp_id)
            continue
        if (exp.get('STATUS') or '').strip() not in ('Draft', 'Rejected'):
            skipped.append(exp_id)
            continue
        if not_empty((exp.get('EXPENSE_REPORT') or '').strip()):
            skipped.append(exp_id)
            continue

        db.execute(
            'UPDATE ' + db.t('EXPTRACK_EXPENSE') +
            ' SET EXPENSE_REPORT = :rid, STATUS = :st WHERE EXPENSE_ID = :eid',
            {'rid': report_id, 'st': 'Added-to-Report', 'eid': exp_id})
        linked.append(exp_id)

    if not linked:
        return {'error': 'None of the selected expenses could be added: they are no longer '
                         'unlinked Draft/Rejected expenses for this employee.'}

    # Recalculate the report total from the lines that are now linked.
    db.execute(
        'UPDATE ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        ' SET TOTAL_AMOUNT = (SELECT COALESCE(SUM(AMOUNT), 0) FROM ' + db.t('EXPTRACK_EXPENSE') +
        ' WHERE EXPENSE_REPORT = :rid) WHERE REPORT_ID = :rid',
        {'rid': report_id})

    for exp_id in linked:
        _log_activity(report_id, employee,
                      str(employee) + ' added Expense ' + str(exp_id) +
                      ' to Report ' + str(report_id))

    out = {'message': str(len(linked)) + ' expense line(s) added to report ' +
                      str(report_id) + '.'}
    if skipped:
        out['prompts'] = [{
            'code': 'ERADD02',
            'type': 'P',
            'message': 'Skipped (no longer addable): ' + ', '.join(skipped)}]
    return out
