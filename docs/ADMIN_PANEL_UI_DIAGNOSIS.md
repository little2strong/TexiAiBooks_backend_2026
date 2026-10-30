# Phase 1 — diagnosis before application changes

Baseline: production preview, Chromium, 1440×900, normal motion, fixed 800 ms API latency, disposable PostgreSQL with synthetic records. See `artifacts/ui-debug/before/` for Lighthouse, Chrome CPU profile, layout events, screenshots and actual API samples. No development records were inserted.

| Symptom / screen | Root cause | Baseline source | Proposed fix |
| --- | --- | --- | --- |
| Queue jumps: measured table height 426 px → 242.27 px | Five-line skeleton is replaced by a differently sized table; footer moves ~185 px | `DataTable.tsx:326`, `styles.css:670` | Shared states inside one fixed scrolling table viewport |
| Sidebar/navigation movement | Width/margin animation; mount transforms create containing contexts around sticky elements | `styles.css:186,346,401,860` | Remove layout animation; stable scrollbar gutter |
| Selection clears after parent updates | Effect depends on query object identity rather than values | `DataTable.tsx:137` | Canonical value dependencies; keep content-hashed React Query keys |
| Blank/crashed panel on unexpected data | JSON is cast, not validated; no empty fallback or error boundary; invalid dates throw | `client.ts:100`, `States.tsx:4`, `format.ts:2`, `main.tsx:90,135` | Resource schemas, explicit unknown values, shared states, route/panel boundaries |
| Profile/mileage/tax loading movement | Generic skeleton replaces multi-panel layout; mileage summary inserted after response | `DriverProfile.tsx:139,170,234` | Matching reserved layouts and always-present summary |
| Invisible row actions | Actions use opacity zero until hover | `styles.css:1272` | Keep actions visible and keyboard accessible |
| Fonts/media can resize | Fonts swap without adjusted fallback/preload; image lacks aspect ratio | `main.tsx:24`, `styles.css:1020` | Preload primary face, adjusted fallback, explicit media frame |
| Errors hard to diagnose | HTTP status mapped to generic message, request identifier discarded; 401 redirect loses message | `client.ts:78` | Visible request ID and session-expired notice |
| Unexplained workflow/figures | Status tags lack meaning; existing tax bands, PAYE and loan inputs omitted | `StatusBadge.tsx:10`, `DriverProfile.tsx:137` | Glossary, next action, breakdowns using server figures/rates |
| Missing workflow timestamps/reviewer attribution | Read responses omit existing audit metadata | `staff.py:90,258,295` | Add read-only audit projections; never invent names/times |
| Some empty real screens | Local DB contains zero drivers; access scope also filters records | Staff driver search | Explicit no-record/scope explanation and clear-filter action |

Corrected baseline CLS: dashboard 0.011308, handoffs 0.005100, driver profile 0.001688, tax workspace 0.006546. An initial 0.403116 handoff reading included full-page screenshot viewport resizing inside the measurement window and was discarded. The original source snapshot was rerun with screenshots outside that window. All four corrected baseline values are below 0.1; the evidence supports a real table-size mismatch, not a claim that this small synthetic journey reproduced severe production CLS. No console errors occurred in these four baseline journeys. No confirmed infinite render loop: React Query hashes query contents. No random row keys, competing Tailwind/theme providers, incorrect resource/accessor mapping or field-name mismatch in captured responses. Styleguide chart already has a sized 180 px parent. Hover borders keep their width. These checks do not establish correctness for unobserved production data.

Additional contract defect from source: populated payment timelines use `type`, while the UI unconditionally calls `.replace` on `label_key`; a prior-assessment profile can therefore crash the tax panel. Normalize the two documented payment variants at the API boundary.

Filing policy from backend: admin/senior role, current `ready_to_file`, real external reference and current record version. Pending receipts and reconciliation issues are review advisories, not enforced filing gates. This UI must not claim otherwise. The panel records an external filing; it does not submit to HMRC.
