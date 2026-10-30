export type Role = "accountant" | "senior_accountant" | "admin" | "support";
export interface Staff {
  id: string;
  name: string;
  email: string;
  role: Role;
  team_id: string | null;
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
  subscription: { status: string; plan_id?: string; renew_at?: string };
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
