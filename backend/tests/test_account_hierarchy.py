"""
Task 2 tests: hierarchy validation, next-code, activate/deactivate, tree payload.

Tests:
  1. List payload includes parent_id, is_group, is_active, has_children, postable, depth.
  2. Duplicate name under SAME parent → 400; same name under DIFFERENT parents → OK.
  3. Cycle: setting parent_id to self or descendant → 400.
  4. Create child under an account that already has journal entries → 400.
  5. GET /api/accounts/next-code?parent_id={p} → non-empty code not already used.
  6. PATCH /api/accounts/{id}/active?is_active=false → postable becomes false; posting blocked.
"""


def _acct(client, h, code, name, account_type="Asset", parent_id=None, is_group=False):
    r = client.post("/api/accounts", headers=h, json={
        "code": code,
        "name": name,
        "type": account_type,
        "parent_id": parent_id,
        "is_group": is_group,
    })
    assert r.status_code == 200, f"_acct {code}: {r.text}"
    return r.json()


def _post_jv(client, h, dr_id, cr_id, amt=10):
    """Post a balanced manual JV using account IDs."""
    return client.post("/api/transactions", headers=h, json={
        "date": "2026-04-01",
        "description": "test hierarchy",
        "entries": [
            {"account_id": dr_id, "debit": amt, "credit": 0},
            {"account_id": cr_id, "debit": 0, "credit": amt},
        ],
    })


# ── Test 1: List payload fields ──────────────────────────────────────────────

def test_list_payload_includes_tree_fields(client, admin_headers):
    h = admin_headers
    parent = _acct(client, h, "8100", "Parent Account")
    child = _acct(client, h, "8101", "Child Account", parent_id=parent["id"])

    r = client.get("/api/accounts", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]

    # Find parent and child in list
    parent_item = next(i for i in items if i["id"] == parent["id"])
    child_item = next(i for i in items if i["id"] == child["id"])

    # Parent item should have all required fields
    for field in ("parent_id", "is_group", "is_active", "has_children", "postable", "depth"):
        assert field in parent_item, f"Missing field '{field}' in list item"

    # Parent: has_children=True, postable=False, depth=0
    assert parent_item["has_children"] is True
    assert parent_item["postable"] is False
    assert parent_item["depth"] == 0
    assert parent_item["parent_id"] is None

    # Child: has_children=False, postable=True, depth=1
    assert child_item["has_children"] is False
    assert child_item["postable"] is True
    assert child_item["depth"] == 1
    assert child_item["parent_id"] == parent["id"]


def test_group_account_not_postable(client, admin_headers):
    h = admin_headers
    g = _acct(client, h, "8200", "Group Hdr", is_group=True)

    r = client.get("/api/accounts", headers=h)
    items = r.json()["items"]
    g_item = next(i for i in items if i["id"] == g["id"])

    assert g_item["is_group"] is True
    assert g_item["postable"] is False


# ── Test 2: Duplicate name within same parent ─────────────────────────────────

def test_dup_name_same_parent_rejected(client, admin_headers):
    h = admin_headers
    parent = _acct(client, h, "7100", "Container")

    _acct(client, h, "7101", "Sub Account", parent_id=parent["id"])

    # Same name under same parent → should be rejected
    r = client.post("/api/accounts", headers=h, json={
        "code": "7102",
        "name": "Sub Account",  # same name
        "type": "Asset",
        "parent_id": parent["id"],
    })
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"


def test_dup_name_different_parent_ok(client, admin_headers):
    h = admin_headers
    parent_a = _acct(client, h, "7200", "Parent A")
    parent_b = _acct(client, h, "7300", "Parent B")

    # Same name under different parents → OK
    _acct(client, h, "7201", "Shared Name", parent_id=parent_a["id"])
    r = client.post("/api/accounts", headers=h, json={
        "code": "7301",
        "name": "Shared Name",  # same name, different parent
        "type": "Asset",
        "parent_id": parent_b["id"],
    })
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


def test_dup_name_top_level_rejected(client, admin_headers):
    """Two top-level accounts (parent_id=None) with same name → 400."""
    h = admin_headers
    _acct(client, h, "7400", "Top Level Name")
    r = client.post("/api/accounts", headers=h, json={
        "code": "7401",
        "name": "Top Level Name",  # same name, both top-level (parent_id=None)
        "type": "Asset",
    })
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"


def test_dup_name_top_level_vs_under_parent_ok(client, admin_headers):
    """Same name at top-level vs under a parent → OK (different parents)."""
    h = admin_headers
    parent = _acct(client, h, "7500", "Parent Container")
    _acct(client, h, "7501", "Unique Name")  # top-level

    r = client.post("/api/accounts", headers=h, json={
        "code": "7502",
        "name": "Unique Name",  # same name but under a parent
        "type": "Asset",
        "parent_id": parent["id"],
    })
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


# ── Test 3: Cycle detection ──────────────────────────────────────────────────

def test_cycle_self_parent_rejected(client, admin_headers):
    """Setting an account's parent to itself → 400."""
    h = admin_headers
    acct = _acct(client, h, "6100", "Self Ref")

    r = client.put(f"/api/accounts/{acct['id']}", headers=h, json={
        "parent_id": acct["id"],
    })
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    assert "cycle" in r.text.lower() or "self" in r.text.lower(), r.text


def test_cycle_descendant_parent_rejected(client, admin_headers):
    """Setting an account's parent to one of its descendants → 400."""
    h = admin_headers
    grandparent = _acct(client, h, "6200", "Grandparent")
    parent = _acct(client, h, "6201", "Parent", parent_id=grandparent["id"])
    child = _acct(client, h, "6202", "Child", parent_id=parent["id"])

    # Try to set grandparent's parent to child (creating a cycle)
    r = client.put(f"/api/accounts/{grandparent['id']}", headers=h, json={
        "parent_id": child["id"],
    })
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    assert "cycle" in r.text.lower(), r.text


def test_create_with_valid_parent_ok(client, admin_headers):
    """Creating a normal parent→child relationship is OK."""
    h = admin_headers
    parent = _acct(client, h, "6300", "Valid Parent")
    r = client.post("/api/accounts", headers=h, json={
        "code": "6301",
        "name": "Valid Child",
        "type": "Asset",
        "parent_id": parent["id"],
    })
    assert r.status_code == 200, r.text


# ── Test 4: Cannot create child under account that has postings ───────────────

def test_cannot_create_child_under_posted_account(client, admin_headers):
    """Creating a child under an account that already has JE postings → 400."""
    h = admin_headers
    # Create two leaf accounts and post a JV to the first one
    dr_acct = _acct(client, h, "5100", "DR Account")
    cr_acct = _acct(client, h, "5101", "CR Account")

    jv_r = _post_jv(client, h, dr_acct["id"], cr_acct["id"])
    assert jv_r.status_code in (200, 201), f"JV post failed: {jv_r.text}"

    # Now try to create a child under dr_acct (which has postings)
    r = client.post("/api/accounts", headers=h, json={
        "code": "5102",
        "name": "Child of Posted",
        "type": "Asset",
        "parent_id": dr_acct["id"],
    })
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    assert "posting" in r.text.lower() or "post" in r.text.lower(), r.text


def test_cannot_move_account_under_posted_account(client, admin_headers):
    """Moving (updating parent_id) an account under a posted account → 400."""
    h = admin_headers
    dr_acct = _acct(client, h, "5200", "DR Acct2")
    cr_acct = _acct(client, h, "5201", "CR Acct2")
    to_move = _acct(client, h, "5202", "Move Me")

    # Post a JV to dr_acct
    jv_r = _post_jv(client, h, dr_acct["id"], cr_acct["id"])
    assert jv_r.status_code in (200, 201), f"JV post failed: {jv_r.text}"

    # Try to move to_move under dr_acct (which has postings)
    r = client.put(f"/api/accounts/{to_move['id']}", headers=h, json={
        "parent_id": dr_acct["id"],
    })
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"


# ── Test 5: next-code endpoint ───────────────────────────────────────────────

def test_next_code_with_parent(client, admin_headers):
    """GET /api/accounts/next-code?parent_id=X → non-empty code not already used."""
    h = admin_headers
    parent = _acct(client, h, "4100", "Code Parent")

    r = client.get(f"/api/accounts/next-code?parent_id={parent['id']}", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "code" in data
    suggested = data["code"]
    assert suggested  # non-empty

    # The suggested code must not already be used
    existing_r = client.get("/api/accounts", headers=h)
    existing_codes = {i["code"] for i in existing_r.json()["items"]}
    assert suggested not in existing_codes, f"Suggested code '{suggested}' already in use"


def test_next_code_without_parent(client, admin_headers):
    """GET /api/accounts/next-code (no parent_id) → non-empty top-level suggestion."""
    h = admin_headers

    r = client.get("/api/accounts/next-code", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "code" in data
    assert data["code"]  # non-empty


def test_next_code_not_already_used(client, admin_headers):
    """Suggested code must not collide with an already-existing code."""
    h = admin_headers
    parent = _acct(client, h, "8500", "NC Parent")
    # Pre-create some children to force the suggestion past them
    _acct(client, h, "8501", "Child A", parent_id=parent["id"])
    _acct(client, h, "8502", "Child B", parent_id=parent["id"])

    r = client.get(f"/api/accounts/next-code?parent_id={parent['id']}", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    suggested = data["code"]

    existing_r = client.get("/api/accounts", headers=h)
    existing_codes = {i["code"] for i in existing_r.json()["items"]}
    assert suggested not in existing_codes, f"Suggested code '{suggested}' is already in use"


# ── Test 6: PATCH /api/accounts/{id}/active ──────────────────────────────────

def test_deactivate_account(client, admin_headers):
    """PATCH /api/accounts/{id}/active?is_active=false → postable becomes false."""
    h = admin_headers
    acct = _acct(client, h, "8600", "Deactivate Me")

    # Deactivate
    r = client.patch(f"/api/accounts/{acct['id']}/active?is_active=false", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_active"] is False

    # List should show postable=False
    list_r = client.get("/api/accounts", headers=h)
    items = list_r.json()["items"]
    item = next(i for i in items if i["id"] == acct["id"])
    assert item["is_active"] is False
    assert item["postable"] is False


def test_deactivated_account_blocks_posting(client, admin_headers):
    """Posting to a deactivated account is blocked."""
    h = admin_headers
    dr_acct = _acct(client, h, "8700", "Inactive Acct")
    cr_acct = _acct(client, h, "8701", "Active Acct")

    # Deactivate dr_acct
    r = client.patch(f"/api/accounts/{dr_acct['id']}/active?is_active=false", headers=h)
    assert r.status_code == 200, r.text

    # Try to post to the deactivated account
    jv_r = _post_jv(client, h, dr_acct["id"], cr_acct["id"])
    assert jv_r.status_code == 400, f"Expected 400, got {jv_r.status_code}: {jv_r.text}"
    assert "inactive" in jv_r.text.lower(), jv_r.text


def test_reactivate_account(client, admin_headers):
    """Reactivating a deactivated account allows posting again."""
    h = admin_headers
    acct_a = _acct(client, h, "8800", "Reactivate Me")
    acct_b = _acct(client, h, "8801", "Partner")

    # Deactivate then reactivate
    client.patch(f"/api/accounts/{acct_a['id']}/active?is_active=false", headers=h)
    r = client.patch(f"/api/accounts/{acct_a['id']}/active?is_active=true", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is True

    # Posting should now succeed
    jv_r = _post_jv(client, h, acct_a["id"], acct_b["id"])
    assert jv_r.status_code in (200, 201), jv_r.text


def test_activate_nonexistent_account(client, admin_headers):
    """PATCH /api/accounts/99999/active → 404."""
    h = admin_headers
    r = client.patch("/api/accounts/99999/active?is_active=false", headers=h)
    assert r.status_code == 404, r.text


# ── Test 7: Type defaults from parent ────────────────────────────────────────

def test_type_defaults_from_parent(client, admin_headers):
    """When type is omitted on create, it defaults from parent's type."""
    h = admin_headers
    parent = _acct(client, h, "1800", "Liability Parent", account_type="Liability")

    r = client.post("/api/accounts", headers=h, json={
        "code": "1801",
        "name": "Child No Type",
        "parent_id": parent["id"],
        # no 'type' field
    })
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "Liability"
