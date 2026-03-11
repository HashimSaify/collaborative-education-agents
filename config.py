"""
config.py
---------
Central configuration and constants for Collaborative Education Agents.
Powered exclusively by Google Gemini.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load environment variables from .env ──────────────────────────────────────
load_dotenv()

# ── Project Paths ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUTS_DIR = BASE_DIR / "outputs"
LOGS_DIR = BASE_DIR / "logs"
STATE_DIR = BASE_DIR / "state"

# Ensure directories exist
OUTPUTS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
STATE_DIR.mkdir(exist_ok=True)

# ── Gemini Configuration ──────────────────────────────────────────────────────
# Google Gemini settings
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")

# Optional: Serper API key for web-search tool inside Researcher Agent
SERPER_API_KEY: str = os.getenv("SERPER_API_KEY", "")

# ── Agent Behaviour ───────────────────────────────────────────────────────────
RESEARCHER_MAX_ITER: int = int(os.getenv("RESEARCHER_MAX_ITER", "5"))
WRITER_MAX_ITER: int = int(os.getenv("WRITER_MAX_ITER", "5"))

# Maximum retries for handoff validation failures
HANDOFF_RETRY_LIMIT: int = int(os.getenv("HANDOFF_RETRY_LIMIT", "2"))

# ── Output Settings ───────────────────────────────────────────────────────────
OUTPUT_TYPES = [
    "study_guide",       
    "summary",           
    "revision_sheet",    
    "bullet_notes",      
]
DEFAULT_OUTPUT_TYPE: str = "study_guide"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: Path = LOGS_DIR / "education_agents.log"

# ── Validation ────────────────────────────────────────────────────────────────
def validate_config() -> list[str]:
    """
    Validates required configuration.
    Returns a list of error messages (empty list = all good).
    """
    errors: list[str] = []
    if not GOOGLE_API_KEY:
        errors.append(
            "GOOGLE_API_KEY is not set. Please add it to your .env file."
        )
    if DEFAULT_OUTPUT_TYPE not in OUTPUT_TYPES:
        errors.append(
            f"DEFAULT_OUTPUT_TYPE '{DEFAULT_OUTPUT_TYPE}' is not valid. "
            f"Choose from: {OUTPUT_TYPES}"
        )
    return errors
