# project: Expense_Management
# object_type: T
# object_name: exptrack_expense
# event_type: form_action
# function_name: submit_expense_for_approval
# form_no: 1
# action_name: Submit
# language: python
# description: Submit expense for approval
# functional_specification: Validate and save the current expense record, then submit it for approval: set the EXPTRACK_EXPENSE row's STATUS and APPROVAL_STATUS to 'Pending' and guarantee a non-blank APPROVER (resolved from the active EXPTRACK_APPROVAL_RULES rule matching the expense CATEGORY and AMOUNT) so Manage Approval picks the record up, ensure a single linked EXPTRACK_EXPENSE_REPORT record exists (reusing it if already linked, otherwise creating exactly one), and return a confirmation message. Only callable when the record's current STATUS is 'Draft' or already 'Pending' (idempotent).
# business_logic: Submit expense for approval


def run(args):
    """Transition a Draft expense to Submitted and ensure a single linked approval report exists."""
    out = {'errors': []}

    expense_id = args.get('EXPENSE_ID')
    if is_empty(expense_id):
        out['errors'].append({'code': 'SUBEXP1', 'field': 'expense_id', 'type': 'E',
                              'message': 'Save the expense before submitting it for approval.'})
        out['error'] = out['errors'][0]['message']
        return out

    row = db.query_one(
        'SELECT EXPENSE_ID, STATUS, APPROVAL_STATUS, AMOUNT, CURRENCY, EXPENSE_REPORT, EMPLOYEE, '
        'DESCRIPTION, CATEGORY, APPROVER '
        'FROM ' + db.t('EXPTRACK_EXPENSE') + ' WHERE EXPENSE_ID = :eid',
        {'eid': expense_id})

    if not row:
        out['errors'].append({'code': 'SUBEXP2', 'field': 'expense_id', 'type': 'E',
                              'message': 'Expense %s was not found.' % expense_id})
        out['error'] = out['errors'][0]['message']
        return out

    current_status = (coalesce(row.get('STATUS'), row.get('status'), '') or '').strip()
    # Re-submitting an already-Pending expense is a no-op: the row is already
    # visible to Manage Approval, so simply re-assert the pending state below.
    if current_status not in ('Draft', 'Pending', ''):
        out['errors'].append({'code': 'EXP_ALREADY_SUBMITTED', 'field': 'status', 'type': 'E',
                              'message': 'Only draft expenses can be submitted'})
        out['error'] = out['errors'][0]['message']
        return out

    amount = to_number(coalesce(row.get('AMOUNT'), row.get('amount'), 0)) or 0
    if amount <= 0:
        out['errors'].append({'code': 'SUBEXP4', 'field': 'amount', 'type': 'E',
                              'message': 'Expense amount must be greater than zero before submission.'})
        out['error'] = out['errors'][0]['message']
        return out

    # Soft check: submitting without a receipt is allowed but worth flagging.
    ignored = set(args.get('_ignore_warnings') or [])
    if is_empty(args.get('RECEIPT_ATTACHMENT')) and 'SUBEXP5' not in ignored:
        out['errors'].append({'code': 'SUBEXP5', 'field': 'receipt_attachment', 'type': 'W',
                              'message': 'No receipt is attached to this expense.'})
        return out

    employee = coalesce(row.get('EMPLOYEE'), row.get('employee'))
    description = coalesce(row.get('DESCRIPTION'), row.get('description'))
    existing_report_id = coalesce(row.get('EXPENSE_REPORT'), row.get('expense_report'))
    category = coalesce(row.get('CATEGORY'), row.get('category'))

    # APPROVER is NOT NULL on EXPTRACK_EXPENSE - if the row has no approver yet,
    # resolve one from the active approval rules before the row is committed as
    # Pending, otherwise Manage Approval would never receive a usable record.
    approver = coalesce(row.get('APPROVER'), row.get('approver'), '')
    approver = (str(approver) if approver is not None else '').strip()
    if is_empty(approver):
        rule = db.query_one(
            'SELECT APPROVER_ROLE FROM ' + db.t('EXPTRACK_APPROVAL_RULES') + ' '
            'WHERE STATUS = :st '
            '  AND (CATEGORY IS NULL OR CATEGORY = :cat) '
            '  AND (MIN_AMOUNT IS NULL OR MIN_AMOUNT <= :amt) '
            '  AND (MAX_AMOUNT IS NULL OR MAX_AMOUNT >= :amt) '
            'ORDER BY CATEGORY, MIN_AMOUNT',
            {'st': 'A', 'cat': category, 'amt': amount})
        if rule:
            approver = coalesce(rule.get('APPROVER_ROLE'), rule.get('approver_role'), '')
            approver = (str(approver) if approver is not None else '').strip()
        if is_empty(approver):
            out['errors'].append({'code': 'SUBEXP6', 'field': 'approver', 'type': 'E',
                                  'message': 'No active approval rule matches this expense '
                                             '- an approver could not be assigned.'})
            out['error'] = out['errors'][0]['message']
            return out

    # Key every write on the full primary key (EXPENSE_REPORT + EXPENSE_ID) when the
    # expense is already linked to a report.
    expense_key = {'EXPENSE_ID': expense_id}
    if not is_empty(existing_report_id):
        expense_key['EXPENSE_REPORT'] = existing_report_id

    # Single transaction: update the expense, then reuse or create the linked
    # approval report, so a mid-way failure never leaves a submitted expense
    # without its report (or an orphaned report). STATUS/APPROVAL_STATUS are set
    # to 'Pending' on this same committing transaction so Manage Approval
    # (which reads EXPTRACK_EXPENSE WHERE STATUS = 'Pending') picks the row up
    # immediately after the commit - nothing is copied into any other table.
    with db.transaction():
        db.update(
            'EXPTRACK_EXPENSE',
            {'STATUS': 'Pending',
             'APPROVAL_STATUS': 'Pending',
             'APPROVER': approver,
             'CHG_DATE': now(),
             'CHG_USER': coalesce(args.get('CHG_USER'), args.get('ADD_USER'), args.get('EMPLOYEE'))},
            expense_key)

        report_id = None
        if not is_empty(existing_report_id):
            existing_report = db.query_one(
                'SELECT REPORT_ID FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') + ' WHERE REPORT_ID = :rid',
                {'rid': existing_report_id})
            if existing_report:
                # Reuse the already-linked report to avoid a duplicate approval record.
                report_id = coalesce(existing_report.get('REPORT_ID'), existing_report.get('report_id'))
                # The report may already exist as a draft/other-status record; make sure it
                # is (re)marked Submitted so it shows up on the Approve Expense Report screen.
                db.update(
                    'EXPTRACK_EXPENSE_REPORT',
                    {'STATUS': 'Submitted'},
                    {'REPORT_ID': report_id})

        if is_empty(report_id):
            report_title = 'Expense Report - ' + str(expense_id)
            # REPORT_ID is auto-generated by the platform's id sequence for
            # EXPTRACK_EXPENSE_REPORT - do not pass it in explicitly.
            new_report_id = db.insert(
                db.t('EXPTRACK_EXPENSE_REPORT'),
                {'REPORT_TITLE': report_title,
                 'EMPLOYEE': employee,
                 'TOTAL_AMOUNT': amount,
                 'STATUS': 'Submitted',
                 'PAYMENT_STATUS': 'Pending'})

            db.update(
                'EXPTRACK_EXPENSE',
                {'EXPENSE_REPORT': new_report_id},
                {'EXPENSE_ID': expense_id})

    return {'prompts': [{'code': 'SUBEXP0', 'type': 'P',
                         'message': 'Expense %s submitted for approval.' % expense_id}]}
