"""Dashboard staff-rights resources are registered and wired to routes."""
from services.permissions import PERMISSION_RESOURCES


def test_dashboard_resources_registered():
    assert "dashboard.financial" in PERMISSION_RESOURCES
    assert "dashboard.operations" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["dashboard.financial"]["category"] == "Dashboard"
    assert PERMISSION_RESOURCES["dashboard.operations"]["category"] == "Dashboard"
    assert PERMISSION_RESOURCES["dashboard.financial"]["label"] == "Financial Dashboard"
    assert PERMISSION_RESOURCES["dashboard.operations"]["label"] == "Operations Dashboard"
