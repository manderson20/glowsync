import os, re, tempfile, shutil

ENV_PATH = os.path.expanduser('~/glowsync/.env')

def set_env_vars(updates: dict):
    """Idempotently set key=value in .env, preserving other lines."""
    os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)
    if not os.path.exists(ENV_PATH):
        open(ENV_PATH,'a').close()

    with open(ENV_PATH,'r',encoding='utf-8') as f:
        lines = f.readlines()

    kv = {k:str(v) for k,v in updates.items() if v is not None}
    keys = set(kv.keys())
    out = []
    seen = set()

    for line in lines:
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$', line.strip())
        if m:
            k = m.group(1)
            if k in kv:
                out.append(f"{k}={kv[k]}\n")
                seen.add(k)
            else:
                out.append(line)
        else:
            out.append(line)

    for k in keys - seen:
        out.append(f"{k}={kv[k]}\n")

    tmp = tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8')
    tmp.writelines(out); tmp.close()
    shutil.move(tmp.name, ENV_PATH)
    return True
