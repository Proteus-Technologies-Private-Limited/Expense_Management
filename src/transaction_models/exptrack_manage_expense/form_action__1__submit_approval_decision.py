# project: Expense_Management
# object_type: T
# object_name: exptrack_manage_expense
# event_type: form_action
# function_name: submit_approval_decision
# form_no: 1
# action_name: Submit
# language: python
# description: Finalise the approval decision and release an approved report to Finance
# functional_specification: Finalise the approval decision held in EXPTRACK_EXPENSE_REPORT.STATUS for the clicked report. Payload is flat: REPORT_ID, STATUS (Pending/Approved/Rejected), APPROVER, APPROVER_COMMENTS, EMPLOYEE. Steps: (1) If STATUS is blank treat it as 'Pending' and return an informational message that no decision was recorded — make no writes. (2) Reject with an error if APPROVER is empty, or if STATUS = 'Rejected' and APPROVER_COMMENTS is empty. (3) UPDATE the EXISTING EXPTRACK_EXPENSE_REPORT row matched on REPORT_ID (never INSERT a second row): set STATUS to the decision, APPROVER to the supplied approver name, APPROVAL_DATE to the current date/time, APPROVER_COMMENTS to the supplied comments, CHG_DATE to now. (4) Recalculate TOTAL_AMOUNT as SUM(AMOUNT) over EXPTRACK_EXPENSE rows whose EXPENSE_REPORT = REPORT_ID and write it back. (5) When the decision is 'Approved', additionally set PAYMENT_STATUS = 'Pending' ONLY when it is not already 'Pending' or 'Paid', and leave PAYMENT_DATE and PAYMENT_REFERENCE untouched — this is what releases the SAME row to Finance Payment Processing (exptrack_finance_payment), which fetches STATUS = 'Approved'. When the decision is 'Rejected' leave PAYMENT_STATUS, PAYMENT_DATE and PAYMENT_REFERENCE untouched; the report is never released to Finance and instead returns to the employee on Manage Reports (exptrack_manage_reports). (6) Propagate the outcome to every EXPTRACK_EXPENSE row whose EXPENSE_REPORT = REPORT_ID: UPDATE STATUS = 'Approved' or 'Rejected' to mirror the decision, APPROVAL_STATUS to the same value, APPROVER and APPROVAL_DATE to the stamped values, and CHG_DATE to the current date/time. (7) Return {"message": "..."} naming the report, the decision and, on Approve, that the report has been released to Finance Payment Processing.
# business_logic: Finalise the approval decision and release an approved report to Finance


def run(args):
    report_id = args.get('REPORT_ID')
    if is_empty(report_id):
        return {'error': 'No report selected for approval.'}
    report_id = str(report_id).strip()

    decision = args.get('STATUS')
    decision = '' if is_empty(decision) else str(decision).strip()

    # (1) blank status = no decision taken; make no writes.
    if decision == '' or decision == 'Pending':
        return {'message': 'No decision was recorded for report ' + report_id
                           + '. The report remains Pending.'}

    if not in_list(decision, 'Approved,Rejected'):
        return {'error': 'Invalid decision "' + decision
                         + '". Choose either Approved or Rejected.'}

    approver = args.get('APPROVER')
    approver = '' if is_empty(approver) else str(approver).strip()
    comments = args.get('APPROVER_COMMENTS')
    comments = '' if is_empty(comments) else str(comments).strip()

    # (2) hard validations
    errors = []
    if approver == '':
        errors.append({'code': 'AEAPPR1', 'field': 'approver', 'type': 'E',
                       'message': 'Approver is required to record a decision.'})
    if decision == 'Rejected' and comments == '':
        errors.append({'code': 'AECMT1', 'field': 'approver_comments', 'type': 'E',
                       'message': 'Approver comments are mandatory when rejecting a report.'})
    if errors:
        return {'errors': errors, 'error': errors[0]['message']}

    stamp = now()

    existing = db.query_one(
        'SELECT REPORT_ID, PAYMENT_STATUS FROM ' + db.t('EXPTRACK_EXPENSE_REPORT')
        + ' WHERE REPORT_ID = :r',
        {'r': report_id})
    if not existing:
        return {'error': 'Report ' + report_id + ' no longer exists.'}

    # (4) recalculate the report total from its expense lines
    total = db.scalar(
        'SELECT SUM(AMOUNT) FROM ' + db.t('EXPTRACK_EXPENSE') + ' WHERE EXPENSE_REPORT = :r',
        {'r': report_id})
    total = to_number(total) or 0

    # (3) update the EXISTING header row - never insert a second one
    header_set = {
        'STATUS': decision,
        'APPROVER': approver,
        'APPROVAL_DATE': stamp,
        'APPROVER_COMMENTS': comments,
        'TOTAL_AMOUNT': total,
        'CHG_DATE': stamp,
    }

    # (5) release to Finance only on approval, and only when payment has not started
    released = False
    if decision == 'Approved':
        pay_status = existing.get('PAYMENT_STATUS')
        pay_status = '' if is_empty(pay_status) else str(pay_status).strip()
        if not in_list(pay_status, 'Pending,Paid'):
            header_set['PAYMENT_STATUS'] = 'Pending'
        released = True
    # On rejection PAYMENT_STATUS / PAYMENT_DATE / PAYMENT_REFERENCE stay untouched.

    db.update(db.t('EXPTRACK_EXPENSE_REPORT'), header_set, {'REPORT_ID': report_id})

    # (6) mirror the outcome onto every expense line of the report
    db.execute(
        'UPDATE ' + db.t('EXPTRACK_EXPENSE') + ' SET STATUS = :s, APPROVAL_STATUS = :s,'
        ' APPROVER = :a, APPROVAL_DATE = :d, CHG_DATE = :d WHERE EXPENSE_REPORT = :r',
        {'s': decision, 'a': approver, 'd': stamp, 'r': report_id})

    # (7) outcome message
    if released:
        msg = ('Report ' + report_id + ' has been Approved by ' + approver
               + ' (total ' + ('%.2f' % float(total))
               + ') and released to Finance Payment Processing.')
    else:
        msg = ('Report ' + report_id + ' has been Rejected by ' + approver
               + ' and returned to the employee on Manage Reports.')
    return {'message': msg}
