import sys
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("OpenPixMod")
    app.setOrganizationName("OpenPixMod")

    logo_path = Path(__file__).resolve().parent / "ui" / "Logo.png"
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    w = MainWindow()
    w.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
