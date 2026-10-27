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

    def validate(self):
        if self.production and (len(self.password) < 12 or len(self.secret) < 32):
            raise ValueError("Production requires APP_PASSWORD (12+ characters) and SECRET_KEY (32+ characters).")
