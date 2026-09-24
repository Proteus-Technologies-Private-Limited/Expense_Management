# project: Expense_Management
# object_type: T
# object_name: exptrack_finance_processing
# event_type: form_validation
# function_name: check_not_processed
# form_no: 1
# language: python
# description: Block edits to an already-processed report
# functional_specification: Runs on save. If args['_action'] is 'add', return None. Otherwise read REPORT_ID from the payload and SELECT PROCESSING_STATUS FROM EXPTRACK_EXPENSE_REPORT WHERE REPORT_ID = that id. If the STORED PROCESSING_STATUS is 'Processed', return {"error": "Report <REPORT_ID> is already processed and cannot be changed."} - the stored value is checked, not the payload value, so a user cannot unlock the row by changing the dropdown before saving. Otherwise return None. Read-only - this function must never write.
# business_logic: Block edits to an already-processed report


def run(args):
    if args.get('_action') == 'add':
        return None

    report_id = args.get('REPORT_ID')
    if is_empty(report_id):
        return None
    report_id = str(report_id).strip()

    stored = db.scalar(
        'SELECT PROCESSING_STATUS FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        ' WHERE REPORT_ID = :rid',
        {'rid': report_id})

    if not_empty(stored) and str(stored).strip() == 'Processed':
        return {'error': 'Report ' + report_id +
                ' is already processed and cannot be changed.'}

    return None
