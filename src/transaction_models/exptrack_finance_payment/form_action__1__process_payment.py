# project: Expense_Management
# object_type: T
# object_name: exptrack_finance_payment
# event_type: form_action
# function_name: process_payment
# form_no: 1
# action_name: Process Payment
# language: python
# description: Record payment on the approved expense report
# functional_specification: Input payload is the clicked EXPTRACK_EXPENSE_REPORT row (flat). Refuse with {"error": ...} when STATUS <> 'Approved', when PAYMENT_STATUS is already 'Paid', or when PAYMENT_REFERENCE is empty/blank. Otherwise UPDATE EXPTRACK_EXPENSE_REPORT SET PAYMENT_STATUS = 'Paid', PAYMENT_DATE = current date (the processing date), PAYMENT_REFERENCE = the reference entered on the form, CHG_DATE = current timestamp, CHG_USER = the acting user WHERE REPORT_ID = the payload REPORT_ID AND STATUS = 'Approved' AND PAYMENT_STATUS <> 'Paid'. If no row was updated (someone else paid it meanwhile), return {"error": "Report <id> has already been paid."}. On success return {"message": "Payment processed for report <REPORT_ID>, reference <PAYMENT_REFERENCE>."}.
# business_logic: Record payment on the approved expense report


def run(args):
    report_id = (args.get('REPORT_ID') or '').strip()
    if is_empty(report_id):
        return {'error': 'Report ID is missing.'}

    status = (args.get('STATUS') or '').strip()
    pay_status = (args.get('PAYMENT_STATUS') or '').strip()
    reference = (args.get('PAYMENT_REFERENCE') or '').strip()

    if status != 'Approved':
        return {'error': 'Report ' + report_id + ' is not approved. Only approved reports can be paid.'}
    if pay_status == 'Paid':
        return {'error': 'Report ' + report_id + ' has already been paid.'}
    if is_empty(reference):
        return {'error': 'Payment reference is required to process the payment.'}

    chg_user = coalesce(args.get('CHG_USER'), args.get('ADD_USER'), args.get('APPROVER'))

    sql = (
        'UPDATE ' + db.t('EXPTRACK_EXPENSE_REPORT') + ' SET '
        'PAYMENT_STATUS = :paid, '
        'PAYMENT_DATE = :pay_date, '
        'PAYMENT_REFERENCE = :reference, '
        'CHG_DATE = :chg_date, '
        'CHG_USER = :chg_user '
        'WHERE REPORT_ID = :report_id '
        "AND STATUS = 'Approved' "
        "AND (PAYMENT_STATUS IS NULL OR PAYMENT_STATUS <> 'Paid')"
    )
    params = {
        'paid': 'Paid',
        'pay_date': today(),
        'reference': reference,
        'chg_date': now(),
        'chg_user': chg_user,
        'report_id': report_id,
    }

    affected = db.execute(sql, params)
    try:
        affected = int(affected)
    except (TypeError, ValueError):
        affected = 1 if affected else 0

    if affected < 1:
        return {'error': 'Report ' + report_id + ' has already been paid.'}

    return {'message': 'Payment processed for report ' + report_id + ', reference ' + reference + '.'}
