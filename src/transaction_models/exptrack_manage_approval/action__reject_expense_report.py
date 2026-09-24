# event: action
# description: Reject the expense report currently shown on the Manage Approval screen.
# functional_specification:
#   - Only a report whose stored STATUS is 'Pending' may be rejected.
#   - Approver comments are mandatory for a rejection (blocking).
#   - On rejection: report STATUS and CURRENT_STATUS become 'Rejected', APPROVAL_DATE is
#     stamped with the current timestamp, PROCESSING_STATUS returns to 'Pending' and
#     PAYMENT_STATUS stays 'Pending'.
#   - All expense lines of the report get STATUS and APPROVAL_STATUS = 'Rejected' and
#     inherit the approver and the rejection comments.


def run(args):
    report_id = args.get('REPORT_ID')
    if is_empty(report_id):
        return 'Report ID is required.'

    report = db.query_one(
        'SELECT REPORT_ID, STATUS, APPROVER FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        ' WHERE REPORT_ID = :r', {'r': report_id})
    if not report:
        return 'Expense report ' + str(report_id) + ' was not found.'

    stored_status = coalesce(report['STATUS'], '')
    if stored_status != 'Pending':
        return 'Report ' + str(report_id) + ' is already ' + stored_status + \
               ' and cannot be rejected.'

    comments = args.get('APPROVER_COMMENTS')
    if is_empty(comments):
        return {'error': 'Approver comments are mandatory when rejecting a report.',
                'errors': [{'code': 'MAREJ01', 'field': 'APPROVER_COMMENTS', 'type': 'E',
                            'message': 'Approver comments are mandatory when rejecting '
                                       'a report.'}]}

    approver = coalesce(args.get('APPROVER'), report['APPROVER'])
    if is_empty(approver):
        return 'An approver must be assigned before the report can be rejected.'

    stamp = datetime.datetime.now()

    db.update(db.t('EXPTRACK_EXPENSE_REPORT'), {
        'STATUS': 'Rejected',
        'CURRENT_STATUS': 'Rejected',
        'APPROVAL_DATE': stamp,
        'APPROVER': approver,
        'APPROVER_COMMENTS': comments,
        'PROCESSING_STATUS': 'Pending',
        'PAYMENT_STATUS': 'Pending',
        'CHG_DATE': stamp,
    }, {'REPORT_ID': report_id})

    db.update(db.t('EXPTRACK_EXPENSE'), {
        'STATUS': 'Rejected',
        'APPROVAL_STATUS': 'Rejected',
        'APPROVER': approver,
        'APPROVER_COMMENTS': comments,
        'CHG_DATE': stamp,
    }, {'EXPENSE_REPORT': report_id})

    return {
        'message': 'Report ' + str(report_id) + ' rejected.',
        'updates': {
            'STATUS': 'Rejected',
            'CURRENT_STATUS': 'Rejected',
            'APPROVAL_DATE': stamp,
            'APPROVER': approver,
            'PROCESSING_STATUS': 'Pending',
        },
        'prompts': [{
            'code': 'MAREJ99', 'type': 'P',
            'message': 'Report ' + str(report_id) +
                       ' rejected. The employee can revise and resubmit it.'}],
    }
