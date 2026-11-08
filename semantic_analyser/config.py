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
    website_fetch_enabled: bool = os.getenv("ENABLE_WEBSITE_FETCH", "false").lower() == "true"
    egress_policy_required: bool = os.getenv("EGRESS_POLICY_REQUIRED", "false").lower() == "true"
    egress_state_path: Path = Path(os.getenv("EGRESS_STATE_PATH", "/run/egress/status.json"))
    fetch_deny_cidrs: tuple = tuple(part.strip() for part in os.getenv("FETCH_DENY_CIDRS", "").split(",") if part.strip())
    fetch_allowed_hosts: tuple = tuple(p.strip().lower() for p in os.getenv("FETCH_ALLOWED_HOSTS", "").split(",") if p.strip())
    trusted_proxy_cidrs: tuple = tuple(p.strip() for p in os.getenv("TRUSTED_PROXY_CIDRS", "").split(",") if p.strip())
    demo_limits_enabled: bool = os.getenv("DEMO_LIMITS_ENABLED", "false").lower() == "true"
    demo_http_concurrency: int = int(os.getenv("DEMO_HTTP_CONCURRENCY", "16"))
    demo_rate_keys: int = int(os.getenv("DEMO_RATE_KEYS", "2048"))
    demo_requests_per_minute: int = int(os.getenv("DEMO_REQUESTS_PER_MINUTE", "240"))
    demo_global_requests_per_minute: int = int(os.getenv("DEMO_GLOBAL_REQUESTS_PER_MINUTE", "1200"))
    demo_sessions_per_hour: int = int(os.getenv("DEMO_SESSIONS_PER_HOUR", "4"))
    demo_global_sessions_per_hour: int = int(os.getenv("DEMO_GLOBAL_SESSIONS_PER_HOUR", "32"))
    demo_outbound_per_hour: int = int(os.getenv("DEMO_OUTBOUND_PER_HOUR", "120"))
    demo_global_outbound_per_hour: int = int(os.getenv("DEMO_GLOBAL_OUTBOUND_PER_HOUR", "600"))
    workspace_storage_bytes: int = int(os.getenv("WORKSPACE_STORAGE_BYTES", str(16*1024*1024)))
    visitor_storage_bytes: int = int(os.getenv("VISITOR_STORAGE_BYTES", str(128*1024*1024)))
    storage_min_free_bytes: int = int(os.getenv("STORAGE_MIN_FREE_BYTES", str(128*1024*1024)))

    def validate(self):
        import ipaddress
        import math
        from .fetch_policy import normalize_url
        if self.production and self.website_fetch_enabled and not self.egress_policy_required:
            raise ValueError('Production website imports require the enforced egress policy.')
        if self.production and self.egress_policy_required and __import__('sys').platform!='linux':
            raise ValueError('Production egress enforcement requires the verified Linux container stack.')
        if self.egress_policy_required and not self.egress_state_path.is_absolute():
            raise ValueError('Egress readiness needs an absolute local file path.')
        for value in self.trusted_proxy_cidrs + self.fetch_deny_cidrs:
            network = ipaddress.ip_network(value, strict=False)
            if value in self.trusted_proxy_cidrs and network.prefixlen != network.max_prefixlen:
                raise ValueError("Proxy trust must name exact /32 or /128 peers, not networks.")
        for host in self.fetch_allowed_hosts:
            target = normalize_url('https://' + host)
            if target.host != host or target.path != '/' or target.query:
                raise ValueError("Allowed fetch hosts must be exact normalised hostnames.")
        limits = [self.demo_http_concurrency, self.demo_rate_keys, self.demo_requests_per_minute,
                  self.demo_global_requests_per_minute, self.demo_sessions_per_hour,
                  self.demo_global_sessions_per_hour, self.demo_outbound_per_hour,
                  self.demo_global_outbound_per_hour, self.workspace_storage_bytes,
                  self.visitor_storage_bytes, self.storage_min_free_bytes]
        if any(not math.isfinite(v) or v <= 0 for v in limits) or self.workspace_storage_bytes < 65536:
            raise ValueError("Demo limits must be positive; SQLite storage needs at least 64 KiB.")
        if self.workspace_mode not in {"local", "visitor"}:
            raise ValueError("WORKSPACE_MODE must be local or visitor.")
        if self.workspace_mode == "visitor" and len(self.secret) < 32:
            raise ValueError("Visitor mode requires SECRET_KEY (32+ characters) for stable ownership cookies.")
        if self.production and (len(self.secret) < 32 or
                                (self.workspace_mode == "local" and len(self.password) < 12) or
                                (self.password and len(self.password) < 12)):
            raise ValueError("Production requires APP_PASSWORD (12+ characters) and SECRET_KEY (32+ characters).")
        if any(not math.isfinite(value) or value <= 0 for value in [self.workspace_idle_seconds, self.workspace_lifetime_seconds,
                                        self.cleanup_interval_seconds, self.max_workspaces, self.max_cached_indexes,
                                        self.analysis_timeout_seconds, self.workspace_lock_seconds]) or self.analysis_queue_size < 0:
            raise ValueError("Workspace/execution limits must be positive; queue size may be zero.")
