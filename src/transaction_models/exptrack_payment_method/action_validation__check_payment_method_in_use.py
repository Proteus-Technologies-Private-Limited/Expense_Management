# project: Expense_Management
# object_type: T
# object_name: exptrack_payment_method
# event_type: action_validation
# function_name: check_payment_method_in_use
# language: python
# description: Check whether the payment method is in use before the action proceeds
# business_logic: A payment method still referenced by Expense rows must not be removed; deactivating one that is still in use is allowed but warned about.


def run(args):
    code = args.get('PAYMENT_METHOD_CODE')
    if is_empty(code):
        return 'Payment method code is required.'

    code = str(code).strip()
    ignored = set(args.get('_ignore_warnings') or [])
    out = {'errors': []}

    total = to_number(db.scalar(
        'SELECT COUNT(*) FROM ' + db.t('EXPTRACK_EXPENSE') +
        ' WHERE PAYMENT_METHOD = :c',
        {'c': code}
    ))

    if total > 0:
        open_cnt = to_number(db.scalar(
            'SELECT COUNT(*) FROM ' + db.t('EXPTRACK_EXPENSE') +
            ' WHERE PAYMENT_METHOD = :c AND APPROVAL_STATUS = :s',
            {'c': code, 's': 'Pending'}
        ))

        if 'PMUSE01' not in ignored:
            out['errors'].append({
                'code': 'PMUSE01',
                'field': 'payment_method_code',
                'type': 'W',
                'message': 'Payment method ' + code + ' is used by ' + str(int(total)) +
                           ' expense record(s). It cannot be deleted; deactivating it will stop it being used on new expenses.'
            })

        if open_cnt > 0 and 'PMUSE02' not in ignored:
            out['errors'].append({
                'code': 'PMUSE02',
                'field': 'payment_method_code',
                'type': 'W',
                'message': str(int(open_cnt)) + ' expense(s) using this payment method are still Pending approval.'
            })
    else:
        out['errors'].append({
            'code': 'PMUSE03',
            'field': 'payment_method_code',
            'type': 'P',
            'message': 'Payment method ' + code + ' is not referenced by any expense.'
        })

    if not out['errors']:
        return None

    for e in out['errors']:
        if e.get('type', 'E') == 'E':
            out['error'] = e['message']
            break

    return out
