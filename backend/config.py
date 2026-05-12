import os
from dotenv import load_dotenv

load_dotenv()

def _clean_env(value: str | None) -> str:
    return (value or "").strip().strip("\"'").strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _clean_env(os.environ.get(name))
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


OPENAI_BASE_URL = _clean_env(
    os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
    or os.environ.get("OPENAI_BASE_URL")
)
OPENAI_API_KEY = _clean_env(
    os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
)

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Models: set OPENAI_MODEL to override all three, or set individually.
# Use a model your key can access; gpt-5-* tiers often have low rate limits (429).
_openai_model_all = _clean_env(os.environ.get("OPENAI_MODEL"))
if _openai_model_all:
    ORCHESTRATOR_MODEL = AGENT_MODEL = META_MODEL = _openai_model_all
else:
    ORCHESTRATOR_MODEL = _clean_env(os.environ.get("ORCHESTRATOR_MODEL")) or "gpt-5-mini"
    AGENT_MODEL = _clean_env(os.environ.get("AGENT_MODEL")) or "gpt-5-mini"
    META_MODEL = _clean_env(os.environ.get("META_MODEL")) or "gpt-5-mini"

MAX_TOOL_RETRIES = 2
CONTEXT_BUDGET_DEFAULT = 8000
JOB_QUEUE_SIZE = 100

# Submission mode: expose only the five assignment endpoints. Default off so the
# bundled dashboard (prompts, eval rerun, observability pages) works without extra env.
STRICT_API_FIVE_ENDPOINTS = _env_bool("STRICT_API_FIVE_ENDPOINTS", default=False)
