import os, json, logging, sys
logging.disable(logging.CRITICAL)
with open('.env') as f:
    for line in f:
        line = line.strip()
        if line and '=' in line and not line.startswith('#'):
            k,_,v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip().strip('"'))
from app import create_app
app = create_app()
routes = sorted([r.rule for r in app.url_map.iter_rules() if 'prospeccion' in r.rule and 'api' in r.rule])
print('\n'.join(routes))
print('OK')
sys.exit(0)
