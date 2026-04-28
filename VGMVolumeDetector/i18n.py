"""
VGM Volume Detecter — Sistema de internacionalização (i18n)
Idiomas suportados: Português (pt), English (en)
"""

STRINGS = {
    # ── Toolbar ──────────────────────────────────────────────────────────
    "open_vgm":           {"pt": "Abrir VGM…",         "en": "Open VGM…"},
    "export_all":         {"pt": "Exportar todos",      "en": "Export all"},
    "no_file":            {"pt": "  Nenhum arquivo aberto", "en": "  No file open"},
    "font_size_tip":      {"pt": "Tamanho da fonte",    "en": "Font size"},

    # ── Sidebar ───────────────────────────────────────────────────────────
    "detected_instruments": {"pt": "  Instrumentos detectados", "en": "  Detected instruments"},

    # ── Status bar ────────────────────────────────────────────────────────
    "ready":              {"pt": "Pronto",              "en": "Ready"},
    "beta_badge":         {"pt": "🚧  BETA v0.1  —  Reporte bugs:",
                           "en": "🚧  BETA v0.1  —  Report bugs:"},
    "analyzing":          {"pt": "Analisando…",         "en": "Analyzing…"},
    "exported":           {"pt": "Exportado",           "en": "Exported"},
    "detected_count":     {"pt": "{n} instrumento(s) detectado(s) · chips: {chips}",
                           "en": "{n} instrument(s) detected · chips: {chips}"},
    "error_open":         {"pt": "Erro ao abrir VGM",   "en": "Error opening VGM"},
    "error_export":       {"pt": "Erro ao exportar",    "en": "Export error"},
    "some_errors":        {"pt": "Alguns erros",        "en": "Some errors"},
    "exported_all":       {"pt": "{n} instrumento(s) exportado(s) → {dir}",
                           "en": "{n} instrument(s) exported → {dir}"},

    # ── Diálogos de arquivo ───────────────────────────────────────────────
    "open_dialog_title":  {"pt": "Abrir arquivo VGM",  "en": "Open VGM file"},
    "save_dialog_title":  {"pt": "Salvar em…",         "en": "Save to…"},
    "save_all_title":     {"pt": "Salvar todos em…",   "en": "Save all to…"},

    # ── Painel de detalhes ────────────────────────────────────────────────
    "select_instrument":  {"pt": "Selecione um instrumento", "en": "Select an instrument"},
    "channel":            {"pt": "Canal",               "en": "Channel"},
    "detected_x":         {"pt": "{n}× detectado",      "en": "{n}× detected"},
    "incomplete_envelope":{"pt": "  ⚠ envelope incompleto (cortado)",
                           "en": "  ⚠ incomplete envelope (cut)"},
    "export_fui":         {"pt": "Exportar instrumento como .fui",
                           "en": "Export instrument as .fui"},

    # ── Macros ────────────────────────────────────────────────────────────
    "volume_macro":       {"pt": "Macro de volume",     "en": "Volume macro"},
    "loop_from":          {"pt": "  ↻ loop a partir do frame {n}",
                           "en": "  ↻ loop from frame {n}"},
    "arp_macro":          {"pt": "Macro de arpejo",     "en": "Arpeggio macro"},
    "duty_cycle":         {"pt": "Duty cycle",          "en": "Duty cycle"},

    # ── Notas utilizadas ─────────────────────────────────────────────────
    "notes_used_noise":   {"pt": "Notas utilizadas (canal de ruído)",
                           "en": "Notes used (noise channel)"},
    "notes_used":         {"pt": "Notas utilizadas",    "en": "Notes used"},
    "no_notes":           {"pt": "Nenhuma nota detectada", "en": "No notes detected"},
    "furnace_hint":       {"pt": "Use a nota mais frequente como referência no Furnace.",
                           "en": "Use the most frequent note as reference in Furnace."},
    "metallic_legend":    {"pt": "M = modo metálico (timbre diferente, mesmas notas)",
                           "en": "M = metallic mode (different timbre, same notes)"},
    "metallic_tip":       {"pt": "Modo metálico (bit 7 ativo)",
                           "en": "Metallic mode (bit 7 active)"},

    # ── Modos de ruído SN76489 ────────────────────────────────────────────
    "noise_simple":       {"pt": "Simples",             "en": "Simple"},
    "noise_complete":     {"pt": "Completo",            "en": "Complete"},
    "noise_periodic":     {"pt": "Periódico",           "en": "Periodic"},
    "noise_periodic_c":   {"pt": "Periódico completo",  "en": "Complete periodic"},

    # ── Arpejo interno ────────────────────────────────────────────────────
    "arp_internal":       {"pt": "Arpejo interno",      "en": "Internal arpeggio"},
    "arp_legend":         {"pt": "azul = agudo  ·  vermelho = grave  ·  laranja = nota base",
                           "en": "blue = higher  ·  red = lower  ·  orange = base note"},

    # ── Export ────────────────────────────────────────────────────────────
    "export_fui":         {"pt": "Exportar como .fui (Furnace)",
                           "en": "Export as .fui (Furnace)"},
    "export_dmp":         {"pt": "Exportar como .dmp (DefleMask)",
                           "en": "Export as .dmp (DefleMask)"},
    "export_dmp_tip":     {"pt": "DefleMask: somente macro de volume (sem suporte a nota fixa)",
                           "en": "DefleMask: volume macro only (no fixed-note arpeggio support)"},
    "export_format_title":{"pt": "Formato de exportação", "en": "Export format"},
    "export_format_label":{"pt": "Exportar todos como:", "en": "Export all as:"},

    # ── About / crédito ──────────────────────────────────────────────────
    "dev_by":             {"pt": "Desenvolvido por",    "en": "Developed by"},
}


_current_lang = "en"


def set_lang(lang: str):
    global _current_lang
    if lang in ("pt", "en"):
        _current_lang = lang


def get_lang() -> str:
    return _current_lang


def t(key: str, **kwargs) -> str:
    """Retorna a string traduzida para o idioma atual."""
    entry = STRINGS.get(key, {})
    text  = entry.get(_current_lang, entry.get("en", key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text
