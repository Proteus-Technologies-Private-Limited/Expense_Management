# project: Expense_Management
# object_type: T
# object_name: exptrack_manage_approval_v2
# event_type: post_commit
# function_name: create_payment_process_record
# language: python
# description: Insert a payment process record for the submitted expense
# functional_specification: Fires after commit of this transaction (Manage Approval, header form EXPTRACK_EXPENSE) only when the committing action was 'Submit'. Reads EXPENSE_ID, EMPLOYEE, CATEGORY, EXPENSE_DATE, PAYMENT_METHOD, STATUS and the linked EXPENSE_REPORT id directly from the just-committed EXPTRACK_EXPENSE row, then reads TRIP and TOTAL_AMOUNT from the matching EXPTRACK_EXPENSE_REPORT row (REPORT_ID = EXPENSE_REPORT). Inserts exactly one new row into EXPTRACK_PAYMENT_PROCESS with STATUS defaulted to 'Pending' and PAYMENT_DATE/PAYMENT_AMOUNT/PAYMENT_REFERENCE left blank for Finance to fill in later. Does nothing for the 'edit'/'update' action. If no matching expense report is found, the insert still proceeds but TRIP/TOTAL_AMOUNT are left blank.
# business_logic: Insert a payment process record for the submitted expense


def _val(row, *names):
    """Case-insensitive lookup of the first present, non-None key."""
    if not row:
        return None
    lowered = {}
    for k, v in row.items():
        lowered[str(k).lower()] = v
    for n in names:
        v = lowered.get(n.lower())
        if v is not None:
            return v
    return None


def run(args):
    try:
        # ---- 1. Only act when the committing action was 'Submit' -------------
        action = str(coalesce(args.get('action'), '')).strip().lower()
        if action != 'submit':
            return None

        header = args.get('header') or {}
        if not isinstance(header, dict) or not header:
            return None

        expense_id = _val(header, 'EXPENSE_ID')
        if is_empty(expense_id):
            return None
        expense_id = str(expense_id).strip()

        # ---- 2. Read the just-committed EXPTRACK_EXPENSE row directly --------
        exp = db.query_one(
            'SELECT EXPENSE_ID, EMPLOYEE, CATEGORY, EXPENSE_DATE, PAYMENT_METHOD, '
            'STATUS, EXPENSE_REPORT '
            'FROM ' + db.t('EXPTRACK_EXPENSE') + ' WHERE EXPENSE_ID = :eid',
            {'eid': expense_id})
        if not exp:
            return None

        employee = _val(exp, 'EMPLOYEE')
        category = _val(exp, 'CATEGORY')
        expense_date = _val(exp, 'EXPENSE_DATE')
        payment_method = _val(exp, 'PAYMENT_METHOD')
        status = _val(exp, 'STATUS')
        report_id = _val(exp, 'EXPENSE_REPORT')

        trip = None
        total_amount = None

        # ---- 3. TRIP and TOTAL_AMOUNT come from the linked report ------------
        if not_empty(report_id):
            report_id = str(report_id).strip()
            rep = db.query_one(
                'SELECT REPORT_ID, TRIP, TOTAL_AMOUNT '
                'FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') + ' WHERE REPORT_ID = :rid',
                {'rid': report_id})
            if rep:
                trip = _val(rep, 'TRIP')
                total_amount = _val(rep, 'TOTAL_AMOUNT')

        # ---- 4. Insert exactly one new payment process record -----------------
        db.insert(db.t('EXPTRACK_PAYMENT_PROCESS'), {
            'EXPENSE_REPORT': report_id,
            'EXPENSE_ID': expense_id,
            'TRIP': trip,
            'CATEGORY': category,
            'EXPENSE_DATE': expense_date,
            'REPORT_EMPLOYEE': employee,
            'REPORT_TOTAL_AMOUNT': total_amount,
            'REPORT_STATUS': status,
            'PAYMENT_METHOD': payment_method,
            'STATUS': 'Pending',
        })

        return None

    except Exception as ex:
        # Side-effect only: report the failure, never block or roll back the save.
        return {'prompts': [{
            'code': 'PPCREATE9',
            'type': 'P',
            'message': 'Payment process record could not be created: ' + str(ex),
        }]}
