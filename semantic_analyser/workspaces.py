"""Temporary cookie-owned SQLite workspaces; one manager per server process."""

import logging
import hashlib
import re
import secrets
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from fastapi import HTTPException
from itsdangerous import BadSignature, URLSafeSerializer

from .collections import CollectionService
from .engine import AnalysisEngine
from .storage import Store

LOG = logging.getLogger(__name__)
COOKIE = "semantic_visitor"
ID_PATTERN = re.compile(r"[a-f0-9]{64}\Z")


@dataclass
class Workspace:
    store: Store
    engine: AnalysisEngine
    lock: threading.RLock = field(default_factory=threading.RLock)
    identifier: str | None = None
    created: float = 0
    touched: float = 0
    active: int = 0

    def __post_init__(self):
        self.collections = CollectionService(self.store, self.engine, self.lock)

    @contextmanager
    def locked(self, seconds):
        if not self.lock.acquire(timeout=seconds):
            raise HTTPException(423, "This workspace is busy. Try again shortly.", headers={"Retry-After": "1"})
        try:
            yield self
        finally:
            self.lock.release()


class WorkspaceManager:
    def __init__(self, settings, shared_engine, clock=time.time):
        self.settings, self.shared_engine, self.clock = settings, shared_engine, clock
        configured = settings.visitor_root or settings.database_path.parent / "visitors"
        if configured.is_symlink():
            raise ValueError("Visitor workspace root must not be a symlink.")
        self.root = configured.resolve()
        self.signer = URLSafeSerializer(settings.secret, salt="semantic-visitor-v1", signer_kwargs={"digest_method": hashlib.sha256})
        self.entries = {}
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.file_lock = None
        self.thread = None

    def start(self):
        self.root.mkdir(parents=True, exist_ok=True)
        lock_path = self.root / ".owner.lock"
        if lock_path.is_symlink():
            raise ValueError("Workspace process lock must not be a symlink.")
        self.file_lock = lock_path.open("a+b")
        try:
            if __import__("os").name == "nt":
                import msvcrt
                self.file_lock.write(b"0")
                self.file_lock.flush()
                self.file_lock.seek(0)
                msvcrt.locking(self.file_lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.file_lock.close()
            self.file_lock = None
            raise RuntimeError("Visitor workspace root is already owned by another process.") from error
        for directory in self.root.iterdir():
            if ID_PATTERN.fullmatch(directory.name) and directory.is_dir() and not directory.is_symlink():
                path = directory / "workspace.sqlite3"
                if path.is_file() and not path.is_symlink():
                    store = Store(path)
                    with store.connect() as db:
                        meta = dict(db.execute("SELECT key,value FROM metadata"))
                    if "created_at" in meta and "last_used_at" in meta:
                        self.entries[directory.name] = self._entry(store, directory.name, float(meta["created_at"]), float(meta["last_used_at"]))
        self.cleanup()
        self.thread = threading.Thread(target=self._sweep, daemon=True, name="workspace-cleanup")
        self.thread.start()

    def _entry(self, store, identifier, created, touched):
        engine = AnalysisEngine(self.shared_engine.revision, model_factory=self.shared_engine.load)
        return Workspace(store, engine, identifier=identifier, created=created, touched=touched)

    def _expired(self, entry):
        now = self.clock()
        return now - entry.touched >= self.settings.workspace_idle_seconds or now - entry.created >= self.settings.workspace_lifetime_seconds

    def _touch(self, entry):
        entry.touched = self.clock()
        with entry.store.connect() as db:
            db.execute("UPDATE metadata SET value=? WHERE key='last_used_at'", (str(entry.touched),))

    def acquire(self, token=None, create=False):
        with self.lock:
            if token:
                try:
                    identifier = self.signer.loads(token)["id"]
                    if not isinstance(identifier, str) or not ID_PATTERN.fullmatch(identifier):
                        raise ValueError("Invalid ID")
                except (BadSignature, KeyError, TypeError, ValueError) as error:
                    raise HTTPException(401, "Invalid visitor session. Reload to start again.") from error
                entry = self.entries.get(identifier)
                if entry is None or self._expired(entry):
                    raise HTTPException(410, "Temporary workspace expired. Reload to start a new one.")
            elif create:
                self.cleanup()
                if len(self.entries) >= self.settings.max_workspaces:
                    raise HTTPException(503, "Temporary workspace capacity is full. Try again later.", headers={"Retry-After": "60"})
                identifier = secrets.token_hex(32)
                directory = self.root / identifier
                directory.mkdir()
                store = Store(directory / "workspace.sqlite3")
                now = self.clock()
                with store.connect() as db:
                    db.executemany("INSERT INTO metadata VALUES (?,?)", [("created_at", str(now)), ("last_used_at", str(now))])
                entry = self._entry(store, identifier, now, now)
                self.entries[identifier] = entry
                token = self.signer.dumps({"id": identifier})
            else:
                raise HTTPException(401, "Start a visitor session before accessing a workspace.")
            self._touch(entry)
            entry.active += 1
            return entry, token

    def pin(self, entry):
        with self.lock:
            entry.active += 1

    def release(self, entry):
        with self.lock:
            entry.active -= 1
            # An expired absolute lifetime is never extended by an active job.
            if entry.identifier in self.entries and not self._expired(entry):
                self._touch(entry)
            cached = sorted((e for e in self.entries.values() if e.engine.cache_key), key=lambda e: e.touched)
            excess = max(0, len(cached) - self.settings.max_cached_indexes)
            for candidate in (e for e in cached if e.active == 0):
                if excess <= 0:
                    break
                candidate.engine.clear_index()
                excess -= 1

    def _remove(self, entry):
        directory = entry.store.path.parent
        if self.root.is_symlink() or directory.is_symlink() or directory.parent.resolve() != self.root:
            raise RuntimeError("Refusing unsafe workspace cleanup path.")
        allowed = {"workspace.sqlite3", "workspace.sqlite3-wal", "workspace.sqlite3-shm"}
        children = list(directory.iterdir())
        if any(p.name not in allowed or p.is_symlink() or not p.is_file() for p in children):
            raise RuntimeError("Refusing cleanup of unexpected workspace contents.")
        for child in children:
            child.unlink()
        directory.rmdir()
        del self.entries[entry.identifier]

    def delete(self, entry):
        with self.lock:
            # The deleting HTTP request owns one lease; jobs/other requests forbid deletion.
            if entry.active != 1:
                raise HTTPException(423, "Workspace has work in progress; try deletion again later.")
            self._remove(entry)

    def revoke(self, token):
        try:
            entry, _ = self.acquire(token)
        except HTTPException:
            return
        try:
            with self.lock:
                with entry.store.connect() as db:
                    db.execute("UPDATE metadata SET value='0' WHERE key='created_at'")
                entry.created = 0
        finally:
            self.release(entry)
        self.cleanup()

    def cleanup(self):
        with self.lock:
            for entry in list(self.entries.values()):
                if entry.active == 0 and self._expired(entry):
                    try:
                        self._remove(entry)
                    except (OSError, RuntimeError):
                        LOG.exception("Temporary workspace cleanup failed")

    def _sweep(self):
        while not self.stop_event.wait(self.settings.cleanup_interval_seconds):
            self.cleanup()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        if self.file_lock:
            if __import__("os").name == "nt":
                import msvcrt
                self.file_lock.seek(0)
                msvcrt.locking(self.file_lock.fileno(), msvcrt.LK_UNLCK, 1)
            self.file_lock.close()
            self.file_lock = None
