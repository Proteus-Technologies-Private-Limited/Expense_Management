# project: Expense_Management
# object_type: T
# object_name: exptrack_expense
# event_type: form_validation
# function_name: log_expense_activity
# form_no: 1
# language: python
# description: Write an Activity Log entry for add/update/delete of an expense
# functional_specification: On add/edit/delete of an EXPTRACK_EXPENSE row, insert an Activity Log entry capturing the actor (logged-in user), the action performed (Added/Updated/Deleted), the expense_id, and a narrative description (e.g. 'John Doe added Expense EXP-1023'). Use payload's _action ('add'/'edit') to determine wording; this validation never blocks the save (always return null/None on success), it only records the log entry as a side effect.
# business_logic: Write an Activity Log entry for add/update/delete of an expense


def run(args):
    """Record an activity-log entry for the expense being added/edited.

    This is purely a side-effect recorder: it must never block the save, so
    every path returns None.
    """
    action = args.get('_action') or 'add'
    verb = 'added' if action == 'add' else 'updated'

    expense_id = args.get('EXPENSE_ID')
    # Actor: on edit the row carries CHG_USER, on add ADD_USER is stamped.
    actor = coalesce(args.get('CHG_USER') if action == 'edit' else None,
                     args.get('ADD_USER'),
                     args.get('EMPLOYEE'),
                     'System')

    amount = to_number(args.get('AMOUNT')) or 0
    currency = coalesce(args.get('CURRENCY'), '')

    narrative = '%s %s Expense %s (%s %s)' % (
        actor, verb, coalesce(expense_id, '(new)'), currency, amount)

    payload = {
        'object_name': 'exptrack_expense',
        'expense_id': expense_id,
        'action': 'Added' if action == 'add' else 'Updated',
        'actor': actor,
        'employee': args.get('EMPLOYEE'),
        'expense_report': args.get('EXPENSE_REPORT'),
        'category': args.get('CATEGORY'),
        'trip': args.get('TRIP'),
        'amount': amount,
        'currency': currency,
        'status': args.get('STATUS'),
        'description': narrative,
        'logged_at': now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    try:
        api.emit_event('exptrack_activity_log', payload)
    except Exception:
        # Logging must never prevent the user from saving the expense.
        pass

    return None
