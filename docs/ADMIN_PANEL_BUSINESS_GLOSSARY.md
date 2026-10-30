# Status glossary and calculation definitions

These descriptions document the existing backend implementation. They do not independently validate statutory rates. Monetary calculations remain on the server; the UI presents returned results and links to the API rule registry. Status tooltips use these same definitions. Unknown statuses disclose that their meaning is not configured.

| Status | Meaning | Next owner | Next transition |
| --- | --- | --- | --- |
| new | Requested accountant help; review has not started. | Assigned accountant or assignment admin | Accountant begins review → In review |
| in_review | Books and evidence are being checked. | Assigned accountant | Request missing evidence or mark ready after review |
| waiting_on_driver | Review is waiting for driver information. | Driver, followed by accountant | Accountant resumes review when evidence arrives |
| ready_to_file | Accountant has marked the handoff ready. | Senior accountant or admin | Record completed external filing with a real reference → Filed |
| filed | A completed external filing has been recorded. | Senior accountant or admin | No automatic next step; corrections require senior review |
| draft | Posting is unconfirmed and excluded from totals. | Driver or accountant | Review and confirm its originating record |
| pending | Evidence or scan is awaiting processing/review. | Scanning service, then reviewer | Scan completes or reviewer records a decision |
| confirmed | Canonical posting is included in confirmed totals. | Reviewer | Correction requires reversal before another confirmation |
| reversed | Prior confirmation has been reversed; excluded from totals. | Reviewer | Correct the original evidence and confirm again |
| claimable | Eligible business deduction under server rules. | Reviewer | Correction or changed eligibility recalculates the deduction |
| personal | Personal cost; no business deduction. | Reviewer | Correct the source if classification is wrong |
| excluded | Explicitly excluded; deduction is zero. | Reviewer | Reverse and review again if the decision was wrong |
| unknown | Claim classification has not been reviewed. | Reviewer | Confirm evidence, category and business share to classify the claim |
| clean | Private evidence passed scanning and can be downloaded. | Reviewer | Review the document |
| generated | Server-generated evidence is available. | Reviewer | Review or download the document |
| failed | Processing failed; evidence may remain quarantined. | Service operator | Resolve the failure and retry when permitted |
| infected | Evidence failed the safety scan and is quarantined. | Driver / service operator | Supply replacement evidence |
| queued | Processing job is waiting. | Processing service | Worker starts the job → Processing |
| processing | Processing job is running. | Processing service | Worker reports success or failure |
| succeeded | Processing completed. | Reviewer | Review the resulting evidence |
| none | No subscription record exists. | Billing administrator | An approved subscription is created |
| trialing | Trial subscription is recorded. | Billing administrator / driver | Trial expires or billing provider activates a plan |
| trial_expired | Recorded trial end has passed. | Billing administrator / driver | Billing provider activates an approved plan |
| active | Subscription is recorded as active. | Billing provider | Provider sends the next billing status |
| past_due | Billing provider reports an unpaid amount. | Driver / billing provider | Provider confirms payment or cancellation |
| canceled | Subscription is recorded as canceled. | Billing administrator / driver | Provider confirms a new approved subscription |
| rejected | Review declined the record. | Reviewer / driver | Provide corrected evidence and review again |
| overdue | Supplied-year deadline passed and handoff is not filed. | Assigned accountant | Complete review and record external filing |

The workflow steps describe the intended review sequence, not a server-enforced state machine. The server allows other non-filed transitions. Only a real audit event receives a transition timestamp; no unvisited step receives an invented date. Requested uses the original request creation timestamp. The most recent transition to each step is shown; the recent audit list preserves repeated/backward changes (up to 50 events), with a link to the complete paginated activity log.

## Numbers

| Figure | Formula / definition |
| --- | --- |
| Income | Sum of confirmed income postings in the selected tax year through the server as-of date. Drafts and reversals are excluded. |
| Deductible expenses | Sum of confirmed expense deductible amounts + eligible mileage deduction. Each expense uses reviewed business share and server eligibility rules. |
| Profit | Confirmed income − deductible expenses (including eligible mileage). |
| Estimated tax | max(0, income tax + Class 4 NI − PAYE tax already paid) + student loan repayment. This is an estimate, not an assessed bill. |
| Estimated liability | max(0, income tax + Class 4 NI − PAYE tax already paid) + student loan repayment. Savings tax is already included in income tax. |
| Income tax | Sum of server tax-band amounts, plus applicable savings tax and after supported relief adjustments. Each band uses its returned base × rate, rounded by the server. |
| Class 4 NI | max(0, min(profit, upper threshold) − lower threshold) × first rate + max(0, profit − upper threshold) × remaining rate. Server applies supported exemptions. Thresholds and rates are listed below from the API. |
| Personal allowance | max(0, standard allowance − floor(max(0, combined income − taper start) ÷ 2)), then any supported Marriage Allowance adjustment. PAYE/property income may use some of this allowance. Standard allowance and taper start come from the API rules below. |
| Payment amount | Payment-on-account eligibility uses prior assessed liability and the configured outside-SA exemption. If eligible: first payment = floor(prior liability ÷ 2); second = prior liability − first. Balancing amount = projected annual liability − advance payments + adjustments. No prior assessment means the amount is unknown. These are server estimates, not an HMRC account balance. |
| Mileage deduction | For each eligible vehicle: eligible business miles in each mileage band × that vehicle/year rate; sum vehicle deductions. Only mileage-method elections qualify; hackney eligibility differs. |
| Visible drivers | Count of non-staff drivers within your access scope, across tax years. |
| Assigned drivers | Count of non-staff drivers within your access scope, across tax years. |
| Pending handoffs | Count of visible handoffs whose status is not Filed, for the selected year plus handoffs with no supplied year. |
| Returns due soon | Non-filed handoffs with a supplied selected year when its deadline is 0–30 days away. Missing-year handoffs are excluded. |
| Overdue returns | Non-filed handoffs with a supplied selected year whose deadline has passed. Missing-year handoffs are excluded. |
| Business miles | Sum of active business mileage logs in the selected tax year through today. Recorded miles and deduction-eligible miles can differ. |
| Pending receipts | Receipts not Confirmed with a date in the selected year, plus all undated receipts. Reversed receipts are included. |
| Unresolved issues | Open reconciliation issues whose statement period overlaps the selected tax year. |
| Handoff age | Whole elapsed days since the original accountant request was created, calculated by the server. |
| Days to deadline | Configured selected-year online deadline − today in Europe/London. Negative values mean overdue. |
| Workload | Count by current handoff status within your access scope for the selected tax year, including handoffs with no supplied year. Bar share = status count ÷ all displayed status counts. |

Rates, thresholds, official links, verification dates and rule-set version come from the existing tax API. Tax details include income, expense deduction, profit, PAYE tax paid, student loans, savings tax, allowance used elsewhere, combined income and each returned tax band. Figures are GBP pence, formatted once for display. Unknown money is ?, zero is ?0.00. Payment timeline rows accept either the backend label_key or type variant; missing assessments remain unknown.

## Actions and backend effects

| Action | Actual behavior / permission |
| --- | --- |
| Sign in / sign out | Staff email and password create a revocable session; logout revokes it. No verification-code step. |
| Recovery / reset | Generic recovery notice; reset requires a valid recovery token. |
| Search / filters / sort / paging | Server allowlisted queries within staff access scope. UTR searches are exact, sent in POST bodies and cannot be saved. |
| Save/delete view | Private staff-scoped query configuration; no financial records changed. |
| Export CSV | Whole filtered result, capped at 10,000 rows; support cannot export. |
| Appearance / density | Client appearance only; no workflow or accounting effect. |
| Assign accountant | Admin/senior only, expected versions checked; changes driver-level assignment, every related handoff version and financial access. Confirmation names the driver(s) and target. |
| Update handoff | Records selected status, reason and expected version. No automatic message or tax submission. |
| Record external filing | Requires admin/senior, previous Ready to file, actual external reference and current version. Records sign-off; never submits to HMRC. |
| Reveal UTR/NI | Authorized non-support staff, reason required and access audited; value hidden on timeout/blur/tab visibility change. No identifiers in audit details. |
| Save receipt fields | Corrects extracted fields; creates/updates an unconfirmed draft. Required before approving changed values. |
| Approve / exclude receipt | Confirmed canonical posting using server eligibility/category/business share. Exclusion confirms with no deduction; explicit confirmation and reason. |
| Undo / reverse confirmation | Reverses the exact mutation, subject to current version, unchanged posting and open period. History remains. |
| Recategorise expense | Manual expense only; source/imported entries use their original correction workflow. Backend recalculates eligibility and audits changes. |
| Upload / download evidence | Upload quarantines private evidence for scanning; download allowed only for clean/generated evidence. Disabled state explains why. |
| Send message | Stores a human accountant-thread message. Push/email delivery is a separate integration. |
| Internal note/ticket | Staff-only entry; support may write these. Never shown in driver chat. |
| Audit / history | Read-only actor, timestamp and before/after evidence. Financial actor metadata is taken from the actual audit; legacy missing actors stay explicit. |
| Next-action links | Open the existing review, message, tax, queue or audit workspace. They do not silently mutate a record. |

## Filing checklist policy

Enforced today: handoff exists; current status Ready to file; senior/admin sign-off; real external reference; optimistic version check. Pending receipt and reconciliation counts are explicitly marked review advisories, because update_handoff does not enforce them. A missing tax year is disclosed but is not silently converted into a new server filing gate.

**Policy question:** Should pending receipts and unresolved reconciliation issues become mandatory server-enforced filing blockers, or remain review advisories?
