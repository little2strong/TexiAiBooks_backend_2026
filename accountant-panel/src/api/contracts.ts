import { z } from 'zod';

const text = z.string();
const nullableText = text.nullable();
const integer = z.number().int().safe();
const count = integer.nonnegative();
const decimal = z.string().regex(/^-?\d+(\.\d+)?$/);
const timestamp = text.refine(value => Number.isFinite(Date.parse(value)), 'Invalid date');
const object = <T extends z.ZodRawShape>(shape: T) => z.object(shape).passthrough();
const record = z.record(text, z.unknown());
const strings = z.array(text);
const staff = object({ id: text, name: text, email: text, role: z.enum(['accountant', 'senior_accountant', 'admin', 'support']), team_id: nullableText });
const driver = object({ id: text, name: text, email: nullableText, accountant_id: nullableText, accountant_name: nullableText, created_at: timestamp });
const event = object({ id: text, actor_name: text, action: text, created_at: timestamp, before: record.nullable(), after: record.nullable() });
const review = { reviewed_by: nullableText.optional(), reviewed_at: timestamp.nullable().optional() };
const handoff = object({ id: text, driver_id: text, driver_name: text, driver_email: nullableText, tax_year: nullableText, request_type: text,
  status: z.enum(['new', 'in_review', 'waiting_on_driver', 'ready_to_file', 'filed']), accountant_id: nullableText, accountant_name: nullableText,
  created_at: timestamp, age_days: count, version: count, filing_reference: nullableText, workflow_events: z.array(event).optional() });
const totals = object({ income_pence: integer, deductible_expenses_pence: integer, profit_pence: integer, estimated_tax_pence: integer.nullable(),
  business_miles: decimal, pending_receipts: count, unresolved_issues: count, mileage_deduction_pence: integer.optional(), as_of: timestamp.optional(), has_data: z.boolean().optional() });
const transaction = object({ id: text, version: count, occurred_on: timestamp, amount_pence: integer, description: nullableText,
  category_id: nullableText, category_name: text, source_name: nullableText, business_use_percent: decimal, deductible_pence: integer,
  review_status: text, claim_status: text, eligibility_reason_codes: strings, receipt_id: nullableText, receipt_version: count.nullable(),
  import_origin_key: nullableText, ai_category: nullableText, ai_confidence: z.union([z.number(), text, z.record(text, z.number())]).nullable(), ai_reason: strings, ...review });
const receipt = object({ id: text, version: count, created_at: timestamp, file_id: text, review_status: text, claim_status: text,
  transaction_id: nullableText, mutation_id: nullableText, scan_status: text.optional(), mime_type: text.optional(),
  merchant: nullableText.optional(), occurred_on: timestamp.nullable().optional(), amount_pence: integer.nullable().optional(),
  vat_pence: integer.nullable().optional(), category_id: nullableText.optional(), business_use_percent: decimal.nullable().optional(),
  extraction: object({ confidence: z.union([z.number(), text, z.record(text, z.number())]).optional(), warnings: strings.optional(), suggested_category_id: text.optional() }).nullable(), warnings: strings, ...review });
const mileage = object({ id: text, occurred_on: timestamp, business_miles: decimal, private_miles: decimal, purpose: text, vehicle_id: text, start_odometer: nullableText, end_odometer: nullableText });
const document = object({ id: text, mime_type: text, size_bytes: count, scan_status: text, created_at: timestamp });
const entry = object({ id: text, body: text, kind: z.enum(['message', 'note', 'ticket']), author: text, created_at: timestamp, staff_id: nullableText });
const tableQuery = object({ page: count.min(1), page_size: count.min(1), sort: text, order: z.enum(['asc', 'desc']), search: text, filters: z.record(text, text) });
const view = object({ id: text, name: text, resource: text, query: tableQuery });
const rule = object({ code: text, value: record, official_url: z.url(), verified_at: timestamp });
const estimateFields = { class2_status: text.optional(), class2_weekly_rate_pence: integer.nullish(), class2_small_profits_threshold_pence: integer.nullish(), frozen: z.boolean().optional(),
  adjustment_income_pence: integer.optional(), adjustment_expenses_pence: integer.optional(), adjustment_capital_allowances_pence: integer.optional(),
  total_pence: integer, income_tax_pence: integer, class4_pence: integer, personal_allowance_pence: integer,
  profit_pence: integer, income_pence: integer, expense_deduction_pence: integer, paye_tax_paid_pence: integer, student_loan_pence: integer,
  savings_tax_pence: integer, allowance_used_elsewhere_pence: integer, combined_income_pence: integer, as_of: timestamp,
  warnings: strings, assumptions: strings, bands: z.array(object({ label: text, rate: text, base_pence: integer, tax_pence: integer })) };
const tax = object({ calculation_context: record.optional(), estimate: z.union([object({ available: z.literal(false), reason: text }), object(estimateFields)]),
  payments: object({ items: z.array(object({ id: text, due_on: timestamp, label_key: text.optional(), type: text.optional(), amount_pence: integer.nullish() })
    .refine(value => Boolean(value.label_key || value.type), 'Payment needs a label or type')), warnings: strings.optional() }),
  rules: object({ id: text, tax_year: text, version: z.union([text, integer]), rules: z.array(rule) }) });
const dashboard = object({ assigned_drivers: count, pending_handoffs: count, due_soon: count, overdue: count, year_not_supplied: count,
  deadline: object({ due_on: timestamp, days_remaining: integer, tax_year: text }), workload: z.array(object({ id: text, status: handoff.shape.status, count })), as_of: timestamp });
const overview = driver.extend({ tax_year: text, utr_masked: nullableText, ni_masked: nullableText, driver_profile: record,
  totals, handoffs: z.array(handoff).optional() });
const config = object({ tax_years: strings, current_tax_year: text, filing_tax_year: text.optional(), idle_timeout_seconds: count, upload_max_bytes: count,
  categories: z.array(object({ id: text, code: text, requires_vehicle: z.boolean() })), sources: z.array(object({ id: text, name: text })) });

// Existing ledger columns retain their established names. New UI-only fields are
// mapped here once, rather than guessed or renamed independently in each widget.
const mapHandoff = handoff.transform(({ workflow_events, ...value }) => ({ ...value, workflowEvents: workflow_events ?? [] }));
export const resourceMappers = {
  staff: staff.transform(value => value), driver: driver.transform(value => value),
  handoff: mapHandoff,
  transaction: transaction.transform(({ reviewed_by, reviewed_at, ...value }) => ({ ...value, reviewerName: reviewed_by ?? null, reviewedAt: reviewed_at ?? null })),
  receipt: receipt.transform(({ reviewed_by, reviewed_at, ...value }) => ({ ...value, reviewerName: reviewed_by ?? null, reviewedAt: reviewed_at ?? null })),
  mileage: mileage.transform(value => value), document: document.transform(value => value), entry: entry.transform(value => value), audit: event.transform(value => value), view: view.transform(value => value),
  config: config.transform(value => value), dashboard: dashboard.transform(value => value),
  overview: overview.transform(({ handoffs, ...value }) => ({ ...value, handoffs: (handoffs ?? []).map(row => mapHandoff.parse(row)) })),
  tax: tax.transform(({ calculation_context, ...value }) => ({ ...value, calculationContext: calculation_context ?? {}, payments: { ...value.payments, items: value.payments.items.map(item => ({ ...item, label_key: item.label_key ?? item.type! })) } })),
};
const page = (schema: z.ZodType) => object({ items: z.array(schema), total: count, page: count.min(1), page_size: count.min(1) });
const returnStatus = z.enum(['in_preparation', 'awaiting_driver', 'driver_approved', 'filed']);
const returnRow = object({ id: text, driver_id: text, driver_name: text, driver_email: nullableText, accountant_name: nullableText, tax_year: text,
  status: returnStatus, version: count, review_version: count, filing_reference: nullableText, filed_at: timestamp.nullable(), filed_by_name: nullableText,
  driver_decided_at: timestamp.nullable(), driver_note: nullableText, created_at: timestamp });
const adjustment = object({ id: text, target: z.enum(['income', 'expenses', 'capital_allowances']), amount_pence: integer, reason: text,
  created_by_name: nullableText, created_at: timestamp, voided_at: timestamp.nullable(), void_reason: nullableText });
const checklistItem = object({ id: text, label: text, status: z.enum(['pass', 'warn', 'block']), detail: text, tab: nullableText });
const returnDetail = returnRow.extend({ checklist: z.array(checklistItem), blockers: count, adjustments: z.array(adjustment), estimate: tax.shape.estimate,
  snapshot: record.nullable(), earlier_snapshots: z.array(record), events: z.array(event) });
const aiRow = object({ id: text, driver_id: text, driver_name: text, created_at: timestamp, version: count, review_status: text, merchant: nullableText.optional(),
  amount_pence: integer.nullable().optional(), occurred_on: timestamp.nullable().optional(), suggested_category: nullableText,
  confidence: z.union([z.number(), text, z.record(text, z.number())]).nullish(), warnings: strings, feedback_verdict: nullableText, feedback_by: nullableText, feedback_reason: nullableText });
const aiSummary = object({ extractions: count, reviewed: count, open: count, accepted: count, corrected: count, rejected: count, acceptance_percent: count.nullable() });
const staffRow = staff.extend({ active: z.boolean(), version: count, team_name: nullableText, last_seen_at: timestamp.nullable(), assigned_drivers: count });
const rateRow = object({ id: text, tax_year: text, region: text, code: text, value: record, status: z.enum(['draft', 'approved', 'active', 'retired']), official_url: text,
  reason: text, version: count, created_by_name: nullableText, approved_by_name: nullableText, created_at: timestamp, activated_at: timestamp.nullable() });
const privacyRow = object({ id: text, driver_id: text, driver_name: text, driver_email: nullableText, kind: z.enum(['export', 'access', 'correction', 'deletion']),
  status: z.enum(['received', 'in_progress', 'completed', 'rejected']), detail: nullableText, due_on: timestamp, retain_until: timestamp.nullable(), resolution: nullableText,
  handled_by_name: nullableText, overdue: z.boolean(), version: count, created_at: timestamp, completed_at: timestamp.nullable() });
const auditRow = object({ id: text, actor_name: text, action: text, driver_id: nullableText, resource_id: nullableText, created_at: timestamp, before: record.nullable(), after: record.nullable() });
const complianceRow = object({ id: text, doc_type: text, reference: nullableText, expires_on: timestamp.nullable(), days_remaining: integer.nullable(), expiry_status: text, created_at: timestamp });
const mtdStatus = object({ status: text, start_date: timestamp.nullable(), confidence: nullableText, reason: text, years_below_count: count,
  threshold_pence: integer.nullable(), qualifying_income_pence: integer.nullable(), test_year: nullableText, near_threshold: z.boolean() });
const mtdView = mtdStatus.extend({ history: z.array(object({ tax_year: text, gross_se_income_pence: integer, source: text })),
  vat: object({ rolling_turnover_pence: integer, threshold_pence: integer, percent_of_threshold: count, status: text, note: text }),
  platform: z.record(text, z.array(object({ source: text, app_gross_pence: integer, platform_reported_gross_pence: integer.nullable(), difference_pence: integer.nullable(), status: text, dispute_note: nullableText }))) });
const tableResources: Record<string, z.ZodType> = { drivers: resourceMappers.driver, handoffs: resourceMappers.handoff, accountants: resourceMappers.staff,
  income: resourceMappers.transaction, expenses: resourceMappers.transaction, mileage: resourceMappers.mileage, documents: resourceMappers.document,
  receipts: resourceMappers.receipt, messages: resourceMappers.entry, notes: resourceMappers.entry, activity: resourceMappers.audit,
  returns: returnRow, 'ai-reviews': aiRow, users: staffRow, rates: rateRow, 'privacy-requests': privacyRow, audit: auditRow, compliance: complianceRow };

export function responseSchema(path: string, method = 'GET'): z.ZodType {
  const tail = path.split('/').filter(Boolean).at(-1);
  if (path.endsWith('/auth/login')) return object({ access_token: text.min(1), expires_in: count.min(1), staff: resourceMappers.staff });
  if (path.endsWith('/teams/search')) return object({ items: z.array(object({ id: text, name: text })) });
  if (path.endsWith('/teams')) return object({ id: text, name: text });
  if (path.endsWith('/ai-reviews/summary')) return aiSummary;
  if (/\/ai-reviews\/[^/]+\/feedback$/.test(path)) return aiRow;
  if (path.endsWith('/rates/effective') || path.includes('/rates/effective?')) return object({ id: nullableText, tax_year: text, region: text, version: nullableText, rules: z.array(rule), unavailable_reason: text.optional() });
  if (/\/staff\/rates(\/[^/]+\/(approve|activate|retire))?$/.test(path) && tail !== 'search') return rateRow;
  if (/\/staff\/users(\/[^/]+)?$/.test(path) && tail !== 'search') return staffRow;
  if (/\/privacy-requests(\/[^/]+(\/execute-deletion)?)?$/.test(path) && tail !== 'search') return privacyRow;
  if (/\/drivers\/[^/]+\/mtd$/.test(path)) return mtdView;
  if (/\/drivers\/[^/]+\/mtd\/override$/.test(path)) return mtdStatus;
  if (path.endsWith('/staff/returns') && method === 'POST') return returnRow;
  if (/\/staff\/returns\/[^/]+(\/.*)?$/.test(path) && tail !== 'search') return returnDetail;
  if (path.endsWith('/auth/forgot-password')) return object({ message: text });
  if (path.endsWith('/me')) return resourceMappers.staff;
  if (tail === 'config') return resourceMappers.config;
  if (tail === 'dashboard') return resourceMappers.dashboard;
  if (tail === 'overview') return resourceMappers.overview;
  if (tail === 'tax') return resourceMappers.tax;
  if (path.endsWith('/views/search')) return object({ items: z.array(resourceMappers.view) });
  if (tail === 'views') return resourceMappers.view;
  if (tail === 'search') {
    const resource = path.split('/').at(-2)!;
    if (!tableResources[resource]) throw new Error(`No table contract: ${resource}`);
    const schema = page(tableResources[resource]);
    return resource === 'mileage' ? schema.extend({ summary: object({ business_miles: decimal, deduction_pence: integer, threshold_remaining: decimal }) }) : schema;
  }
  if (tail === 'reveal') return object({ value: text, expires_in: count });
  if (path.endsWith('/handoffs/assign')) return object({ items: z.array(resourceMappers.handoff) });
  if (/\/handoffs\/[^/]+$/.test(path)) return resourceMappers.handoff;
  if (tail === 'review') return object({ receipt: resourceMappers.receipt, mutation_id: text });
  if (/\/receipts\/[^/]+$/.test(path) && method === 'GET') return resourceMappers.receipt;
  // Mutation envelopes differ by operation; the fields consumed by the UI are validated.
  if (/\/receipts\/[^/]+$/.test(path)) return resourceMappers.receipt;
  if (/\/expenses\/[^/]+$/.test(path)) return object({ id: text, version: count, amount_pence: integer, deductible_pence: integer, review_status: text });
  if (tail === 'messages' || tail === 'notes') return resourceMappers.entry;
  if (tail === 'documents') return object({ id: text });
  if (tail === 'reversals') return object({ receipt: resourceMappers.receipt, transaction: object({ id: text, review_status: text }) });
  throw new Error(`No API response contract for ${path.replace(/[a-f0-9-]{36}/g, ':id')}`);
}

export function decodeResponse(path: string, method: string, value: unknown, requestId: string): unknown {
  const result = responseSchema(path, method).safeParse(value);
  if (result.success) return result.data;
  const fields = result.error.issues.map(issue => issue.path.join('.') || '(response)').join(', ');
  console.error(`API contract mismatch: ${path.replace(/[a-f0-9-]{36}/g, ':id')} — ${fields} — request ${requestId}`);
  throw new Error(`The server returned unexpected data (${fields}). Retry or contact support. Request ID: ${requestId}`);
}
