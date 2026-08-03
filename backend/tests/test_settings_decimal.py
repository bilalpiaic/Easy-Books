"""decimal_places setting round-trips and rejects invalid values."""

import pytest


@pytest.mark.parametrize("dp", ["0", "2", "4"])
def test_decimal_places_persists(client, admin_headers, dp):
    h = admin_headers
    r = client.patch("/api/settings", headers=h, json={"decimal_places": dp})
    assert r.status_code == 200
    got = client.get("/api/settings", headers=h).json()
    assert got["decimal_places"] == dp


def test_decimal_places_rejects_invalid(client, admin_headers):
    r = client.patch("/api/settings", headers=admin_headers, json={"decimal_places": "3"})
    assert r.status_code == 400
