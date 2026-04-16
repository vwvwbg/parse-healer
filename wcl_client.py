"""Warcraft Logs API v2 client."""

import os
import requests

TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
API_URL = "https://www.warcraftlogs.com/api/v2/client"


def get_token():
    client_id = os.environ.get("WCL_CLIENT_ID")
    client_secret = os.environ.get("WCL_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "WCL_CLIENT_ID and WCL_CLIENT_SECRET must be set as environment variables.\n"
            "Get your API key at: https://www.warcraftlogs.com/api/clients"
        )
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
