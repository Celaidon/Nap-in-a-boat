# FastAPI app: REST endpoints (contract 4.3), startup validation, static frontend.
import importlib
import json
import logging
from contextlib import asynccontextmanager

import jsonschema
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.server.generate import fake_session, fake_stream
from src.server.models import ModelManager
from src.server.settings import ROOT, Settings
from src.server.simulate import ApiSimulator
from src.server.ws import router as ws_router

SCHEMA_DIR = ROOT / "contracts" / "schemas"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")


class ConfigError(RuntimeError):
    """Raised at startup when a data file is missing or breaks its contract schema."""


def load_checked(path, schema_name: str, label: str) -> dict:
    """Load a JSON file and validate it against a contract schema, or fail loudly."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"{label} file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{label} file {path} is not valid JSON: {exc}") from None

    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        where = "/".join(str(p) for p in exc.absolute_path) or "(top level)"
        raise ConfigError(
            f"{label} file {path} does not match {schema_name}: {exc.message} (at {where})"
        ) from None
    return data


def load_scoring(module_name: str):
    """Import SCORING_MODULE and return its score_tasks, or fail loudly at startup."""
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ConfigError(f"SCORING_MODULE '{module_name}' cannot be imported: {exc}") from None
    score_tasks = getattr(module, "score_tasks", None)
    if not callable(score_tasks):
        raise ConfigError(f"SCORING_MODULE '{module_name}' has no score_tasks function")
    return score_tasks


def create_app(settings: Settings | None = None, stream=None) -> FastAPI:
    """`stream` replaces the token source (tests inject one); otherwise it follows the settings."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Refuse to start if either file is invalid, with a readable message.
        app.state.registry = load_checked(
            settings.resolve(settings.registry_path), "registry.schema.json", "Registry"
        )
        app.state.metrics = load_checked(
            settings.resolve(settings.metrics_path), "metrics.schema.json", "Metrics"
        )
        # Real tokens come from the ModelManager unless FAKE_GENERATOR is on (frontend/dev work).
        app.state.manager = ModelManager(app.state.registry, settings)
        app.state.stream = stream or (fake_stream if settings.fake_generator else app.state.manager.stream)
        app.state.session = fake_session if settings.fake_generator else app.state.manager.session
        app.state.simulated = None
        if settings.sim_provider:  # hosted-API demo mode: always reported to the UI as simulated
            sim = ApiSimulator(settings, app.state.registry)
            app.state.simulated = {"provider": settings.sim_provider, "writing_model": sim.writing_model, "code_model": sim.code_model}
            app.state.stream, app.state.session = stream or sim.stream, sim.session
        app.state.score_tasks = load_scoring(settings.scoring_module)  # used by the Best Blend Finder
        yield

    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="BlendLab", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.finder_running = False  # only one Best Blend Finder run at a time
    app.include_router(ws_router)

    @app.get("/health")
    async def health() -> dict:
        manager = getattr(app.state, "manager", None)
        return {"status": "ok", "loaded": manager.loaded if manager else [], "simulated": app.state.simulated}

    @app.get("/api/registry")
    async def registry() -> dict:
        return app.state.registry

    @app.get("/api/metrics")
    async def metrics() -> dict:
        return app.state.metrics

    # The built frontend. Mounted last so it never shadows the routes above, and skipped when it has not been built.
    web_dir = settings.resolve(settings.web_dir)
    if (web_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

    return app


app = create_app()
