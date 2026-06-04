"""ui_density setting round-trips through the settings PATCH."""


def test_ui_density_persists(client, admin_headers):
    h = admin_headers
    r = client.patch("/api/settings", headers=h, json={"ui_density": "compact"})
    assert r.status_code == 200
    got = client.get("/api/settings", headers=h).json()
    assert got["ui_density"] == "compact"


def test_ui_density_rejects_invalid(client, admin_headers):
    r = client.patch("/api/settings", headers=admin_headers, json={"ui_density": "huge"})
    assert r.status_code == 400
