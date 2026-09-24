# project: Expense_Management
# object_type: T
# object_name: exptrack_finance_processing
# event_type: form_action
# function_name: process_report
# form_no: 1
# action_name: Process
# language: python
# description: Mark the approved report as Processed
# functional_specification: Payload is the clicked EXPTRACK_EXPENSE_REPORT row, flat. Read REPORT_ID. UPDATE EXPTRACK_EXPENSE_REPORT SET PROCESSING_STATUS = 'Processed', PROCESSED_DATE = the current date, PROCESSED_BY = the logged-in Finance user's short id, CHG_DATE = current timestamp WHERE REPORT_ID = the payload's REPORT_ID AND STATUS = 'Approved' AND (PROCESSING_STATUS IS NULL OR PROCESSING_STATUS <> 'Processed'). If no row is updated, return {"error": "Report <REPORT_ID> is already processed or is not an approved report."}. On success return {"message": "Report <REPORT_ID> marked as Processed."}. Use portable SQL only - no RETURNING, no schema qualification.
# business_logic: Mark the approved report as Processed


def run(args):
    report_id = args.get('REPORT_ID')
    if is_empty(report_id):
        return {'error': 'Report id is missing.'}
    report_id = str(report_id).strip()

    # The logged-in user's short id is carried on the row's audit columns.
    processed_by = coalesce(args.get('CHG_USER'), args.get('ADD_USER'),
                            args.get('PROCESSED_BY'))
    if not_empty(processed_by):
        processed_by = str(processed_by).strip()[:10]
    else:
        processed_by = None

    row = db.query_one(
        'SELECT REPORT_ID FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        " WHERE REPORT_ID = :rid AND STATUS = 'Approved'"
        "   AND (PROCESSING_STATUS IS NULL OR PROCESSING_STATUS <> 'Processed')",
        {'rid': report_id})
    if not row:
        return {'error': 'Report ' + report_id +
                ' is already processed or is not an approved report.'}

    db.execute(
        'UPDATE ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        " SET PROCESSING_STATUS = 'Processed',"
        "     PROCESSED_DATE = :pdate,"
        "     PROCESSED_BY = :puser,"
        "     CHG_DATE = :chg"
        " WHERE REPORT_ID = :rid AND STATUS = 'Approved'"
        "   AND (PROCESSING_STATUS IS NULL OR PROCESSING_STATUS <> 'Processed')",
        {'pdate': today(), 'puser': processed_by, 'chg': now(), 'rid': report_id})

    return {'message': 'Report ' + report_id + ' marked as Processed.'}
