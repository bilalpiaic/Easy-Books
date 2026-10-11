"""docs/Easy-Books_Installer.bat must stay wired to the live Windows install path."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "docs" / "Easy-Books_Installer.bat"


def test_easy_books_installer_bat_exists_and_hands_off_to_install_and_run():
    text = INSTALLER.read_text(encoding="utf-8")
    assert INSTALLER.is_file()
    assert "https://github.com/bilalpiaic/Easy-Books.git" in text
    assert "install-and-run.bat" in text
    assert "git pull --ff-only" in text
    assert "frontend/package-lock.json" in text
    assert "Easy-Books.bat" in text
    assert "Git.Git" in text
