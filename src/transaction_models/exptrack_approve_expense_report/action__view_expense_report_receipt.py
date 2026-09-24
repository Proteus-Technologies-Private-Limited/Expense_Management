# project: Expense_Management
# object_type: T
# object_name: exptrack_approve_expense_report
# event_type: action
# function_name: view_expense_report_receipt
# action_name: View Receipt
# language: python
# description: Show the receipt attachment for this report
# functional_specification: Given RECEIPT_ATTACHMENT from the current form payload, return {"html": "..."} containing an <img>/<embed> or a download link pointing at the RECEIPT_ATTACHMENT URL so the approver can view the receipt in a modal. If RECEIPT_ATTACHMENT is blank, return {"html": "<p>No receipt attached.</p>"}.
# business_logic: Show the receipt attachment for this report


def run(args):
    url = args.get('RECEIPT_ATTACHMENT')
    if is_empty(url) or not str(url).strip():
        return {'html': '<p>No receipt attached.</p>'}

    url = str(url).strip()
    safe = (url.replace('&', '&amp;').replace('<', '&lt;')
               .replace('>', '&gt;').replace('"', '&quot;'))
    lower = url.lower().split('?')[0]

    if lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg')):
        body = ('<img src="' + safe + '" alt="Receipt" '
                'style="max-width:100%;max-height:70vh;display:block;margin:0 auto;" />')
    elif lower.endswith('.pdf'):
        body = ('<embed src="' + safe + '" type="application/pdf" '
                'style="width:100%;height:70vh;border:0;" />')
    else:
        body = '<p>This receipt type cannot be previewed inline.</p>'

    link = ('<p style="margin-top:8px;text-align:center;">'
            '<a href="' + safe + '" target="_blank" rel="noopener noreferrer">'
            'Open / download receipt</a></p>')

    return {'html': '<div style="text-align:center;">' + body + link + '</div>'}
