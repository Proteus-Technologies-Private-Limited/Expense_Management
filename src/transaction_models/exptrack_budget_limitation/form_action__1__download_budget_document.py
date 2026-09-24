# project: Expense_Management
# object_type: T
# object_name: exptrack_budget_limitation
# event_type: form_action
# function_name: download_budget_document
# form_no: 1
# action_name: Download Budget Document
# language: python
# description: Download the uploaded budget document file
# functional_specification: Stream the file stored at the current row's BUDGET_DOCUMENT column (table EXPTRACK_BUDGET_LIMITATION) back to the browser as a file download/attachment using the platform's standard file-download response, preserving the original file name and content type. If BUDGET_DOCUMENT is empty/null, return a user-facing message that no document is attached instead of erroring.
# business_logic: Download the uploaded budget document file


CONTENT_TYPES = {
    'pdf': 'application/pdf',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'ppt': 'application/vnd.ms-powerpoint',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'csv': 'text/csv',
    'txt': 'text/plain',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'zip': 'application/zip',
}


def run(args):
    doc = args.get('BUDGET_DOCUMENT')
    limit_id = args.get('BUDGET_LIMITATION_ID')

    # The action payload may not carry the stored path (e.g. fired from a grid
    # row) - fall back to the persisted value for this record.
    if is_empty(doc) and not_empty(limit_id):
        row = db.query_one(
            'SELECT BUDGET_DOCUMENT FROM ' + db.t('EXPTRACK_BUDGET_LIMITATION') +
            ' WHERE BUDGET_LIMITATION_ID = :id',
            {'id': limit_id})
        if row:
            doc = row['BUDGET_DOCUMENT']

    if is_empty(doc):
        return {'prompts': [{'code': 'BLDOC01',
                             'field': 'BUDGET_DOCUMENT',
                             'type': 'P',
                             'message': 'No budget document is attached to this record.'}]}

    path = str(doc).strip()
    file_name = re.split(r'[\\/]', path)[-1] or 'budget_document'
    ext = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else ''
    content_type = CONTENT_TYPES.get(ext, 'application/octet-stream')

    return {
        'file': {
            'path': path,
            'name': file_name,
            'content_type': content_type,
            'disposition': 'attachment',
        },
        'message': 'Downloading ' + file_name,
    }
