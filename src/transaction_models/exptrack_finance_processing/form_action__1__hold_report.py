# project: Expense_Management
# object_type: T
# object_name: exptrack_finance_processing
# event_type: form_action
# function_name: hold_report
# form_no: 1
# action_name: Hold
# language: python
# description: Put the approved report On Hold
# functional_specification: Payload is the clicked EXPTRACK_EXPENSE_REPORT row, flat. Read REPORT_ID and PROCESSING_REMARKS. If PROCESSING_REMARKS is blank, return {"error": "Remarks are mandatory when a report is put On Hold."}. Otherwise UPDATE EXPTRACK_EXPENSE_REPORT SET PROCESSING_STATUS = 'On Hold', PROCESSING_REMARKS = the payload's remarks, CHG_DATE = current timestamp WHERE REPORT_ID = the payload's REPORT_ID AND STATUS = 'Approved' AND (PROCESSING_STATUS IS NULL OR PROCESSING_STATUS <> 'Processed'). If no row is updated, return {"error": "Report <REPORT_ID> is already processed or is not an approved report."}. On success return {"message": "Report <REPORT_ID> put On Hold."}. Use portable SQL only.
# business_logic: Put the approved report On Hold


def run(args):
    report_id = args.get('REPORT_ID')
    if is_empty(report_id):
        return {'error': 'Report id is missing.'}
    report_id = str(report_id).strip()

    remarks = args.get('PROCESSING_REMARKS')
    if is_empty(remarks) or not str(remarks).strip():
        return {'error': 'Remarks are mandatory when a report is put On Hold.'}
    remarks = str(remarks).strip()

    # Only an approved, not-yet-processed report may be put On Hold.
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
        " SET PROCESSING_STATUS = 'On Hold',"
        "     PROCESSING_REMARKS = :rem,"
        "     CHG_DATE = :chg"
        " WHERE REPORT_ID = :rid AND STATUS = 'Approved'"
        "   AND (PROCESSING_STATUS IS NULL OR PROCESSING_STATUS <> 'Processed')",
        {'rem': remarks, 'chg': now(), 'rid': report_id})

    return {'message': 'Report ' + report_id + ' put On Hold.'}
