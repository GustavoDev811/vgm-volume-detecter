"""
Analisador de instrumentos PSG.
Extrai envelopes de volume com detecção de loop, arpejo interno e notas de ruído.
"""

import math
from dataclasses import dataclass, field
from collections import Counter
from typing import Optional
from .parser import VGMData, RegisterWrite


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

NES_NOISE_PERIODS_NTSC = [
    4, 8, 16, 32, 64, 96, 128, 160,
    202, 254, 380, 508, 762, 1016, 2034, 4068
]

AY_CLOCK_DEFAULT = 1_789_773


# ---------------------------------------------------------------------------
# Estruturas de dados
# ---------------------------------------------------------------------------

@dataclass
class NoteUsage:
    note: str
    count: int
    percent: float
    period: int = 0        # índice de período
    metallic: bool = False # 2A03: modo metálico (bit 7 do reg 0x0E)
    # SN76489 noise mode: "simple", "periodic", "complete_simple", "complete_periodic"
    noise_mode: str = ""


@dataclass
class EnvelopeInfo:
    """
    Envelope de volume com ponto de loop opcional.
    loop_point == -1  → sem loop (toca e encerra)
    loop_point >= 0   → loop a partir desse índice
    """
    values: list[int]
    loop_point: int = -1


@dataclass
class AYEnvelope:
    """
    Envelope de hardware do AY-3-8910 / YM2149 / Sunsoft 5B.
    O chip tem um gerador de envelope com 8 formas (shapes) e período próprio.
    Quando ativo, substitui o volume manual do canal.
    """
    shape: int          # 0-7: forma do envelope (attack, decay, sustain, etc.)
    period: int         # período do envelope (0-65535)
    active: bool = True # se o envelope estava ativo neste instrumento


@dataclass
class Instrument:
    id: str
    name: str
    chip: str
    channel: str
    is_noise: bool
    volume_macro: list[int]
    loop_point: int
    arp_macro: list[int]
    pitch_macro: list[int]
    notes_used: list[NoteUsage] = field(default_factory=list)
    noise_arp: list[str] = field(default_factory=list)
    noise_arp_info: Optional[object] = None  # NoiseArpInfo
    frame_start: int = 0
    frame_end: int = 0
    occurrences: int = 1
    duty_cycle: Optional[int] = None
    truncated: bool = False
    # AY-3-8910 / YM2149 / Sunsoft 5B
    ay_envelope: Optional[AYEnvelope] = None  # envelope de hardware do AY
    ay_noise_period: Optional[int] = None     # período do gerador de noise do AY
    ay_tone_noise_mix: Optional[int] = None   # bits de mix tom+noise (reg 0x07)


# ---------------------------------------------------------------------------
# Conversão de período → nota
# ---------------------------------------------------------------------------

def _period_to_note(period: int, clock: int, octave_offset: int = 0) -> Optional[str]:
    if period <= 0:
        return None
    try:
        freq     = clock / (32.0 * period)
        midi     = 69 + 12 * math.log2(freq / 440.0)
        midi_int = round(midi) + (octave_offset * 12)
        if midi_int < 0 or midi_int > 127:
            return None
        octave   = max(0, (midi_int // 12) - 1)
        note_idx = midi_int % 12
        return f"{NOTE_NAMES[note_idx]}-{octave}"
    except (ValueError, ZeroDivisionError):
        return None


def _sn76489_noise_note(reg_val: int, clock: int) -> Optional[str]:
    rate = reg_val & 0x03
    if rate == 3:
        return None
    period = {0: 0x10, 1: 0x20, 2: 0x40}[rate]
    return _period_to_note(period, clock, octave_offset=-6)


# Tabela de notas do ruído do 2A03 conforme mapeamento real do Furnace Tracker.
# Derivada empiricamente usando VGMs reais com notas e arpejos conhecidos.
# Âncoras confirmadas marcadas com #✓
NES_NOISE_NOTE_TABLE = {
    0x0F: 24,   # C-0  ✓ confirmado
    0x0E: 64,   # E-3  ✓ confirmado (F-3 arpejo -1st)
    0x0D: 62,   # D-3  interpolado
    0x0C: 60,   # C-3  interpolado
    0x0B: 58,   # A#2  ✓ confirmado (C#3 arpejo -3st)
    0x0A: 57,   # A-2  interpolado
    0x09: 55,   # G-2  interpolado
    0x08: 53,   # F-2  interpolado
    0x07: 52,   # E-2  interpolado
    0x06: 51,   # D#2  interpolado
    0x05: 50,   # D-2  ✓ confirmado (base de C-3/C#3/F-3 no VGM)
    0x04: 53,   # F-2  interpolado
    0x03: 56,   # G#2  ✓ confirmado (C-3 arpejo)
    0x02: 57,   # A-2  ✓ confirmado (C-3 arpejo)
    0x01: 60,   # C-3  interpolado
    0x00: 63,   # D#3  ✓ confirmado
}

NOTE_NAMES_FULL = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]


def _midi_to_note(midi: int) -> str:
    # Furnace: C-0 = MIDI 24. Notas simples usam hífen (C-0, D-2),
    # notas com sustenido não precisam (C#0, D#1).
    octave   = (midi // 12) - 2
    note_idx = midi % 12
    name     = NOTE_NAMES_FULL[note_idx]
    sep      = "-" if "#" not in name else ""
    return f"{name}{sep}{octave}"


def _nes_noise_note(reg_val: int, clock: int = 1_789_773) -> Optional[str]:
    """
    Retorna a nota base do ruído do 2A03 conforme o Furnace Tracker.
    O ciclo de repetição por oitava é tratado separadamente na coleta de notas.
    """
    idx  = reg_val & 0x0F
    midi = NES_NOISE_NOTE_TABLE.get(idx)
    if midi is None:
        return None
    return _midi_to_note(midi)


def _nes_noise_note_cycle(reg_val: int, played_midi: int) -> str:
    """
    Dado o valor de registrador e o MIDI real tocado (considerando o ciclo),
    retorna a nota exata que o Furnace mostraria.
    O ciclo do 2A03 repete de 16 em 16 semitons (0x0F) ou varia por período.
    """
    idx       = reg_val & 0x0F
    base_midi = NES_NOISE_NOTE_TABLE.get(idx, 12)
    # Ajusta para a oitava mais próxima do played_midi
    diff  = played_midi - base_midi
    cycle = 16  # ciclo padrão do 0x0F; outros períodos podem variar
    adjusted = base_midi + round(diff / cycle) * cycle
    return _midi_to_note(adjusted)


# ---------------------------------------------------------------------------
# Detecção de loop interno no envelope
# ---------------------------------------------------------------------------

def _detect_loop(vols: list[int], min_loop: int = 2) -> EnvelopeInfo:
    """
    Analisa uma sequência de volumes e detecta loop interno.

    Casos:
    A) Termina em 0 (envelope com fim natural):
       - Procura sub-padrão repetido na parte ativa (antes do 0 final).
       - Se encontrar: guarda ataque + um ciclo do loop + zero final.
       - Se não encontrar: devolve a sequência EXATA, sem modificar.

    B) Não termina em 0 (canal sempre ativo = loop contínuo):
       - Procura onde a sequência começa a se repetir.
       - Se encontrar: guarda ataque + um ciclo do padrão repetido.
       - Se não encontrar: usa loop_point=0 (a sequência inteira em loop).

    Comparação é EXATA — [15·9·0] ≠ [15·9·0·0].
    """
    n = len(vols)
    if n == 0:
        return EnvelopeInfo(values=[], loop_point=-1)

    ends_with_zero = (vols[-1] == 0)

    if ends_with_zero:
        body = vols[:-1]   # parte ativa (sem o zero final)
        if len(body) < min_loop * 2:
            return EnvelopeInfo(values=vols, loop_point=-1)

        # Busca padrão repetido dentro do body
        for loop_start in range(0, len(body) - min_loop * 2 + 1):
            segment = body[loop_start:]
            for pat_len in range(min_loop, len(segment) // 2 + 1):
                pattern = segment[:pat_len]
                reps    = 0
                pos     = 0
                while pos + pat_len <= len(segment):
                    if segment[pos:pos + pat_len] == pattern:
                        reps += 1
                        pos  += pat_len
                    else:
                        break
                if reps >= 2 and pos == len(segment):
                    # Loop confirmado: ataque + um ciclo + zero
                    compact = body[:loop_start] + pattern + [0]
                    return EnvelopeInfo(values=compact, loop_point=loop_start)

        # Sem loop detectado — devolve exatamente o que veio
        return EnvelopeInfo(values=vols, loop_point=-1)

    else:
        # Canal nunca silenciou — loop contínuo
        for loop_start in range(0, n - min_loop * 2 + 1):
            segment = vols[loop_start:]
            for pat_len in range(min_loop, len(segment) // 2 + 1):
                pattern = segment[:pat_len]
                reps    = 0
                pos     = 0
                while pos + pat_len <= len(segment):
                    if segment[pos:pos + pat_len] == pattern:
                        reps += 1
                        pos  += pat_len
                    else:
                        break
                if reps >= 2 and pos == len(segment):
                    compact = vols[:loop_start] + pattern
                    return EnvelopeInfo(values=compact, loop_point=loop_start)

        # Sem padrão encontrado — loop na posição 0 (sequência inteira em loop)
        return EnvelopeInfo(values=vols[:min(64, n)], loop_point=0)


# ---------------------------------------------------------------------------
# Nomenclatura de instrumentos
# ---------------------------------------------------------------------------

def _inst_name(channel: str, env: EnvelopeInfo, idx: int, total: int) -> str:
    """
    Gera nome legível com valores e indicação de loop.
    Exemplos:
      'Square 1  [15·13·9·0]'
      'Square 1 — inst.2  [15·13 ↻ 9·5·0]'
      'Square 1  [↻ 15·15·15]'
    """
    vals = env.values
    lp   = env.loop_point
    num  = f" — inst.{idx+1}" if total > 1 else ""

    if lp < 0:
        parts = "·".join(str(v) for v in vals[:10])
        if len(vals) > 10:
            parts += "…"
        return f"{channel}{num}  [{parts}]"
    elif lp == 0:
        parts = "·".join(str(v) for v in vals[:8])
        if len(vals) > 8:
            parts += "…"
        return f"{channel}{num}  [↻ {parts}]"
    else:
        atk  = "·".join(str(v) for v in vals[:lp])
        loop = "·".join(str(v) for v in vals[lp:lp + 6])
        if len(vals) - lp > 6:
            loop += "…"
        return f"{channel}{num}  [{atk} ↻ {loop}]"


# ---------------------------------------------------------------------------
# Extração de eventos de nota individuais
# ---------------------------------------------------------------------------

def _split_into_note_events(writes: list[RegisterWrite], chip: str,
                             vol_fn, freq_fn) -> list[dict]:
    """
    Percorre os writes de um canal frame a frame e separa em eventos individuais.

    Regras:
    - Coleta TODOS os valores de volume em ordem, sem pular nenhum frame escrito.
    - Um evento começa quando o volume sai de 0, ou na primeira escrita do canal
      (chips como o 2A03 nunca escrevem explicitamente 0 antes de começar).
    - Um evento termina quando o volume vai a 0 — o 0 final É incluído.
    - REINÍCIO DE ATAQUE: se o volume sobe enquanto o evento ainda está ativo
      (ex: estava em 9 e vai para 15), o evento atual é fechado naquele frame
      (sem zero final — foi interrompido) e um novo evento começa imediatamente.
    - Frequências escritas enquanto o volume está ativo são capturadas
      para detecção de arpejo interno.
    """
    events      = []
    cur_vols    = []
    cur_freqs   = []
    in_note     = False
    frame_start = 0
    last_vol    = 0
    first_write = True   # primeira escrita do canal inicia evento mesmo sem zero

    def _close_event(frame_end: int):
        if cur_vols:
            events.append({
                "volumes":     cur_vols[:],
                "freqs":       cur_freqs[:],
                "frame_start": frame_start,
                "frame_end":   frame_end,
            })

    for w in writes:
        if w.chip != chip:
            continue

        v = vol_fn(w)
        f = freq_fn(w)

        if v is not None:
            if not in_note:
                # Inicia evento se volume > 0 OU se é a primeira escrita do canal
                if v > 0 or first_write:
                    first_write = False
                    if v > 0:
                        in_note     = True
                        frame_start = w.frame
                        cur_vols    = [v]
                        cur_freqs   = []
                        last_vol    = v
                    # se v == 0 na primeira escrita, só marca que já houve escrita
                    else:
                        first_write = False
            else:
                # Reinício de ataque: volume sobe no meio de um envelope ativo
                if v > last_vol and last_vol > 0:
                    _close_event(w.frame)
                    cur_vols    = [v]
                    cur_freqs   = []
                    frame_start = w.frame
                    last_vol    = v
                else:
                    cur_vols.append(v)
                    last_vol = v
                    if v == 0:
                        _close_event(w.frame)
                        cur_vols  = []
                        cur_freqs = []
                        in_note   = False
                        last_vol  = 0

        if f is not None and in_note:
            cur_freqs.append(f)

    # Evento sem zero final (loop contínuo ou fim do VGM com canal ativo)
    if in_note and cur_vols:
        _close_event(frame_start + len(cur_vols))

    return events


def _is_truncated(vols: list[int]) -> bool:
    """Evento truncado = não termina em 0 e não é loop contínuo detectado."""
    return len(vols) > 0 and vols[-1] != 0


def _group_events(events: list[dict], chip: str = "", is_noise: bool = False) -> list[dict]:
    """
    Agrupa eventos com exatamente o mesmo padrão de volume.
    Preserva ordem de primeira aparição.

    Eventos truncados (cortados no meio, sem zero final):
    - Se já existe um padrão completo cujo início bate com o truncado,
      o truncado é contado como ocorrência desse padrão completo.
    - Se não existe padrão completo correspondente, o truncado é listado
      sozinho mas marcado com truncated=True (não vira instrumento separado
      na GUI — só conta nas ocorrências do completo quando ele aparecer).
    - Dois truncados com o mesmo padrão parcial são agrupados entre si.
    """
    complete: dict[tuple, dict] = {}   # padrões que terminam em 0
    truncated: dict[tuple, dict] = {}  # padrões cortados

    for ev in events:
        vols = ev["volumes"]
        key  = tuple(vols)

        if not _is_truncated(vols):
            if key not in complete:
                env       = _detect_loop(vols)
                arp       = _build_arp_macro(ev["freqs"], len(vols))
                noise_arp      = _build_noise_arp(ev["freqs"], chip) if is_noise else []
                noise_arp_info = _build_noise_arp_info(ev["freqs"], chip) if is_noise else None
                complete[key] = {
                    "env":           env,
                    "arp_macro":     arp,
                    "noise_arp":     noise_arp,
                    "noise_arp_info": noise_arp_info,
                    "frame_start":   ev["frame_start"],
                    "occurrences":   1,
                    "truncated":     False,
                }
            else:
                complete[key]["occurrences"] += 1
        else:
            matched = False
            for ck, cd in complete.items():
                if list(ck[:len(vols)]) == vols:
                    cd["occurrences"] += 1
                    matched = True
                    break
            if not matched:
                if key not in truncated:
                    env       = _detect_loop(vols)
                    arp       = _build_arp_macro(ev["freqs"], len(vols))
                    noise_arp      = _build_noise_arp(ev["freqs"], chip) if is_noise else []
                    noise_arp_info = _build_noise_arp_info(ev["freqs"], chip) if is_noise else None
                    truncated[key] = {
                        "env":           env,
                        "arp_macro":     arp,
                        "noise_arp":     noise_arp,
                        "noise_arp_info": noise_arp_info,
                        "frame_start":   ev["frame_start"],
                        "occurrences":   1,
                        "truncated":     True,
                    }
                else:
                    truncated[key]["occurrences"] += 1

    # Segunda passagem: tenta associar truncados órfãos a completos que
    # apareceram depois deles na música
    still_orphan = {}
    for tk, td in truncated.items():
        matched = False
        for ck, cd in complete.items():
            if list(ck[:len(tk)]) == list(tk):
                cd["occurrences"] += td["occurrences"]
                matched = True
                break
        if not matched:
            still_orphan[tk] = td

    # Monta resultado: completos + truncados órfãos, por ordem de aparição
    all_groups = list(complete.values()) + list(still_orphan.values())
    all_groups.sort(key=lambda x: x["frame_start"])
    return all_groups


def _build_arp_macro(freqs: list[int], vol_len: int) -> list[int]:
    """
    Constrói macro de arpejo a partir das frequências capturadas durante o envelope.
    Retorna lista de offsets em semitons relativos à primeira nota.
    Se não houver variação, retorna [0] * vol_len.
    """
    if len(freqs) < 2:
        return [0] * vol_len

    # Verifica se há variação real de frequência
    if len(set(freqs)) < 2:
        return [0] * vol_len

    # Converte frequências para MIDI e calcula offsets relativos à primeira
    def freq_to_midi(f: int) -> int:
        if f <= 0:
            return 0
        try:
            return round(69 + 12 * math.log2(f / 440.0))
        except ValueError:
            return 0

    base  = freq_to_midi(freqs[0])
    arp   = [freq_to_midi(f) - base for f in freqs]

    # Ajusta tamanho para coincidir com o envelope de volume
    if len(arp) < vol_len:
        arp += [arp[-1]] * (vol_len - len(arp))
    return arp[:vol_len]


# ---------------------------------------------------------------------------
# Coleta de notas para canais de ruído
# ---------------------------------------------------------------------------

def _nes_noise_freq_fn():
    """Captura mudanças de período do ruído do 2A03 (reg 0x0E)."""
    def fn(w: RegisterWrite) -> Optional[int]:
        if w.register == 0x0E:
            return w.value & 0x0F  # retorna o índice de período (0-15)
        return None
    return fn


def _sn_noise_freq_fn():
    """Captura mudanças de período do ruído do SN76489."""
    def fn(w: RegisterWrite) -> Optional[int]:
        if w.value & 0xE0 == 0xE0:
            return w.value & 0x07  # rate 0-3
        return None
    return fn


@dataclass
class NoiseArpInfo:
    """Informações do arpejo do canal de ruído."""
    notes: list[str]        # sequência de notas ex: ['A#0', 'C-1', 'C#1']
    offsets: list[int]      # offsets em semitons relativos à nota base ex: [0, -2, -3]
    base_note: str          # nota principal (offset 0)
    semitones_above: int    # máximo de semitons acima da base
    semitones_below: int    # máximo de semitons abaixo da base


def _note_to_midi_furnace(note: str) -> Optional[int]:
    """Converte nota no formato Furnace (C-0, D#1, A#0) para MIDI."""
    if not note or note == "?":
        return None
    try:
        # Formato: NOTA-OITAVA (C-0) ou NOTA#OITAVA (C#0, D#1)
        if len(note) >= 3 and note[1] == '#':
            name = note[:2]
            oct_ = int(note[2:])
        else:
            # C-0, D-1, A-0 etc — hífen é separador
            name = note[0]
            rest = note[1:]
            oct_ = int(rest.replace('-', '')) if rest.startswith('-') else int(rest.lstrip('-'))
            if '-' in rest:
                oct_ = int(rest[1:]) if rest[0] == '-' else int(rest.split('-')[1])
        notes_map = {'C':0,'C#':1,'D':2,'D#':3,'E':4,'F':5,'F#':6,'G':7,'G#':8,'A':9,'A#':10,'B':11}
        return (oct_ + 2) * 12 + notes_map[name]
    except (ValueError, KeyError, IndexError):
        return None


def _build_noise_arp_info(freqs: list[int], chip: str) -> Optional[NoiseArpInfo]:
    """
    Constrói informações completas do arpejo de ruído incluindo offsets.
    
    A nota base é a mais frequente na sequência.
    Os offsets são calculados em semitons relativos à nota base.
    O ciclo de 16 semitons é considerado — notas que diferem por múltiplos
    de 16 semitons são tratadas como o mesmo timbre em oitavas diferentes.
    """
    if not freqs or len(set(freqs)) < 2:
        return None

    if chip == "2A03":
        notes = [_nes_noise_note(f) or "?" for f in freqs]
    elif chip == "SN76489":
        notes = [_sn76489_noise_note(f, 3_579_545) or "?" for f in freqs]
    else:
        return None

    # Converte todas as notas para MIDI
    midis = [_note_to_midi_furnace(n) for n in notes]
    valid_midis = [m for m in midis if m is not None]
    if not valid_midis:
        return None

    # Nota base = a mais frequente
    from collections import Counter as C
    most_common_note = C(notes).most_common(1)[0][0]
    base_midi = _note_to_midi_furnace(most_common_note)
    if base_midi is None:
        return None

    # Calcula offsets relativos à nota base
    # Usa o ciclo de 16 semitons: se a diferença for > 8, ajusta para o ciclo mais próximo
    CYCLE = 16
    offsets = []
    for midi in midis:
        if midi is None:
            offsets.append(0)
            continue
        raw_diff = midi - base_midi
        # Normaliza para o intervalo [-CYCLE/2, CYCLE/2]
        normalized = ((raw_diff + CYCLE // 2) % CYCLE) - CYCLE // 2
        offsets.append(normalized)

    above = max((o for o in offsets if o > 0), default=0)
    below = abs(min((o for o in offsets if o < 0), default=0))

    return NoiseArpInfo(
        notes=notes,
        offsets=offsets,
        base_note=most_common_note,
        semitones_above=above,
        semitones_below=below,
    )


def _build_noise_arp(freqs: list[int], chip: str) -> list[str]:
    """Converte sequência de índices de período em sequência de notas."""
    if not freqs or len(set(freqs)) < 2:
        return []
    if chip == "2A03":
        return [_nes_noise_note(f) or "?" for f in freqs]
    elif chip == "SN76489":
        return [_sn76489_noise_note(f, 3_579_545) or "?" for f in freqs]
    return []


# ---------------------------------------------------------------------------
# Coleta de notas para canais de ruído
# ---------------------------------------------------------------------------

def _collect_noise_notes_sn76489(writes: list[RegisterWrite], clock: int) -> list[NoteUsage]:
    """Coleta notas do ruído SN76489 agrupadas por período."""
# Notas fixas do ruído simples/periódico do SN76489
# rate 0 → C- (qualquer oitava), rate 1 → C# (qualquer oitava), rate 2 → D-
SN_NOISE_RATE_NOTES = {0: "C-", 1: "C#", 2: "D-"}


def _collect_noise_notes_sn76489(writes: list[RegisterWrite], clock: int) -> list[NoteUsage]:
    """
    Coleta notas do ruído SN76489 diferenciando os 3 modos:
    - Ruído simples   (type_bit=0, rate=0,1,2): notas C-, C#, D- fixas → verde
    - Ruído completo  (type_bit=0, rate=3):     frequência do canal 2 → verde escuro
    - Ruído periódico (type_bit=1, rate=0,1,2): C-, C#, D- periódico → laranja
    - Ruído periódico completo (type_bit=1, rate=3): freq canal 2 periódico → laranja
    """
    counts: Counter = Counter()
    for w in writes:
        if w.chip != "SN76489":
            continue
        # Byte de frequência do canal de ruído: 1110_t_rr (bits7-5=111, bit4=0)
        if w.value & 0xF0 == 0xE0:
            type_bit = (w.value >> 2) & 1
            rate     = w.value & 0x03
            periodic = bool(type_bit)

            if rate == 3:
                # Frequência determinada pelo canal 2 — ruído completo
                mode = "complete_periodic" if periodic else "complete_simple"
                note = "~ch2"  # placeholder — nota vem do canal 2
            else:
                mode = "periodic" if periodic else "simple"
                note = SN_NOISE_RATE_NOTES[rate]

            counts[(rate, note, mode)] += 1

    if not counts:
        return []
    total = sum(counts.values())
    result = []
    for (period, note, mode), count in counts.most_common():
        result.append(NoteUsage(
            note=note,
            count=count,
            percent=round(count / total * 100, 1),
            period=period,
            metallic=False,
            noise_mode=mode,
        ))
    return result


def _collect_noise_notes_2a03(writes: list[RegisterWrite], clock: int) -> list[NoteUsage]:
    """
    Coleta notas do ruído 2A03 agrupadas por período e modo (normal/metálico).
    Bit 7 do reg 0x0E = 0 → ruído normal, = 1 → ruído metálico (timbre diferente).
    """
    counts: Counter = Counter()
    for w in writes:
        if w.chip == "2A03" and w.register == 0x0E:
            period   = w.value & 0x0F
            metallic = bool(w.value & 0x80)
            note     = _nes_noise_note(period)
            if note:
                counts[(period, note, metallic)] += 1
    if not counts:
        return []
    total = sum(counts.values())
    result = []
    for (period, note, metallic), count in counts.most_common():
        result.append(NoteUsage(
            note=note,
            count=count,
            percent=round(count / total * 100, 1),
            period=period,
            metallic=metallic,
        ))
    return result


def _note_counts_to_usage(counter: Counter) -> list[NoteUsage]:
    """Legado — mantido para compatibilidade."""
    if not counter:
        return []
    total = sum(counter.values())
    return [
        NoteUsage(note=n, count=c, percent=round(c / total * 100, 1))
        for n, c in counter.most_common()
    ]


# ---------------------------------------------------------------------------
# Helpers de extração de volume por chip
# ---------------------------------------------------------------------------

def _sn_vol_fn(ch: int):
    """Extrai volume do SN76489 para um canal (0-2=tom, 3=ruído)."""
    def fn(w: RegisterWrite) -> Optional[int]:
        if w.value & 0x90 == 0x90:
            if (w.value >> 5) & 0x03 == ch:
                return 15 - (w.value & 0x0F)
        return None
    return fn


def _freq_to_note_furnace(freq_hz: float) -> Optional[str]:
    """
    Converte frequência em Hz para nota no formato Furnace.
    Usa A4=440Hz como referência. C-0 = MIDI 24 no Furnace.
    """
    if freq_hz <= 0:
        return None
    try:
        midi     = 69 + 12 * math.log2(freq_hz / 440.0)
        midi_int = round(midi)
        if midi_int < 0 or midi_int > 127:
            return None
        octave   = midi_int // 12 - 2
        note_idx = midi_int % 12
        name     = NOTE_NAMES_FULL[note_idx]
        sep      = "-" if "#" not in name else ""
        return f"{name}{sep}{octave}"
    except (ValueError, ZeroDivisionError):
        return None


def _sn_freq_fn(ch: int, clock: int):
    """
    Extrai frequência do SN76489 para canal de tom.
    O SN76489 usa dois bytes para definir o período:
    - Byte latch: 1_cc_0_dddd (bit7=1, bits 5-4=canal, bit4=0, bits 3-0=nibble baixo)
    - Byte data:  0_0_dddddd  (bit7=0, bits 5-0=nibble alto)
    Período completo = (nibble_alto << 4) | nibble_baixo
    Frequência = clock / (32 * period)
    """
    _last_period_lo = [0]

    def fn(w: RegisterWrite) -> Optional[int]:
        val = w.value
        if val & 0x80:
            # Byte latch — verifica canal e bit de tipo (0=freq, 1=vol)
            if ((val >> 5) & 0x03) == ch and not (val & 0x10):
                _last_period_lo[0] = val & 0x0F
        else:
            # Byte de dados do período (nibble alto)
            period = ((val & 0x3F) << 4) | _last_period_lo[0]
            if period > 0:
                freq = clock / (32.0 * period)
                return round(freq)
        return None
    return fn


def _nes_vol_fn(reg: int):
    def fn(w: RegisterWrite) -> Optional[int]:
        if w.register == reg:
            return w.value & 0x0F
        return None
    return fn


def _nes_freq_fn(reg_lo: int, reg_hi: int, clock: int):
    """Extrai frequência do 2A03 para canais de pulso."""
    _last_lo = [0]
    def fn(w: RegisterWrite) -> Optional[int]:
        if w.register == reg_lo:
            _last_lo[0] = w.value & 0xFF
        elif w.register == reg_hi:
            period = ((w.value & 0x07) << 8) | _last_lo[0]
            if period > 0:
                freq = clock / (16.0 * (period + 1))
                return round(freq)
        return None
    return fn


def _ay_vol_fn(vol_reg: int):
    def fn(w: RegisterWrite) -> Optional[int]:
        if w.register == vol_reg:
            return w.value & 0x0F
        return None
    return fn


def _ay_freq_fn(ch_idx: int, clock: int):
    """Extrai frequência do AY-3-8910 para um canal."""
    reg_lo  = ch_idx * 2
    reg_hi  = ch_idx * 2 + 1
    _lo     = [0]
    def fn(w: RegisterWrite) -> Optional[int]:
        if w.register == reg_lo:
            _lo[0] = w.value & 0xFF
        elif w.register == reg_hi:
            period = ((w.value & 0x0F) << 8) | _lo[0]
            if period > 0:
                freq = clock / (16.0 * period)
                return round(freq)
        return None
    return fn


def _vrc6_vol_fn(ctrl_reg: int):
    """Extrai volume do VRC6 — reg de controle tem volume nos bits 3-0."""
    def fn(w: RegisterWrite) -> Optional[int]:
        if w.register == ctrl_reg:
            if w.value & 0x80:  # canal habilitado
                return w.value & 0x0F
            else:
                return 0
        return None
    return fn


def _vrc6_freq_fn(reg_lo: int, reg_hi: int, clock: int):
    """Extrai frequência dos canais de pulso do VRC6."""
    _lo = [0]
    def fn(w: RegisterWrite) -> Optional[int]:
        if w.register == reg_lo:
            _lo[0] = w.value & 0xFF
        elif w.register == reg_hi:
            period = ((w.value & 0x0F) << 8) | _lo[0]
            if period > 0:
                freq = clock / (16.0 * (period + 1))
                return round(freq)
        return None
    return fn


def _vrc6_saw_vol_fn():
    """
    Volume do canal saw do VRC6 — reg $B000 (reg 0x00).
    Bits 5-0 = acumulador (0-63). Normaliza para 0-15 para o MacroBar.
    """
    def fn(w: RegisterWrite) -> Optional[int]:
        if w.register == 0x00:
            raw_vol = w.value & 0x3F  # 6 bits = 0-63
            if w.value & 0x80:        # canal habilitado
                return round(raw_vol * 15 / 63)
            return 0
        return None
    return fn


def _collect_tone_notes(events: list[dict], chip: str) -> list[NoteUsage]:
    """
    Coleta as notas usadas num canal de tom a partir das frequências capturadas.
    Agrupa por nota (arredondada) e calcula frequência de uso.
    """
    from collections import Counter as C
    counts: C = C()
    for ev in events:
        for freq in ev.get("freqs", []):
            note = _freq_to_note_furnace(freq)
            if note:
                counts[note] += 1
    if not counts:
        return []
    total = sum(counts.values())
    return [
        NoteUsage(note=n, count=c, percent=round(c / total * 100, 1))
        for n, c in counts.most_common(8)  # top 8 notas
    ]


# ---------------------------------------------------------------------------
# Função principal de análise
# ---------------------------------------------------------------------------

def CHIP_CLOCKS_FALLBACK(chip: str) -> int:
    return {"SN76489": 3_579_545, "2A03": 1_789_773, "AY8910": 1_789_773}.get(chip, 1_000_000)


def _make_instrument(id_: str, channel: str, chip: str, is_noise: bool,
                     group: dict, idx: int, total: int,
                     noise_notes: list[NoteUsage],
                     duty: Optional[int] = None,
                     tone_notes: Optional[list[NoteUsage]] = None) -> Instrument:
    env            = group["env"]
    noise_arp      = group.get("noise_arp", [])
    noise_arp_info = group.get("noise_arp_info", None)
    notes          = noise_notes if is_noise else (tone_notes or [])
    return Instrument(
        id=id_,
        name=_inst_name(channel, env, idx, total),
        chip=chip,
        channel=channel,
        is_noise=is_noise,
        volume_macro=env.values,
        loop_point=env.loop_point,
        arp_macro=group["arp_macro"],
        pitch_macro=[0] * len(env.values),
        notes_used=notes,
        noise_arp=noise_arp,
        noise_arp_info=noise_arp_info,
        frame_start=group["frame_start"],
        occurrences=group["occurrences"],
        duty_cycle=duty,
        truncated=group.get("truncated", False),
    )


def _analyze_tone_channel(writes, chip_name: str, id_prefix: str,
                           ch_label: str, vol_fn, freq_fn,
                           duty: Optional[int] = None) -> list[Instrument]:
    """Helper reutilizável para analisar qualquer canal de tom PSG."""
    events = _split_into_note_events(writes, chip_name, vol_fn, freq_fn)
    if not events:
        return []
    tone_notes = _collect_tone_notes(events, chip_name)
    groups     = _group_events(events)
    result     = []
    for idx, grp in enumerate(groups):
        result.append(_make_instrument(
            f"{id_prefix}_{idx}", ch_label, chip_name, False,
            grp, idx, len(groups), [],
            duty=duty, tone_notes=tone_notes,
        ))
    return result


def analyze(vgm: VGMData, manual_range: Optional[tuple[int, int]] = None) -> list[Instrument]:
    """
    Analisa um VGMData e retorna lista de Instrument.
    Suporta: SN76489, YM2612(PSG), 2A03, AY8910, VRC6, Sunsoft 5B.
    """
    instruments = []
    writes = vgm.writes

    if manual_range:
        writes = [w for w in writes if manual_range[0] <= w.frame <= manual_range[1]]

    sn_clock  = vgm.header.sn76489_clock or CHIP_CLOCKS_FALLBACK("SN76489")
    nes_clock = vgm.header.nes_apu_clock or 1_789_773
    ay_clock  = vgm.header.ay8910_clock  or AY_CLOCK_DEFAULT
    vrc6_clock = getattr(vgm.header, 'vrc6_clock', 0) or 1_789_773

    # ── SN76489 (SMS, Game Gear, Mega Drive PSG) ─────────────────────────────
    # No Mega Drive o SN76489 coexiste com o YM2612 — processamos só o PSG
    if "SN76489" in vgm.chips:
        sn_writes = [w for w in writes if w.chip == "SN76489"]
        chip_label = "SN76489"

        for ch in range(3):
            ch_label = f"Square {ch+1}"
            instruments += _analyze_tone_channel(
                sn_writes, "SN76489", f"sn_sq{ch}",
                ch_label, _sn_vol_fn(ch), _sn_freq_fn(ch, sn_clock),
            )

        # Ruído SN76489
        noise_events = _split_into_note_events(
            sn_writes, "SN76489", _sn_vol_fn(3), _sn_noise_freq_fn()
        )
        noise_notes = _collect_noise_notes_sn76489(sn_writes, sn_clock)
        if noise_events:
            groups = _group_events(noise_events, chip="SN76489", is_noise=True)
            for idx, grp in enumerate(groups):
                instruments.append(_make_instrument(
                    f"sn_noise_{idx}", "Noise", "SN76489", True,
                    grp, idx, len(groups), noise_notes,
                ))

    # ── 2A03 (NES APU) ───────────────────────────────────────────────────────
    if "2A03" in vgm.chips:
        nes_writes = [w for w in writes if w.chip == "2A03"]

        for ch_key, vol_reg, freq_lo, freq_hi, label in [
            ("pulse1", 0x00, 0x02, 0x03, "Pulse A"),
            ("pulse2", 0x04, 0x06, 0x07, "Pulse B"),
        ]:
            # Coleta duty cycle — pode variar por instrumento, pega o mais frequente
            duty_counts: Counter = Counter()
            for w in nes_writes:
                if w.register == vol_reg:
                    duty_counts[(w.value >> 6) & 0x03] += 1
            duty = duty_counts.most_common(1)[0][0] if duty_counts else None

            freq_fn = _nes_freq_fn(freq_lo, freq_hi, nes_clock)
            events  = _split_into_note_events(nes_writes, "2A03", _nes_vol_fn(vol_reg), freq_fn)
            if not events:
                continue
            tone_notes = _collect_tone_notes(events, "2A03")
            groups     = _group_events(events)
            for idx, grp in enumerate(groups):
                # Duty cycle por instrumento: pega o do primeiro evento do grupo
                grp_duty = duty
                instruments.append(_make_instrument(
                    f"2a03_{ch_key}_{idx}", label, "2A03", False,
                    grp, idx, len(groups), [],
                    duty=grp_duty, tone_notes=tone_notes,
                ))

        # Triangle
        tri_events = _split_into_note_events(
            nes_writes, "2A03", _nes_vol_fn(0x08),
            _nes_freq_fn(0x0A, 0x0B, nes_clock),
        )
        if tri_events:
            tone_notes = _collect_tone_notes(tri_events, "2A03")
            groups = _group_events(tri_events)
            for idx, grp in enumerate(groups):
                instruments.append(_make_instrument(
                    f"2a03_tri_{idx}", "Triangle", "2A03", False,
                    grp, idx, len(groups), [], tone_notes=tone_notes,
                ))

        # Ruído 2A03
        noise_events = _split_into_note_events(
            nes_writes, "2A03", _nes_vol_fn(0x0C), _nes_noise_freq_fn()
        )
        noise_notes = _collect_noise_notes_2a03(nes_writes, nes_clock)
        if noise_events:
            groups = _group_events(noise_events, chip="2A03", is_noise=True)
            for idx, grp in enumerate(groups):
                instruments.append(_make_instrument(
                    f"2a03_noise_{idx}", "Noise", "2A03", True,
                    grp, idx, len(groups), noise_notes,
                ))

    # ── AY-3-8910 / YM2149 / Sunsoft 5B ─────────────────────────────────────
    # Registradores relevantes:
    # 0x00-0x01 = período tom A (lo/hi)
    # 0x02-0x03 = período tom B
    # 0x04-0x05 = período tom C
    # 0x06      = período noise (5 bits)
    # 0x07      = mixer (bits 0-2 = tone enable, bits 3-5 = noise enable, invertido)
    # 0x08-0x0A = volume canal A/B/C (bit 4 = usar envelope)
    # 0x0B-0x0C = período envelope (lo/hi)
    # 0x0D      = shape do envelope (4 bits: CONT ATT ALT HOLD)
    if "AY8910" in vgm.chips:
        ay_writes = [w for w in writes if w.chip == "AY8910"]

        # Detecta envelope de hardware global
        env_shape  = None
        env_period = None
        for w in ay_writes:
            if w.register == 0x0D:
                env_shape = w.value & 0x0F
            if w.register == 0x0B:
                env_period = (env_period or 0) & 0xFF00 | (w.value & 0xFF)
            if w.register == 0x0C:
                env_period = ((w.value & 0xFF) << 8) | ((env_period or 0) & 0xFF)

        # Detecta mixer e período de noise
        mixer_vals: Counter = Counter()
        noise_vals: Counter = Counter()
        for w in ay_writes:
            if w.register == 0x07:
                mixer_vals[w.value & 0x3F] += 1
            if w.register == 0x06:
                noise_vals[w.value & 0x1F] += 1
        mixer_mode   = mixer_vals.most_common(1)[0][0] if mixer_vals else None
        noise_period = noise_vals.most_common(1)[0][0] if noise_vals else None

        for ch_idx, ch_name in enumerate(["A", "B", "C"]):
            label   = f"Canal {ch_name}"
            vol_reg = 0x08 + ch_idx

            # Detecta se este canal usa envelope de hardware (bit 4 do vol reg)
            uses_env = any(
                w.register == vol_reg and bool(w.value & 0x10)
                for w in ay_writes
            )
            ay_env = None
            if uses_env and env_shape is not None:
                ay_env = AYEnvelope(
                    shape=env_shape,
                    period=env_period or 0,
                    active=True,
                )

            # Detecta mix tom+noise para este canal
            ch_mix = None
            if mixer_mode is not None:
                tone_en  = not bool((mixer_mode >> ch_idx) & 1)
                noise_en = not bool((mixer_mode >> (ch_idx + 3)) & 1)
                ch_mix   = (1 if tone_en else 0) | (2 if noise_en else 0)

            insts_ch = _analyze_tone_channel(
                ay_writes, "AY8910", f"ay_{ch_name.lower()}",
                label, _ay_vol_fn(vol_reg), _ay_freq_fn(ch_idx, ay_clock),
            )
            # Aplica envelope e mix em todos os instrumentos do canal
            for inst in insts_ch:
                inst.ay_envelope     = ay_env
                inst.ay_noise_period = noise_period
                inst.ay_tone_noise_mix = ch_mix
            instruments += insts_ch

    # ── VRC6 ─────────────────────────────────────────────────────────────────
    if "VRC6" in vgm.chips:
        # VRC6 Pulse 1: ctrl=$9000, freq_lo=$9001, freq_hi=$9002
        # VRC6 Pulse 2: ctrl=$A000, freq_lo=$A001, freq_hi=$A002
        # VRC6 Saw:     ctrl=$B000, freq_lo=$B001, freq_hi=$B002
        for chip_sub, id_pre, label, ctrl, freq_lo, freq_hi in [
            ("VRC6_P1", "vrc6_p1", "VRC6 Pulse 1", 0x00, 0x01, 0x02),
            ("VRC6_P2", "vrc6_p2", "VRC6 Pulse 2", 0x00, 0x01, 0x02),
        ]:
            sub_writes = [w for w in writes if w.chip == chip_sub]
            if not sub_writes:
                continue
            # Duty cycle do VRC6: bits 6-4 do registrador de controle (3 bits = 8 valores)
            duty_counts: Counter = Counter()
            for w in sub_writes:
                if w.register == ctrl:
                    duty_counts[(w.value >> 4) & 0x07] += 1
            duty = duty_counts.most_common(1)[0][0] if duty_counts else None

            instruments += _analyze_tone_channel(
                sub_writes, chip_sub, id_pre, label,
                _vrc6_vol_fn(ctrl),
                _vrc6_freq_fn(freq_lo, freq_hi, vrc6_clock),
                duty=duty,
            )

        # VRC6 Sawtooth
        saw_writes = [w for w in writes if w.chip == "VRC6_SAW"]
        if saw_writes:
            instruments += _analyze_tone_channel(
                saw_writes, "VRC6_SAW", "vrc6_saw", "VRC6 Saw",
                _vrc6_saw_vol_fn(),
                _vrc6_freq_fn(0x01, 0x02, vrc6_clock),
            )

    return instruments