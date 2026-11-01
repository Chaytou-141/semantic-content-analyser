"""Read-only, bounded readiness from the privileged namespace policy owner.

This is an operational interlock, not the firewall. The app's read-only mount and
UID/capability separation protect the status file; kernel rules enforce networking.
"""
import json
import math
import os
from pathlib import Path
import stat
import time


def policy_status(path, now=None):
    try:
        flags=os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_CLOEXEC',0) | getattr(os,'O_NONBLOCK',0)
        if not stat.S_ISREG(Path(path).lstat().st_mode):return None
        with os.fdopen(os.open(path,flags), 'rb') as handle:
            metadata=os.fstat(handle.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=0 or metadata.st_mode & 0o022:return None
            raw=handle.read(4097)
        if len(raw)>4096:return None
        value=json.loads(raw)
        if type(value.get('version')) is not int or type(value.get('monotonic')) not in {int,float}:return None
        if value.get('netns')!=os.readlink('/proc/self/ns/net'):return None
        age=(time.monotonic() if now is None else now)-value['monotonic']
        if value.get('version')!=1 or value.get('policy_ready') is not True or not math.isfinite(age) or not 0<=age<=5:return None
        return value
    except (OSError,ValueError,TypeError,KeyError,AttributeError):return None


def app_ready(path, require_model=True):
    value=policy_status(path)
    return bool(value and value.get('app_healthy') is True and
                (not require_model or value.get('model_loaded') is True))


if __name__=='__main__':
    raise SystemExit(0 if app_ready(os.environ['EGRESS_STATE_PATH'],
                                  os.getenv('PRELOAD_MODEL','false').lower()=='true') else 1)
