"""
Build do VGMVolumeDetector.exe usando PyInstaller.
Execute este script na pasta C:\\VGMVolumeDetector:
    python build_exe.py
O .exe será gerado em dist\\VGMVolumeDetector.exe
"""

import subprocess
import sys
import os

def main():
    # Verifica se PyInstaller está instalado
    try:
        import PyInstaller
    except ImportError:
        print("Instalando PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Caminho da logo para incluir no exe
    logo = os.path.join("VGMVolumeDetector", "logo.png")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                        # tudo em um único .exe
        "--windowed",                       # sem janela de terminal
        "--name", "VGM Volume Detecter",               # nome do executável
        "--add-data", f"{logo};VGMVolumeDetector",   # inclui a logo dentro do exe
        "--clean",                          # limpa cache anterior
        "run.py",                           # entry point
    ]

    print("Gerando VGMVolumeDetector.exe...")
    print("Comando:", " ".join(cmd))
    print()

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print()
        print("=" * 50)
        print("Sucesso! Arquivo gerado em:")
        print("  dist\\VGMVolumeDetector.exe")
        print()
        print("Pode compartilhar esse único arquivo.")
        print("=" * 50)
    else:
        print()
        print("Erro no build. Verifique as mensagens acima.")

if __name__ == "__main__":
    main()
