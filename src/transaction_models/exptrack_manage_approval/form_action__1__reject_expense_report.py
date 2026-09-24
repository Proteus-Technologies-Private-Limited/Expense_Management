# event: form_action
# form: 1 (Manage Approval - header)
# description: Form-level "Reject" button on the Manage Approval header form.
# functional_specification:
#   - Rejects the report identified by REPORT_ID on the header form.
#   - Blocks when the report does not exist, is not 'Pending', has no approver, or when
#     APPROVER_COMMENTS (the rejection reason) is empty.
#   - Sets report STATUS/CURRENT_STATUS = 'Rejected', stamps APPROVAL_DATE, resets
#     PROCESSING_STATUS to 'Pending', keeps PAYMENT_STATUS 'Pending' and stores the
#     rejection comments; cascades 'Rejected' to every expense line of the report.


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

    out = {'errors': []}

    comments = args.get('APPROVER_COMMENTS')
    if is_empty(comments):
        out['errors'].append({
            'code': 'MAFREJ01', 'field': 'APPROVER_COMMENTS', 'type': 'E',
            'message': 'Enter the rejection reason in Approver Comments before rejecting.'})

    approver = coalesce(args.get('APPROVER'), report['APPROVER'])
    if is_empty(approver):
        out['errors'].append({
            'code': 'MAFREJ02', 'field': 'APPROVER', 'type': 'E',
            'message': 'An approver must be assigned before the report can be rejected.'})

    if out['errors']:
        out['error'] = out['errors'][0]['message']
        return out

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
            'APPROVER_COMMENTS': {'value': comments, 'protect': '1'},
        },
    }
