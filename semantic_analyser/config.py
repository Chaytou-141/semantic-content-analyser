import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


@dataclass
class Settings:
    database_path: Path = Path(os.getenv("DATABASE_PATH", str(ROOT / "runtime/workspace.sqlite3")))
    password: str = os.getenv("APP_PASSWORD", "")
    secret: str = os.getenv("SECRET_KEY", "")
    production: bool = os.getenv("APP_ENV", "development") == "production"
    model_revision: str = os.getenv("MODEL_REVISION", MODEL_REVISION)
    preload_model: bool = os.getenv("PRELOAD_MODEL", "false").lower() == "true"
    workspace_mode: str = os.getenv("WORKSPACE_MODE", "local")
    visitor_root: Path | None = Path(os.environ["VISITOR_WORKSPACE_ROOT"]) if os.getenv("VISITOR_WORKSPACE_ROOT") else None
    workspace_idle_seconds: float = float(os.getenv("WORKSPACE_IDLE_SECONDS", "3600"))
    workspace_lifetime_seconds: float = float(os.getenv("WORKSPACE_LIFETIME_SECONDS", "86400"))
    cleanup_interval_seconds: float = float(os.getenv("WORKSPACE_CLEANUP_SECONDS", "60"))
    max_workspaces: int = int(os.getenv("MAX_VISITOR_WORKSPACES", "32"))
    max_cached_indexes: int = int(os.getenv("MAX_CACHED_INDEXES", "4"))
    analysis_queue_size: int = int(os.getenv("ANALYSIS_QUEUE_SIZE", "2"))
    analysis_timeout_seconds: float = float(os.getenv("ANALYSIS_TIMEOUT_SECONDS", "60"))
    workspace_lock_seconds: float = float(os.getenv("WORKSPACE_LOCK_SECONDS", "1"))

    def validate(self):
        if self.workspace_mode not in {"local", "visitor"}:
            raise ValueError("WORKSPACE_MODE must be local or visitor.")
        if self.workspace_mode == "visitor" and len(self.secret) < 32:
            raise ValueError("Visitor mode requires SECRET_KEY (32+ characters) for stable ownership cookies.")
        if self.production and (len(self.secret) < 32 or
                                (self.workspace_mode == "local" and len(self.password) < 12) or
                                (self.password and len(self.password) < 12)):
            raise ValueError("Production requires APP_PASSWORD (12+ characters) and SECRET_KEY (32+ characters).")
        if any(value <= 0 for value in [self.workspace_idle_seconds, self.workspace_lifetime_seconds,
                                        self.cleanup_interval_seconds, self.max_workspaces, self.max_cached_indexes,
                                        self.analysis_timeout_seconds, self.workspace_lock_seconds]) or self.analysis_queue_size < 0:
            raise ValueError("Workspace/execution limits must be positive; queue size may be zero.")
