"""
VGM Parser — decodifica arquivos .vgm e .vgz frame a frame.
Suporta: SN76489, YM2612 (Mega Drive PSG), 2A03 (NES APU),
         AY-3-8910, VRC6, Sunsoft 5B, MMC5
"""

import struct
import gzip
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VGMHeader:
    version: int
    total_samples: int
    gd3_offset: int
    loop_offset: int
    loop_samples: int
    rate: int
    data_offset: int
    sn76489_clock: int
    ym2612_clock: int
    ym2151_clock: int
    ay8910_clock: int
    nes_apu_clock: int
    # Chips de expansão NES
    vrc6_clock: int = 0
    mmc5_clock: int = 0
    fds_clock: int = 0
    n163_clock: int = 0
    # Sistema de origem inferido do header
    system: str = "unknown"   # "nes", "sms", "md", "msx", etc.


@dataclass
class RegisterWrite:
    """Uma escrita em registrador capturada de um comando VGM."""
    frame: int
    chip: str
    register: int
    value: int


@dataclass
class VGMData:
    header: VGMHeader
    writes: list[RegisterWrite] = field(default_factory=list)
    chips: set[str] = field(default_factory=set)
    total_frames: int = 0
    vgm_fps: float = 60.0   # taxa real do VGM em Hz (60, 50, ou valor customizado)


def _detect_system(header: VGMHeader) -> str:
    """Infere o sistema de origem com base nos clocks presentes."""
    if header.ym2612_clock and header.sn76489_clock:
        return "md"      # Mega Drive / Genesis
    if header.nes_apu_clock:
        return "nes"
    if header.sn76489_clock and not header.ym2612_clock:
        # SMS clock = 3.579545 MHz, GG = 3.579545 MHz
        return "sms"
    if header.ay8910_clock:
        return "msx"
    if header.ym2151_clock:
        return "arcade"
    return "unknown"


def _read_header(data: bytes) -> VGMHeader:
    if data[:4] != b"Vgm ":
        raise ValueError("Arquivo não é um VGM válido (magic bytes incorretos)")

    version      = struct.unpack_from("<I", data, 0x08)[0]
    sn_clock     = struct.unpack_from("<I", data, 0x0C)[0]
    ym2612_clock = struct.unpack_from("<I", data, 0x10)[0]
    total_samp   = struct.unpack_from("<I", data, 0x18)[0]
    loop_off     = struct.unpack_from("<I", data, 0x1C)[0]
    loop_samp    = struct.unpack_from("<I", data, 0x20)[0]
    rate         = struct.unpack_from("<I", data, 0x24)[0] if version >= 0x101 else 0
    ym2151_clock = struct.unpack_from("<I", data, 0x30)[0] if version >= 0x151 else 0
    gd3_off      = struct.unpack_from("<I", data, 0x14)[0]

    if version >= 0x150:
        raw_off = struct.unpack_from("<I", data, 0x34)[0]
        data_offset = (0x34 + raw_off) if raw_off else 0x40
    else:
        data_offset = 0x40

    if data_offset < 0x40:
        data_offset = 0x40

    nes_clock = ay_clock = vrc6_clock = mmc5_clock = fds_clock = n163_clock = 0

    if version >= 0x151 and len(data) > 0x84:
        nes_clock  = struct.unpack_from("<I", data, 0x84)[0]
    if version >= 0x151 and len(data) > 0x74:
        ay_clock   = struct.unpack_from("<I", data, 0x74)[0]
    if version >= 0x161 and len(data) > 0xC0:
        vrc6_clock = struct.unpack_from("<I", data, 0xC0)[0]
    if version >= 0x161 and len(data) > 0xD0:
        mmc5_clock = struct.unpack_from("<I", data, 0xD0)[0]
    if version >= 0x161 and len(data) > 0xC4:
        fds_clock  = struct.unpack_from("<I", data, 0xC4)[0]
    if version >= 0x161 and len(data) > 0xCC:
        n163_clock = struct.unpack_from("<I", data, 0xCC)[0]

    hdr = VGMHeader(
        version=version,
        total_samples=total_samp,
        gd3_offset=gd3_off,
        loop_offset=loop_off,
        loop_samples=loop_samp,
        rate=rate,
        data_offset=data_offset,
        sn76489_clock=sn_clock,
        ym2612_clock=ym2612_clock,
        ym2151_clock=ym2151_clock,
        ay8910_clock=ay_clock,
        nes_apu_clock=nes_clock,
        vrc6_clock=vrc6_clock,
        mmc5_clock=mmc5_clock,
        fds_clock=fds_clock,
        n163_clock=n163_clock,
    )
    hdr.system = _detect_system(hdr)
    return hdr


def parse_vgm(path: str) -> VGMData:
    """Lê um arquivo .vgm ou .vgz e retorna VGMData com todos os writes."""
    with open(path, "rb") as f:
        raw = f.read()

    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)

    header = _read_header(raw)
    data   = VGMData(header=header)
    pos    = header.data_offset
    frame  = 0
    buf    = raw

    chips_present = set()
    if header.sn76489_clock:  chips_present.add("SN76489")
    if header.ym2612_clock:   chips_present.add("YM2612")
    if header.nes_apu_clock:  chips_present.add("2A03")
    if header.ay8910_clock:   chips_present.add("AY8910")
    if header.vrc6_clock:     chips_present.add("VRC6")
    if header.mmc5_clock:     chips_present.add("MMC5")
    if header.fds_clock:      chips_present.add("FDS")
    if header.n163_clock:     chips_present.add("N163")

    data.chips = chips_present

    # ── Calcula taxa real do VGM ──────────────────────────────────────────────
    # O campo rate do header (offset 0x24) é o refresh rate em Hz.
    # 0 = não especificado → inferir pelo sistema ou usar 60Hz padrão.
    # O VGM corre a 44100 samples/s. Um frame NTSC = 735 samples, PAL = 882.
    # Casos customizados (overclock etc.) têm rate diferente de 50/60.
    if header.rate > 0:
        data.vgm_fps = float(header.rate)
    else:
        # Sem rate explícito — infere pelo sistema
        if header.system in ("sms", "md"):
            # Mega Drive / Master System: maioria NTSC=60, PAL=50
            # Sem info explícita, assume 60Hz
            data.vgm_fps = 60.0
        elif header.system == "nes":
            data.vgm_fps = 60.098  # NTSC exato do NES
        elif header.system == "msx":
            data.vgm_fps = 50.0    # MSX é majoritariamente PAL
        else:
            data.vgm_fps = 60.0
    writes = []

    while pos < len(buf):
        if pos >= len(buf):
            break
        cmd = buf[pos]; pos += 1

        if cmd == 0x66:
            break

        # ── Waits ──────────────────────────────────────────────────────
        elif cmd == 0x61:
            frame += struct.unpack_from("<H", buf, pos)[0]; pos += 2
        elif cmd == 0x62:
            frame += 735
        elif cmd == 0x63:
            frame += 882
        elif 0x70 <= cmd <= 0x7F:
            frame += (cmd & 0x0F) + 1

        # ── SN76489 (SMS, GG, MD PSG) ──────────────────────────────────
        elif cmd == 0x50:
            val = buf[pos]; pos += 1
            writes.append(RegisterWrite(frame, "SN76489", 0xFF, val))
            chips_present.add("SN76489")

        # ── YM2612 (Mega Drive FM) — ignorado, só registramos presença ─
        elif cmd == 0x52:
            pos += 2
        elif cmd == 0x53:
            pos += 2

        # ── 2A03 / NES APU ─────────────────────────────────────────────
        elif cmd in (0xB4, 0xB5):
            reg = buf[pos]; val = buf[pos+1]; pos += 2
            writes.append(RegisterWrite(frame, "2A03", reg, val))
            chips_present.add("2A03")

        # ── AY-3-8910 / Sunsoft 5B ─────────────────────────────────────
        elif cmd == 0xA0:
            reg = buf[pos]; val = buf[pos+1]; pos += 2
            chip = "AY8910"
            writes.append(RegisterWrite(frame, chip, reg & 0x7F, val))
            chips_present.add(chip)

        # ── VRC6 ───────────────────────────────────────────────────────
        # 0x90 = VRC6 Pulse 1 ($9000-$9002): [reg 0-2][val]
        # 0x91 = VRC6 Pulse 2 ($A000-$A002): [reg 0-2][val]
        # 0x92 = VRC6 Sawtooth ($B000-$B002): [reg 0-2][val]
        elif cmd in (0x90, 0x91, 0x92):
            reg = buf[pos]; val = buf[pos+1]; pos += 2
            chip_map = {0x90: "VRC6_P1", 0x91: "VRC6_P2", 0x92: "VRC6_SAW"}
            chip = chip_map[cmd]
            writes.append(RegisterWrite(frame, chip, reg, val))
            chips_present.add("VRC6")

        # ── MMC5 ───────────────────────────────────────────────────────
        elif cmd == 0xBD:
            reg = buf[pos]; val = buf[pos+1]; pos += 2
            writes.append(RegisterWrite(frame, "MMC5", reg, val))
            chips_present.add("MMC5")

        # ── Data blocks ────────────────────────────────────────────────
        # 0x67: [0x66 fixo][tipo 1B][tamanho 4B][dados]
        elif cmd == 0x67:
            pos += 1                  # 0x66 fixo
            pos += 1                  # tipo
            blk_size = struct.unpack_from("<I", buf, pos)[0]; pos += 4
            pos += blk_size
        # 0x68: [0x66 fixo][tipo 1B][src_addr 3B][dst_addr 3B][size 3B][dados]
        elif cmd == 0x68:
            pos += 1                  # 0x66 fixo
            pos += 1                  # tipo
            pos += 3                  # endereço fonte
            pos += 3                  # endereço destino
            blk_size = struct.unpack_from("<I", buf, pos)[0] & 0xFFFFFF; pos += 3
            pos += blk_size

        # ── Comandos com 2 bytes de dados (skip) ───────────────────────
        elif cmd in (0x51, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
                     0x5A, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F,
                     0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7,
                     0xA8, 0xA9, 0xAA, 0xAB, 0xAC, 0xAD, 0xAE, 0xAF,
                     0xB0, 0xB1, 0xB2, 0xB3, 0xB9, 0xBA, 0xBB, 0xBC,
                     0xBE, 0xBF,
                     0xC4, 0xC5, 0xC6, 0xC7, 0xC8,
                     0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6):
            pos += 2
        elif cmd in (0xC0, 0xC1, 0xC2, 0xC3):
            pos += 3
        elif cmd == 0xE0:
            pos += 4
        elif cmd in (0x30, 0x3F):
            pos += 1
        else:
            pos += 1

    data.writes       = writes
    data.chips        = chips_present
    data.total_frames = frame
    return data