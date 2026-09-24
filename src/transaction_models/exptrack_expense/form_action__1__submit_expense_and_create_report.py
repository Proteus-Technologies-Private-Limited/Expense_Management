# project: Expense_Management
# object_type: T
# object_name: exptrack_expense
# event_type: form_action
# function_name: submit_expense_and_create_report
# form_no: 1
# action_name: Submit
# language: python
# description: Submit this expense - create a new Expense Report for it and mark both as Submitted
# functional_specification: Blocks with EXP_ALREADY_SUBMITTED when the expense is already linked to a
#   report whose STATUS is 'Submitted' or 'Approved'. Otherwise resolves the target report - reuse the
#   linked Draft/Rejected report of the same employee, else an existing Draft report owned by the
#   logged-in user, else INSERT a new EXPTRACK_EXPENSE_REPORT (auto-generated REPORT_ID, EMPLOYEE =
#   logged-in user, REPORT_DATE = today, TOTAL_AMOUNT = sum of linked expense AMOUNTs) - sets that
#   report's STATUS to 'Submitted', links the expense to it and sets the expense's STATUS to 'Pending',
#   all in one transaction, so the report is immediately visible to Approval Management (which lists
#   reports where STATUS='Submitted'). A missing employee / logged-in user is a blocking error.
# business_logic: Submit this expense - create a new Expense Report for it and mark both as Submitted


def run(args):
    expense_id = args.get('EXPENSE_ID')
    if is_empty(expense_id):
        return 'Expense must be saved before it can be submitted.'

    row = db.query_one(
        'SELECT EXPENSE_ID, EMPLOYEE, TRIP, AMOUNT, EXPENSE_REPORT, STATUS, CATEGORY, ' +
        'PAYMENT_METHOD, CURRENCY, RECEIPT_ATTACHMENT, DESCRIPTION FROM ' +
        db.t('EXPTRACK_EXPENSE') + ' WHERE EXPENSE_ID = :e', {'e': expense_id})
    if not row:
        return 'Expense record not found.'

    def g(k):
        v = row.get(k)
        return row.get(k.lower()) if v is None else v

    employee = g('EMPLOYEE')
    trip = g('TRIP')
    amount = to_number(g('AMOUNT')) or 0
    existing_report = g('EXPENSE_REPORT')
    category = g('CATEGORY')
    payment_method = g('PAYMENT_METHOD')
    currency = g('CURRENCY')
    receipt_attachment = g('RECEIPT_ATTACHMENT')
    description = g('DESCRIPTION')

    # Look up the category name for this expense's category code.
    category_row = db.query_one(
        'SELECT CATEGORY_NAME FROM ' + db.t('EXPTRACK_EXPENSE_CATEGORY') +
        ' WHERE CATEGORY_CODE = :c', {'c': category})

    def catg(k):
        if not category_row:
            return None
        v = category_row.get(k)
        return category_row.get(k.lower()) if v is None else v

    category_name = catg('CATEGORY_NAME')

    # Look up the payment method name for this expense's payment method code.
    payment_method_row = db.query_one(
        'SELECT PAYMENT_METHOD_NAME FROM ' + db.t('EXPTRACK_PAYMENT_METHOD') +
        ' WHERE PAYMENT_METHOD_CODE = :p', {'p': payment_method})

    def pmg(k):
        if not payment_method_row:
            return None
        v = payment_method_row.get(k)
        return payment_method_row.get(k.lower()) if v is None else v

    payment_method_name = pmg('PAYMENT_METHOD_NAME')

    # Look up the trip name for this expense's trip, to use as the report title
    # (mirrors the auto-filled Trip Name field shown on Manage Expense).
    trip_row = db.query_one(
        'SELECT TRIP_NAME FROM ' + db.t('EXPTRACK_TRIP') +
        ' WHERE TRIP_ID = :t', {'t': trip})

    def tg(k):
        if not trip_row:
            return None
        v = trip_row.get(k)
        return trip_row.get(k.lower()) if v is None else v

    trip_name = tg('TRIP_NAME')

    # Resolve the logged-in user / owning employee. Without one we cannot own a report,
    # so block with an error rather than letting the INSERT fail on EMPLOYEE NOT NULL.
    if is_empty(employee):
        employee = args.get('EMPLOYEE') or args.get('employee')
    if is_empty(employee):
        return {'error': 'Cannot submit this expense: no employee (logged-in user) is associated with it.',
                'errors': [{'code': 'EXP_NO_EMPLOYEE', 'field': 'EMPLOYEE', 'type': 'E',
                            'message': 'Cannot submit this expense: no employee (logged-in user) is associated with it.'}]}

    # ---------------------------------------------------------------------
    # (2) Guard: if this expense is already linked to a report that is itself
    # Submitted or Approved, it has already gone for approval - change nothing.
    # ---------------------------------------------------------------------
    existing_report_row = None
    if not_empty(existing_report):
        existing_report_row = db.query_one(
            'SELECT REPORT_ID, EMPLOYEE, STATUS FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
            ' WHERE REPORT_ID = :r', {'r': existing_report})

    def rg(k):
        if not existing_report_row:
            return None
        v = existing_report_row.get(k)
        return existing_report_row.get(k.lower()) if v is None else v

    existing_report_status = (rg('STATUS') or '').strip()
    existing_report_id = rg('REPORT_ID')

    if in_list(existing_report_status, ['Submitted', 'Approved']):
        msg = 'This expense has already been submitted for approval on report %s.' % existing_report_id
        return {'error': msg,
                'errors': [{'code': 'EXP_ALREADY_SUBMITTED', 'field': 'EXPENSE_ID', 'type': 'E',
                            'message': msg}]}

    # ---------------------------------------------------------------------
    # (3) Resolve the target report.
    # ---------------------------------------------------------------------
    report_id = None

    # 3a. Reuse the report already linked to this expense when it is still open
    # (Draft / Rejected) and belongs to the same employee.
    if existing_report_row and in_list(existing_report_status, ['Draft', 'Rejected']) \
            and rg('EMPLOYEE') == employee:
        report_id = existing_report_id
        db.update('EXPTRACK_EXPENSE_REPORT',
                  {'REPORT_TITLE': coalesce(trip_name, 'Expense Report'),
                   'TRIP': trip,
                   'CURRENCY': currency,
                   'CATEGORY_NAME': category_name,
                   'PAYMENT_METHOD_NAME': payment_method_name,
                   'RECEIPT_ATTACHMENT': receipt_attachment,
                   'DESCRIPTION': description,
                   'REPORT_DATE': today(),
                   'STATUS': 'Submitted',
                   'CHG_DATE': now()},
                  {'REPORT_ID': report_id})

    # 3b. Otherwise reuse any open (Draft) report already owned by this employee.
    if is_empty(report_id):
        open_report = db.query_one(
            'SELECT REPORT_ID FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
            ' WHERE EMPLOYEE = :emp AND STATUS = :st', {'emp': employee, 'st': 'Draft'})
        if open_report:
            report_id = open_report.get('REPORT_ID')
            if report_id is None:
                report_id = open_report.get('report_id')
            db.update('EXPTRACK_EXPENSE_REPORT',
                      {'REPORT_TITLE': coalesce(trip_name, 'Expense Report'),
                       'TRIP': trip,
                       'CURRENCY': currency,
                       'CATEGORY_NAME': category_name,
                       'PAYMENT_METHOD_NAME': payment_method_name,
                       'RECEIPT_ATTACHMENT': receipt_attachment,
                       'DESCRIPTION': description,
                       'REPORT_DATE': today(),
                       'STATUS': 'Submitted',
                       'CHG_DATE': now()},
                      {'REPORT_ID': report_id})

    # 3c. Otherwise create a brand-new report, using the platform's standard
    # auto-generate/sequence mechanism for REPORT_ID (e.g. RPT-00001).
    if is_empty(report_id):
        report_id = auto_generate('EXPTRACK_EXPENSE_REPORT', 'REPORT_ID', 'RPT-')
        db.insert('EXPTRACK_EXPENSE_REPORT', {
            'REPORT_ID': report_id,
            'EMPLOYEE': employee,
            'REPORT_DATE': today(),          # submission date per the report model
            'REPORT_TITLE': coalesce(trip_name, 'Expense Report'),
            'TRIP': trip,
            'TOTAL_AMOUNT': amount,
            'CATEGORY_NAME': category_name,
            'PAYMENT_METHOD_NAME': payment_method_name,
            'CURRENCY': currency,
            'RECEIPT_ATTACHMENT': receipt_attachment,
            'DESCRIPTION': description,
            'STATUS': 'Submitted',
            'APPROVER': None,
            'APPROVAL_DATE': None,
            'APPROVER_COMMENTS': None,
            'PERIOD_FROM': None,
            'PERIOD_TO': None,
        })

    # ---------------------------------------------------------------------
    # (4) Link this expense to the resolved report and mark it Pending approval.
    # ---------------------------------------------------------------------
    db.update('EXPTRACK_EXPENSE',
              {'EXPENSE_REPORT': report_id,
               'STATUS': 'Pending',
               'CHG_DATE': now()},
              {'EXPENSE_ID': expense_id})

    # Keep the report total in step with the expenses actually linked to it.
    total_amount = db.scalar(
        'SELECT COALESCE(SUM(AMOUNT), 0) FROM ' + db.t('EXPTRACK_EXPENSE') +
        ' WHERE EXPENSE_REPORT = :r', {'r': report_id})
    db.update('EXPTRACK_EXPENSE_REPORT',
              {'TOTAL_AMOUNT': to_number(total_amount) or 0},
              {'REPORT_ID': report_id})

    # (5) All of the above commits as one transaction; the report is now visible to
    # exptrack_manage_expense / approval management, which lists STATUS = 'Submitted'.
    return 'Expense submitted for approval on report %s.' % report_id
