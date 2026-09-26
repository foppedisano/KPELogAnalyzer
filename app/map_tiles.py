"""Optional OSM background. Only viewport tiles requested by an explicit UI toggle."""
import json
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from .db import path

LOCK = threading.Lock()


def tile(z, x, y, referer):
    z,x,y=int(z),int(x),int(y)
    if not 0<=z<=18 or not 0<=x<2**z or not 0<=y<2**z:
        raise ValueError('Tile non valida')
    folder=path().parent/'map-cache'
    folder.mkdir(exist_ok=True)
    name=f'{z}-{x}-{y}'
    image=folder/(name+'.png');meta=folder/(name+'.json')
    with LOCK:
        cached=json.loads(meta.read_text()) if meta.exists() else {}
        if image.exists() and cached.get('expires',0)>time.time():return image.read_bytes()
        headers={'User-Agent':'KPELogAnalyzer/1.0 (+https://github.com/foppedisano/KPELogAnalyzer)', 'Referer':referer}
        if cached.get('etag'):headers['If-None-Match']=cached['etag']
        if cached.get('modified'):headers['If-Modified-Since']=cached['modified']
        try:
            with urlopen(Request(f'https://tile.openstreetmap.org/{z}/{x}/{y}.png',headers=headers),timeout=8) as response:
                data=response.read(1024*1024+1)
                if len(data)>1024*1024 or not data.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('Risposta cartografica non valida')
                tmp=folder/(name+'.tmp');tmp.write_bytes(data);tmp.replace(image)
                cached=dict(etag=response.headers.get('ETag'),modified=response.headers.get('Last-Modified'))
        except HTTPError as error:
            if error.code!=304 or not image.exists():raise ValueError('Cartografia online temporaneamente non disponibile') from error
        except (URLError, TimeoutError) as error:
            raise ValueError('Cartografia online temporaneamente non disponibile') from error
        cached['expires']=time.time()+7*86400
        meta.write_text(json.dumps(cached))
        return image.read_bytes()
