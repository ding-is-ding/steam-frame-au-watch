#!/usr/bin/env python3
"""Monitor public Australian Steam Frame hardware inventory, alert on restocks."""

import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

COUNTRY = "AU"
ITEMS = {"1629484": "Steam Frame 256GB", "1629486": "Steam Frame 1TB"}
STEAM_PAGE = "https://store.steampowered.com/hardware/steamframe"
STEAM_API = (
    "https://api.steampowered.com/"
    "IPhysicalGoodsService/CheckInventoryAvailableByPackage/v1/"
)
STATE_FILE = Path(__file__).with_name("stock-status.json")


def check_sydney_inventory():
    endpoint = os.environ.get("AU_ENDPOINT_URL", "").strip()
    if not endpoint:
        return None
    if not endpoint.startswith("https://"):
        raise RuntimeError("AU_ENDPOINT_URL must be an HTTPS address")
    request = urllib.request.Request(
        endpoint,
        headers={"User-Agent": "SteamFrameAUStockWatcher/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=35) as response:
        payload = json.load(response)
    if payload.get("region") != "syd1" or payload.get("egress_country") != "AU":
        raise RuntimeError("Sydney endpoint did not verify Australian outbound location")
    models = payload.get("models", {})
    if any(not isinstance(models.get(pid), bool) for pid in ITEMS):
        raise RuntimeError("Sydney endpoint returned incomplete inventory data")
    print("Verified Sydney function with Australian outbound IP")
    return models


def check_inventory(package_id):
    params = urllib.parse.urlencode({
        "origin": "https://store.steampowered.com",
        "country_code": COUNTRY,
        "packageid": package_id,
    })
    request = urllib.request.Request(
        f"{STEAM_API}?{params}",
        headers={"User-Agent": "SteamFrameAUStockWatcher/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    available = payload.get("response", {}).get("inventory_available")
    if not isinstance(available, bool):
        raise ValueError(f"Missing boolean inventory_available for package {package_id}")
    return available


def notify(webhook_url, title, message, mention_user="", color=3447003):
    # A webhook URL is a secret, so never print it, even on error.
    user_id = mention_user.strip()
    if user_id and not re.fullmatch(r"[0-9]{17,21}", user_id):
        raise ValueError("DISCORD_USER_ID should contain only the numeric Discord user ID")
    payload = {
        "username": "Steam Frame AU Watch",
        "content": f"<@{user_id}>" if user_id else "",
        "embeds": [{
            "title": title,
            "description": message,
            "url": STEAM_PAGE,
            "color": color,
            "footer": {"text": "Australia (AU) | Steam hardware inventory"},
        }],
        "allowed_mentions": {"parse": [], "users": [user_id] if user_id else []},
    }
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
headers={
    "Content-Type": "application/json",
    "User-Agent": "SteamFrameAUStockWatcher/1.0",
},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status not in (200, 204):
                raise RuntimeError(f"Discord returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Discord returned HTTP {exc.code}") from None


def main():
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")):
        raise RuntimeError("Configure the DISCORD_WEBHOOK_URL GitHub Actions secret")
    mention_user = os.environ.get("DISCORD_USER_ID", "")
    send_test = os.environ.get("SEND_TEST", "false").lower() == "true"

    if send_test:
        notify(
            webhook_url,
            "✅ Your Steam Frame Discord tracker is connected",
            "Test message only. The tracker checks both Steam Frame models using country_code=AU. "
            "A test does **not** mean either model is in stock.",
            mention_user,
        )
        print("Discord test message sent")

    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    else:
        state = {}
    statuses = state.get("models", {})
    # Require Australian IP verification whenever the Sydney endpoint is configured.
    sydney_statuses = check_sydney_inventory()
    successes = 0
    for package_id, name in ITEMS.items():
        try:
            available = (sydney_statuses[package_id] if sydney_statuses is not None
                         else check_inventory(package_id))
            old_status = statuses.get(package_id)  # None means we have never checked.
            print(f"{name}: {'IN STOCK' if available else 'out of stock'} (previous: {old_status})")
            # Unknown -> available and out of stock -> available both merit an alert.
            if available and old_status is not True:
                notify(
                    webhook_url,
                    f"🟢 {name} inventory AVAILABLE in Australia",
                    f"Steam's public inventory API reports **{name}** available in Australia.\n\n"
                    f"🛒 **[Open Steam listing / Check Add to Cart](https://store.steampowered.com/sub/{package_id}/?curator_clanid=4777282)**\n\n"
                    "⚠️ Steam Frame purchases are reservation-restricted. "
                    "This alert does **not** guarantee your account can check out. "
                    "Check Steam and your purchase invitation.",
                    mention_user,
                    color=5763719,
                )
                print(f"Discord availability alert sent: {name}")
            statuses[package_id] = available
            successes += 1
        except (ValueError, RuntimeError, urllib.error.URLError, TimeoutError, OSError, KeyError) as exc:
            # Avoid pretending an API failure means out of stock. Preserve last good status.
            print(f"WARNING: unable to check {name}: {type(exc).__name__}: {exc}", file=sys.stderr)

    if not successes:
        raise RuntimeError("All Steam availability checks failed; no status was changed")

    # Keep the original webhook exclusively for stock availability alerts.
    # Post a separate hourly heartbeat ONLY after both package IDs were
    # successfully checked and BOTH are confirmed out of stock.
    status_webhook_url = os.environ.get("DISCORD_STATUS_WEBHOOK_URL", "").strip()
    if successes == len(ITEMS) and all(statuses.get(pid) is False for pid in ITEMS):
        if status_webhook_url:
            checked_at = dt.datetime.now(dt.timezone(dt.timedelta(hours=11)))
            # Timestamp includes the current Sydney offset as supplied by the runner.
            # The inventory result itself is from the validated Sydney endpoint.
            try:
                notify(
                    status_webhook_url,
                    "🔴 Steam Frame AU: Still out of stock",
                    "**256GB:** Out of stock\\n"
                    "**1TB:** Out of stock\\n\\n"
                    f"✅ Both Australian inventory checks succeeded.\\n"
                    f"🕒 Checked: {checked_at.strftime('%d %b %Y %I:%M %p')} (AEDT)\\n\\n"
                    "This is the regular out-of-stock status report. "
                    "The separate restock channel only gets availability alerts.",
                    color=9807270,
                )
                print("Out-of-stock status sent to second Discord webhook")
            except (ValueError, RuntimeError, urllib.error.URLError, TimeoutError, OSError) as exc:
                # A secondary webhook problem must not disrupt stock alerts or saved state.
                print(f"WARNING: status Discord webhook failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        else:
            print("Out-of-stock status webhook not configured; skipping status report")
    else:
        print("No all-out-of-stock report: inventory available or a check failed")

    state["models"] = statuses
    # A weekly metadata update keeps this scheduled workflow active in a public repo.
    today = dt.datetime.now(dt.timezone.utc).date()
    iso = today.isocalendar()
    state["last_checked_week"] = f"{iso.year}-W{iso.week:02d}"
    updated = json.dumps(state, indent=2, sort_keys=True) + "\n"
    if not STATE_FILE.exists() or STATE_FILE.read_text(encoding="utf-8") != updated:
        STATE_FILE.write_text(updated, encoding="utf-8")
        print("Recorded stock status in stock-status.json")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, urllib.error.URLError, OSError) as exc:
        # Important: print error messages, not the secret URL.
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
