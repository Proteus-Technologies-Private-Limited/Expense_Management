# project: Expense_Management
# object_type: T
# object_name: exptrack_trip
# event_type: form_action
# function_name: close_trip
# form_no: 1
# action_name: Close-trip
# language: python
# description: Close the trip
# functional_specification: Set STATUS to 'Closed' on the current trip record and return the updated status as a protected (read-only) field so the trip is locked from further manual status changes. Reopening a Closed trip is not permitted anywhere in this flow.
# business_logic: Close the trip

CLOSED = 'Closed'


def run(args):
    trip_id = args.get('TRIP_ID')
    if is_empty(trip_id):
        return {'error': 'Trip ID is required to close the trip.'}

    row = db.query_one(
        'SELECT trip_id, status FROM ' + db.t('exptrack_trip') + ' WHERE trip_id = :t',
        {'t': trip_id})
    if row is None:
        return {'error': 'Trip ' + str(trip_id) + ' does not exist.'}

    current = (row.get('status') or row.get('STATUS') or '').strip()

    if current == CLOSED:
        # Already closed; reopening is not permitted, so simply keep it locked.
        return {
            'prompts': [{'code': 'TRPCL1', 'field': 'status', 'type': 'P',
                         'message': 'Trip is already closed.'}],
            'updates': {'STATUS': {'value': CLOSED, 'protect': '1'}},
        }

    db.update('exptrack_trip', {'status': CLOSED}, {'trip_id': trip_id})

    return {
        'prompts': [{'code': 'TRPCL2', 'field': 'status', 'type': 'P',
                     'message': 'Trip closed. Status can no longer be changed.'}],
        'updates': {'STATUS': {'value': CLOSED, 'protect': '1'}},
    }
