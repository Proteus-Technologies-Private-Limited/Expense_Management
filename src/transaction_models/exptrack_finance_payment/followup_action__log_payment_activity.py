# project: Expense_Management
# object_type: T
# object_name: exptrack_finance_payment
# event_type: followup_action
# function_name: log_payment_activity
# action_name: log_payment_activity
# condition: on-edit
# language: python
# description: Write a payment entry to the activity log
# functional_specification: After a payment edit on EXPTRACK_EXPENSE_REPORT, when PAYMENT_STATUS = 'Paid', write an activity-log style narrative entry capturing the acting Finance user, the action ('Processed payment'), the REPORT_ID, TOTAL_AMOUNT and PAYMENT_REFERENCE. Never block the save; report-only.
# business_logic: Write a payment entry to the activity log


def run(args):
    pay_status = (args.get('PAYMENT_STATUS') or '').strip()
    if pay_status != 'Paid':
        return None

    report_id = (args.get('REPORT_ID') or '').strip()
    reference = (args.get('PAYMENT_REFERENCE') or '').strip()
    amount = to_number(args.get('TOTAL_AMOUNT')) or 0
    currency = (args.get('CURRENCY') or '').strip()
    actor = (coalesce(args.get('CHG_USER'), args.get('ADD_USER'), 'Finance') or 'Finance').strip()

    stamp = now()
    try:
        stamp_text = stamp.strftime('%Y-%m-%d %H:%M:%S')
    except AttributeError:
        stamp_text = str(stamp)

    amount_text = '{0:,.2f}'.format(float(amount))
    if not_empty(currency):
        amount_text = currency + ' ' + amount_text

    ref_text = ', reference ' + reference if not_empty(reference) else ', reference not recorded'

    narrative = (
        stamp_text + ' - ' + actor + ' - Processed payment for report ' + report_id +
        ' of ' + amount_text + ref_text + '.'
    )

    # Report-only: a prompt never blocks the save.
    return {'prompts': [{
        'code': 'FPLOG1',
        'field': 'PAYMENT_STATUS',
        'type': 'P',
        'message': narrative,
    }]}
