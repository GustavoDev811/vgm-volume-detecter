"""
VGM Volume Detecter — Exportador de instrumentos.

Formatos:
  .fui — Furnace Tracker v0.6.9 (versão 187)
  .dmp — DefleMask v1.0.0 (versão 0x0B = 11)

Referências:
  Furnace: https://github.com/tildearrow/furnace/blob/master/doc/4-instrument/
  DefleMask: https://www.deflemask.com/DMP_SPECS.txt
"""

import struct
import os
from typing import Optional
from .analyzer import Instrument

# ─────────────────────────────────────────────────────────────────────────────
# Furnace .fui — versão 187 (0.6.9)
# ─────────────────────────────────────────────────────────────────────────────

FINS_MAGIC   = b"-Furnace instr.-"
FUI_VERSION  = 187   # versão do formato .fui do Furnace 0.6.9

# Tipos de instrumento (campo ins_type no INS2)
FUI_TYPE = {
    "SN76489":  0x03,   # SN76489 / T6W28
    "2A03":     0x01,   # NES / 2A03
    "AY8910":   0x04,   # AY-3-8910 / SSG
    "VRC6_P1":  0x0B,   # VRC6
    "VRC6_P2":  0x0B,
    "VRC6_SAW": 0x0B,
    "MMC5":     0x01,   # trata como NES
}

# Tags de feature
FEAT_NAME = b"NAME"
FEAT_MA   = b"MA  "   # macros
FEAT_NA   = b"NA  "   # NES APU (duty cycle)
FEAT_END  = b"EN  "   # marcador de fim

# Índices de macro
MACRO_VOL   = 0
MACRO_ARP   = 1
MACRO_PITCH = 2
MACRO_DUTY  = 4


def _calc_speed(vgm_fps: float) -> int:
    """
    Calcula o Step Length (speed) correto para o Furnace a partir do
    refresh rate real do VGM.

    O engine do Furnace roda a 60 ticks/s (NTSC padrão).
    speed = round(engine_hz / vgm_fps), mínimo 1.

    Exemplos:
      60Hz NTSC  → speed=1  (timing exato)
      50Hz PAL   → speed=1  (≈83% correto — melhor aproximação possível)
      30Hz       → speed=2
      20Hz       → speed=3
      120Hz OC   → speed=1  (acima de 60Hz não tem como representar < 1)
    """
    engine_hz = 60.0
    return max(1, round(engine_hz / vgm_fps))
    """String no formato Furnace: [len 2B][bytes][null]."""
    encoded = s.encode("utf-8") + b"\x00"
    return struct.pack("<H", len(encoded)) + encoded


def _pack_macro_fui(index: int, values: list[int],
                    loop: int = -1, release: int = -1,
                    delay: int = 0, speed: int = 1) -> bytes:
    """
    Macro no formato Furnace v187:
    [index 1B][length 4B][loop 4B signed][release 4B signed][open 1B]
    [delay 1B][speed 1B (step length)]
    [value0 4B signed] ... [valueN 4B signed]

    speed=2 corresponde a Step Length 2 no Furnace, necessário para
    reproduzir o timing correto de VGMs gravados a 60fps.
    """
    buf = bytearray()
    buf += struct.pack("<B", index)
    buf += struct.pack("<I", len(values))
    buf += struct.pack("<i", loop)
    buf += struct.pack("<i", release)
    buf += struct.pack("<B", 0)        # open = 0 (fechado)
    buf += struct.pack("<B", delay)    # delay = 0
    buf += struct.pack("<B", speed)    # speed = step length (2 = timing correto)
    for v in values:
        buf += struct.pack("<i", v)
    return bytes(buf)


def _build_fui(instrument: Instrument, vgm_fps: float = 60.0) -> bytes:
    """Gera binário .fui para Furnace 0.6.9.
    
    vgm_fps: taxa real do VGM em Hz — usada para calcular o Step Length
    correto de cada macro, garantindo timing preciso no Furnace.
    """
    ins_type = FUI_TYPE.get(instrument.chip, 0x01)
    speed    = _calc_speed(vgm_fps)   # Step Length calculado dinamicamente
    features = bytearray()

    # NAME
    name_data = _pack_str_fui(instrument.name)
    features += FEAT_NAME
    features += struct.pack("<I", len(name_data))
    features += name_data

    # MA — macros
    macros_buf  = bytearray()
    macro_count = 0

    if instrument.volume_macro:
        lp = instrument.loop_point if instrument.loop_point >= 0 else -1
        macros_buf += _pack_macro_fui(MACRO_VOL, instrument.volume_macro, loop=lp, speed=speed)
        macro_count += 1

    if instrument.arp_macro and any(v != 0 for v in instrument.arp_macro):
        macros_buf += _pack_macro_fui(MACRO_ARP, instrument.arp_macro, speed=speed)
        macro_count += 1

    if instrument.pitch_macro and any(v != 0 for v in instrument.pitch_macro):
        macros_buf += _pack_macro_fui(MACRO_PITCH, instrument.pitch_macro, speed=speed)
        macro_count += 1

    if macro_count > 0:
        ma_data = struct.pack("<H", macro_count) + bytes(macros_buf)
        features += FEAT_MA
        features += struct.pack("<I", len(ma_data))
        features += ma_data

    # NA — NES APU feature para 2A03 e MMC5
    # Formato: [initial_duty_env 1B][flags 1B][sweep_params 1B][reserved 1B]
    # initial_duty_env: bits 7-6 = duty, bits 5-0 = envelope/volume
    if instrument.chip in ("2A03", "MMC5"):
        duty = instrument.duty_cycle if instrument.duty_cycle is not None else 0
        # bits 7-6 = duty (0-3), bit 4 = envelope disable (1=disable), bits 3-0 = volume
        initial_val = ((duty & 0x03) << 6) | 0x10 | 0x0F  # duty + env_disable + max_vol
        na_data = struct.pack("<BBBB",
            initial_val,  # duty + envelope settings
            0,            # flags
            0,            # sweep params
            0,            # reserved
        )
        features += FEAT_NA
        features += struct.pack("<I", len(na_data))
        features += na_data

    # Features específicas por chip — obrigatórias para o Furnace carregar
    if instrument.chip == "SN76489":
        # SN  — T6W28/SN76489: [lfsr_preset 4B][flags 1B]
        sn_data = struct.pack("<IB", 0, 0)
        features += b"SN  "
        features += struct.pack("<I", len(sn_data))
        features += sn_data

    elif instrument.chip == "AY8910":
        # AY  — AY-3-8910/SSG: [flags 1B]
        ay_data = struct.pack("<B", 0)
        features += b"AY  "
        features += struct.pack("<I", len(ay_data))
        features += ay_data

    # EN — fim
    features += FEAT_END
    features += struct.pack("<I", 0)

    # INS2 block: [version 2B][type 2B][features...]
    ins2_body  = struct.pack("<HH", FUI_VERSION, ins_type) + bytes(features)
    ins2_block = b"INS2" + struct.pack("<I", len(ins2_body)) + ins2_body

    # Arquivo: [magic 16B][version 2B][reserved 2B][INS2 block]
    # IMPORTANTE: após magic+version vêm 2 bytes RESERVADOS (não tamanho)
    buf = bytearray()
    buf += FINS_MAGIC
    buf += struct.pack("<H", FUI_VERSION)
    buf += struct.pack("<H", 0)            # 2 bytes reservados = 0x0000
    buf += ins2_block
    return bytes(buf)


# ─────────────────────────────────────────────────────────────────────────────
# DefleMask .dmp — versão 0x0B (DefleMask v1.0.0)
# ─────────────────────────────────────────────────────────────────────────────

DMP_VERSION  = 0x0B   # versão oficial do DefleMask v1.0.0
DMP_STD_MODE = 0       # STANDARD (PSG)
DMP_FM_MODE  = 1

# Códigos de sistema do .dmp
DMP_SYSTEM = {
    "SN76489":  0x03,   # SYSTEM_SMS (SMS/Genesis PSG)
    "2A03":     0x06,   # SYSTEM_NES
    "AY8910":   0x03,   # AY → trata como SMS (mais compatível no DefleMask)
    "MMC5":     0x06,   # MMC5 → NES
}


def _pack_macro_dmp(values: list[int], loop: int = -1) -> bytes:
    """
    Macro no formato DefleMask:
    [ENVELOPE_SIZE 1B]
    [ENVELOPE_VALUE 4B signed] × ENVELOPE_SIZE
    [LOOP_POSITION 1B] (só se ENVELOPE_SIZE > 0; 0xFF = sem loop)
    """
    buf = bytearray()
    size = len(values)
    buf += struct.pack("<B", size)
    for v in values:
        buf += struct.pack("<i", v)
    if size > 0:
        lp_byte = loop if (loop >= 0 and loop < size) else 0xFF
        buf += struct.pack("<B", lp_byte)
    return bytes(buf)


def _build_dmp(instrument: Instrument) -> bytes:
    """
    Gera binário .dmp para DefleMask v1.0.0.

    Suporte AY-3-8910 / YM2149 / Sunsoft 5B:
    - Se o canal usa envelope de hardware (ay_envelope), exporta os parâmetros
      do envelope no campo SSG/AY do .dmp
    - Volume macro exportado normalmente (0-15 ou envelope)
    - Mix tom+noise preservado quando detectado

    Limitações:
    - Arpejo com nota fixa (@) não suportado: exportado zerado
    - Wavetable macro vazio (PSG não usa)
    """
    buf    = bytearray()
    system = DMP_SYSTEM.get(instrument.chip, 0x03)

    # Header
    buf += struct.pack("<B", DMP_VERSION)
    buf += struct.pack("<B", system)
    buf += struct.pack("<B", DMP_STD_MODE)

    # VOLUME MACRO
    # Para AY com envelope ativo: gera macro de volume constante em 15
    # (o envelope de hardware controla o volume real)
    if instrument.chip == "AY8910" and instrument.ay_envelope and instrument.ay_envelope.active:
        vol = [15]  # volume máximo — envelope de HW controla o shape
        lp  = -1
    else:
        vol = instrument.volume_macro or []
        lp  = instrument.loop_point if instrument.loop_point >= 0 else -1
    buf += _pack_macro_dmp(vol, loop=lp)

    # ARPEJO MACRO — sempre vazio (sem suporte a nota fixa no .dmp)
    buf += _pack_macro_dmp([], loop=-1)
    buf += struct.pack("<B", 0)   # ARPEGGIO MACRO MODE = 0 (Normal)

    # DUTY/NOISE MACRO
    if instrument.chip in ("2A03", "MMC5") and instrument.duty_cycle is not None:
        buf += _pack_macro_dmp([instrument.duty_cycle], loop=0)
    else:
        buf += _pack_macro_dmp([], loop=-1)

    # WAVETABLE MACRO (vazio para PSG)
    buf += _pack_macro_dmp([], loop=-1)

    # ── AY-3-8910 / YM2149 / Sunsoft 5B — campos específicos ────────────────
    # O DefleMask v1.0.0 suporta envelope de hardware do AY no campo SSG:
    # [envelope_enabled 1B][envelope_shape 1B][envelope_period_lo 1B][envelope_period_hi 1B]
    # [noise_enabled 1B][noise_period 1B]
    if instrument.chip == "AY8910":
        env = instrument.ay_envelope
        if env and env.active:
            buf += struct.pack("<B", 1)              # envelope habilitado
            buf += struct.pack("<B", env.shape & 0x0F)  # shape 0-15
            buf += struct.pack("<H", env.period & 0xFFFF)  # período (lo+hi)
        else:
            buf += struct.pack("<B", 0)   # envelope desabilitado
            buf += struct.pack("<B", 0)   # shape = 0
            buf += struct.pack("<H", 0)   # período = 0

        # Noise
        noise_en  = bool(instrument.ay_tone_noise_mix and instrument.ay_tone_noise_mix & 2)
        noise_per = instrument.ay_noise_period or 0
        buf += struct.pack("<B", 1 if noise_en else 0)
        buf += struct.pack("<B", noise_per & 0x1F)

    return bytes(buf)


# ─────────────────────────────────────────────────────────────────────────────
# Funções públicas
# ─────────────────────────────────────────────────────────────────────────────

def _safe_name(name: str) -> str:
    """Remove caracteres inválidos para nome de arquivo."""
    return "".join(c if c.isalnum() or c in "-_ " else "_" for c in name)


def export_fui(instrument: Instrument, output_dir: str) -> str:
    """Exporta como .fui (Furnace Tracker 0.6.9, versão 187)."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{_safe_name(instrument.name)}.fui")
    with open(path, "wb") as f:
        f.write(_build_fui(instrument))
    return path


def export_dmp(instrument: Instrument, output_dir: str, vgm_fps: float = 60.0) -> str:
    """
    Exporta como .dmp (DefleMask v1.0.0, versão 0x0B).
    Apenas volume macro — DefleMask não suporta nota fixa (@) no arpejo.
    O timing do .dmp é controlado pelo próprio DefleMask — vgm_fps não afeta o .dmp.
    """
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{_safe_name(instrument.name)}.dmp")
    with open(path, "wb") as f:
        f.write(_build_dmp(instrument))
    return path


def export_notes_info(instrument: Instrument, output_dir: str) -> Optional[str]:
    """Gera .txt com as notas utilizadas pelo instrumento."""
    if not instrument.notes_used:
        return None
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{_safe_name(instrument.name)}_notas.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"Instrumento: {instrument.name}\n")
        f.write(f"Chip: {instrument.chip} | Canal: {instrument.channel}\n")
        f.write("-" * 40 + "\n")
        f.write("Notas utilizadas (do VGM original):\n\n")
        for nu in instrument.notes_used:
            mode_str  = f" [{nu.noise_mode}]" if nu.noise_mode else ""
            metal_str = " [metálico]" if nu.metallic else ""
            bar = "#" * int(nu.percent / 5)
            f.write(f"  {nu.note:<6} {bar:<20} {nu.percent:>5.1f}%  "
                    f"({nu.count}x){mode_str}{metal_str}\n")
        f.write("\n")
        f.write("Use a nota mais frequente como referencia no Furnace Tracker.\n")
    return path
