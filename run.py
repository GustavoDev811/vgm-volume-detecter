#!/usr/bin/env python3
import sys
import os
import traceback

def _log_error(msg: str):
    """Salva erro em arquivo log ao lado do executável."""
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "vgmvolumedetector_error.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

try:
    from VGMVolumeDetector.gui import main
    if __name__ == "__main__":
        main()
except Exception as e:
    err = f"ERRO FATAL:\n{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
    _log_error(err)
    # Tenta mostrar caixa de erro mesmo sem GUI
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "VGM Volume Detecter — Erro Fatal", err[:800])
    except Exception:
        pass
    sys.exit(1)
