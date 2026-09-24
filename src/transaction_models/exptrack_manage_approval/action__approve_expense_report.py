# event: action
# description: Approve the expense report currently shown on the Manage Approval screen.
# functional_specification:
#   - Only a report whose stored STATUS is 'Pending' may be approved.
#   - The report must have at least one expense line.
#   - On approval: report STATUS and CURRENT_STATUS become 'Approved', APPROVAL_DATE is
#     stamped with the current timestamp, PROCESSING_STATUS moves to 'In Progress',
#     PAYMENT_STATUS stays 'Pending' and the approver comments entered on the form are kept.
#   - All expense lines of the report get STATUS and APPROVAL_STATUS = 'Approved' and
#     inherit the approver and the approver comments.
#   - Warn (override-able) when any expense line has no receipt attachment.


def run(args):
    ignored = set(args.get('_ignore_warnings') or [])
    out = {'errors': []}

    report_id = args.get('REPORT_ID')
    if is_empty(report_id):
        return 'Report ID is required.'

    report = db.query_one(
        'SELECT REPORT_ID, STATUS, APPROVER, TOTAL_AMOUNT FROM ' +
        db.t('EXPTRACK_EXPENSE_REPORT') + ' WHERE REPORT_ID = :r', {'r': report_id})
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
    if missing_receipt and 'MAAPP01' not in ignored:
        out['errors'].append({
            'code': 'MAAPP01', 'field': 'RECEIPT_ATTACHMENT', 'type': 'W',
            'message': 'Expense line(s) without a receipt attachment: ' +
                       ', '.join(missing_receipt[:10]) + '. Approve anyway?'})
        return out

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
        },
        'prompts': [{
            'code': 'MAAPP99', 'type': 'P',
            'message': 'Report ' + str(report_id) + ' approved and sent for processing.'}],
    }
