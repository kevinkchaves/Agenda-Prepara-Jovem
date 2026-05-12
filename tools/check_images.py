from pathlib import Path
import base64
IMAGES_DIR = Path(__file__).parent.parent / 'images'
for p in IMAGES_DIR.iterdir():
    if p.is_file():
        try:
            data = p.read_bytes()
            b64len = len(base64.b64encode(data))
            print(p.name, 'OK', p.stat().st_size, 'bytes, b64len=', b64len)
        except Exception as e:
            print(p.name, 'ERROR', e)
