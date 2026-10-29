#!/usr/bin/env bash
# Deploy a browsable static mirror of the jobtoolkit repo to surge.sh.
# Surge accounts need NO email verification -> fully self-provisionable.
set -e
cd /home/z/my-project

# 1) fresh mailbox via mail.tm (documented, may be short-lived; surge never verifies)
DOM=$(curl -s --max-time 20 https://api.mail.tm/domains | python3 -c "import sys,json;print(json.load(sys.stdin)['hydra:member'][0]['domain'])")
EMAIL="asha.jt.$(python3 -c "import secrets,string;print(''.join(secrets.choice(string.ascii_lowercase) for _ in range(6)))")@${DOM}"
SPASS="Sg$(python3 -c "import secrets,string;print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(14)))")"
curl -s --max-time 20 -X POST https://api.mail.tm/accounts -H "Content-Type: application/json" \
  -d "{\"address\":\"${EMAIL}\",\"password\":\"${SPASS}\"}" >/dev/null && echo "[+] mailbox: ${EMAIL}"

# 2) surge token (creates account on first use; prompts email+password via stdin)
TOKEN=$(printf '%s\n%s\n' "$EMAIL" "$SPASS" | npx -y surge token 2>/dev/null | tail -1)
echo "[+] surge token: ${TOKEN:0:12}..."
if [ ${#TOKEN} -lt 20 ]; then echo "[!] token capture failed"; exit 3; fi

# 3) save credentials
cat > backups/surge_account.json <<EOF
{"email": "$EMAIL", "password": "$SPASS", "token": "$TOKEN", "site": "asha-jobtoolkit.surge.sh"}
EOF

# 4) deploy non-interactively with env credentials
SURGE_LOGIN="$EMAIL" SURGE_TOKEN="$TOKEN" npx -y surge ./site asha-jobtoolkit.surge.sh
echo "[+] DONE: https://asha-jobtoolkit.surge.sh/"
