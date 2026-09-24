# project: Expense_Management
# object_type: T
# object_name: exptrack_payment_process_new
# event_type: form_action
# function_name: process_expense_payment
# form_no: 1
# action_name: Process Payment
# language: python
# description: Record the payment for this expense
# functional_specification: Record that the finance processor named in FINANCE_NAME has processed payment for this expense (EXPENSE_ID). Stamp the current date/time as the processing/payment date and return a confirmation message including the Expense ID and Finance Name. If a linked EXPTRACK_EXPENSE_REPORT record exists (EXPTRACK_EXPENSE.EXPENSE_REPORT = EXPTRACK_EXPENSE_REPORT.REPORT_ID), update its PAYMENT_STATUS to 'Paid', PROCESSING_STATUS to 'Processed', PROCESSED_DATE to today, PROCESSED_BY to the finance name/user, and PAYMENT_DATE to today.
# business_logic: Record the payment for this expense


def run(args):
    ignored = set(args.get('_ignore_warnings') or [])
    out = {'errors': []}

    expense_id = args.get('expense_id')
    finance_name = args.get('finance_name')

    if is_empty(expense_id):
        out['errors'].append({
            'code': 'PPNEXP1', 'field': 'expense_id', 'type': 'E',
            'message': 'Expense ID is required to process a payment.'})
        out['error'] = out['errors'][0]['message']
        return out

    expense = db.query_one(
        'SELECT EXPENSE_ID, APPROVAL_STATUS, EXPENSE_REPORT, FINANCE_NAME '
        'FROM ' + db.t('EXPTRACK_EXPENSE') + ' WHERE EXPENSE_ID = :e',
        {'e': expense_id})

    if not expense:
        out['errors'].append({
            'code': 'PPNEXP2', 'field': 'expense_id', 'type': 'E',
            'message': 'Expense ' + str(expense_id) + ' does not exist.'})
        out['error'] = out['errors'][0]['message']
        return out

    # Fall back to the finance name already recorded on the expense.
    if is_empty(finance_name):
        finance_name = expense.get('FINANCE_NAME')
    if is_empty(finance_name):
        out['errors'].append({
            'code': 'PPNFIN1', 'field': 'finance_name', 'type': 'E',
            'message': 'Finance Name is required to process a payment.'})
        out['error'] = out['errors'][0]['message']
        return out
    finance_name = str(finance_name).strip()

    approval_status = (expense.get('APPROVAL_STATUS') or '').strip()
    if approval_status != 'Approved':
        out['errors'].append({
            'code': 'PPNAPR1', 'field': 'status', 'type': 'E',
            'message': 'Expense ' + str(expense_id) + ' is not approved (approval status: '
                       + (approval_status or 'blank')
                       + '). Payment cannot be processed.'})
        out['error'] = out['errors'][0]['message']
        return out

    processed_on = today()
    stamped_at = now()
    report_id = expense.get('EXPENSE_REPORT')
    report_msg = ''

    if not_empty(report_id):
        report = db.query_one(
            'SELECT REPORT_ID, PAYMENT_STATUS FROM ' + db.t('EXPTRACK_EXPENSE_REPORT')
            + ' WHERE REPORT_ID = :r', {'r': report_id})
        if report:
            already_paid = (report.get('PAYMENT_STATUS') or '').strip() == 'Paid'
            if already_paid and 'PPNPAID1' not in ignored:
                out['errors'].append({
                    'code': 'PPNPAID1', 'field': 'status', 'type': 'W',
                    'message': 'Expense report ' + str(report_id)
                               + ' is already marked Paid. Proceeding will overwrite '
                                 'the existing payment details.'})
                return out

            db.update(
                'EXPTRACK_EXPENSE_REPORT',
                {
                    'PAYMENT_STATUS': 'Paid',
                    'PROCESSING_STATUS': 'Processed',
                    'PROCESSED_DATE': processed_on,
                    'PROCESSED_BY': finance_name[:10],
                    'PAYMENT_DATE': processed_on,
                    'CHG_DATE': stamped_at,
                    'CHG_USER': finance_name[:10],
                },
                {'REPORT_ID': report_id})
            report_msg = ' Expense report ' + str(report_id) + ' marked Paid / Processed.'
        else:
            report_msg = ' No expense report found for ' + str(report_id) + '.'

    # Stamp the processing finance user on the expense itself.
    db.update(
        'EXPTRACK_EXPENSE',
        {'FINANCE_NAME': finance_name, 'CHG_DATE': stamped_at,
         'CHG_USER': finance_name[:10]},
        {'EXPENSE_ID': expense_id})

    out['errors'].append({
        'code': 'PPNDONE1', 'type': 'P',
        'message': 'Payment for Expense ID ' + str(expense_id)
                   + ' processed by Finance Name ' + finance_name + ' on '
                   + stamped_at.strftime('%Y-%m-%d %H:%M') + '.' + report_msg})
    return out
