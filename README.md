# Expense_Management

A ready-to-import **Twasta** sample application for employee expenses. Employees
record expenses and trips, managers approve or reject them, and finance pays
out what was approved. Every step is recorded in an activity log.

Import it from **Samples Gallery** inside Twasta, or paste this repository into
**Workbench → Import from Git**:

```
https://github.com/Proteus-Technologies-Private-Limited/Expense_Management
```

## What it does

- **Master data.** Expense categories (Travel, Lodging, Meals, …) and payment
  methods (Cash, Corporate Card, Bank Transfer, …), each linked to a category.
  Retire an entry by setting it Inactive rather than deleting it. A payment
  method that is in use can't be removed.
- **Trips.** Record a business trip with its destination, dates and purpose.
  Trip IDs are generated as `TRIP-00001`, and a trip moves from Planned to
  Upcoming to Completed. Only the Close-trip action can close it.
- **Expenses.** Capture an expense with its category, trip, payment method,
  amount and receipt, then submit it for approval. If an expense is rejected,
  it goes back to the employee to correct and resubmit.
- **Approval.** Approval rules route an expense by category and amount range.
  The approver reviews the expense and its receipt and approves or rejects it.
  Every decision is written to the approval activity log.
- **Finance.** An approved expense becomes a payment-process record, and
  finance records the payment outcome against it. Budget and limitation
  records hold the finance owner, department and supporting budget document.
- **Report.** A printable expense report (PDF).
- **Dashboards.** Transaction analysis, approval analysis and payment-process
  analysis. They show status counts, approved and paid totals, and breakdowns
  by category, payment method and approver.

## Objects

| Type | Count | Examples |
|---|---|---|
| T | 23 | `exptrack_expense`, `exptrack_trip`, `exptrack_expense_category`, `exptrack_payment_method`, `exptrack_manage_approval_v2`, `exptrack_payment_process_new`, `exptrack_budget_limitation` |
| V | 45 | Status counts, totals, category/method/approver breakdowns, trends |
| D | 10 | Transaction, approval and payment-process analysis dashboards |
| P | 2 | Home and approval-management pages |
| R | 1 | `exptrack_expense_report_pdf` |

Tables are prefixed `EXPTRACK_` (expense, trip, expense report, category,
payment method, approval rules, manage approval, payment process, budget
limitation, budget policy). Business logic is Python (`src/`).

## Roles

| Role | Can do |
|---|---|
| `employee` | Record expenses, trips and expense reports; maintain categories and payment methods |
| `manager` | Approve or reject expense reports |
| `finance` | Print the expense report; maintain categories and payment methods |
| `administrator` | Maintain categories and payment methods |

New sign-ups default to `employee`. After importing, adjust the role grants to fit
your organization.

## After importing

1. **Deploy** the project to create its tables.
2. Add expense categories and payment methods under **Master Data Management**.
3. Add project users and give them roles under **System administration →
   Users** in the running application.

Expenses, receipts and approval history are per-install data and aren't
included in this repository.

## Licence

Published as a Twasta sample application for anyone to import, copy and adapt.
