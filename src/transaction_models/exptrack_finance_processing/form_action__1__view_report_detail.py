# project: Expense_Management
# object_type: T
# object_name: exptrack_finance_processing
# event_type: form_action
# function_name: view_report_detail
# form_no: 1
# action_name: View Report
# language: python
# description: Show the linked expense report and its lines
# functional_specification: Payload is the clicked EXPTRACK_EXPENSE_REPORT row, flat. Read REPORT_ID. SELECT the report header (REPORT_ID, REPORT_TITLE, EMPLOYEE, REPORT_DATE, TOTAL_AMOUNT, CURRENCY, STATUS, APPROVER, APPROVAL_DATE, PAYMENT_STATUS, PROCESSING_STATUS, PROCESSING_REMARKS) from EXPTRACK_EXPENSE_REPORT, and its expense lines (EXPENSE_ID, EXPENSE_DATE, CATEGORY, DESCRIPTION, PAYMENT_METHOD, AMOUNT, CURRENCY, APPROVAL_STATUS, RECEIPT_ATTACHMENT) from EXPTRACK_EXPENSE WHERE EXPENSE_REPORT = the report id, ordered by EXPENSE_DATE. Render a read-only HTML fragment: a header definition block followed by a table of the lines and a total row, with RECEIPT_ATTACHMENT rendered as a link when present. Return {"html": "..."}. Read-only - this function must never write.
# business_logic: Show the linked expense report and its lines


def run(args):
    report_id = args.get('REPORT_ID')
    if is_empty(report_id):
        return {'error': 'Report id is missing.'}
    report_id = str(report_id).strip()

    hdr = db.query_one(
        'SELECT REPORT_ID, REPORT_TITLE, EMPLOYEE, REPORT_DATE, TOTAL_AMOUNT,'
        '       CURRENCY, STATUS, APPROVER, APPROVAL_DATE, PAYMENT_STATUS,'
        '       PROCESSING_STATUS, PROCESSING_REMARKS'
        '  FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') +
        ' WHERE REPORT_ID = :rid',
        {'rid': report_id})
    if not hdr:
        return {'error': 'Report ' + report_id + ' was not found.'}

    lines = db.query(
        'SELECT EXPENSE_ID, EXPENSE_DATE, CATEGORY, DESCRIPTION, PAYMENT_METHOD,'
        '       AMOUNT, CURRENCY, APPROVAL_STATUS, RECEIPT_ATTACHMENT'
        '  FROM ' + db.t('EXPTRACK_EXPENSE') +
        ' WHERE EXPENSE_REPORT = :rid'
        ' ORDER BY EXPENSE_DATE',
        {'rid': report_id}) or []

    def esc(v):
        if v is None:
            return ''
        s = str(v).strip()
        return (s.replace('&', '&amp;').replace('<', '&lt;')
                 .replace('>', '&gt;').replace('"', '&quot;'))

    def money(v):
        n = to_number(v)
        if n is None:
            return ''
        return '{:,.2f}'.format(float(n))

    hdr_fields = [
        ('Report ID', hdr.get('REPORT_ID')),
        ('Title', hdr.get('REPORT_TITLE')),
        ('Employee', hdr.get('EMPLOYEE')),
        ('Report Date', hdr.get('REPORT_DATE')),
        ('Total Amount', money(hdr.get('TOTAL_AMOUNT'))),
        ('Currency', hdr.get('CURRENCY')),
        ('Status', hdr.get('STATUS')),
        ('Approver', hdr.get('APPROVER')),
        ('Approval Date', hdr.get('APPROVAL_DATE')),
        ('Payment Status', hdr.get('PAYMENT_STATUS')),
        ('Processing Status', hdr.get('PROCESSING_STATUS')),
        ('Processing Remarks', hdr.get('PROCESSING_REMARKS')),
    ]

    parts = []
    parts.append('<div class="exp-report-detail" style="font-family:sans-serif;font-size:13px;">')
    parts.append('<h3 style="margin:0 0 8px 0;">Expense Report ' + esc(report_id) + '</h3>')
    parts.append('<dl style="display:grid;grid-template-columns:auto 1fr;'
                 'gap:4px 12px;margin:0 0 14px 0;">')
    for label, value in hdr_fields:
        parts.append('<dt style="font-weight:600;color:#555;">' + esc(label) + '</dt>')
        parts.append('<dd style="margin:0;">' + esc(value) + '</dd>')
    parts.append('</dl>')

    parts.append('<table border="1" cellspacing="0" cellpadding="4" '
                 'style="border-collapse:collapse;width:100%;">')
    parts.append('<thead><tr style="background:#f0f0f0;">'
                 '<th align="left">Expense ID</th>'
                 '<th align="left">Date</th>'
                 '<th align="left">Category</th>'
                 '<th align="left">Description</th>'
                 '<th align="left">Payment Method</th>'
                 '<th align="right">Amount</th>'
                 '<th align="left">Currency</th>'
                 '<th align="left">Approval Status</th>'
                 '<th align="left">Receipt</th>'
                 '</tr></thead><tbody>')

    total = Decimal('0')
    if not lines:
        parts.append('<tr><td colspan="9" align="center">No expense lines.</td></tr>')
    for ln in lines:
        amt = to_number(ln.get('AMOUNT'))
        if amt is not None:
            total = total + Decimal(str(amt))
        receipt = ln.get('RECEIPT_ATTACHMENT')
        if not_empty(receipt) and str(receipt).strip():
            r = esc(receipt)
            receipt_html = ('<a href="' + r + '" target="_blank" '
                            'rel="noopener noreferrer">View</a>')
        else:
            receipt_html = ''
        parts.append(
            '<tr>'
            '<td>' + esc(ln.get('EXPENSE_ID')) + '</td>'
            '<td>' + esc(ln.get('EXPENSE_DATE')) + '</td>'
            '<td>' + esc(ln.get('CATEGORY')) + '</td>'
            '<td>' + esc(ln.get('DESCRIPTION')) + '</td>'
            '<td>' + esc(ln.get('PAYMENT_METHOD')) + '</td>'
            '<td align="right">' + esc(money(ln.get('AMOUNT'))) + '</td>'
            '<td>' + esc(ln.get('CURRENCY')) + '</td>'
            '<td>' + esc(ln.get('APPROVAL_STATUS')) + '</td>'
            '<td>' + receipt_html + '</td>'
            '</tr>')

    parts.append('</tbody><tfoot><tr style="background:#f7f7f7;font-weight:600;">'
                 '<td colspan="5" align="right">Total</td>'
                 '<td align="right">' + esc(money(total)) + '</td>'
                 '<td>' + esc(hdr.get('CURRENCY')) + '</td>'
                 '<td colspan="2"></td>'
                 '</tr></tfoot></table>')
    parts.append('</div>')

    return {'html': ''.join(parts)}
