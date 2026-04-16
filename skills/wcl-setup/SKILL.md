---
name: wcl-setup
description: Configure Warcraft Logs API credentials for ParseHealer
disable-model-invocation: true
argument-hint: ""
---

# WCL Setup — Configure API Credentials

Set up your Warcraft Logs API credentials so `/wcl-compare` can access log data.

## Steps

1. Ask the user if they already have a WCL API key. If not, direct them to: https://www.warcraftlogs.com/api/clients
   - They need to create a new API client (any name, any redirect URL)
   - This gives them a **Client ID** and **Client Secret**

2. Ask the user for their **Client ID** and **Client Secret**.

3. Determine the plugin's installed location by running:
```bash
python3 -c "from pathlib import Path; print(Path.home() / '.claude' / 'skills' / 'wcl-compare' / 'scripts')"
```

4. Write the credentials to a `.env` file in the scripts directory:
```bash
cat > "<scripts_dir>/.env" << 'ENVEOF'
WCL_CLIENT_ID=<user_provided_id>
WCL_CLIENT_SECRET=<user_provided_secret>
ENVEOF
```

5. Verify the credentials work:
```bash
python3 "<scripts_dir>/wcl_client.py"
```

If successful, it will print "Token obtained: ..." and rate limit info. If it fails, help the user troubleshoot (wrong credentials, expired client, etc.).

6. Confirm setup is complete and remind the user they can now use `/wcl-compare`.
