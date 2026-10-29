"""Daily digest: what's new in Asha's job memory, pushed via apprise.

Channel is one APPRISE_URL env var (apprise speaks 100+ services):
  ntfy://ntfy.sh/<secret-topic>     zero-signup push to the ntfy app
  tgram://<bot-token>/<chat-id>     Telegram bot (BotFather, 2 min setup)
  mailtos://user:app-pass@gmail.com SMTP
Without APPRISE_URL the digest prints to stdout (cron log).

Optional env:
  DIGEST_TITLE   (default: "Asha FISI job digest")

F10: "LIKELY EXPIRED" is now correlated with the run manifest (data/runs/*.json):
rows whose sources all failed/were not run today are labelled "source-down"
instead of implying the posting expired.
"""
from __future__ import annotations
import glob, json, os
from datetime import datetime, timezone

from pipeline import history

RUNS_DIR = "/home/z/my-project/data/runs"


def latest_manifest() -> dict | None:
    """Most recent run manifest from TODAY, if any (else None)."""
    paths = sorted(glob.glob(f"{RUNS_DIR}/*.json"))
    if not paths:
        return None
    try:
        m = json.load(open(paths[-1], encoding="utf-8"))
    except Exception:
        return None
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return m if str(m.get("ts", "")).startswith(today) else None


def _expiry_split(gone: list[dict]) -> tuple[list[dict], list[dict], bool]:
    """Split gone rows into (truly-expired, source-down, has_manifest_today).
    A row is only 'truly expired' if at least one of its sources was OK today —
    otherwise today's pull simply never re-checked it."""
    m = latest_manifest()
    if not m:
        return gone, [], False
    # memory rows carry DISPLAY names ("Talent.com", "Kimeta") while the
    # manifest carries source ids ("talent", "kimeta") — match either, both
    # case-insensitively (F10 fix after first live digest mislabelled rows)
    ok = {s.lower() for s in (m.get("ok_sources") or [])} \
        | {n.lower() for n in (m.get("ok_display_names") or [])}
    expired, down = [], []
    for r in gone:
        srcs = {s.strip().lower() for s in (r.get("source") or "").split("+") if s.strip()}
        if srcs & ok:
            expired.append(r)       # a source that ran OK today did not re-see it
        else:
            down.append(r)          # every source that knows this row was down/not run
    return expired, down, True


def build_digest(max_new: int = 12) -> str:
    """Compose the text digest from the job memory."""
    st = history.stats()
    today = datetime.now(timezone.utc).date().isoformat()
    lines = [f"Asha FISI digest — {today}", ""]

    fresh = history.new_today(limit=max_new)
    if fresh:
        lines.append(f"NEW TODAY ({len(fresh)}):")
        for r in fresh:
            jr = "*" if r.get("junior_signal") else " "
            ft = "" if not r.get("ft_unknown") else " [FT?]"
            lines.append(f"  {jr} {r['title'][:52]} | {r['company'][:22]} | "
                         f"{(r['city'] or '?')[:14]} | {r['url'][:70]}{ft}")
    else:
        lines.append("NEW TODAY: none (all postings already known)")

    gone = history.gone_today(limit=25)
    if gone:
        expired, down, has_manifest = _expiry_split(gone)
        if expired:
            lines.append("")
            lines.append(f"LIKELY EXPIRED ({len(expired)}):")
            for r in expired[:5]:
                lines.append(f"  - {r['title'][:50]} | {r['company'][:24]} "
                             f"(last seen {r['last_seen']})")
        if down:
            lines.append("")
            lines.append(f"NOT RE-CHECKED TODAY — source down/absent ({len(down)}):")
            for r in down[:5]:
                lines.append(f"  - {r['title'][:50]} | {r['company'][:24]} "
                             f"(last seen {r['last_seen']}; sources {r.get('source', '?')})")
        if not has_manifest:
            lines.append("")
            lines.append("(no fetch manifest for today — expiry lines are unreliable)")

    lines += ["", f"memory: {st['total']} postings since {st['first_seen_ever']}, "
                  f"{st['seen_today']} re-seen today"]
    return "\n".join(lines)


def send(text: str) -> tuple[bool, str]:
    """Send via APPRISE_URL if set; otherwise report stdout mode."""
    url = os.environ.get("APPRISE_URL", "").strip()
    if not url:
        return False, "APPRISE_URL not set — printing digest to stdout instead:\n"
    try:
        import apprise
        ap = apprise.Apprise()
        if not ap.add(url):
            return False, f"invalid APPRISE_URL: {url[:40]}..."
        res = ap.notify(title=os.environ.get("DIGEST_TITLE", "Asha FISI job digest"),
                        body=text)
        ok = getattr(res, "status", res)
        ok_val = ok == 0 if isinstance(ok, int) else getattr(ok, "name", "") == "SUCCESS"
        return (bool(ok_val),
                f"apprise -> {url.split('://')[0]}://{url.split('://', 1)[-1].split('/')[0]}: "
                f"{getattr(ok, 'name', ok)}")
    except Exception as e:
        return False, f"apprise send failed: {type(e).__name__}: {str(e)[:120]}"


def cmd_digest(args) -> int:
    text = build_digest()
    ok, msg = send(text)
    if not ok and msg.startswith("APPRISE_URL not set"):
        print(msg)
        print(text)
        return 0
    print(msg)
    return 0 if ok else 1
