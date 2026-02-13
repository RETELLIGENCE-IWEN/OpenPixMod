import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def _asset_path(*parts: str) -> Path:
    # PyInstaller onefile extracts bundled files under sys._MEIPASS.
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / Path(*parts)
    return Path(__file__).resolve().parent / Path(*parts)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("OpenPixMod")
    app.setOrganizationName("OpenPixMod")

    logo_path = _asset_path("assets", "Logo.png")
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    w = MainWindow(logo_path=logo_path)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
