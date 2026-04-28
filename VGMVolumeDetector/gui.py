"""
VGM Volume Detecter — Interface gráfica principal (PyQt6)
"""

import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QLabel, QPushButton,
    QFileDialog, QStatusBar, QFrame, QProgressBar, QMessageBox,
    QScrollArea, QSizePolicy, QToolBar, QGroupBox, QSpinBox,
    QCheckBox, QSlider,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QAction, QPixmap, QImage

from .parser import parse_vgm, VGMData
from .analyzer import analyze, Instrument
from .exporter import export_dmp, export_notes_info
from .i18n import t, set_lang, get_lang


ACCENT_NOISE  = "#BA7517"
ACCENT_PULSE  = "#185FA5"
ACCENT_TRI    = "#0F6E56"
ACCENT_OTHER  = "#5F5E5A"

CHIP_COLORS = {
    "SN76489":  "#534AB7",
    "YM2612":   "#534AB7",  # Mega Drive — mesmo agrupamento visual do SN
    "2A03":     "#185FA5",
    "AY8910":   "#0F6E56",
    "VRC6":     "#993556",  # rosa — expansão NES
    "VRC6_P1":  "#993556",
    "VRC6_P2":  "#993556",
    "VRC6_SAW": "#712B13",
    "MMC5":     "#3B6D11",
    "FDS":      "#854F0B",
    "N163":     "#0F6E56",
}

# Tamanho de fonte global — alterado pelo slider na toolbar
_THEME = "light"

def get_theme() -> str:
    return _THEME

def set_theme(theme: str):
    global _THEME
    _THEME = theme

def apply_theme(app: "QApplication"):
    """Aplica tema claro ou escuro na aplicação."""
    from PyQt6.QtGui import QPalette, QColor
    if _THEME == "dark":
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window,          QColor("#1A1A1A"))
        palette.setColor(QPalette.ColorRole.Base,            QColor("#212121"))
        palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#2A2A2A"))
        palette.setColor(QPalette.ColorRole.Button,          QColor("#2E2E2E"))
        palette.setColor(QPalette.ColorRole.Mid,             QColor("#3A3A3A"))
        palette.setColor(QPalette.ColorRole.Midlight,        QColor("#333333"))
        palette.setColor(QPalette.ColorRole.Shadow,          QColor("#0A0A0A"))
        palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#2A2A2A"))
        palette.setColor(QPalette.ColorRole.WindowText,      QColor("#ECECEC"))
        palette.setColor(QPalette.ColorRole.Text,            QColor("#ECECEC"))
        palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#ECECEC"))
        palette.setColor(QPalette.ColorRole.BrightText,      QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.ToolTipText,     QColor("#ECECEC"))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#AAAAAA"))
        palette.setColor(QPalette.ColorRole.Link,            QColor("#6CB4F0"))
        palette.setColor(QPalette.ColorRole.Highlight,       QColor("#1A5A8A"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        app.setPalette(palette)
        app.setStyleSheet("""
            QWidget { color: #ECECEC; background-color: transparent; }
            QMainWindow, QDialog { background-color: #1A1A1A; }
            QToolBar { background-color: #252525; border-bottom: 1px solid #3A3A3A; }
            QStatusBar { background-color: #1A1A1A; color: #AAAAAA; }
            QListWidget { background-color: #212121; color: #ECECEC; border: none; }
            QListWidget::item { color: #ECECEC; border-bottom: 0.5px solid #3A3A3A; padding: 6px 12px; }
            QListWidget::item:selected { background-color: #1A5A8A; color: #FFFFFF; }
            QScrollArea { background-color: transparent; border: none; }
            QGroupBox { color: #AAAAAA; }
            QLabel { color: #ECECEC; background-color: transparent; }
            QSplitter::handle { background-color: #3A3A3A; }
        """)
    else:
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window,          QColor("#F5F4F0"))
        palette.setColor(QPalette.ColorRole.Base,            QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#EEF0F2"))
        palette.setColor(QPalette.ColorRole.Button,          QColor("#E8E6E0"))
        palette.setColor(QPalette.ColorRole.Mid,             QColor("#C8C6C0"))
        palette.setColor(QPalette.ColorRole.Midlight,        QColor("#DEDAD4"))
        palette.setColor(QPalette.ColorRole.Shadow,          QColor("#A0A0A0"))
        palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#FFFBEF"))
        palette.setColor(QPalette.ColorRole.WindowText,      QColor("#1A1A1A"))
        palette.setColor(QPalette.ColorRole.Text,            QColor("#1A1A1A"))
        palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#1A1A1A"))
        palette.setColor(QPalette.ColorRole.BrightText,      QColor("#000000"))
        palette.setColor(QPalette.ColorRole.ToolTipText,     QColor("#1A1A1A"))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#666666"))
        palette.setColor(QPalette.ColorRole.Link,            QColor("#185FA5"))
        palette.setColor(QPalette.ColorRole.Highlight,       QColor("#185FA5"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        app.setPalette(palette)
        app.setStyleSheet("""
            QWidget { color: #1A1A1A; background-color: transparent; }
            QMainWindow, QDialog { background-color: #F5F4F0; }
            QToolBar { background-color: #ECEAE4; border-bottom: 1px solid #C8C6C0; }
            QStatusBar { background-color: #F5F4F0; color: #666666; }
            QListWidget { background-color: #FFFFFF; color: #1A1A1A; border: none; }
            QListWidget::item { color: #1A1A1A; border-bottom: 0.5px solid #C8C6C0; padding: 6px 12px; }
            QListWidget::item:selected { background-color: #185FA5; color: #FFFFFF; }
            QScrollArea { background-color: transparent; border: none; }
            QGroupBox { color: #555555; }
            QLabel { color: #1A1A1A; background-color: transparent; }
            QSplitter::handle { background-color: #C8C6C0; }
        """)


_FONT_SIZE = 12

def get_font_size() -> int:
    return _FONT_SIZE

def set_font_size(size: int):
    global _FONT_SIZE
    _FONT_SIZE = max(8, min(20, size))


class LogoBackground(QWidget):
    """Widget que desenha a logo do VGM Volume Detecter ao fundo — opacidade varia por tema."""
    def __init__(self, parent=None):
        super().__init__(parent)
        logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
        self._pixmap = QPixmap(logo_path) if os.path.exists(logo_path) else None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def paintEvent(self, event):
        if not self._pixmap or self._pixmap.isNull():
            return
        p = QPainter(self)
        # Tema escuro: mais visível. Tema claro: bem sutil para não poluir
        opacity = 0.20 if get_theme() == "dark" else 0.07
        p.setOpacity(opacity)
        size = max(self.width(), self.height()) * 1.05
        scaled = self._pixmap.scaled(
            int(size), int(size),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width()  - scaled.width())  // 2
        y = (self.height() - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)


class ParseWorker(QThread):
    done    = pyqtSignal(object, list)
    error   = pyqtSignal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self):
        try:
            vgm   = parse_vgm(self.path)
            insts = analyze(vgm)
            self.done.emit(vgm, insts)
        except Exception as e:
            import traceback
            self.error.emit(f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")


class UnifiedArpBar(QWidget):
    """
    Visualizador de arpejo unificado com régua numérica lateral.
    - Coluna numérica à esquerda: -16 a +16
    - Linha pontilhada preta espessa no 0 (nota padrão)
    - Linhas pontilhadas cinzas finas nas outras posições
    - Cada frame do envelope = uma coluna
    - Azul = agudo (acima do 0), Vermelho = grave (abaixo do 0)
    - Linha pontilhada cinza no topo indicando até onde a nota chega
    """
    RULER_W  = 28   # largura da coluna numérica à esquerda
    RANGE    = 16   # semitons acima e abaixo
    NUM_H    = 14   # altura da área de números embaixo

    def __init__(self, offsets: list[int], notes: list[str] = None):
        super().__init__()
        self.offsets = offsets
        self.notes   = notes or []
        total_rows   = self.RANGE * 2 + 1
        row_h        = 6
        self.setMinimumHeight(total_rows * row_h + 8 + self.NUM_H)
        self.setMaximumHeight(total_rows * row_h + 8 + self.NUM_H)

    def paintEvent(self, event):
        if not self.offsets:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W        = self.width()
        H        = self.height()
        RANGE    = self.RANGE
        RULER_W  = self.RULER_W
        NUM_H    = self.NUM_H
        n        = len(self.offsets)
        chart_w  = W - RULER_W - 4
        bw       = max(4, min(18, (chart_w - n * 2) // n))
        gap      = 2
        total    = RANGE * 2 + 1
        row_h    = max(4, (H - 4 - NUM_H) // total)
        zero_y   = 4 + RANGE * row_h   # y da linha do 0

        p.fillRect(self.rect(), Qt.GlobalColor.transparent)

        font = p.font()
        font.setPointSize(7)
        p.setFont(font)

        # ── Régua numérica ──────────────────────────────────────────────
        for st in range(-RANGE, RANGE + 1):
            y = zero_y - st * row_h

            # Linha horizontal
            if st == 0:
                # Linha sólida mais espessa para o 0 — adapta ao tema
                line_color = QColor("#ECECEC") if get_theme() == "dark" else QColor("#2C2C2A")
                pen = QPen(line_color, 1.5)
                p.setPen(pen)
                p.drawLine(RULER_W, y, W - 2, y)
            elif st % 4 == 0:
                c = QColor("#AAAAAA") if get_theme() == "dark" else QColor("#888780")
                c.setAlpha(80)
                pen = QPen(c, 0.5, Qt.PenStyle.DashLine)
                pen.setDashPattern([4, 4])
                p.setPen(pen)
                p.drawLine(RULER_W, y, W - 2, y)
            else:
                c = QColor("#888888") if get_theme() == "dark" else QColor("#888780")
                c.setAlpha(35)
                pen = QPen(c, 0.5, Qt.PenStyle.DotLine)
                p.setPen(pen)
                p.drawLine(RULER_W, y, W - 2, y)

            # Número na régua
            if st == 0 or st % 4 == 0:
                label = f"+{st}" if st > 0 else str(st)
                text_color = QColor("#ECECEC") if get_theme() == "dark" else QColor("#2C2C2A")
                ruler_color = QColor("#AAAAAA") if get_theme() == "dark" else QColor("#5F5E5A")
                p.setPen(text_color if st == 0 else ruler_color)
                p.drawText(0, y - 5, RULER_W - 2, 10,
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                           label)

        # ── Colunas por frame ───────────────────────────────────────────
        color_above = QColor("#185FA5")  # azul — agudo
        color_below = QColor("#993C1D")  # vermelho — grave
        color_zero  = QColor("#EF9F27")  # laranja — nota base

        for i, offset in enumerate(self.offsets):
            x   = RULER_W + 2 + i * (bw + gap)
            col_y = zero_y - offset * row_h

            if offset == 0:
                # Nota base — retângulo laranja centrado na linha do 0
                p.setPen(Qt.PenStyle.NoPen)
                c = QColor(color_zero); c.setAlpha(200)
                p.setBrush(c)
                p.drawRoundedRect(x, zero_y - row_h // 2, bw, row_h, 2, 2)

                # Linha pontilhada cinza no topo da coluna
                c2 = QColor("#888780"); c2.setAlpha(100)
                pen2 = QPen(c2, 0.5, Qt.PenStyle.DashLine)
                pen2.setDashPattern([2, 2])
                p.setPen(pen2)
                p.drawLine(x + bw // 2, 4, x + bw // 2, zero_y - row_h // 2)

            elif offset > 0:
                # Agudo — coluna azul crescendo para cima
                top_y = zero_y - offset * row_h
                h_col = offset * row_h
                p.setPen(Qt.PenStyle.NoPen)
                c = QColor(color_above)
                p.setBrush(c)
                p.drawRoundedRect(x, top_y, bw, h_col, 2, 2)

                # Linha pontilhada no topo
                c2 = QColor("#185FA5"); c2.setAlpha(150)
                pen2 = QPen(c2, 0.5, Qt.PenStyle.DashLine)
                pen2.setDashPattern([2, 2])
                p.setPen(pen2)
                p.drawLine(x + bw // 2, 4, x + bw // 2, top_y)

            else:
                # Grave — coluna vermelha crescendo para baixo
                bot_y = zero_y + abs(offset) * row_h
                h_col = abs(offset) * row_h
                p.setPen(Qt.PenStyle.NoPen)
                c = QColor(color_below)
                p.setBrush(c)
                p.drawRoundedRect(x, zero_y, bw, h_col, 2, 2)

                # Linha pontilhada no fundo
                c2 = QColor("#993C1D"); c2.setAlpha(150)
                pen2 = QPen(c2, 0.5, Qt.PenStyle.DashLine)
                pen2.setDashPattern([2, 2])
                p.setPen(pen2)
                p.drawLine(x + bw // 2, bot_y, x + bw // 2, H - NUM_H - 2)

        # ── Números embaixo de cada coluna ──────────────────────────────
        num_y = H - NUM_H + 1   # y base da área de texto
        font_num = p.font()
        font_num.setPointSize(6)
        font_num.setBold(True)
        p.setFont(font_num)

        for i, offset in enumerate(self.offsets):
            x = RULER_W + 2 + i * (bw + gap)
            label = f"+{offset}" if offset > 0 else str(offset)

            if offset > 0:
                tc = QColor("#185FA5")
            elif offset < 0:
                tc = QColor("#993C1D")
            else:
                tc = QColor("#EF9F27")

            p.setPen(tc)
            p.drawText(x, num_y, bw, NUM_H,
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                       label)


class ArpBar(QWidget):
    """Mantido para compatibilidade — delega para UnifiedArpBar."""
    def __init__(self, offsets: list[int], notes: list[str] = None):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(UnifiedArpBar(offsets, notes))


class MacroBar(QWidget):
    """Widget que desenha barras de macro. Volume 0 = espaço vazio. Corte = linha vermelha."""
    def __init__(self, values: list[int], loop_point: int = -1,
                 color: str = "#185FA5", max_val: int = 15,
                 truncated: bool = False):
        super().__init__()
        self.values     = values
        self.loop_point = loop_point
        self.color      = QColor(color)
        self.max_val    = max_val
        self.truncated  = truncated
        self.setMinimumHeight(60)
        self.setMaximumHeight(60)

    def paintEvent(self, event):
        if not self.values:
            return
        p   = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w   = self.width()
        h   = self.height() - 8
        n   = len(self.values)
        bw  = max(4, min(20, (w - n * 2) // n))
        gap = 2

        p.fillRect(self.rect(), Qt.GlobalColor.transparent)

        # Linha de base
        base_y = h + 2
        base_color = QColor(self.color)
        base_color.setAlpha(40)
        p.setPen(QPen(base_color, 1))
        p.drawLine(0, base_y, min(n * (bw + gap), w), base_y)

        for i, val in enumerate(self.values):
            x = i * (bw + gap)

            # Decide cor: amarelo para frames dentro do loop
            in_loop = (self.loop_point >= 0 and i >= self.loop_point)
            bar_color = QColor("#EF9F27") if in_loop else QColor(self.color)

            # Loop point — linha vertical antes da barra
            if self.loop_point >= 0 and i == self.loop_point:
                lp_color = QColor("#EF9F27")
                lp_color.setAlpha(220)
                p.setPen(QPen(lp_color, 1.5))
                p.drawLine(x - 1, 0, x - 1, base_y)
                p.setPen(Qt.PenStyle.NoPen)

            if val == 0:
                dot_color = QColor(bar_color)
                dot_color.setAlpha(50)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(dot_color)
                p.drawEllipse(x + bw // 2 - 1, base_y - 1, 3, 3)
                continue

            bh = max(2, int(val / self.max_val * h))
            y  = base_y - bh

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bar_color)
            p.drawRoundedRect(x, y, bw, bh, 2, 2)

            hi_color = QColor(bar_color)
            hi_color.setAlpha(60)
            p.setBrush(hi_color)
            p.drawRoundedRect(x, y, bw, min(3, bh), 2, 2)

        # Indicador de corte — linha vermelha vertical no final + triângulo
        if self.truncated and self.values and self.values[-1] != 0:
            last_x = (n - 1) * (bw + gap) + bw
            last_val = self.values[-1]
            last_h = max(2, int(last_val / self.max_val * h))
            cut_y_top = base_y - last_h

            # Linha vermelha vertical
            cut_color = QColor("#E24B4A")
            p.setPen(QPen(cut_color, 2))
            p.drawLine(last_x + 2, cut_y_top, last_x + 2, base_y)

            # Seta apontando para direita (indicando que continua mas foi cortado)
            p.setBrush(cut_color)
            p.setPen(Qt.PenStyle.NoPen)
            mid_y = (cut_y_top + base_y) // 2
            tri = [
                (last_x + 3, mid_y - 4),
                (last_x + 3, mid_y + 4),
                (last_x + 8, mid_y),
            ]
            from PyQt6.QtGui import QPolygon
            from PyQt6.QtCore import QPoint
            poly = QPolygon([QPoint(x, y) for x, y in tri])
            p.drawPolygon(poly)


class NoiseArpWidget(QWidget):
    """Visualizador do arpejo de ruído com ArpBar e badges de range."""
    def __init__(self, info):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 6, 0, 0)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        title = QLabel("Arpejo interno")
        title.setStyleSheet("font-size: 11px; font-weight: 500; color: #BA7517;")
        top_row.addWidget(title)

        base_lbl = QLabel(info.base_note)
        base_lbl.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        base_lbl.setStyleSheet(
            "background: #FAEEDA; color: #633806; border-radius: 3px; padding: 2px 6px;"
        )
        top_row.addWidget(base_lbl)

        if info.semitones_above > 0:
            lbl = QLabel(f"+{info.semitones_above} st")
            lbl.setStyleSheet(
                "background: #E6F1FB; color: #0C447C; font-size: 11px;"
                "border-radius: 3px; padding: 2px 5px;"
            )
            top_row.addWidget(lbl)

        if info.semitones_below > 0:
            lbl = QLabel(f"-{info.semitones_below} st")
            lbl.setStyleSheet(
                "background: #FAECE7; color: #712B13; font-size: 11px;"
                "border-radius: 3px; padding: 2px 5px;"
            )
            top_row.addWidget(lbl)

        top_row.addStretch()
        top_w = QWidget(); top_w.setLayout(top_row)
        layout.addWidget(top_w)
        layout.addWidget(ArpBar(info.offsets, info.notes))

        leg = QLabel("azul = agudo  ·  vermelho = grave  ·  laranja = nota base")
        leg.setStyleSheet("font-size: 10px; color: palette(placeholderText);")
        layout.addWidget(leg)


class NoteUsageWidget(QWidget):
    """Lista de notas utilizadas com cores por modo de ruído SN76489."""

    # Cores por modo de ruído SN76489
    MODE_STYLES = {
        "simple":            ("#EAF3DE", "#27500A", "Simples"),
        "complete_simple":   ("#C0DD97", "#173404", "Completo"),
        "periodic":          ("#FAEEDA", "#633806", "Periódico"),
        "complete_periodic": ("#FAC775", "#412402", "Periódico completo"),
    }

    def __init__(self, notes_used, font_size: int = 12):
        super().__init__()
        fs = font_size
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        if not notes_used:
            lbl = QLabel(t("no_notes"))
            lbl.setStyleSheet(f"color: palette(placeholderText); font-size: {fs}px;")
            layout.addWidget(lbl)
            return

        has_modes    = any(nu.noise_mode for nu in notes_used)
        has_metallic = any(nu.metallic   for nu in notes_used)

        for nu in notes_used:
            row = QWidget()

            # Cor de fundo conforme modo
            if nu.noise_mode and nu.noise_mode in self.MODE_STYLES:
                bg_color, _, _ = self.MODE_STYLES[nu.noise_mode]
                row.setStyleSheet(
                    f"background: {bg_color}; border: 0.5px solid palette(mid); border-radius: 6px;"
                )
            elif nu.metallic:
                row.setStyleSheet(
                    "background: #FFF4F0; border: 0.5px solid palette(mid); border-radius: 6px;"
                )
            else:
                row.setStyleSheet(
                    "background: palette(base); border: 0.5px solid palette(mid); border-radius: 6px;"
                )

            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 4, 8, 4)
            rl.setSpacing(6)

            # Período / rate
            per_lbl = QLabel(f"0x{nu.period:02X}")
            per_lbl.setFont(QFont("Courier New", fs - 2))
            per_lbl.setStyleSheet("color: palette(placeholderText);")
            per_lbl.setMinimumWidth(32)
            rl.addWidget(per_lbl)

            # Nome da nota
            note_lbl = QLabel(nu.note)
            note_lbl.setFont(QFont("Courier New", fs, QFont.Weight.Bold))
            note_lbl.setMinimumWidth(38)
            rl.addWidget(note_lbl)

            # Badge de modo (SN76489)
            if nu.noise_mode and nu.noise_mode in self.MODE_STYLES:
                bg, fg, label = self.MODE_STYLES[nu.noise_mode]
                mode_lbl = QLabel(label)
                mode_lbl.setStyleSheet(
                    f"background: {fg}; color: #fff; font-size: 10px; font-weight: 500;"
                    "border-radius: 3px; padding: 1px 5px;"
                )
                rl.addWidget(mode_lbl)

            # Badge metálico (2A03)
            if nu.metallic:
                metal_lbl = QLabel("M")
                metal_lbl.setStyleSheet(
                    "background: #993C1D; color: #fff; font-size: 10px; font-weight: 500;"
                    "border-radius: 3px; padding: 1px 4px;"
                )
                metal_lbl.setToolTip("Modo metálico (bit 7 ativo)")
                rl.addWidget(metal_lbl)

            # Barra de frequência
            bar_frame = QFrame()
            bar_frame.setFixedHeight(6)
            bar_frame.setStyleSheet(
                f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                f"stop:0 #EF9F27, stop:{nu.percent/100:.2f} #EF9F27,"
                f"stop:{nu.percent/100+0.001:.2f} #E5E4DD, stop:1 #E5E4DD);"
                f"border-radius: 3px;"
            )
            rl.addWidget(bar_frame, stretch=1)

            pct_lbl = QLabel(f"{nu.percent:.0f}%")
            pct_lbl.setStyleSheet(f"color: palette(placeholderText); font-size: {fs-1}px;")
            pct_lbl.setMinimumWidth(32)
            pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            rl.addWidget(pct_lbl)

            layout.addWidget(row)

        # Legendas
        if has_modes:
            leg_row = QHBoxLayout()
            leg_row.setSpacing(8)
            for mode, (bg, fg, label) in self.MODE_STYLES.items():
                dot = QLabel(f"■ {label}")
                dot.setStyleSheet(f"color: {fg}; font-size: 10px;")
                leg_row.addWidget(dot)
            leg_row.addStretch()
            leg_w = QWidget(); leg_w.setLayout(leg_row)
            layout.addWidget(leg_w)

        if has_metallic:
            leg = QLabel(t("metallic_legend"))
            leg.setStyleSheet(f"color: palette(placeholderText); font-size: {fs-2}px;")
            layout.addWidget(leg)

        note_hint = QLabel(t("furnace_hint"))
        note_hint.setStyleSheet(f"color: palette(placeholderText); font-size: {fs-1}px; margin-top: 4px;")
        note_hint.setWordWrap(True)
        layout.addWidget(note_hint)


class InstrumentDetailPanel(QWidget):
    """Painel direito: detalhes do instrumento selecionado."""
    export_requested     = pyqtSignal(object, str)   # (instrument, format)

    def __init__(self):
        super().__init__()
        self._instrument: Instrument | None = None

        self._bg = LogoBackground(self)
        self._bg.lower()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        self.title_lbl = QLabel("Selecione um instrumento")
        self.title_lbl.setStyleSheet(f"font-size: {get_font_size()+3}px; font-weight: 500;")
        self.meta_lbl  = QLabel("")
        self.meta_lbl.setStyleSheet(f"color: palette(placeholderText); font-size: {get_font_size()}px;")
        root.addWidget(self.title_lbl)
        root.addWidget(self.meta_lbl)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: palette(placeholderText);")
        root.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.scroll_inner = QWidget()
        self.scroll_inner.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(self.scroll_inner)
        self.scroll_layout.setSpacing(14)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.scroll_inner)
        root.addWidget(scroll, stretch=1)

        # Botões de export lado a lado
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.export_dmp_btn = QPushButton(t("export_dmp"))
        self.export_dmp_btn.setEnabled(False)
        self.export_dmp_btn.setToolTip(t("export_dmp_tip"))
        self.export_dmp_btn.setStyleSheet(
            "QPushButton { background: #EAF3DE; color: #27500A; border: none;"
            "border-radius: 6px; padding: 8px; font-weight: 500; font-size: 12px; }"
            "QPushButton:hover { background: #C7E0A4; }"
            "QPushButton:disabled { color: palette(placeholderText); background: palette(button); }"
        )
        self.export_dmp_btn.clicked.connect(lambda: self._on_export("dmp"))
        btn_row.addWidget(self.export_dmp_btn)

        btn_widget = QWidget(); btn_widget.setLayout(btn_row)
        root.addWidget(btn_widget)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._bg.setGeometry(0, 0, self.width(), self.height())

    def apply_font_size(self, size: int):
        set_font_size(size)
        self.title_lbl.setStyleSheet(f"font-size: {size+3}px; font-weight: 500;")
        self.meta_lbl.setStyleSheet(f"color: palette(placeholderText); font-size: {size}px;")
        if self._instrument:
            self.show_instrument(self._instrument)

    def _clear_scroll(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_instrument(self, inst: Instrument):
        self._instrument = inst
        self._clear_scroll()
        fs = get_font_size()

        self.title_lbl.setText(inst.name)
        self.title_lbl.setStyleSheet(f"font-size: {fs+3}px; font-weight: 500;")
        chip_badge = f"  [{inst.chip}]" if inst.chip else ""
        occ   = f" · {t('detected_x', n=inst.occurrences)}" if inst.occurrences > 1 else ""
        trunc = t("incomplete_envelope") if inst.truncated else ""
        self.meta_lbl.setText(f"{t('channel')}: {inst.channel}{chip_badge}{occ}{trunc}")
        self.meta_lbl.setStyleSheet(f"color: palette(placeholderText); font-size: {fs}px;")
        self.export_dmp_btn.setEnabled(True)
        self.export_dmp_btn.setText(t("export_dmp"))

        grp_style = f"QGroupBox {{ font-size: {fs-1}px; font-weight: 500; color: palette(placeholderText); }}"
        color = ACCENT_NOISE if inst.is_noise else CHIP_COLORS.get(inst.chip, ACCENT_OTHER)

        if inst.volume_macro:
            loop_lbl = ""
            if inst.loop_point >= 0:
                loop_lbl = t("loop_from", n=inst.loop_point)
            grp = QGroupBox(f"{t('volume_macro')}{loop_lbl}")
            grp.setStyleSheet(grp_style)
            gl = QVBoxLayout(grp)
            gl.addWidget(MacroBar(inst.volume_macro, inst.loop_point, color, truncated=inst.truncated))
            vals_str = " → ".join(str(v) for v in inst.volume_macro[:32])
            if len(inst.volume_macro) > 32:
                vals_str += " …"
            from PyQt6.QtWidgets import QLineEdit
            hint = QLineEdit(vals_str)
            hint.setReadOnly(True)
            hint.setStyleSheet(
                f"font-size: {fs-1}px; color: palette(placeholderText);"
                "border: none; background: transparent; padding: 0;"
            )
            gl.addWidget(hint)
            self.scroll_layout.addWidget(grp)

        has_arp       = inst.arp_macro and any(v != 0 for v in inst.arp_macro)
        has_noise_arp = inst.is_noise and inst.noise_arp_info

        if has_arp or has_noise_arp:
            grp2 = QGroupBox(t("arp_macro"))
            grp2.setStyleSheet(grp_style)
            gl2  = QVBoxLayout(grp2)

            if has_noise_arp:
                info = inst.noise_arp_info
                top_row = QHBoxLayout()
                top_row.setSpacing(6)
                base_lbl = QLabel(info.base_note)
                base_lbl.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
                base_lbl.setStyleSheet(
                    "background: #FAEEDA; color: #633806; border-radius: 3px; padding: 2px 6px;"
                )
                top_row.addWidget(base_lbl)
                if info.semitones_above > 0:
                    lbl = QLabel(f"+{info.semitones_above} st")
                    lbl.setStyleSheet(
                        "background: #E6F1FB; color: #0C447C; font-size: 11px;"
                        "border-radius: 3px; padding: 2px 5px;"
                    )
                    top_row.addWidget(lbl)
                if info.semitones_below > 0:
                    lbl = QLabel(f"-{info.semitones_below} st")
                    lbl.setStyleSheet(
                        "background: #FAECE7; color: #712B13; font-size: 11px;"
                        "border-radius: 3px; padding: 2px 5px;"
                    )
                    top_row.addWidget(lbl)
                top_row.addStretch()
                top_w = QWidget(); top_w.setLayout(top_row)
                gl2.addWidget(top_w)
                gl2.addWidget(UnifiedArpBar(info.offsets, info.notes))
                leg = QLabel(t("arp_legend"))
                leg.setStyleSheet("font-size: 10px; color: palette(placeholderText);")
                gl2.addWidget(leg)
            else:
                gl2.addWidget(MacroBar(inst.arp_macro, -1, "#1D9E75", max_val=24))

            self.scroll_layout.addWidget(grp2)

        if inst.duty_cycle is not None:
            is_vrc6 = inst.chip in ("VRC6_P1", "VRC6_P2", "VRC6")
            if is_vrc6:
                duty_names = {
                    0: "6.25%", 1: "12.5%", 2: "18.75%", 3: "25%",
                    4: "31.25%", 5: "37.5%", 6: "43.75%", 7: "50%"
                }
            else:
                duty_names = {0: "12.5%", 1: "25%", 2: "50%", 3: "75%"}
            duty_str = duty_names.get(inst.duty_cycle, f"valor {inst.duty_cycle}")
            d_lbl = QLabel(f"{t('duty_cycle')}: {duty_str}")
            d_lbl.setStyleSheet(f"font-size: {fs+1}px; color: palette(windowText);")
            self.scroll_layout.addWidget(d_lbl)

        # AY-3-8910 / YM2149 / Sunsoft 5B — envelope de hardware
        if inst.chip == "AY8910" and inst.ay_envelope and inst.ay_envelope.active:
            # Nomes dos 8 shapes do envelope AY
            AY_SHAPES = {
                0: "\\\\  (decay, hold 0)",    1: "\\\\  (decay, hold 0)",
                2: "\\\\  (decay, hold 0)",    3: "\\\\  (decay, hold 0)",
                4: "//  (attack, hold 0)",     5: "//  (attack, hold 0)",
                6: "//  (attack, hold 0)",     7: "//  (attack, hold 0)",
                8: "\\\\\\\\ (decay, repeat)", 9: "\\_ (decay, hold low)",
                10: "\\/  (decay+attack)",     11: "\\‾ (decay, hold high)",
                12: "// (attack, repeat)",     13: "/‾ (attack, hold high)",
                14: "/\\  (attack+decay)",     15: "/_ (attack, hold low)",
            }
            env   = inst.ay_envelope
            shape_desc = AY_SHAPES.get(env.shape, f"shape {env.shape}")
            grp_ay = QGroupBox("Envelope de hardware AY")
            grp_ay.setStyleSheet(
                f"QGroupBox {{ font-size: {fs-1}px; font-weight: 500; color: #0F6E56;"
                "border: 1px solid #7CC9B0; border-radius: 6px; margin-top: 6px; padding-top: 8px; }}"
            )
            gl_ay = QVBoxLayout(grp_ay)
            row_ay = QHBoxLayout()
            for label_txt, value_txt in [
                ("Shape:", f"{env.shape}  {shape_desc}"),
                ("Período:", str(env.period)),
            ]:
                lbl = QLabel(label_txt)
                lbl.setStyleSheet(f"font-size: {fs-1}px; color: palette(placeholderText);")
                val = QLabel(value_txt)
                val.setStyleSheet(f"font-size: {fs}px; font-weight: 600;")
                row_ay.addWidget(lbl); row_ay.addWidget(val)
                row_ay.addSpacing(16)
            row_ay.addStretch()
            row_w = QWidget(); row_w.setLayout(row_ay)
            gl_ay.addWidget(row_w)
            if inst.ay_noise_period is not None and inst.ay_tone_noise_mix and inst.ay_tone_noise_mix & 2:
                n_lbl = QLabel(f"Noise: período {inst.ay_noise_period}")
                n_lbl.setStyleSheet(f"font-size: {fs-1}px; color: palette(placeholderText);")
                gl_ay.addWidget(n_lbl)
            self.scroll_layout.addWidget(grp_ay)
            self.scroll_layout.addWidget(d_lbl)

        if inst.is_noise:
            grp3 = QGroupBox(t("notes_used_noise"))
            grp3.setStyleSheet(
                f"QGroupBox {{ font-size: {fs-1}px; font-weight: 500; color: #BA7517;"
                "border: 1px solid #FAC775; border-radius: 6px; margin-top: 6px; padding-top: 8px; }"
            )
            gl3 = QVBoxLayout(grp3)
            gl3.addWidget(NoteUsageWidget(inst.notes_used, fs))
            self.scroll_layout.addWidget(grp3)
        elif inst.notes_used:
            grp4 = QGroupBox(t("notes_used"))
            grp4.setStyleSheet(grp_style)
            gl4  = QVBoxLayout(grp4)
            gl4.addWidget(NoteUsageWidget(inst.notes_used, fs))
            self.scroll_layout.addWidget(grp4)

        self.scroll_layout.addStretch()

    def _on_export(self, fmt: str = "dmp"):
        if self._instrument:
            self.export_requested.emit(self._instrument, fmt)


class CreditWidget(QWidget):
    """Crédito do desenvolvedor com avatar e link do YouTube."""
    YT_URL = "https://youtube.com/@evolution_br811?si=ueISK_fhEikczXi6"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 8, 0)
        layout.setSpacing(6)

        dev_lbl = QLabel(f"{t('dev_by')} ")
        dev_lbl.setStyleSheet("font-size: 12px; font-weight: 400;")
        layout.addWidget(dev_lbl)

        # Nome clicável — abre o YouTube
        name_lbl = QLabel(
            f'<a href="{self.YT_URL}" style="font-weight:700; text-decoration:none;">'
            f'Evolution BR811</a>'
        )
        name_lbl.setStyleSheet("font-size: 12px;")
        name_lbl.setOpenExternalLinks(True)
        name_lbl.setToolTip("YouTube: @evolution_br811")
        layout.addWidget(name_lbl)

        # Ícone do YouTube
        yt_lbl = QLabel(
            f'<a href="{self.YT_URL}" style="color:#E24B4A; font-weight:700; text-decoration:none;">▶ YT</a>'
        )
        yt_lbl.setStyleSheet("font-size: 12px;")
        yt_lbl.setOpenExternalLinks(True)
        yt_lbl.setToolTip("Abrir canal no YouTube")
        layout.addWidget(yt_lbl)

        # Avatar circular
        avatar_path = os.path.join(os.path.dirname(__file__), "avatar.png")
        if os.path.exists(avatar_path):
            px = QPixmap(avatar_path).scaled(
                26, 26,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            from PyQt6.QtGui import QPainterPath
            from PyQt6.QtCore import QRectF
            circle_px = QPixmap(26, 26)
            circle_px.fill(Qt.GlobalColor.transparent)
            cp = QPainter(circle_px)
            cp.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addEllipse(QRectF(0, 0, 26, 26))
            cp.setClipPath(path)
            cp.drawPixmap(0, 0, px)
            cp.end()

            avatar_lbl = QLabel()
            avatar_lbl.setPixmap(circle_px)
            avatar_lbl.setFixedSize(26, 26)
            avatar_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            avatar_lbl.mousePressEvent = lambda _: __import__('webbrowser').open(self.YT_URL)
            avatar_lbl.setToolTip("Abrir canal no YouTube")
            layout.addWidget(avatar_lbl)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VGM Volume Detecter  —  Beta v0.1")
        self.resize(900, 580)
        self._instruments: list[Instrument] = []
        self._vgm: VGMData | None = None
        self._current_path: str = ""
        self._worker: ParseWorker | None = None   # ← mantém referência forte
        self._build_ui()

    def _build_ui(self):
        toolbar = QToolBar("Principal")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setStyleSheet(
            "QToolBar { spacing: 4px; padding: 3px 6px; }"
        )
        self.addToolBar(toolbar)

        # ── Ações principais ─────────────────────────────────────────────
        self.act_open = QAction(t("open_vgm"), self)
        self.act_open.triggered.connect(self._open_file)
        toolbar.addAction(self.act_open)

        self.act_export_all = QAction(t("export_all"), self)
        self.act_export_all.setEnabled(False)
        self.act_export_all.triggered.connect(self._export_all)
        toolbar.addAction(self.act_export_all)

        self.file_lbl = QLabel(t("no_file"))
        self.file_lbl.setStyleSheet("color: palette(placeholderText); font-size: 12px; padding: 0 6px;")
        toolbar.addWidget(self.file_lbl)

        # Espaço expansível
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # ── Tema ☀ / 🌙 ─────────────────────────────────────────────────
        self.theme_lbl = QLabel("Tema:")
        self.theme_lbl.setStyleSheet("color: palette(windowText); font-size: 11px; font-weight: 500;")
        toolbar.addWidget(self.theme_lbl)

        self.theme_btn = QPushButton("☀  Claro")
        self.theme_btn.setFixedHeight(28)
        self.theme_btn.setMinimumWidth(80)
        self.theme_btn.setToolTip("Alternar tema claro / escuro")
        self.theme_btn.setStyleSheet(
            "QPushButton { background: #F5E642; color: #1A1A1A; border: none;"
            "border-radius: 5px; font-size: 11px; font-weight: 700; padding: 0 8px; }"
            "QPushButton:hover { background: #E8D800; }"
        )
        self.theme_btn.clicked.connect(self._toggle_theme)
        toolbar.addWidget(self.theme_btn)

        toolbar.addWidget(QLabel("  "))

        # ── Idioma ───────────────────────────────────────────────────────
        self.lang_lbl = QLabel("Idioma:")
        self.lang_lbl.setStyleSheet("color: palette(windowText); font-size: 11px; font-weight: 500;")
        toolbar.addWidget(self.lang_lbl)

        self.lang_btn = QPushButton("🌐  PT | EN")
        self.lang_btn.setFixedHeight(28)
        self.lang_btn.setMinimumWidth(88)
        self.lang_btn.setStyleSheet(
            "QPushButton { background: #185FA5; color: #FFFFFF; border: none;"
            "border-radius: 5px; font-size: 11px; font-weight: 700; padding: 0 8px; }"
            "QPushButton:hover { background: #0C447C; }"
        )
        self.lang_btn.setToolTip("Switch language / Mudar idioma")
        self.lang_btn.clicked.connect(self._toggle_lang)
        toolbar.addWidget(self.lang_btn)

        toolbar.addWidget(QLabel("  "))

        # ── Tamanho de fonte ─────────────────────────────────────────────
        font_box = QWidget()
        font_layout = QHBoxLayout(font_box)
        font_layout.setContentsMargins(0, 0, 0, 0)
        font_layout.setSpacing(4)

        self.font_lbl_label = QLabel("Fonte:")
        self.font_lbl_label.setStyleSheet("color: palette(windowText); font-size: 11px; font-weight: 500;")
        font_layout.addWidget(self.font_lbl_label)

        self.font_lbl_s = QLabel("A")
        self.font_lbl_s.setStyleSheet("color: palette(windowText); font-size: 10px;")
        font_layout.addWidget(self.font_lbl_s)

        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setMinimum(8)
        self.font_slider.setMaximum(20)
        self.font_slider.setValue(12)
        self.font_slider.setFixedWidth(80)
        self.font_slider.setToolTip(t("font_size_tip"))
        self.font_slider.valueChanged.connect(self._on_font_size_changed)
        font_layout.addWidget(self.font_slider)

        self.font_lbl_l = QLabel("A")
        self.font_lbl_l.setStyleSheet("color: palette(windowText); font-size: 18px; font-weight: 700;")
        font_layout.addWidget(self.font_lbl_l)

        toolbar.addWidget(font_box)
        toolbar.addWidget(QLabel(" "))

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left.setObjectName("sidebarPanel")
        left.setAutoFillBackground(True)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        self.sidebar_lbl = QLabel(t("detected_instruments"))
        self.sidebar_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 500; color: palette(placeholderText); padding: 8px 0 4px 12px;"
            "text-transform: uppercase; letter-spacing: 1px;"
        )
        ll.addWidget(self.sidebar_lbl)

        self.inst_list = QListWidget()
        self.inst_list.setStyleSheet(
            "QListWidget { border: none; background: palette(base); color: palette(windowText); }"
            "QListWidget::item { padding: 6px 12px; border-bottom: 0.5px solid palette(mid); }"
            "QListWidget::item:selected { background: palette(highlight); color: palette(highlightedText); }"
        )
        self.inst_list.currentRowChanged.connect(self._on_inst_selected)
        ll.addWidget(self.inst_list)
        left.setMinimumWidth(200)
        left.setMaximumWidth(260)

        self.detail = InstrumentDetailPanel()
        self.detail.export_requested.connect(self._export_single)

        splitter.addWidget(left)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(1, 3)

        self.setCentralWidget(splitter)

        status = QStatusBar()
        self.status_lbl = QLabel(t("ready"))
        status.addWidget(self.status_lbl)

        # Badge de beta — visível o tempo todo, com link de email para feedback
        FEEDBACK_EMAIL = "evolutionfeedbacks@gmail.com"
        self._beta_badge_base = "beta_badge"  # chave i18n
        self.beta_lbl = QLabel()
        self._update_beta_badge()
        self.beta_lbl.setOpenExternalLinks(True)
        self.beta_lbl.setStyleSheet(
            "color: #7A4F00; background: #FFE082; border-radius: 4px;"
            "padding: 2px 8px; font-size: 11px; font-weight: 600;"
        )
        self.beta_lbl.setToolTip(f"Enviar feedback: {FEEDBACK_EMAIL}")
        status.addPermanentWidget(self.beta_lbl)

        self.credit_widget = CreditWidget()
        status.addPermanentWidget(self.credit_widget)
        self.setStatusBar(status)

    def _toggle_theme(self):
        new_theme = "dark" if get_theme() == "light" else "light"
        set_theme(new_theme)

        # Atualiza botão de tema
        if new_theme == "dark":
            self.theme_btn.setText("🌙  Escuro")
            self.theme_btn.setStyleSheet(
                "QPushButton { background: #3C3C3C; color: #ECECEC; border: none;"
                "border-radius: 5px; font-size: 11px; font-weight: 700; padding: 0 8px; }"
                "QPushButton:hover { background: #555555; }"
            )
        else:
            self.theme_btn.setText("☀  Claro")
            self.theme_btn.setStyleSheet(
                "QPushButton { background: #F5E642; color: #1A1A1A; border: none;"
                "border-radius: 5px; font-size: 11px; font-weight: 700; padding: 0 8px; }"
                "QPushButton:hover { background: #E8D800; }"
            )

        # Aplica paleta
        apply_theme(QApplication.instance())

        # Força repropagação da paleta em TODOS os widgets filhos
        for w in self.findChildren(QWidget):
            w.setPalette(QApplication.instance().palette())
            w.update()

        # Repinta logo com nova opacidade
        self.detail._bg.update()

        # Re-exibe instrumento para reconstruir labels com novas cores
        if self.detail._instrument:
            self.detail.show_instrument(self.detail._instrument)

    def _toggle_lang(self):
        new_lang = "pt" if get_lang() == "en" else "en"
        set_lang(new_lang)
        self._retranslate_ui()
        # Re-exibe instrumento atual se houver
        if self.detail._instrument:
            self.detail.show_instrument(self.detail._instrument)

    def _update_beta_badge(self):
        """Atualiza o texto do badge de beta conforme o idioma atual."""
        FEEDBACK_EMAIL = "evolutionfeedbacks@gmail.com"
        label_text = t("beta_badge")
        self.beta_lbl.setText(
            f'{label_text} '
            f'<a href="mailto:{FEEDBACK_EMAIL}" '
            f'style="color:#7A4F00; font-weight:700;">'
            f'{FEEDBACK_EMAIL}</a>'
        )

    def _retranslate_ui(self):
        """Atualiza todos os textos da UI para o idioma atual."""
        self.act_open.setText(t("open_vgm"))
        self.act_export_all.setText(t("export_all"))
        self.file_lbl.setText(self.file_lbl.text())  # mantém nome do arquivo
        self.sidebar_lbl.setText(t("detected_instruments"))
        self.status_lbl.setText(t("ready"))
        self._update_beta_badge()
        # Recria o crédito com o texto traduzido
        dev_lbl = self.credit_widget.findChild(QLabel)
        if dev_lbl:
            dev_lbl.setText(f"{t('dev_by')} ")

    def _on_font_size_changed(self, size: int):
        self.detail.apply_font_size(size)
        # Escala os botões e labels da toolbar proporcionalmente
        btn_fs   = max(9, size - 1)
        lbl_fs   = max(9, size - 1)
        s_fs     = max(8, size - 3)
        l_fs     = max(12, size + 4)

        self.theme_lbl.setStyleSheet(f"color: palette(windowText); font-size: {lbl_fs}px; font-weight: 500;")
        self.lang_lbl.setStyleSheet(f"color: palette(windowText); font-size: {lbl_fs}px; font-weight: 500;")
        self.font_lbl_label.setStyleSheet(f"color: palette(windowText); font-size: {lbl_fs}px; font-weight: 500;")
        self.font_lbl_s.setStyleSheet(f"color: palette(windowText); font-size: {s_fs}px;")
        self.font_lbl_l.setStyleSheet(f"color: palette(windowText); font-size: {l_fs}px; font-weight: 700;")

        for btn, bg, hover, fg in [
            (self.theme_btn, "#F5E642", "#E8D800", "#1A1A1A"),
            (self.lang_btn,  "#185FA5", "#0C447C", "#FFFFFF"),
        ]:
            btn.setStyleSheet(
                f"QPushButton {{ background: {bg}; color: {fg}; border: none;"
                f"border-radius: 5px; font-size: {btn_fs}px; font-weight: 700; padding: 0 8px; }}"
                f"QPushButton:hover {{ background: {hover}; }}"
            )
        # Ajusta altura dos botões
        btn_h = max(24, size + 14)
        self.theme_btn.setFixedHeight(btn_h)
        self.lang_btn.setFixedHeight(btn_h)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir arquivo VGM", "", "VGM Files (*.vgm *.vgz);;All Files (*)"
        )
        if not path:
            return
        self._current_path = path
        self.file_lbl.setText(f"  {os.path.basename(path)}")
        self.status_lbl.setText("Analisando…")
        self.inst_list.clear()
        self._instruments = []

        self._worker = ParseWorker(path)
        self._worker.done.connect(self._on_parse_done)
        self._worker.error.connect(self._on_parse_error)
        self._worker.start()

    def _on_parse_done(self, vgm: VGMData, instruments: list[Instrument]):
        self._vgm = vgm
        self._instruments = instruments
        self.inst_list.clear()

        # Nome amigável do console
        SYSTEM_NAMES = {
            "md":      "Mega Drive / Genesis",
            "sms":     "Master System",
            "nes":     "NES / Famicom",
            "msx":     "MSX",
            "arcade":  "Arcade",
            "unknown": "Sistema desconhecido",
        }
        system     = getattr(vgm.header, 'system', 'unknown')
        sys_name   = SYSTEM_NAMES.get(system, system.upper())
        chips_str  = ", ".join(sorted(vgm.chips)) if vgm.chips else "?"
        fps        = vgm.vgm_fps
        fps_str    = f"{fps:.0f}Hz" if fps == int(fps) else f"{fps:.3f}Hz"
        self.file_lbl.setText(
            f"  {os.path.basename(self._current_path or '')}  "
            f"[{sys_name}  •  {fps_str}]"
        )
        self.status_lbl.setText(
            t("detected_count", n=len(instruments), chips=chips_str)
        )
        self.act_export_all.setEnabled(bool(instruments))

        from collections import OrderedDict
        channels: OrderedDict[str, list[Instrument]] = OrderedDict()
        for inst in instruments:
            key = f"{inst.chip} / {inst.channel}"
            if key not in channels:
                channels[key] = []
            channels[key].append(inst)

        for ch_key, ch_insts in channels.items():
            sep_item = QListWidgetItem(ch_key)
            sep_item.setFlags(Qt.ItemFlag.NoItemFlags)
            sep_item.setForeground(QColor("#888"))
            font = sep_item.font()
            font.setPointSize(10)
            font.setBold(False)
            sep_item.setFont(font)
            sep_item.setBackground(QColor(0, 0, 0, 0))
            self.inst_list.addItem(sep_item)

            for inst in ch_insts:
                item = QListWidgetItem()
                color = ACCENT_NOISE if inst.is_noise else CHIP_COLORS.get(inst.chip, ACCENT_OTHER)
                item.setText(f"  {inst.name}")
                item.setForeground(QColor(color))
                item.setData(Qt.ItemDataRole.UserRole, inst)
                self.inst_list.addItem(item)

        if instruments:
            for i in range(self.inst_list.count()):
                if self.inst_list.item(i).data(Qt.ItemDataRole.UserRole):
                    self.inst_list.setCurrentRow(i)
                    break

    def _on_parse_error(self, msg: str):
        self.status_lbl.setText(f"Error: {msg}")
        QMessageBox.critical(self, t("error_open"), msg)

    def _on_inst_selected(self, row: int):
        if row < 0:
            return
        item = self.inst_list.item(row)
        if not item:
            return
        inst = item.data(Qt.ItemDataRole.UserRole)
        if inst is None:
            return
        self.detail.show_instrument(inst)

    def _export_single(self, inst: Instrument, fmt: str = "dmp"):
        from PyQt6.QtWidgets import QInputDialog, QFileDialog
        ext = fmt

        # Pede o nome do arquivo — mostra chip no título
        default_name = "".join(
            c if c.isalnum() or c in "-_ " else "_" for c in inst.name
        ).strip()
        file_name, ok = QInputDialog.getText(
            self, f"Exportar {inst.chip} — {inst.channel}",
            f"Nome do arquivo (.{ext}):",
            text=default_name,
        )
        if not ok or not file_name.strip():
            return
        file_name = file_name.strip()

        # Pede a pasta
        out_dir = QFileDialog.getExistingDirectory(self, t("save_dialog_title"))
        if not out_dir:
            return

        try:
            vgm_fps = self._vgm.vgm_fps if self._vgm else 60.0
            path = os.path.join(out_dir, f"{file_name}.{ext}")
            if fmt == "dmp":
                from .exporter import _build_dmp
                data = _build_dmp(inst)
            with open(path, "wb") as f:
                f.write(data)
            export_notes_info(inst, out_dir)
            self.status_lbl.setText(f"{t('exported')}: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, t("error_export"), str(e))

    def _export_all(self):
        if not self._instruments:
            return
        # Pergunta o formato primeiro
        from PyQt6.QtWidgets import QInputDialog
        fmt, ok = QInputDialog.getItem(
            self, t("export_format_title"), t("export_format_label"),
            [".dmp (DefleMask)"], 0, False
        )
        if not ok:
            return
        use_dmp = fmt.startswith(".dmp")

        out_dir = QFileDialog.getExistingDirectory(self, t("save_all_title"))
        if not out_dir:
            return

        errors  = []
        success = 0
        for inst in self._instruments:
            try:
                if use_dmp:
                    export_dmp(inst, out_dir)
                else:
                    export_dmp(inst, out_dir)
                export_notes_info(inst, out_dir)
                success += 1
            except Exception as e:
                errors.append(f"{inst.name}: {e}")

        if errors:
            QMessageBox.warning(self, t("some_errors"), "\n".join(errors))
        else:
            self.status_lbl.setText(t("exported_all", n=success, dir=out_dir))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("VGM Volume Detecter")
    apply_theme(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
