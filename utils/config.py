from pathlib import Path
from dotenv import load_dotenv
import os
import yaml

# explicitly load from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def get_secret(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing secret: {key} — check your .env file")
    return value