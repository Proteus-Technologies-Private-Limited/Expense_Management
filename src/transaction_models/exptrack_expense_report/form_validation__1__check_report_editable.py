# form_validation: check_report_editable
# Object: exptrack_expense_report
# Description: Validate that the Expense Report is in an editable state before allowing
#   the form to be saved. Reports that have already been Submitted, Approved, Rejected,
#   or Cancelled must not be edited by the employee.
# Functional Spec:
#   - Only reports with STATUS = 'Draft' (or with no status set, i.e. a new report) may be
#     edited/saved.
#   - If the report's current STATUS is Submitted, Approved, Rejected, or Cancelled, block
#     the save with a clear validation error.

def run(args):
    status = args.get('status')

    # New reports (no status yet) are always editable.
    if is_empty(status):
        return None

    # Draft reports remain editable.
    if status == 'Draft':
        return None

    # Any other status means the report is locked from further edits.
    return 'This expense report cannot be edited because its status is "{}". Only reports in Draft status can be modified.'.format(status)
