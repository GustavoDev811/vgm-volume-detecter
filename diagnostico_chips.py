import gzip, struct

path = r'C:\Users\USUÁRIO\teste.vgm'

with open(path, 'rb') as f: raw = f.read()
if raw[:2] == b'\x1f\x8b': raw = gzip.decompress(raw)

ver       = struct.unpack_from('<I', raw, 0x08)[0]
sn_clock  = struct.unpack_from('<I', raw, 0x0C)[0]
ym_clock  = struct.unpack_from('<I', raw, 0x10)[0]
raw_off   = struct.unpack_from('<I', raw, 0x34)[0] if len(raw) > 0x38 else 0
data_off  = (0x34 + raw_off) if raw_off else 0x40

print(f'versao:    {hex(ver)}')
print(f'sn_clock:  {sn_clock} ({hex(sn_clock)})')
print(f'ym_clock:  {ym_clock} ({hex(ym_clock)})')
print(f'data_off:  {hex(data_off)}')
print()

# Conta opcodes relevantes nos primeiros 2000 bytes de dados
pos = data_off
counts = {}
b4_count = x50_count = x52_count = 0
while pos < min(data_off + 2000, len(raw)):
    cmd = raw[pos]; pos += 1
    if cmd == 0x66: break
    elif cmd == 0x50: x50_count += 1; pos += 1
    elif cmd == 0x52: x52_count += 1; pos += 2
    elif cmd in (0xB4, 0xB5): b4_count += 1; pos += 2
    elif cmd == 0x61: pos += 2
    elif cmd in (0x62, 0x63): pass
    elif 0x70 <= cmd <= 0x7F: pass
    elif cmd == 0x67:
        pos += 2
        sz = struct.unpack_from('<I', raw, pos)[0]; pos += 4; pos += sz
    elif cmd == 0x68:
        pos += 2
        sz = struct.unpack_from('<I', raw, pos)[0] & 0xFFFFFF; pos += 3; pos += sz
    else: pos += 1

print(f'0x50 (SN76489): {x50_count}x')
print(f'0x52 (YM2612):  {x52_count}x')
print(f'0xB4 (2A03):    {b4_count}x')