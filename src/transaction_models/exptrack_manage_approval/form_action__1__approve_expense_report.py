# event: form_action
# form: 1 (Manage Approval - header)
# description: Form-level "Approve" button on the Manage Approval header form.
# functional_specification:
#   - Approves the report identified by REPORT_ID on the header form.
#   - Blocks when the report does not exist, is not 'Pending', has no approver or has
#     no expense lines.
#   - Warns (override-able, code MAFAPP01) when any expense line has no receipt.
#   - Sets report STATUS/CURRENT_STATUS = 'Approved', stamps APPROVAL_DATE, moves
#     PROCESSING_STATUS to 'In Progress', keeps PAYMENT_STATUS 'Pending' and stores the
#     approver comments; cascades 'Approved' to every expense line of the report.


def run(args):
    ignored = set(args.get('_ignore_warnings') or [])

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
               ' and cannot be approved.'

    approver = coalesce(args.get('APPROVER'), report['APPROVER'])
    if is_empty(approver):
        return 'An approver must be assigned before the report can be approved.'

    comments = args.get('APPROVER_COMMENTS')

    lines = db.query(
        'SELECT EXPENSE_ID, RECEIPT_ATTACHMENT FROM ' + db.t('EXPTRACK_EXPENSE') +
        ' WHERE EXPENSE_REPORT = :r', {'r': report_id})
    if not lines:
        return 'Report ' + str(report_id) + ' has no expense lines to approve.'

    missing_receipt = [str(ln['EXPENSE_ID']) for ln in lines if is_empty(ln['RECEIPT_ATTACHMENT'])]
    if missing_receipt and 'MAFAPP01' not in ignored:
        return {'errors': [{
            'code': 'MAFAPP01', 'field': 'RECEIPT_ATTACHMENT', 'type': 'W',
            'message': 'Expense line(s) without a receipt attachment: ' +
                       ', '.join(missing_receipt[:10]) + '. Approve anyway?'}]}

    stamp = datetime.datetime.now()

    db.update(db.t('EXPTRACK_EXPENSE_REPORT'), {
        'STATUS': 'Approved',
        'CURRENT_STATUS': 'Approved',
        'APPROVAL_DATE': stamp,
        'APPROVER': approver,
        'APPROVER_COMMENTS': comments,
        'PROCESSING_STATUS': 'In Progress',
        'PAYMENT_STATUS': 'Pending',
        'CHG_DATE': stamp,
    }, {'REPORT_ID': report_id})

    db.update(db.t('EXPTRACK_EXPENSE'), {
        'STATUS': 'Approved',
        'APPROVAL_STATUS': 'Approved',
        'APPROVER': approver,
        'APPROVER_COMMENTS': comments,
        'CHG_DATE': stamp,
    }, {'EXPENSE_REPORT': report_id})

    return {
        'message': 'Report ' + str(report_id) + ' approved (' + str(len(lines)) +
                   ' expense line(s)).',
        'updates': {
            'STATUS': 'Approved',
            'CURRENT_STATUS': 'Approved',
            'APPROVAL_DATE': stamp,
            'APPROVER': approver,
            'PROCESSING_STATUS': 'In Progress',
            'APPROVER_COMMENTS': {'value': comments, 'protect': '1'},
        },
    }
