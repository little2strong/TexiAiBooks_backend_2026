"""Export secret-free OpenAPI and honest proposed-operation coverage, without DB access."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
# Documentation-only values; no actual credential is needed to build OpenAPI.
os.environ.setdefault("POSTGRES_PASSWORD","documentation-process-password-not-for-deployment")
os.environ.setdefault("JWT_SECRET_KEY","documentation-process-signing-key-not-for-deployment")

from app.core.config import Settings
from app.main import create_app

EXTERNAL={"A01","A02","A03","A07","V01","C08","S03","S04","S05","S06",
          "U02","U03","U04","U05","U06","U07","U08","U09","U10","B02"}
EVIDENCE={
    "A":"tests/test_auth.py, test_auth_security.py, test_identity.py, test_books_integrations.py",
    "P":"tests/test_books.py, test_books_integrations.py, test_books_workflows.py",
    "F":"tests/test_books_workflows.py",
    "I":"tests/test_books_workflows.py",
    "V":"tests/test_books.py, test_books_workflows.py; HMRC vehicle guidance",
    "L":"tests/test_books.py, test_books_concurrency.py",
    "R":"tests/test_books_integrations.py, test_books_workflows.py",
    "C":"tests/test_books.py, test_books_workflows.py; controlled scanner/OCR",
    "D":"tests/test_books.py, test_books_workflows.py; canonical CSV only",
    "Q":"tests/test_books.py, test_books_workflows.py; both resolution modes",
    "M":"tests/test_books.py, test_books_workflows.py",
    "T":"tests/test_books.py, test_books_integrations.py, test_books_workflows.py; official source registry",
    "K":"tests/test_books.py, test_books_workflows.py",
    "N":"tests/test_books_workflows.py; in-app feed only",
    "E":"tests/test_books.py, test_books_workflows.py; real CSV/PDF/ZIP output",
    "H":"tests/test_books_workflows.py; request recording, no delivery claim",
    "S":"tests/test_books_integrations.py; configured trial policy, disabled billing boundary",
    "U":"tests/test_books_integrations.py; immutable preview, durable outbox, controlled acknowledgement/timeout",
    "B":"tests/test_books_integrations.py; opt-in context, failed-provider persistence",
}


def notes(id):
    if id in {"A01","A02","A07"}: return "Challenge lifecycle implemented; real SMS adapter, encryption key ring and stable phone hashing key required"
    if id=="A03": return "Existing signed OIDC verifier retained; approved client IDs and native provider flow required"
    if id=="V01": return "Returns unavailable/manual fallback until a lookup provider is installed"
    if id=="C08": return "Retry lifecycle works; scanner/OCR provider required for extraction success; manual review works independently"
    if id=="S03": return "Trial lifecycle tested with synthetic approved offer; real price/terms/cohort policy must be supplied"
    if id in {"S04","S05","S06"}: return "Selected billing provider/signature protocol required; unavailable returns 503; never acknowledges unverified events"
    if id.startswith("U") and id!="U01": return "Internal HMRC contracts/outbox implemented and controlled-tested; live OAuth, obligation mapping, provider worker, recognition and fraud headers required"
    if id=="B02": return "Assistant adapter/consent policy required; absent provider returns 503, provider failure persists failed outcome"
    if id.startswith("D"): return "Usable canonical CSV workflow; native Uber/Bolt PDF templates remain blocked on representative files and parser specification"
    if id=="F01": return "Stable code/UUID catalogs; council codes entered manually; no council authority validation claimed"
    if id=="H01": return "Verified recipient configuration and consent required; records requested/delivered=false only"
    if id=="R07": return "Prospective or reasoned open-year correction of inherited defaults; explicit per-record shares remain authoritative"
    if id.startswith("T"): return "2025-26/2026-27 estimates, declared simplified tax scope; no assessed-liability or full-return claim"
    if id in {"S01","S02"}: return "Empty catalog/no subscription by default; entitlements follow approved configured offers and verified events"
    return "Implemented internal contract; see OpenAPI and workflow tests"


def main():
    settings=Settings(_env_file=None,postgres_password="documentation-process-password-not-for-deployment",
        jwt_secret_key="documentation-process-signing-key-not-for-deployment")
    app=create_app(settings)
    schema=app.openapi()
    operations={v["operationId"]:(method.upper(),path,v) for path,methods in schema["paths"].items()
                for method,v in methods.items() if method in {"get","post","put","patch","delete"}}
    proposed=json.loads((ROOT/"docs/proposed_operations.json").read_text(encoding="utf-8"))
    coverage=[]
    for operation in proposed:
        id=operation["id"]
        method,path,contract=operations[id]
        coverage.append({"id":id,"proposed_path":operation["path"],"method":method,"actual_path":path,
            "status":"External dependency required" if id in EXTERNAL else "Existing and verified",
            "evidence":EVIDENCE[id[0]],"notes":notes(id)})
    (ROOT/"docs/openapi.json").write_text(json.dumps(schema,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (ROOT/"docs/operation_coverage.json").write_text(json.dumps(coverage,indent=2)+"\n",encoding="utf-8")
    summary=["# Actual API contracts","",
        "Generated by `python scripts/export_contracts.py`. Exact schemas, defaults and validation: [openapi.json](openapi.json). Proposed requests are preserved separately in [proposed_operations.json](proposed_operations.json).",
        "",f"{len(operations)} actual HTTP method/path operations; all {len(coverage)} proposed IDs accounted for. Of those, {len(coverage)-len(EXTERNAL)} internal contracts are implemented and {len(EXTERNAL)} remain integration/configuration dependent. A registered route is not evidence of a live external integration.",
        "","Base prefix is `/api/v1`; health endpoints remain `/health` and `/health/db`. Protected endpoints use Bearer access JWT. Existing form login and password recovery contracts remain available. See [AUTH_API.md](AUTH_API.md) and the frontend handoff for wire examples.",
        "","| ID | Actual method and path | Classification | Evidence / limitations |","| --- | --- | --- | --- |"]
    for op in coverage:
        summary.append(f"| {op['id']} | {op['method']} `{op['actual_path']}` | {op['status']} | {op['notes']}; {op['evidence']} |")
    summary += ["","Additional operations:",""]
    for id,(method,path,_) in sorted(operations.items(),key=lambda x:x[1][1]):
        if id not in {item["id"] for item in coverage}: summary.append(f"- {method} `{path}`")
    (ROOT/"docs/ACTUAL_API_CONTRACTS.md").write_text("\n".join(summary)+"\n",encoding="utf-8")
    print(f"Exported {len(operations)} operations; {len(coverage)} proposed IDs; {len(EXTERNAL)} explicitly dependent.")


if __name__=="__main__": main()
