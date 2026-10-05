# Reads configuration from environment variables (and a local .env file, never committed).
# Swapping mock files for real ones is a config change only; see plan section 6.3.
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root (or /app inside Docker). Relative paths in settings resolve against it.
ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    registry_path: str = "contracts/mocks/registry.json"  # later: models/registry.json
    metrics_path: str = "contracts/mocks/metrics.json"  # later: results/metrics.json
    scoring_module: str = "contracts.scoring"  # later: src.eval.scoring
    dev_model_override: str = ""  # one GGUF used for every blend_id; empty in production
    fake_generator: bool = False  # stream a fixed sentence instead of running a model
    models_dir: str = "./local_models"
    max_loaded_models: int = 2
    web_dir: str = "web/dist"  # the built frontend (npm run build in web/)
    ping_interval_s: float = 20.0  # server -> client ping period
    pong_timeout_s: float = 60.0  # close the socket after this long with no client traffic

    do_spaces_key: str = ""
    do_spaces_secret: str = ""
    do_spaces_region: str = "blr1"
    do_spaces_bucket: str = "blendlab-models"

    def resolve(self, path: str) -> Path:
        """Turn a possibly-relative setting into an absolute path."""
        p = Path(path)
        return p if p.is_absolute() else ROOT / p
