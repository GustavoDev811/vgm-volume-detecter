import glob

for f in glob.glob('**/*.py', recursive=True):
    c = open(f, encoding='utf-8').read()
    if 'vgm2dmf' in c:
        new = c \
            .replace('from vgm2dmf', 'from vgmvolumedetector') \
            .replace('import vgm2dmf', 'import vgmvolumedetector') \
            .replace('.vgm2dmf', '.vgmvolumedetector')
        open(f, 'w', encoding='utf-8').write(new)
        print('OK: ' + f)

print('Pronto!')