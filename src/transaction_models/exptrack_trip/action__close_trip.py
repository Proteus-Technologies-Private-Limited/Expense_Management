# project: Expense_Management
# object_type: T
# object_name: exptrack_trip
# event_type: action
# function_name: close_trip
# action_name: Close Trip
# language: python
# description: Close the trip and lock it from further expense linkage
# functional_specification: Given the trip record's TRIP_ID and current STATUS from the payload: if STATUS is already 'Closed', return an error 'Trip is already closed.'. Otherwise UPDATE EXPTRACK_TRIP SET STATUS = 'Closed' WHERE TRIP_ID = the payload's trip id. Return a confirmation message 'Trip <TRIP_ID> has been closed.' Reopening a closed trip is not permitted anywhere in this application; once STATUS = 'Closed' no further expense can be linked to this trip (enforced by the Expense object's cross_update / validation against this trip's STATUS).
# business_logic: Close the trip and lock it from further expense linkage


def run(args):
    trip_id = args.get('TRIP_ID')
    if is_empty(trip_id):
        return 'Trip ID is required.'
    trip_id = str(trip_id).strip()

    row = db.query_one(
        'SELECT trip_id, status FROM ' + db.t('exptrack_trip') + ' WHERE trip_id = :t',
        {'t': trip_id}
    )
    if not row:
        return 'Trip ' + trip_id + ' does not exist.'

    current_status = coalesce(row.get('status'), row.get('STATUS'), args.get('STATUS'), '')
    if str(current_status).strip() == 'Closed':
        return 'Trip is already closed.'

    db.update(
        'exptrack_trip',
        {'status': 'Closed', 'chg_date': now()},
        {'trip_id': trip_id}
    )

    return {
        'prompts': [{
            'code': 'TRPCLS1',
            'field': 'STATUS',
            'type': 'P',
            'message': 'Trip ' + trip_id + ' has been closed.'
        }],
        'updates': {'STATUS': {'value': 'Closed', 'protect': '1'}}
    }
