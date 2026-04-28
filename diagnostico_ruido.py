import gzip
import struct

path = r'C:\Users\USUÁRIO\teste.vgm'

with open(path, 'rb') as f:
    raw = f.read()

if raw[:2] == b'\x1f\x8b':
    raw = gzip.decompress(raw)

ver = struct.unpack_from('<I', raw, 0x08)[0]
raw_off = struct.unpack_from('<I', raw, 0x34)[0]
data_off = (0x34 + raw_off) if raw_off else 0x40

# Extrai todos os writes do canal de ruído (reg 0x0C = vol, 0x0E = período)
pos = data_off
frame = 0
noise_events = []

while pos < len(raw):
    cmd = raw[pos]; pos += 1
    if cmd == 0x66: break
    elif cmd == 0x61: frame += struct.unpack_from('<H', raw, pos)[0]; pos += 2
    elif cmd == 0x62: frame += 735
    elif cmd == 0x63: frame += 882
    elif 0x70 <= cmd <= 0x7F: frame += (cmd & 0x0F) + 1
    elif cmd in (0xB4, 0xB5):
        reg = raw[pos]; val = raw[pos+1]; pos += 2
        if reg in (0x0C, 0x0E):
            noise_events.append((frame, reg, val))
    elif cmd == 0x67:
        pos += 2
        blk_size = struct.unpack_from('<I', raw, pos)[0]; pos += 4
        pos += blk_size
    elif cmd == 0x68:
        pos += 2
        blk_size = struct.unpack_from('<I', raw, pos)[0] & 0xFFFFFF; pos += 3
        pos += blk_size
    elif cmd == 0x50: pos += 1
    elif cmd == 0xE0: pos += 4
    else: pos += 1

print(f'Total de writes de ruído: {len(noise_events)}')
print()
print('Primeiros 60 eventos (frame, reg, valor):')
for frame, reg, val in noise_events[:60]:
    reg_name = 'VOL ' if reg == 0x0C else 'FREQ'
    vol = val & 0x0F if reg == 0x0C else None
    period = val & 0x0F if reg == 0x0E else None
    extra = f'vol={vol}' if vol is not None else f'period=0x{period:02X}'
    print(f'  frame={frame:6d} {reg_name} {extra}')