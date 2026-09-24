# project: Expense_Management
# object_type: T
# object_name: exptrack_manage_reports
# event_type: action
# function_name: view_report_summary
# action_name: View Report
# language: python
# description: Show a read-only summary of the selected report
# functional_specification: Given the clicked EXPTRACK_EXPENSE_REPORT row (REPORT_ID in the flat payload), read the report header and its EXPTRACK_EXPENSE lines (EXPENSE_REPORT = REPORT_ID) and return {"message": "..."} summarising Report ID, Report Date, Total Amount with Currency, the derived Current Status (STATUS='Draft'->Draft; 'Submitted'->Pending Approval; 'Rejected'->Rejected; 'Cancelled'->Cancelled; 'Approved' with PAYMENT_STATUS='Pending'->Approved; 'Approved' with PAYMENT_STATUS='Paid'->Payment Processed; otherwise the raw STATUS), the approver comments when the report is Rejected, and the count and total of its expense lines. Perform NO writes — this screen is strictly read-only. Refuse with {"error": ...} if the report's EMPLOYEE is not the logged-in user.
# business_logic: Show a read-only summary of the selected report


def run(args):
    report_id = args.get('REPORT_ID')
    if is_empty(report_id):
        return {'error': 'No report selected.'}

    hdr = db.query_one(
        'SELECT REPORT_ID, REPORT_TITLE, REPORT_DATE, TOTAL_AMOUNT, CURRENCY, '
        'STATUS, PAYMENT_STATUS, APPROVER_COMMENTS, EMPLOYEE '
        'FROM ' + db.t('EXPTRACK_EXPENSE_REPORT') + ' WHERE REPORT_ID = :r',
        {'r': report_id})
    if not hdr:
        return {'error': 'Report ' + str(report_id) + ' not found.'}

    # Ownership check - the logged-in user's employee code arrives on the payload row.
    current_emp = args.get('EMPLOYEE')
    owner = hdr.get('EMPLOYEE')
    if not_empty(current_emp) and not_empty(owner) \
            and str(current_emp).strip() != str(owner).strip():
        return {'error': 'You are not authorised to view this report - it belongs to employee '
                         + str(owner).strip() + '.'}

    status = str(coalesce(hdr.get('STATUS'), '')).strip()
    pay_status = str(coalesce(hdr.get('PAYMENT_STATUS'), '')).strip()

    if status == 'Draft':
        current_status = 'Draft'
    elif status == 'Submitted':
        current_status = 'Pending Approval'
    elif status == 'Rejected':
        current_status = 'Rejected'
    elif status == 'Cancelled':
        current_status = 'Cancelled'
    elif status == 'Approved' and pay_status == 'Pending':
        current_status = 'Approved'
    elif status == 'Approved' and pay_status == 'Paid':
        current_status = 'Payment Processed'
    else:
        current_status = status

    agg = db.query_one(
        'SELECT COUNT(*) AS LINE_COUNT, COALESCE(SUM(AMOUNT), 0) AS LINE_TOTAL '
        'FROM ' + db.t('EXPTRACK_EXPENSE') + ' WHERE EXPENSE_REPORT = :r',
        {'r': report_id}) or {}
    line_count = int(to_number(coalesce(agg.get('LINE_COUNT'), 0)) or 0)
    line_total = float(to_number(coalesce(agg.get('LINE_TOTAL'), 0)) or 0)

    currency = str(coalesce(hdr.get('CURRENCY'), '')).strip()
    total_amount = float(to_number(coalesce(hdr.get('TOTAL_AMOUNT'), 0)) or 0)
    cur_sfx = (' ' + currency) if currency else ''

    rpt_date = hdr.get('REPORT_DATE')
    if rpt_date is not None and hasattr(rpt_date, 'strftime'):
        rpt_date_txt = rpt_date.strftime('%Y-%m-%d')
    else:
        rpt_date_txt = str(coalesce(rpt_date, ''))

    parts = ['Report ' + str(hdr.get('REPORT_ID')).strip()]
    title = str(coalesce(hdr.get('REPORT_TITLE'), '')).strip()
    if title:
        parts.append('Title: ' + title)
    parts.append('Date: ' + rpt_date_txt)
    parts.append('Total: ' + ('%.2f' % total_amount) + cur_sfx)
    parts.append('Current Status: ' + current_status)
    if current_status == 'Rejected':
        comments = str(coalesce(hdr.get('APPROVER_COMMENTS'), '')).strip()
        parts.append('Approver Comments: ' + (comments if comments else 'None provided'))
    parts.append('Expense Lines: ' + str(line_count)
                 + ' totalling ' + ('%.2f' % line_total) + cur_sfx)

    return {'message': ' | '.join(parts)}
