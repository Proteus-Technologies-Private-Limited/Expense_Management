# project: Expense_Management
# object_type: T
# object_name: exptrack_manage_expense
# event_type: action
# function_name: submit_approval_decision
# action_name: Submit
# language: python
# description: Finalise the approval decision and release an approved report to Finance
# functional_specification: Payload is the FLAT EXPTRACK_EXPENSE row (EXPENSE_ID, EMPLOYEE, AMOUNT, TRIP, CATEGORY, PAYMENT_METHOD, CURRENCY, DESCRIPTION, RECEIPT_ATTACHMENT, EXPENSE_REPORT, STATUS, APPROVAL_STATUS, APPROVER_COMMENTS). Steps: (1) Read the decision: decision = APPROVAL_STATUS; when blank/NULL treat it as 'Approved'. Normalise 'Reject' to 'Rejected'. Do NOT block on the current STATUS - an expense already Submitted/Approved only produces an informational message appended to the result, never an error. (2) If the decision is 'Rejected' and APPROVER_COMMENTS is blank, return {"error": "Approver Comments are mandatory when the decision is Rejected."}. (3) UPDATE EXPTRACK_EXPENSE SET STATUS = decision, APPROVAL_STATUS = decision, APPROVER = logged-in user short id, APPROVAL_DATE = current timestamp, CHG_DATE = current timestamp WHERE EXPENSE_ID = the payload expense id. (4) Resolve the linked report: report_id = EXPENSE_REPORT. If blank, look for an existing EXPTRACK_EXPENSE_REPORT row for the same EMPLOYEE whose STATUS is 'Draft' or 'Submitted' and reuse its REPORT_ID; otherwise generate a new REPORT_ID (max 20 chars, RPT-00001 style, unique) and INSERT a row carrying EMPLOYEE, REPORT_DATE = today, REPORT_TITLE = the linked trip's TRIP_NAME (fall back to a generated title referencing the expense), TRIP, TOTAL_AMOUNT = the expense AMOUNT, CURRENCY, CATEGORY_NAME from EXPTRACK_EXPENSE_CATEGORY.CATEGORY_NAME for the expense's CATEGORY, PAYMENT_METHOD_NAME from EXPTRACK_PAYMENT_METHOD.PAYMENT_METHOD_NAME for the expense's PAYMENT_METHOD, RECEIPT_ATTACHMENT, DESCRIPTION, STATUS = 'Submitted', PAYMENT_STATUS = 'Pending', PROCESSING_STATUS = 'Pending', ADD_DATE/ADD_USER. Write the resolved REPORT_ID back onto EXPTRACK_EXPENSE.EXPENSE_REPORT. (5) Recalculate that report's TOTAL_AMOUNT as SUM(AMOUNT) over all EXPTRACK_EXPENSE rows whose EXPENSE_REPORT = report_id. (6) UPDATE EXPTRACK_EXPENSE_REPORT SET STATUS = decision ('Approved' or 'Rejected'), APPROVER = logged-in user, APPROVAL_DATE = current timestamp, APPROVER_COMMENTS = the expense's APPROVER_COMMENTS, CHG_DATE = current timestamp WHERE REPORT_ID = report_id. When the decision is 'Approved' also set PAYMENT_STATUS = 'Pending' so the report is released to Finance and appears on exptrack_finance_payment (which lists reports with STATUS = 'Approved'); when 'Rejected' leave PAYMENT_STATUS untouched. (7) Return {"message": "Expense <id> <decision>; report <report_id> updated."} plus the informational note from step 1 when applicable. Any failure must return {"error": "..."} so the whole action rolls back.
# business_logic: Finalise the approval decision and release an approved report to Finance


def _val(args, name):
    """Case-insensitive payload read."""
    if name in args:
        return args[name]
    return args.get(name.lower())


def _txt(v):
    return '' if v is None else str(v).strip()


def _rowval(row, name):
    if not row:
        return None
    if name in row:
        return row[name]
    return row.get(name.lower())


def _actor(args):
    return _txt(coalesce(_val(args, 'CHG_USER'), _val(args, 'ADD_USER'), _val(args, 'APPROVER')))[:10]


def _actor_name(args, actor):
    """Display/full name of the logged-in user; falls back to the short user id."""
    name = _txt(coalesce(_val(args, 'CHG_USER_NAME'), _val(args, 'ADD_USER_NAME'),
                         _val(args, 'USER_NAME'), _val(args, 'USER_FULL_NAME'),
                         _val(args, 'FULL_NAME'), _val(args, 'DISPLAY_NAME')))
    if not name and actor:
        # Look the name up from the user master when the payload does not carry it.
        try:
            urow = db.query_one(
                'SELECT USER_NAME FROM ' + db.t('SEC_USER') + ' WHERE USER_ID = :u', {'u': actor})
            name = _txt(_rowval(urow, 'USER_NAME'))
        except Exception:
            name = ''
    if not name:
        name = actor
    return name[:100]


def _err(code, message):
    """Blocking error entry (with the legacy 'error' key alongside it)."""
    return {'errors': [{'code': code, 'type': 'E', 'message': message}], 'error': message}


def _next_report_id():
    """RPT-00001 style, unique, max 20 chars."""
    last = db.scalar(
        'SELECT MAX(REPORT_ID) FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        " WHERE REPORT_ID LIKE 'RPT-%'", {})
    seq = 0
    last = _txt(last)
    if len(last) > 4 and last[4:].isdigit():
        seq = int(last[4:])
    for _ in range(1000):
        seq = seq + 1
        candidate = 'RPT-' + str(seq).zfill(5)
        exists = db.scalar(
            'SELECT REPORT_ID FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') + ' WHERE REPORT_ID = :r',
            {'r': candidate})
        if not exists:
            return candidate
    return None


def run(args):
    expense_id = _txt(_val(args, 'EXPENSE_ID'))
    if not expense_id:
        return {'error': 'Expense Id is missing.'}

    employee = _txt(_val(args, 'EMPLOYEE'))
    comments = _txt(_val(args, 'APPROVER_COMMENTS'))[:500]
    actor = _actor(args)
    actor_name = _actor_name(args, actor)
    stamp = now()

    # (1) Decision - APPROVAL_STATUS is no longer on the form, so STATUS carries the decision.
    current_status = _txt(_val(args, 'STATUS'))
    decision = current_status
    if not decision:
        decision = _txt(_val(args, 'APPROVAL_STATUS'))
    if not decision:
        decision = 'Approved'
    if decision == 'Reject':
        decision = 'Rejected'
    if decision == 'Pending':
        return {'error': 'Select Approved or Rejected in Status before submitting the decision.'}
    if decision not in ('Approved', 'Rejected'):
        return {'error': 'Unsupported approval decision "' + decision + '".'}

    note = ''
    if current_status in ('Approved', 'Rejected', 'Submitted'):
        note = ' Note: expense was already ' + current_status + '; the decision has been re-applied.'

    # (2) Load the selected report header by its PK (EXPTRACK_EXPENSE_REPORT.REPORT_ID) and run
    #     the decision guards against the STORED row before anything is written.
    linked_report = _txt(_val(args, 'EXPENSE_REPORT'))
    if linked_report:
        rep_row = db.query_one(
            'SELECT REPORT_ID, STATUS, EMPLOYEE FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
            ' WHERE REPORT_ID = :r', {'r': linked_report})
        if not rep_row:
            return _err('MA_REPORT_NOT_FOUND',
                        'Expense report ' + linked_report + ' could not be found.')

        # (2a) Only a report still sitting at STATUS = 'Submitted' may be decided; an
        #      already Approved/Rejected (or Draft/Cancelled) report is left untouched.
        if _txt(_rowval(rep_row, 'STATUS')) != 'Submitted':
            return _err('MA_NOT_SUBMITTED', 'Only submitted reports can be decided.')

        # (2b) Self-approval guard - the report owner may not decide their own report.
        rep_employee = _txt(_rowval(rep_row, 'EMPLOYEE'))
        if rep_employee and actor and rep_employee == actor:
            return _err('MA_SELF_APPROVE', 'You cannot decide on your own expense report.')

    # (2c) Self-approval guard on the expense itself (report not yet created).
    if employee and actor and employee == actor:
        return _err('MA_SELF_APPROVE', 'You cannot decide on your own expense report.')

    # (2d) Rejection always needs a reason.
    if decision == 'Rejected' and not comments:
        return _err('MA_REJECT_COMMENT', 'Approver comments are mandatory when rejecting.')

    try:
        # (3) The expense itself
        db.execute(
            'UPDATE ' + db.t('EXPTRACK_EXPENSE') + ' SET STATUS = :st, APPROVAL_STATUS = :ast,'
            ' APPROVER = :apr, APPROVAL_DATE = :adt, CHG_DATE = :cdt WHERE EXPENSE_ID = :eid',
            {'st': decision, 'ast': decision, 'apr': actor_name or None, 'adt': stamp,
             'cdt': stamp, 'eid': expense_id})

        # (4) Resolve the linked report
        report_id = _txt(_val(args, 'EXPENSE_REPORT'))
        if not report_id and employee:
            open_rep = db.query_one(
                'SELECT REPORT_ID FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
                " WHERE EMPLOYEE = :emp AND STATUS IN ('Draft', 'Submitted')"
                ' ORDER BY REPORT_DATE DESC, REPORT_ID DESC', {'emp': employee})
            if open_rep:
                report_id = _txt(_rowval(open_rep, 'REPORT_ID'))

        if not report_id:
            report_id = _next_report_id()
            if not report_id:
                return {'error': 'Unable to generate a new Report Id.'}

            trip = _txt(_val(args, 'TRIP'))
            title = _txt(_val(args, 'REPORT_TITLE'))
            if not title and trip:
                trow = db.query_one(
                    'SELECT TRIP_NAME FROM ' + db.t('EXPTRACK_TRIP') + ' WHERE TRIP_ID = :t',
                    {'t': trip})
                title = _txt(_rowval(trow, 'TRIP_NAME'))
            if not title:
                title = 'Expense Report for ' + expense_id
            title = title[:150]

            category = _txt(_val(args, 'CATEGORY'))
            category_name = _txt(_val(args, 'CATEGORY_NAME'))
            if not category_name and category:
                crow = db.query_one(
                    'SELECT CATEGORY_NAME FROM ' + db.t('EXPTRACK_EXPENSE_CATEGORY') +
                    ' WHERE CATEGORY_CODE = :c', {'c': category})
                category_name = _txt(_rowval(crow, 'CATEGORY_NAME'))

            pay_method = _txt(_val(args, 'PAYMENT_METHOD'))
            pay_name = _txt(_val(args, 'PAYMENT_METHOD_NAME'))
            if not pay_name and pay_method:
                prow = db.query_one(
                    'SELECT PAYMENT_METHOD_NAME FROM ' + db.t('EXPTRACK_PAYMENT_METHOD') +
                    ' WHERE PAYMENT_METHOD_CODE = :p', {'p': pay_method})
                pay_name = _txt(_rowval(prow, 'PAYMENT_METHOD_NAME'))

            db.insert('EXPTRACK_EXPENSE_REPORT', {
                'REPORT_ID': report_id,
                'REPORT_TITLE': title,
                'EMPLOYEE': employee,
                'STATUS': 'Submitted',
                'REPORT_DATE': today(),
                'TOTAL_AMOUNT': to_number(_val(args, 'AMOUNT')),
                'PAYMENT_STATUS': 'Pending',
                'PROCESSING_STATUS': 'Pending',
                'CURRENCY': _txt(_val(args, 'CURRENCY')) or None,
                'TRIP': trip or None,
                'CATEGORY_NAME': category_name or None,
                'PAYMENT_METHOD_NAME': pay_name or None,
                'RECEIPT_ATTACHMENT': _txt(_val(args, 'RECEIPT_ATTACHMENT')) or None,
                'DESCRIPTION': _txt(_val(args, 'DESCRIPTION'))[:250] or None,
                'ADD_DATE': stamp,
                'ADD_USER': actor or None,
            })

        # Link the expense to the resolved report
        db.execute(
            'UPDATE ' + db.t('EXPTRACK_EXPENSE') + ' SET EXPENSE_REPORT = :rid, CHG_DATE = :cdt'
            ' WHERE EXPENSE_ID = :eid',
            {'rid': report_id, 'cdt': stamp, 'eid': expense_id})

        # (5) Recalculate the report total
        total = db.scalar(
            'SELECT SUM(AMOUNT) FROM ' + db.t('EXPTRACK_EXPENSE') + ' WHERE EXPENSE_REPORT = :rid',
            {'rid': report_id})
        total = to_number(total) or 0

        # (6) Finalise the report
        sets = ('STATUS = :st, APPROVER = :apr, APPROVAL_DATE = :adt,'
                ' APPROVER_COMMENTS = :cmt, TOTAL_AMOUNT = :tot, CHG_DATE = :cdt')
        params = {'st': decision, 'apr': actor_name or None, 'adt': stamp,
                  'cmt': comments or None, 'tot': total, 'cdt': stamp, 'rid': report_id}
        if decision == 'Approved':
            # Release to Finance (exptrack_finance_payment lists STATUS = 'Approved').
            sets = sets + ', PAYMENT_STATUS = :pst'
            params['pst'] = 'Pending'
        db.execute(
            'UPDATE ' + db.t('EXPTRACK_EXPENSE_REPORT') + ' SET ' + sets + ' WHERE REPORT_ID = :rid',
            params)

        # (6a) Cascade the decision to every expense line carried by this report.
        db.execute(
            'UPDATE ' + db.t('EXPTRACK_EXPENSE') + ' SET STATUS = :st, APPROVER = :apr,'
            ' APPROVAL_DATE = :adt, CHG_DATE = :cdt WHERE EXPENSE_REPORT = :rid',
            {'st': decision, 'apr': actor_name or None, 'adt': stamp, 'cdt': stamp,
             'rid': report_id})
    except Exception as exc:
        return {'error': 'Could not submit the approval decision: ' + str(exc)}

    # (7)
    result = {'message': ('Expense ' + expense_id + ' ' + decision + '; report ' + report_id +
                          ' updated.' + note)}
    if decision == 'Approved':
        # Prompt confirming the release to Finance Payment Processing.
        result['errors'] = [{'code': 'MA_RELEASED', 'type': 'P',
                             'message': 'Report approved and released to Finance Payment Processing.'}]
    return result
