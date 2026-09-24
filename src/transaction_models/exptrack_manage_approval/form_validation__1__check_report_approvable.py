# event: form_validation
# form: 1 (Manage Approval - header)
# description: Check that the expense report on the Manage Approval form is in an
#              approvable state before the record is saved.
# functional_specification:
#   - The report must exist and must carry an approver.
#   - A report that is already Approved or Rejected cannot be re-decided (blocking).
#   - A decision of Rejected must carry approver comments (blocking).
#   - The report must have at least one expense line (blocking).
#   - Warn (override-able) when the header TOTAL_AMOUNT does not match the sum of
#     the expense lines, and when an approved line has no receipt attachment.
#   - Inform (prompt) when the report amount exceeds the highest active approval
#     rule limit for its category.


def run(args):
    ignored = set(args.get('_ignore_warnings') or [])
    out = {'errors': []}

    report_id = args.get('REPORT_ID')
    if is_empty(report_id):
        return 'Report ID is required.'

    status = coalesce(args.get('STATUS'), '')
    approver = args.get('APPROVER')
    comments = args.get('APPROVER_COMMENTS')

    if is_empty(approver):
        out['errors'].append({
            'code': 'MAAPRV01', 'field': 'APPROVER', 'type': 'E',
            'message': 'An approver must be assigned before the report can be actioned.'})

    # Current stored decision - a finalised report may not be decided again.
    stored = db.query_one(
        'SELECT STATUS, TOTAL_AMOUNT, CATEGORY FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        ' WHERE REPORT_ID = :r', {'r': report_id})

    if args.get('_action') == 'edit' and stored:
        stored_status = coalesce(stored['STATUS'], '')
        if stored_status in ('Approved', 'Rejected') and status != stored_status:
            out['errors'].append({
                'code': 'MAAPRV02', 'field': 'STATUS', 'type': 'E',
                'message': 'Report ' + str(report_id) + ' is already ' + stored_status +
                           ' and cannot be decided again.'})

    if status == 'Rejected' and is_empty(comments):
        out['errors'].append({
            'code': 'MAAPRV03', 'field': 'APPROVER_COMMENTS', 'type': 'E',
            'message': 'Approver comments are mandatory when rejecting a report.'})

    lines = db.query(
        'SELECT EXPENSE_ID, AMOUNT, RECEIPT_ATTACHMENT FROM ' + db.t('EXPTRACK_EXPENSE') +
        ' WHERE EXPENSE_REPORT = :r', {'r': report_id})

    if not lines:
        out['errors'].append({
            'code': 'MAAPRV04', 'field': 'REPORT_ID', 'type': 'E',
            'message': 'Report ' + str(report_id) + ' has no expense lines to approve.'})
    else:
        line_total = Decimal('0')
        missing_receipt = []
        for ln in lines:
            line_total += Decimal(str(coalesce(to_number(ln['AMOUNT']), 0)))
            if is_empty(ln['RECEIPT_ATTACHMENT']):
                missing_receipt.append(str(ln['EXPENSE_ID']))

        header_total = Decimal(str(coalesce(to_number(args.get('TOTAL_AMOUNT')), 0)))
        if header_total != line_total and 'MAAPRV05' not in ignored:
            out['errors'].append({
                'code': 'MAAPRV05', 'field': 'TOTAL_AMOUNT', 'type': 'W',
                'message': 'Header total (' + str(header_total) + ') does not match the sum of '
                           'expense lines (' + str(line_total) + ').'})

        if status == 'Approved' and missing_receipt and 'MAAPRV06' not in ignored:
            out['errors'].append({
                'code': 'MAAPRV06', 'field': 'RECEIPT_ATTACHMENT', 'type': 'W',
                'message': 'Expense line(s) without a receipt attachment: ' +
                           ', '.join(missing_receipt[:10]) + '.'})

    # Informational: amount above the highest active approval-rule limit.
    category = args.get('CATEGORY')
    if not_empty(category):
        max_limit = db.scalar(
            'SELECT MAX(MAX_AMOUNT) FROM ' + db.t('EXPTRACK_APPROVAL_RULES') +
            ' WHERE CATEGORY = :c AND STATUS = :s', {'c': category, 's': 'A'})
        amt = to_number(args.get('TOTAL_AMOUNT'))
        if max_limit is not None and amt is not None and to_number(max_limit) < amt:
            out['errors'].append({
                'code': 'MAAPRV07', 'field': 'TOTAL_AMOUNT', 'type': 'P',
                'message': 'Report amount exceeds the highest active approval limit (' +
                           str(max_limit) + ') for category ' + str(category) + '.'})

    if not out['errors']:
        return None

    for e in out['errors']:
        if e['type'] == 'E':
            out['error'] = e['message']
            break
    return out
