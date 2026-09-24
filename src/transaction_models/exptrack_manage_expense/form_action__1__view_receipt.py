# project: Expense_Management
# object_type: T
# object_name: exptrack_manage_expense
# event_type: form_action
# function_name: view_receipt
# form_no: 1
# action_name: View Receipt
# language: python
# description: Show the report's receipt attachments
# functional_specification: For the clicked REPORT_ID, return {"html": "..."} rendering the report's RECEIPT_ATTACHMENT URL plus the RECEIPT_ATTACHMENT of every EXPTRACK_EXPENSE row whose EXPENSE_REPORT = REPORT_ID, each as a clickable link (and an inline <img> when the URL ends in an image extension), labelled with the expense id, date, category and amount. When there is no attachment at all, return html saying no receipt was uploaded for this report.
# business_logic: Show the report's receipt attachments


def run(args):
    report_id = args.get('REPORT_ID')
    if is_empty(report_id):
        return {'html': '<div style="padding:12px;font-family:sans-serif;">No report selected.</div>'}

    report_id = str(report_id).strip()

    def esc(v):
        if v is None:
            return ''
        s = str(v)
        s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return s.replace('"', '&quot;')

    def is_image(url):
        u = str(url).strip().lower()
        # drop any query string before checking the extension
        u = u.split('?')[0].split('#')[0]
        for ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.tif', '.tiff'):
            if u.endswith(ext):
                return True
        return False

    def fmt_date(v):
        if is_empty(v):
            return ''
        d = to_date(v)
        if d is not None:
            try:
                return d.strftime('%Y-%m-%d')
            except Exception:
                pass
        return str(v)[:10]

    hdr = db.query_one(
        'SELECT REPORT_ID, REPORT_TITLE, RECEIPT_ATTACHMENT, CURRENCY '
        'FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') + ' WHERE REPORT_ID = :r',
        {'r': report_id})

    lines = db.query(
        'SELECT EXPENSE_ID, EXPENSE_DATE, CATEGORY, AMOUNT, CURRENCY, RECEIPT_ATTACHMENT '
        'FROM ' + db.t('EXPTRACK_EXPENSE') + ' WHERE EXPENSE_REPORT = :r '
        'ORDER BY EXPENSE_DATE, EXPENSE_ID',
        {'r': report_id}) or []

    def block(url, label):
        u = str(url).strip()
        out = ['<div style="margin:0 0 14px 0;padding:10px;border:1px solid #ddd;border-radius:6px;">']
        out.append('<div style="font-weight:600;margin-bottom:6px;">' + label + '</div>')
        out.append('<div><a href="' + esc(u) + '" target="_blank" rel="noopener noreferrer">'
                   + esc(u) + '</a></div>')
        if is_image(u):
            out.append('<div style="margin-top:8px;"><img src="' + esc(u)
                       + '" alt="' + label + '" style="max-width:420px;max-height:320px;'
                       'border:1px solid #eee;border-radius:4px;" /></div>')
        out.append('</div>')
        return ''.join(out)

    parts = []
    title = ''
    if hdr and not_empty(hdr.get('REPORT_TITLE')):
        title = ' &ndash; ' + esc(str(hdr.get('REPORT_TITLE')).strip())

    if hdr and not_empty(hdr.get('RECEIPT_ATTACHMENT')):
        parts.append(block(hdr.get('RECEIPT_ATTACHMENT'),
                           'Report receipt (' + esc(report_id) + ')'))

    # category names for nicer labels
    cat_names = {}
    for ln in lines:
        code = ln.get('CATEGORY')
        if not_empty(code):
            cat_names[str(code).strip()] = str(code).strip()
    if cat_names:
        rows = db.query(
            'SELECT CATEGORY_CODE, CATEGORY_NAME FROM ' + db.t('EXPTRACK_EXPENSE_CATEGORY'),
            {}) or []
        for r in rows:
            code = r.get('CATEGORY_CODE')
            if not_empty(code) and str(code).strip() in cat_names:
                cat_names[str(code).strip()] = str(r.get('CATEGORY_NAME') or code).strip()

    for ln in lines:
        url = ln.get('RECEIPT_ATTACHMENT')
        if is_empty(url):
            continue
        cat_code = '' if is_empty(ln.get('CATEGORY')) else str(ln.get('CATEGORY')).strip()
        cat = cat_names.get(cat_code, cat_code)
        amt = to_number(ln.get('AMOUNT')) or 0
        cur = '' if is_empty(ln.get('CURRENCY')) else str(ln.get('CURRENCY')).strip()
        label = esc(str(ln.get('EXPENSE_ID') or '').strip())
        bits = [fmt_date(ln.get('EXPENSE_DATE')), cat, ('%s %.2f' % (cur, float(amt))).strip()]
        bits = [b for b in bits if b]
        if bits:
            label = label + ' &middot; ' + esc(' | '.join(bits))
        parts.append(block(url, label))

    if not parts:
        return {'html': '<div style="padding:12px;font-family:sans-serif;">'
                        'No receipt was uploaded for report <b>' + esc(report_id) + '</b>'
                        + title + '.</div>'}

    html = ('<div style="padding:12px;font-family:sans-serif;">'
            '<h3 style="margin:0 0 12px 0;">Receipts for ' + esc(report_id) + title + '</h3>'
            + ''.join(parts) + '</div>')
    return {'html': html}
