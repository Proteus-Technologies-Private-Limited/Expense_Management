# project: Expense_Management
# object_type: T
# object_name: exptrack_payment_method
# event_type: form_validation
# function_name: check_payment_method_not_referenced
# form_no: 1
# language: python
# description: Prevent delete of a payment method referenced by an Expense
# functional_specification: Given the payment_method_code of the record being deleted, check EXPTRACK_EXPENSE for any row where PAYMENT_METHOD equals this code. If at least one such row exists, return an error message stating the payment method is referenced by an Expense and can only be set Inactive, not deleted. Otherwise return no error.
# business_logic: Prevent delete of a payment method referenced by an Expense


def run(args):
    code = args.get('PAYMENT_METHOD_CODE')
    if is_empty(code):
        return None

    used = db.scalar(
        'SELECT COUNT(*) FROM ' + db.t('EXPTRACK_EXPENSE') +
        ' WHERE PAYMENT_METHOD = :c',
        {'c': str(code).strip()}
    )

    if to_number(used) > 0:
        return {
            'error': 'Payment method ' + str(code).strip() +
                     ' is referenced by an Expense and cannot be deleted. Set its status to Inactive instead.',
            'errors': [{
                'code': 'PMREF01',
                'field': 'payment_method_code',
                'type': 'E',
                'message': 'Payment method ' + str(code).strip() +
                           ' is referenced by an Expense and cannot be deleted. Set its status to Inactive instead.'
            }]
        }

    return None
