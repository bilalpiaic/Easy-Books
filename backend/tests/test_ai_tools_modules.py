"""Module-gated AI tools + agents (PR3 of the AI expansion).

Executor smoke tests for every module tool against a real in-memory DB (no
LLM) — including the (user, session) arg-order functions (hrm/healthcare),
where a swapped-args bug would only surface at runtime — plus triage-prompt
module gating and one routed module-agent pipeline test."""
import json

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models import User
from services.ai_agents import AGENTS
from services.ai_tools import TOOL_REGISTRY, execute_tool, filter_by_modules


def _signup(client, email, company="Co"):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": company, "business_model": "simple",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install(client, auth, *modules):
    for m in modules:
        r = client.post(f"/api/modules/{m}/install", headers=auth)
        assert r.status_code in (200, 201), f"{m}: {r.text}"


def _user_for(client, email) -> tuple[Session, User]:
    session = Session(client.app.state.engine)
    user = session.exec(select(User).where(User.email == email)).first()
    assert user is not None
    return session, user


def _run(session, user, name, tool_input=None):
    text, is_error = execute_tool(name, tool_input or {}, session, user)
    return json.loads(text), is_error


def test_module_tools_smoke(client: TestClient):
    """Every module tool executes without error once its module is installed.
    Books are mostly empty — this locks signatures and arg order, not figures."""
    auth = _signup(client, "mt1@t.com")
    # deps are installed recursively by the modules router
    _install(client, auth, "inventory", "production", "hrm", "telecom",
             "healthcare", "purchase_store", "weaving", "pra")

    r = client.post("/api/products", headers=auth,
                    json={"name": "Widget", "product_type": "stock"})
    assert r.status_code in (200, 201), r.text
    product_id = r.json()["id"]
    r = client.post("/api/employees", headers=auth, json={"name": "Jo Worker"})
    assert r.status_code in (200, 201), r.text
    r = client.post("/api/healthcare/patients", headers=auth, json={"name": "Pat Ient"})
    assert r.status_code in (200, 201), r.text
    patient_id = r.json()["id"]

    r = client.post("/api/customers", headers=auth, json={"name": "Weave Co"})
    assert r.status_code in (200, 201), r.text
    customer_id = r.json()["id"]
    r = client.post("/api/weaving/contracts", headers=auth, json={
        "customer_id": customer_id,
        "start_date": "2026-01-01",
        "contract_meters": 1000,
        "pick_per_inch": 50,
        "assumed_yarn_rate_per_kg": 10,
        "fabric_return_price_per_meter": 5,
        "weaving_rate": 2,
        "expected_shrinkage_pct": 1,
    })
    assert r.status_code in (200, 201), r.text
    wv_contract_id = r.json()["id"]

    r = client.post("/api/invoices", headers=auth, json={
        "customer_id": customer_id,
        "issue_date": "2026-07-20",
        "due_date": "2026-08-20",
        "lines": [{"description": "Svc", "qty": 1, "rate": 100}],
    })
    assert r.status_code in (200, 201), r.text
    invoice_id = r.json()["id"]

    session, user = _user_for(client, "mt1@t.com")
    try:
        cases = {
            # inventory
            "get_product_ledger": {"product_id": product_id},
            "get_inventory_performance": {},
            "get_product_performance": {},
            "get_product_valuation": {},
            "find_product": {"query": "wid"},
            # hrm — (user, session) arg order inside
            "get_hrm_summary": {},
            "get_attendance_summary": {"year": 2026, "month": 7},
            "find_employee": {"query": "jo"},
            # healthcare — (user, session) arg order inside
            "get_healthcare_dashboard": {},
            "get_opd_summary": {},
            "get_doctor_collections": {},
            "get_lab_summary": {},
            "get_ipd_census": {},
            "get_hc_revenue_by_type": {},
            "get_patient_statement": {"patient_id": patient_id},
            "find_patient": {"query": "pat"},
            # telecom
            "get_telecom_dashboard": {},
            "get_commission_aging": {},
            "get_float_statement": {},
            "get_sim_utilisation": {},
            "get_revenue_by_stream": {},
            "get_fca_target_progress": {},
            "get_stock_issuance": {},
            "get_rso_ledger": {},
            "find_rso": {"query": "x"},
            "get_postpaid_book": {},
            "get_tracker_statement": {},
            # purchase_store
            "get_gate_register": {},
            "get_three_way_match": {},
            "get_purchase_vendor_performance": {},
            "get_gate_outward_register": {},
            "get_dispatch_reconciliation": {},
            "get_issue_register": {},
            "get_stock_tie_out": {},
            # production
            "get_manufacturing_dashboard": {},
            "get_wip_aging": {},
            "get_production_summary": {},
            "get_customer_custody": {},
            # weaving — (user, session) arg order inside
            "get_weaving_dashboard": {},
            "get_weaving_daily": {},
            "get_contract_control": {"contract_id": wv_contract_id},
            "get_weaving_customer_kpi": {},
            "find_wv_contract": {"query": "WC"},
            # pra
            "get_pra_logs": {},
            "get_invoice_pra_status": {"invoice_id": invoice_id},
            "get_pra_today_summary": {"start": "2026-07-01", "end": "2026-07-31"},
        }
        for name, tool_input in cases.items():
            payload, is_error = _run(session, user, name, tool_input)
            assert is_error is False, f"{name}: {payload}"
    finally:
        session.close()


def test_every_module_tool_is_smoke_tested():
    """Guard: any future module tool must be added to the smoke test above."""
    module_tools = {n for n, t in TOOL_REGISTRY.items() if t.required_module is not None}
    import inspect
    src = inspect.getsource(test_module_tools_smoke)
    missing = {n for n in module_tools if f'"{n}"' not in src}
    assert not missing, f"module tools missing from smoke test: {sorted(missing)}"


def test_filter_by_modules_gates_tools():
    all_names = list(TOOL_REGISTRY)
    base_only = filter_by_modules(all_names, {"base"})
    assert "get_ar_aging" in base_only
    assert "get_hrm_summary" not in base_only
    assert "get_telecom_dashboard" not in base_only
    with_hrm = filter_by_modules(all_names, {"base", "hrm"})
    assert "get_hrm_summary" in with_hrm
    assert "get_telecom_dashboard" not in with_hrm


def test_agent_tools_stay_inside_their_module():
    """Each module-gated agent may only reference base tools or tools of its
    own module — anything else would be silently dropped by the runtime
    module filter and confuse the specialist's prompt."""
    for agent in AGENTS.values():
        allowed = {None, agent.required_module}
        for name in agent.tools:
            mod = TOOL_REGISTRY[name].required_module
            assert mod in allowed, (
                f"agent {agent.key!r} (module {agent.required_module!r}) references "
                f"tool {name!r} from module {mod!r}"
            )


# ── LLM-pipeline tests (mocked litellm) ──────────────────────────────────────

class _Delta:
    def __init__(self, content=None):
        self.content = content
        self.tool_calls = None

class _Choice:
    def __init__(self, content=None, finish_reason=None):
        self.delta = _Delta(content)
        self.finish_reason = finish_reason

class _Chunk:
    def __init__(self, **kw):
        self.choices = [_Choice(**kw)]

def _stream_from(chunks):
    async def gen():
        for c in chunks:
            yield c
    return gen()


class _Message:
    def __init__(self, content):
        self.content = content

class _MsgChoice:
    def __init__(self, content):
        self.message = _Message(content)

class _Completion:
    def __init__(self, content):
        self.choices = [_MsgChoice(content)]


def _ai_setup(client, monkeypatch, email, *extra_modules):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    auth = _signup(client, email)
    _install(client, auth, "ai_assistant", *extra_modules)
    client.patch("/api/settings", headers=auth, json={"ai_api_key_openai": "sk-test"})
    sid = client.post("/api/ai/sessions", headers=auth, json={}).json()["id"]
    return auth, sid


def test_uninstalled_module_agent_absent_from_triage_and_unroutable(client: TestClient, monkeypatch):
    """Without hrm installed, the payroll agent must not be offered to triage,
    and even a triage response naming it must fall back to general."""
    auth, sid = _ai_setup(client, monkeypatch, "mt2@t.com")   # no hrm

    triage_prompts = []
    calls = []
    async def fake_acompletion(**kwargs):
        if kwargs.get("stream") is False:
            triage_prompts.append(kwargs["messages"][0]["content"])
            return _Completion("payroll")          # names a gated agent
        calls.append(kwargs)
        return _stream_from([_Chunk(content="ok"), _Chunk(finish_reason="stop")])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "how many employees do I have?"}) as r:
        list(r.iter_lines())

    assert "payroll" not in triage_prompts[0]
    assert "telecom" not in triage_prompts[0]
    # routed to general (all 7 base fallback tools), not the gated agent
    tool_names = {t["function"]["name"] for t in calls[0]["tools"]}
    assert tool_names == set(AGENTS["general"].tools)


def test_installed_module_routes_to_module_agent(client: TestClient, monkeypatch):
    """With telecom installed, triage sees the telecom agent and the
    specialist runs with exactly its tool subset."""
    auth, sid = _ai_setup(client, monkeypatch, "mt3@t.com", "telecom")

    triage_prompts = []
    calls = []
    async def fake_acompletion(**kwargs):
        if kwargs.get("stream") is False:
            triage_prompts.append(kwargs["messages"][0]["content"])
            return _Completion("telecom")
        calls.append(kwargs)
        return _stream_from([_Chunk(content="Float looks fine."), _Chunk(finish_reason="stop")])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "what is my float position?"}) as r:
        lines = list(r.iter_lines())

    assert "telecom" in triage_prompts[0]
    tool_names = {t["function"]["name"] for t in calls[0]["tools"]}
    assert tool_names == set(AGENTS["telecom"].tools)
    stage_labels = [
        json.loads(l[len("data: "):]).get("label", "")
        for l in lines
        if l.startswith("data: ") and json.loads(l[len("data: "):]).get("type") == "stage"
    ]
    assert any("Telecom Agent" in s for s in stage_labels)
