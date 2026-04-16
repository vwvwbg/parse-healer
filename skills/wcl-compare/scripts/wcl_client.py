"""Warcraft Logs API v2 client."""

import json
import os
from pathlib import Path

import requests

TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
API_URL = "https://www.warcraftlogs.com/api/v2/client"

SCRIPT_DIR = Path(__file__).resolve().parent


def _load_credentials():
    """Load WCL credentials. Priority: env vars > .env file > settings.local.json."""
    client_id = os.environ.get("WCL_CLIENT_ID")
    client_secret = os.environ.get("WCL_CLIENT_SECRET")
    if client_id and client_secret:
        return client_id, client_secret

    # Try .env in the scripts directory
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip()
                if key == "WCL_CLIENT_ID":
                    client_id = value
                elif key == "WCL_CLIENT_SECRET":
                    client_secret = value
        if client_id and client_secret:
            return client_id, client_secret

    # Try ~/.claude/settings.local.json
    settings_file = Path.home() / ".claude" / "settings.local.json"
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text(encoding="utf-8"))
            wcl = settings.get("wcl", {})
            client_id = wcl.get("clientId") or client_id
            client_secret = wcl.get("clientSecret") or client_secret
            if client_id and client_secret:
                return client_id, client_secret
        except (json.JSONDecodeError, AttributeError):
            pass

    raise RuntimeError(
        "WCL credentials not found. Set them up using one of:\n"
        "  1. Run /wcl-setup in Claude Code\n"
        "  2. Set WCL_CLIENT_ID and WCL_CLIENT_SECRET environment variables\n"
        "  3. Create a .env file in the scripts directory\n"
        "Get your API key at: https://www.warcraftlogs.com/api/clients"
    )


def get_token():
    client_id, client_secret = _load_credentials()
    resp = requests.post(
        TOKEN_URL,
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def query(graphql_query: str, variables: dict | None = None, token: str | None = None):
    if token is None:
        token = get_token()
    payload = {"query": graphql_query}
    if variables:
        payload["variables"] = variables
    resp = requests.post(
        API_URL,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    token = get_token()
    print(f"Token obtained: {token[:20]}...")
    result = query("{ rateLimitData { limitPerHour pointsSpentThisHour pointsResetIn } }", token=token)
    print(f"Rate limit: {result}")
