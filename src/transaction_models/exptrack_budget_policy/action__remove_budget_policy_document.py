# project: Expense_Management
# object_type: T
# object_name: exptrack_budget_policy
# event_type: action
# function_name: remove_budget_policy_document
# action_name: Remove Document
# language: python
# description: Remove the uploaded budget policy document
# functional_specification: Clear the uploaded Budget Policy Document from the current EXPTRACK_BUDGET_POLICY record: UPDATE EXPTRACK_BUDGET_POLICY SET BUDGET_POLICY_DOCUMENT = NULL, CHG_DATE = current timestamp, CHG_USER = the acting user WHERE BUDGET_POLICY_ID = the payload's BUDGET_POLICY_ID. Return {"updates": {"BUDGET_POLICY_DOCUMENT": ""}} so the form field clears immediately. If the record carries no document, return {"error": "No budget policy document is attached to this tier."}.
# business_logic: Remove the uploaded budget policy document


def run(args):
    policy_id = args.get('BUDGET_POLICY_ID')
    if is_empty(policy_id):
        return {'error': 'Budget Policy ID is missing; save the record before removing the document.'}

    row = db.query_one(
        'SELECT BUDGET_POLICY_DOCUMENT FROM ' + db.t('EXPTRACK_BUDGET_POLICY') +
        ' WHERE BUDGET_POLICY_ID = :pid',
        {'pid': policy_id}
    )
    if not row:
        return {'error': 'Budget policy record not found.'}

    # Prefer the stored value; fall back to whatever the form is carrying.
    doc = coalesce(row['BUDGET_POLICY_DOCUMENT'], args.get('BUDGET_POLICY_DOCUMENT'))
    if is_empty(doc):
        return {'error': 'No budget policy document is attached to this tier.'}

    db.update(
        'EXPTRACK_BUDGET_POLICY',
        {
            'BUDGET_POLICY_DOCUMENT': None,
            'CHG_DATE': now(),
            'CHG_USER': coalesce(args.get('CHG_USER'), args.get('ADD_USER'), args.get('CREATED_BY')),
        },
        {'BUDGET_POLICY_ID': policy_id}
    )

    return {'updates': {'BUDGET_POLICY_DOCUMENT': ''}}
