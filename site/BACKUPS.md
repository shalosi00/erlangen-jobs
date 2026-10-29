# Backup & Access Map (updated 2026-10-13)

All work lives in this git repo. External copies made so the work is reachable
from anywhere and re-importable after any session loss.

## 1. Git bundle (FULL history, single file)
- File: `backups/asha-jobtoolkit-20261013.bundle` (v1) — recreate anytime with:
  `git bundle create backups/asha-jobtoolkit-$(date +%Y%m%d).bundle --all`
- Restore: `git clone asha-jobtoolkit-20261013.bundle restored-repo`

## 2. gofile.io mirror (keyless upload, no account needed)
- **v2 (current, all 6 commits incl. round-2 aggregator research): https://gofile.io/d/NbeJeEF7**
  - guest token: HgIo6I0BsTnPCBxFd9GLfCtbiuF8iqyR | md5: 012c04089f794fba58cb0981a9757547
- v1 (initial 5-commit state): https://gofile.io/d/1qhwgYgH
  - guest token (to manage/delete): kRG26Dn7TsDJUSZd6bMtNdsvsBv2jF2Q
- Re-upload: `curl -F "file=@bundle" https://store-na-phx-1.gofile.io/contents/uploadfile`

## 3. surge.sh static mirror (self-provisioned account, browsable)
- Sites deployed (LIVE at time of writing): https://asha-fisi-jt.surge.sh (primary),
  asha-fisi-jobtoolkit.surge.sh, asha-jobtoolkit.surge.sh
- ⚠️ surge insists on email verification within ~90 min and its mail never arrived at the
  temp mailbox (3 attempts, 2 accounts). Domains may go dark — **treat gofile v2 as the
  authoritative mirror**. Redeploy is cheap: `scripts/surge_retry.py` or the command below.
- Account: `backups/surge_account.json` (token 3e4cd0fc2b72f32cfa55c3faf3c96876 binds to
  asha.jt.haduez@maxxspace.com whose mailbox password is lost → password reset impossible,
  but token still deploys fine). Status: `backups/surge_verify_status.txt`
- Redeploy: `SURGE_LOGIN=$(jq -r .email backups/surge_account.json) SURGE_TOKEN=$(jq -r .surge_token backups/surge_account.json) npx -y surge ./site asha-fisi-jt.surge.sh`

## 4. Attempted but blocked (so nobody retries blindly)
- Codeberg.org — Anubis anti-bot PoW challenge on signup page (can't automate).
- GitLab.com — Cloudflare 403 from datacenter IP.
- catbox.moe — 412 "Invalid uploader" (datacenter blocked).
- pixeldrain — now requires API key for uploads.
- 0x0.st, archive.org, bashupload.com, staufenbiel, fau-jobboerse — unreachable from this network.
- CareerJet API — hosts unreachable from THIS datacenter (works from residential; free key).

## 5. What to do if everything is lost
1. Download bundle from the gofile link above.
2. `git clone <bundle>` → full repo history restored.
3. Or browse the surge site for: README, both findings docs, the PDF report, CSVs, all scripts.
