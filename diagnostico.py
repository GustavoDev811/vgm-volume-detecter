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

print('versao:', hex(ver))
print('data_offset:', hex(data_off))
print('tamanho total:', len(raw), 'bytes')
print()

pos = data_off
opcodes_encontrados = {}
b4_count = 0

while pos < len(raw):
    cmd = raw[pos]; pos += 1

    if cmd == 0x66:
        print('fim de dados em pos:', hex(pos-1))
        break
    elif cmd == 0x67:
        pos += 1                  # byte 0x66 fixo
        blk_type = raw[pos]; pos += 1
        blk_size = struct.unpack_from('<I', raw, pos)[0]; pos += 4
        print(f'data block: tipo={hex(blk_type)} tamanho={blk_size} bytes — pulando...')
        pos += blk_size
        print(f'  continuando em pos={hex(pos)}')
        print(f'  próximos bytes: {" ".join(hex(b) for b in raw[pos:pos+16])}')
    elif cmd == 0x61:
        pos += 2
    elif cmd in (0x62, 0x63):
        pass
    elif 0x70 <= cmd <= 0x7F:
        pass
    elif cmd == 0x50:
        pos += 1
    elif cmd == 0xB4:
        reg = raw[pos]; val = raw[pos+1]; pos += 2
        b4_count += 1
        if b4_count <= 5:
            print(f'0xB4: reg={hex(reg)} val={hex(val)}')
    elif cmd == 0xB5:
        pos += 2
    elif cmd == 0xE0:
        pos += 4
    else:
        opcodes_encontrados[hex(cmd)] = opcodes_encontrados.get(hex(cmd), 0) + 1
        pos += 1

print(f'\ntotal 0xB4 encontrados: {b4_count}')
if opcodes_encontrados:
    print('outros opcodes não mapeados:', opcodes_encontrados)