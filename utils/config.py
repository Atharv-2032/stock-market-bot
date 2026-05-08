import yaml
import os
from dotenv import load_dotenv

load_dotenv()

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def get_secret(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing secret: {key} — check your .env file")
    return value