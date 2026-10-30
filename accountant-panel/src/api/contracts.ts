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
const estimateFields = { total_pence: integer, income_tax_pence: integer, class4_pence: integer, personal_allowance_pence: integer,
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
  subscription: object({ status: text, plan_id: text.nullish(), renew_at: text.nullish() }), totals, handoffs: z.array(handoff).optional() });
const config = object({ tax_years: strings, current_tax_year: text, idle_timeout_seconds: count, upload_max_bytes: count,
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
const tableResources: Record<string, z.ZodType> = { drivers: resourceMappers.driver, handoffs: resourceMappers.handoff, accountants: resourceMappers.staff,
  income: resourceMappers.transaction, expenses: resourceMappers.transaction, mileage: resourceMappers.mileage, documents: resourceMappers.document,
  receipts: resourceMappers.receipt, messages: resourceMappers.entry, notes: resourceMappers.entry, activity: resourceMappers.audit };

export function responseSchema(path: string, method = 'GET'): z.ZodType {
  const tail = path.split('/').filter(Boolean).at(-1);
  if (path.endsWith('/auth/login')) return object({ access_token: text.min(1), expires_in: count.min(1), staff: resourceMappers.staff });
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
