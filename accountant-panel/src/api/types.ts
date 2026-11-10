export type Role = "admin" | "accountant";
export interface Staff {
  id: string;
  name: string;
  email: string;
  role: Role;
}
export interface TableQuery {
  page: number;
  page_size: number;
  sort: string;
  order: "asc" | "desc";
  search: string;
  filters: Record<string, string>;
}
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
export interface Driver {
  id: string;
  name: string;
  email: string | null;
  accountant_id: string | null;
  accountant_name: string | null;
  created_at: string;
}
export type HandoffStatus =
  "new" | "in_review" | "waiting_on_driver" | "ready_to_file" | "filed";
export interface Handoff {
  workflowEvents: AuditEvent[];
  id: string;
  driver_id: string;
  driver_name: string;
  driver_email: string | null;
  tax_year: string | null;
  request_type: string;
  status: HandoffStatus;
  accountant_id: string | null;
  accountant_name: string | null;
  created_at: string;
  age_days: number;
  version: number;
  filing_reference: string | null;
}
export interface Config {
  tax_years: string[];
  current_tax_year: string;
  filing_tax_year?: string;
  idle_timeout_seconds: number;
  upload_max_bytes: number;
  categories: { id: string; code: string; requires_vehicle: boolean }[];
  sources: { id: string; name: string }[];
}
export interface Dashboard {
  assigned_drivers: number;
  pending_handoffs: number;
  due_soon: number;
  overdue: number;
  year_not_supplied: number;
  deadline: { due_on: string; days_remaining: number; tax_year: string };
  workload: { id: string; status: HandoffStatus; count: number }[];
  as_of: string;
}
export interface Totals {
  mileage_deduction_pence?: number;
  as_of?: string;
  has_data?: boolean;
  income_pence: number;
  deductible_expenses_pence: number;
  profit_pence: number;
  estimated_tax_pence: number | null;
  business_miles: string;
  pending_receipts: number;
  unresolved_issues: number;
}
export interface Overview extends Driver {
  handoffs: Handoff[];
  tax_year: string;
  utr_masked: string | null;
  ni_masked: string | null;
  driver_profile: {
    licence_type?: string;
    council_code?: string;
    work_pattern?: string;
  };
  totals: Totals;
}
export interface Transaction {
  reviewerName?: string | null;
  reviewedAt?: string | null;
  id: string;
  version: number;
  occurred_on: string;
  amount_pence: number;
  description: string | null;
  category_id: string | null;
  category_name: string;
  source_name: string | null;
  business_use_percent: string;
  deductible_pence: number;
  review_status: string;
  claim_status: string;
  eligibility_reason_codes: string[];
  receipt_id: string | null;
  receipt_version: number | null;
  import_origin_key: string | null;
  ai_category: string | null;
  ai_confidence: number | string | Record<string, number> | null;
  ai_reason: string[];
}
export interface Mileage {
  id: string;
  occurred_on: string;
  business_miles: string;
  private_miles: string;
  purpose: string;
  vehicle_id: string;
  start_odometer: string | null;
  end_odometer: string | null;
}
export interface Document {
  id: string;
  mime_type: string;
  size_bytes: number;
  scan_status: string;
  created_at: string;
}
export interface Entry {
  id: string;
  body: string;
  kind: "message" | "note" | "ticket";
  author: string;
  created_at: string;
  staff_id: string | null;
}
export interface AuditEvent {
  id: string;
  actor_name: string;
  action: string;
  created_at: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  driver_id?: string | null;
  driver_name?: string | null;
}
export interface Receipt {
  reviewerName?: string | null;
  reviewedAt?: string | null;
  id: string;
  version: number;
  created_at: string;
  file_id: string;
  scan_status: string;
  mime_type: string;
  review_status: string;
  claim_status: string;
  transaction_id: string | null;
  mutation_id: string | null;
  merchant?: string;
  occurred_on?: string;
  amount_pence?: number;
  vat_pence?: number;
  category_id?: string;
  business_use_percent?: string;
  extraction: {
    confidence?: number | string | Record<string, number>;
    warnings?: string[];
    suggested_category_id?: string;
  } | null;
  warnings: string[];
}
export interface TaxRule {
  code: string;
  value: Record<string, unknown>;
  official_url: string;
  verified_at: string;
  managed?: boolean;
}
export interface TaxResult {
  calculationContext?: Record<string, unknown>;
  estimate: {
    income_pence?: number;
    expense_deduction_pence?: number;
    paye_tax_paid_pence?: number;
    student_loan_pence?: number;
    savings_tax_pence?: number;
    allowance_used_elsewhere_pence?: number;
    combined_income_pence?: number;
    as_of?: string;
    available?: boolean;
    reason?: string;
    class2_status?: string;
    class2_weekly_rate_pence?: number | null;
    class2_small_profits_threshold_pence?: number | null;
    frozen?: boolean;
    adjustment_income_pence?: number;
    adjustment_expenses_pence?: number;
    adjustment_capital_allowances_pence?: number;
    total_pence?: number;
    income_tax_pence?: number;
    class4_pence?: number;
    personal_allowance_pence?: number;
    profit_pence?: number;
    warnings?: string[];
    assumptions?: string[];
    bands?: {
      label: string;
      rate: string;
      base_pence: number;
      tax_pence: number;
    }[];
  };
  payments: {
    prior_year_liability_pence?: number | null;
    advance_payments_pence?: number | null;
    adjustments_pence?: number | null;
    estimated_year_liability_pence?: number | null;
    tax_paid_outside_sa_pence?: number | null;
    items: {
      id: string;
      due_on: string;
      label_key: string;
      amount_pence?: number | null;
    }[];
    warnings?: string[];
  };
  rules: { id: string; tax_year: string; version: string | number; rules: TaxRule[] };
}
export interface SavedView {
  id: string;
  name: string;
  resource: string;
  query: TableQuery;
}
export interface StaffLoginResult {
  access_token: string;
  expires_in: number;
  staff: Staff;
}
export type ReturnStatus = "in_preparation" | "awaiting_driver" | "driver_approved" | "filed";
export interface TaxReturnRow {
  id: string;
  driver_id: string;
  driver_name: string;
  driver_email: string | null;
  accountant_name: string | null;
  tax_year: string;
  status: ReturnStatus;
  version: number;
  review_version: number;
  filing_reference: string | null;
  filed_at: string | null;
  filed_by_name: string | null;
  driver_decided_at: string | null;
  driver_note: string | null;
  created_at: string;
}
export interface TaxAdjustment {
  id: string;
  target: "income" | "expenses" | "capital_allowances";
  amount_pence: number;
  reason: string;
  created_by_name: string | null;
  created_at: string;
  voided_at: string | null;
  void_reason: string | null;
}
export interface ChecklistItem {
  id: string;
  label: string;
  status: "pass" | "warn" | "block";
  detail: string;
  tab: string | null;
}
export interface TaxReturnDetail extends TaxReturnRow {
  checklist: ChecklistItem[];
  blockers: number;
  adjustments: TaxAdjustment[];
  estimate: TaxResult["estimate"];
  snapshot: Record<string, unknown> | null;
  earlier_snapshots: Record<string, unknown>[];
  events: AuditEvent[];
}
export interface AiReviewRow {
  id: string;
  driver_id: string;
  driver_name: string;
  created_at: string;
  version: number;
  review_status: string;
  merchant?: string | null;
  amount_pence?: number | null;
  occurred_on?: string | null;
  suggested_category: string | null;
  confidence?: number | string | Record<string, number> | null;
  warnings: string[];
  feedback_verdict: string | null;
  feedback_by: string | null;
  feedback_reason: string | null;
}
export interface AiSummary {
  extractions: number;
  reviewed: number;
  open: number;
  accepted: number;
  corrected: number;
  rejected: number;
  acceptance_percent: number | null;
}
export interface StaffRow extends Staff {
  active: boolean;
  version: number;
  last_seen_at: string | null;
  assigned_drivers: number;
}
export interface AdminOverview {
  tax_year: string;
  as_of: string;
  drivers: { total: number; unassigned: number };
  staff: { admins: number; accountants: number; inactive: number };
  handoffs: { open: number; unassigned: number; new: number; in_review: number; waiting_on_driver: number; ready_to_file: number };
  returns: { in_preparation: number; awaiting_driver: number; driver_approved: number; filed: number };
  privacy: { open: number; overdue: number };
  rates: { draft: number; approved: number };
  ai_reviews_open: number;
  deadline: { due_on: string; days_remaining: number; tax_year: string };
  workload: { id: string; name: string; active: boolean; assigned_drivers: number; open_handoffs: number; returns_in_progress: number }[];
}
export interface RateRow {
  id: string;
  tax_year: string;
  region: string;
  code: string;
  value: Record<string, unknown>;
  status: "draft" | "approved" | "active" | "retired";
  official_url: string;
  reason: string;
  version: number;
  created_by_name: string | null;
  approved_by_name: string | null;
  created_at: string;
  activated_at: string | null;
}
export interface PrivacyRow {
  id: string;
  driver_id: string;
  driver_name: string;
  driver_email: string | null;
  kind: "export" | "access" | "correction" | "deletion";
  status: "received" | "in_progress" | "completed" | "rejected";
  detail: string | null;
  due_on: string;
  retain_until: string | null;
  resolution: string | null;
  handled_by_name: string | null;
  overdue: boolean;
  version: number;
  created_at: string;
  completed_at: string | null;
}
export interface ComplianceRow {
  id: string;
  doc_type: string;
  reference: string | null;
  expires_on: string | null;
  days_remaining: number | null;
  expiry_status: string;
  created_at: string;
}
export interface MtdView {
  status: string;
  start_date: string | null;
  confidence: string | null;
  reason: string;
  years_below_count: number;
  threshold_pence: number | null;
  qualifying_income_pence: number | null;
  test_year: string | null;
  near_threshold: boolean;
  history: { tax_year: string; gross_se_income_pence: number; gross_property_income_pence?: number; paye_income_pence?: number; source: string }[];
  vat: { rolling_turnover_pence: number; threshold_pence: number; percent_of_threshold: number; status: string; note: string };
  platform: Record<string, { source: string; app_gross_pence: number; platform_reported_gross_pence: number | null; difference_pence: number | null; status: string; dispute_note: string | null }[]>;
}
export type DriverResource =
  | "income"
  | "expenses"
  | "mileage"
  | "documents"
  | "messages"
  | "notes"
  | "activity";
export const initialQuery: TableQuery = {
  page: 1,
  page_size: 25,
  sort: "created_at",
  order: "desc",
  search: "",
  filters: {},
};
