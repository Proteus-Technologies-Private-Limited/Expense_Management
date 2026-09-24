# project: Expense_Management
# object_type: T
# object_name: exptrack_manage_expense
# event_type: post_commit
# function_name: log_approval_activity
# language: python
# description: Write the approval decision to the Activity Log
# functional_specification: After the save commits, write one Activity Log entry for the approval decision, capturing the actor (the approver / changing user), the action ('Approved' or 'Rejected' derived from the header STATUS), the affected REPORT_ID, the EMPLOYEE who raised the report, TOTAL_AMOUNT and the decision timestamp, with a narrative DESCRIPTION such as 'Manager approved Report RPT-0088'. Only log when the header STATUS is Approved or Rejected; skip a Pending save. Cleanup-only — never block the save. ASSUMPTION: no activity-log table exists in the current design; the implementer must write to the project's activity-log table once it is introduced, or make this a no-op until then.
# business_logic: Write the approval decision to the Activity Log

# ASSUMPTION (carried from the specification): the current data design contains NO
# activity-log table. Writing to an invented table would fail at runtime, so this hook
# assembles the log entry and then no-ops. When the project introduces its activity-log
# table, set ACTIVITY_LOG_TABLE below to its name and map `entry` onto its real columns.
ACTIVITY_LOG_TABLE = None


def run(args):
    # post_commit is cleanup-only: it must never surface a failure that disturbs the save.
    try:
        header = args.get('header') or {}

        status = header.get('STATUS')
        status = '' if is_empty(status) else str(status).strip()

        # Only a finalised decision is worth logging; a Pending save is skipped.
        if not in_list(status, 'Approved,Rejected'):
            return None

        report_id = header.get('REPORT_ID')
        report_id = '' if is_empty(report_id) else str(report_id).strip()

        employee = header.get('EMPLOYEE')
        employee = '' if is_empty(employee) else str(employee).strip()

        actor = coalesce(header.get('APPROVER'), header.get('CHG_USER'),
                         header.get('ADD_USER'))
        actor = '' if is_empty(actor) else str(actor).strip()

        total_amount = to_number(header.get('TOTAL_AMOUNT')) or 0

        decided_at = header.get('APPROVAL_DATE')
        if is_empty(decided_at):
            decided_at = now()

        verb = 'approved' if status == 'Approved' else 'rejected'
        description = ((actor or 'Approver') + ' ' + verb + ' Report ' + report_id).strip()

        entry = {
            'ACTOR': actor,
            'ACTION': status,
            'REPORT_ID': report_id,
            'EMPLOYEE': employee,
            'TOTAL_AMOUNT': total_amount,
            'ACTIVITY_DATE': decided_at,
            'DESCRIPTION': description,
        }

        if not ACTIVITY_LOG_TABLE:
            # No activity-log table in this design yet - intentional no-op.
            return None

        db.insert(db.t(ACTIVITY_LOG_TABLE), entry)
        return None
    except Exception:
        # Never let logging disturb a committed save.
        return None
