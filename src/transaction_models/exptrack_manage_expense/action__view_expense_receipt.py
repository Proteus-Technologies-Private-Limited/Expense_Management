# project: Expense_Management
# object_type: T
# object_name: exptrack_manage_expense
# event_type: action
# function_name: view_expense_receipt
# action_name: View Receipt
# language: python
# description: Show the attached receipt for the selected expense
# functional_specification: Payload is the FLAT EXPTRACK_EXPENSE row. Read RECEIPT_ATTACHMENT (the stored file URL). If blank, return {"error": "No receipt attached."}. Otherwise return {"html": "..."} rendering the receipt for review - an <img> tag when the URL ends in an image extension (.png/.jpg/.jpeg/.gif/.webp), otherwise an <iframe> for a PDF plus a plain download link. Include the expense id, date, category name, amount with currency and description above the attachment so the approver sees the full context.
# business_logic: Show the attached receipt for the selected expense


def _val(args, name):
    """Case-insensitive payload read."""
    if name in args:
        return args[name]
    return args.get(name.lower())


def _txt(v):
    return '' if v is None else str(v).strip()


def _esc(v):
    s = _txt(v)
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return s.replace('"', '&quot;').replace("'", '&#39;')


def run(args):
    url = _txt(_val(args, 'RECEIPT_ATTACHMENT'))
    if not url:
        return {'error': 'No receipt attached.'}

    expense_id = _txt(_val(args, 'EXPENSE_ID'))
    expense_date = _txt(_val(args, 'EXPENSE_DATE'))[:10]
    currency = _txt(_val(args, 'CURRENCY'))
    description = _txt(_val(args, 'DESCRIPTION'))

    amount = to_number(_val(args, 'AMOUNT'))
    amount_txt = '' if amount is None else '{0:,.2f}'.format(float(amount))

    # Category name: prefer the form's denormalised value, else resolve from the master.
    category_code = _txt(_val(args, 'CATEGORY'))
    category_name = _txt(_val(args, 'CATEGORY_NAME'))
    if not category_name and category_code:
        row = db.query_one(
            'SELECT CATEGORY_NAME FROM ' + db.t('EXPTRACK_EXPENSE_CATEGORY') +
            ' WHERE CATEGORY_CODE = :c', {'c': category_code})
        if row:
            category_name = _txt(row.get('CATEGORY_NAME') or row.get('category_name'))
    if not category_name:
        category_name = category_code

    safe_url = _esc(url)
    lower_url = url.split('?')[0].lower()
    is_image = lower_url.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))

    header = (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.6;'
        'margin-bottom:10px">'
        '<div style="font-size:15px;font-weight:600;margin-bottom:6px">Receipt &ndash; Expense '
        + _esc(expense_id) + '</div>'
        '<div><b>Date:</b> ' + _esc(expense_date) + '</div>'
        '<div><b>Category:</b> ' + _esc(category_name) + '</div>'
        '<div><b>Amount:</b> ' + _esc(currency) + ' ' + _esc(amount_txt) + '</div>'
        '<div><b>Description:</b> ' + (_esc(description) if description else '&ndash;') + '</div>'
        '</div>')

    if is_image:
        body = ('<img src="' + safe_url + '" alt="Receipt for expense ' + _esc(expense_id) + '" '
                'style="max-width:100%;border:1px solid #ccc;border-radius:4px" />')
    else:
        body = ('<iframe src="' + safe_url + '" title="Receipt for expense ' + _esc(expense_id) +
                '" style="width:100%;height:600px;border:1px solid #ccc;border-radius:4px">'
                '</iframe>')

    link = ('<div style="margin-top:10px;font-family:Arial,Helvetica,sans-serif;font-size:13px">'
            '<a href="' + safe_url + '" target="_blank" rel="noopener">Download / open receipt</a>'
            '</div>')

    return {'html': '<div>' + header + body + link + '</div>'}
