# project: Expense_Management
# object_type: T
# object_name: exptrack_budget_limitation
# event_type: form_action
# function_name: view_budget_limitation
# form_no: 1
# action_name: View
# language: python
# description: Read-only display of budget limitation details
# functional_specification: Return an HTML modal showing the current row's Finance Name (FINANCE_NAME), Department (DEPARTMENT) and Budget Document (BUDGET_DOCUMENT) as read-only, labelled fields. No save/edit control is included; this is a display-only view for the Employee role.
# business_logic: Read-only display of budget limitation details


def _esc(v):
    """HTML-escape a value, returning a dash for empties."""
    if is_empty(v):
        return '-'
    s = str(v)
    return (s.replace('&', '&amp;')
             .replace('<', '&lt;')
             .replace('>', '&gt;')
             .replace('"', '&quot;')
             .replace("'", '&#39;'))


def _field(label, value):
    return (
        '<div style="margin-bottom:14px;">'
        '<div style="font-size:12px;color:#6b7280;text-transform:uppercase;'
        'letter-spacing:.4px;margin-bottom:4px;">' + _esc(label) + '</div>'
        '<div style="font-size:14px;color:#111827;font-weight:500;'
        'word-break:break-all;">' + _esc(value) + '</div>'
        '</div>'
    )


def run(args):
    limit_id = args.get('BUDGET_LIMITATION_ID')

    finance_name = args.get('FINANCE_NAME')
    department = args.get('DEPARTMENT')
    budget_document = args.get('BUDGET_DOCUMENT')

    # Prefer the stored row so the view always reflects committed data.
    if not_empty(limit_id):
        row = db.query_one(
            'SELECT FINANCE_NAME, DEPARTMENT, BUDGET_DOCUMENT FROM '
            + db.t('EXPTRACK_BUDGET_LIMITATION')
            + ' WHERE BUDGET_LIMITATION_ID = :id',
            {'id': limit_id})
        if row:
            finance_name = row['FINANCE_NAME']
            department = row['DEPARTMENT']
            budget_document = row['BUDGET_DOCUMENT']
        else:
            return 'Budget limitation record not found.'

    doc_html = _esc(budget_document)
    if not_empty(budget_document):
        doc_html = ('<a href="' + _esc(budget_document) + '" target="_blank" '
                    'rel="noopener noreferrer" style="color:#2563eb;'
                    'text-decoration:underline;word-break:break-all;">'
                    + _esc(budget_document) + '</a>')

    html = (
        '<div style="font-family:Segoe UI,Arial,sans-serif;max-width:560px;'
        'padding:18px 20px;">'
        '<h3 style="margin:0 0 4px 0;font-size:18px;color:#111827;">'
        'Budget Limitation Details</h3>'
        '<div style="font-size:12px;color:#6b7280;margin-bottom:16px;">'
        'Reference: ' + _esc(limit_id) + '</div>'
        '<div style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;'
        'background:#f9fafb;">'
        + _field('Finance Name', finance_name)
        + _field('Department', department)
        + '<div style="margin-bottom:0;">'
          '<div style="font-size:12px;color:#6b7280;text-transform:uppercase;'
          'letter-spacing:.4px;margin-bottom:4px;">Budget Document</div>'
          '<div style="font-size:14px;color:#111827;font-weight:500;">'
        + doc_html +
        '</div></div>'
        '</div>'
        '<div style="margin-top:12px;font-size:12px;color:#6b7280;">'
        'This is a read-only view. No changes can be made here.</div>'
        '</div>'
    )

    return {'html': html}
