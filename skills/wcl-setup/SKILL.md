---
name: wcl-setup
description: >
  Configure Warcraft Logs API credentials for ParseHealer.
  Use when the user wants to set up WCL API keys, configure
  parse-healer credentials, or when wcl_client.py reports
  missing credentials.
disable-model-invocation: true
argument-hint: ""
---

# WCL Setup — Configure API Credentials

Set up Warcraft Logs API credentials so `/wcl-compare` can access log data.

## Scripts

```bash
SCRIPTS_DIR="${CLAUDE_SKILL_DIR}/../wcl-compare/scripts"
```

## Steps

1. Ask the user if they already have a WCL API key. If not, direct them to: https://www.warcraftlogs.com/api/clients
   - They need to create a new API client (any name, any redirect URL)
   - This gives them a **Client ID** and **Client Secret**

2. Ask the user for their **Client ID** and **Client Secret**.

3. Write the credentials to the persistent config directory (survives plugin updates):
```bash
mkdir -p ~/.config/parse-healer
cat > ~/.config/parse-healer/.env << 'ENVEOF'
WCL_CLIENT_ID=<user_provided_id>
WCL_CLIENT_SECRET=<user_provided_secret>
ENVEOF
```

4. Verify the credentials work:
```bash
python3 "$SCRIPTS_DIR/wcl_client.py"
```

If successful, it prints "Token obtained: ..." and rate limit info. If it fails, help troubleshoot (wrong credentials, expired client, etc.).

5. Confirm setup is complete and remind the user they can now use `/wcl-compare`.
