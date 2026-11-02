import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field


def find_project_root() -> Path:
    """Find the root directory of the pixel-corp repository."""
    current = Path(__file__).resolve().parent
    while current.parent != current:
        if (current / "config").exists() and (current / "build.md").exists():
            return current
        if (current / "config").exists() and (current / "BUILD.md").exists():
            return current
        current = current.parent
    # Fallback to 2 levels up from backend/app
    return Path(__file__).resolve().parent.parent.parent.parent


PROJECT_ROOT = find_project_root()


class ProviderConfig(BaseModel):
    base_url: str
    api_key_env: str


class TierConfig(BaseModel):
    provider: str
    model: str
    fallbacks: List[str] = Field(default_factory=list)


class LimitConfig(BaseModel):
    rpm: int = 30
    tpm: int = 6000
    rpd: int = 1000
    tpd: int = 100000


class ModelsConfig(BaseModel):
    default_provider: str = "groq"
    providers: Dict[str, ProviderConfig] = Field(default_factory=dict)
    tiers: Dict[str, TierConfig] = Field(default_factory=dict)
    limits: Dict[str, LimitConfig] = Field(default_factory=dict)


class ApprovalGates(BaseModel):
    external_side_effects: bool = True
    hire_dynamic_agents_threshold: int = 5
    freelance_client_ready: bool = True


class SettingsConfig(BaseModel):
    max_depth: int = 4
    max_children: int = 8
    max_attempts: int = 3
    max_revisions: int = 2
    tool_step_cap: int = 8
    task_token_budget: int = 25000
    global_concurrency: int = 2
    wip_limit_per_agent: int = 1
    approval_gates: ApprovalGates = Field(default_factory=ApprovalGates)


class RoleDef(BaseModel):
    key: str
    title: str
    department: str
    level: int
    reports_to: Optional[str] = None
    tier: str = "fast"
    count: int = 1
    tools: List[str] = Field(default_factory=list)
    prompt: str


class OrgConfig(BaseModel):
    company_charter: str
    roles: Dict[str, RoleDef] = Field(default_factory=dict)


class AppSettings(BaseModel):
    environment: str = os.getenv("ENVIRONMENT", "development")
    port: int = int(os.getenv("PORT", "8000"))
    host: str = os.getenv("HOST", "0.0.0.0")
    cors_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///pixel_corp.sqlite")
    workspaces_root: Path = PROJECT_ROOT / os.getenv("WORKSPACES_ROOT", "workspaces")
    models: ModelsConfig
    settings: SettingsConfig
    org: OrgConfig


def load_yaml(file_path: Path) -> Dict[str, Any]:
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def get_app_settings() -> AppSettings:
    config_dir = PROJECT_ROOT / "config"
    models_data = load_yaml(config_dir / "models.yaml")
    settings_data = load_yaml(config_dir / "settings.yaml")
    org_data = load_yaml(config_dir / "org.yaml")

    return AppSettings(
        models=ModelsConfig(**models_data),
        settings=SettingsConfig(**settings_data),
        org=OrgConfig(**org_data),
    )
