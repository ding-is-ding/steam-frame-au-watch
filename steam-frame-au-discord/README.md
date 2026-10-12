# Steam Frame AU → Discord stock tracker (free)

This checks Steam's public hardware inventory API for **Australia (`AU`)** for:

- Steam Frame 256GB: package `1629484`
- Steam Frame 1TB: package `1629486`

Runs **hourly** using GitHub Actions, with no computer left on and no Steam account credentials. Sends a Discord message only when a model transitions to available, plus an optional setup test message. Saves last-known status in `stock-status.json` and updates it weekly to keep the GitHub Actions schedule active.

## Setup

1. On Discord desktop, open your intended alerts channel → **Edit Channel → Integrations → Webhooks → New Webhook**. Create a webhook for that channel and copy its URL. Keep it secret.
2. Create a **public** GitHub repository (for instance `steam-frame-au-watch`). Public repositories can use standard GitHub Actions runners free of charge.
3. Upload `steam_frame_tracker.py` to the repo root and `.github/workflows/check-stock.yml` into that exact folder (or copy the contents using GitHub's **Add file → Create new file** feature). README is optional.
4. In your repository, go to **Settings → Secrets and variables → Actions → New repository secret** and create `DISCORD_WEBHOOK_URL` with the URL you copied.
5. **Optional** to ping your personal Discord account: Discord **User Settings → Advanced → Developer Mode**; right-click your user → **Copy User ID**. Add it as another repository secret named `DISCORD_USER_ID`. This will put a direct mention in messages for better phone notifications.
6. Go to **Actions → Steam Frame Australia stock tracker → Run workflow**. Leave **Send a test message to Discord** checked and run it. The Actions logs show both inventory results, and Discord should receive a test message.
7. Scheduled checks run hourly automatically. You only get availability notifications on a change from unavailable to available (or if the first-ever successful check is available).

If the workflow fails with a Git push permissions error, in **Settings → Actions → General → Workflow permissions**, choose **Read and write permissions** if the control is available, and rerun. The workflow already requests `contents: write`.

## Important limitations

- **Inventory ≠ checkout eligibility.** Steam Frame packages require a reservation. Inventory being available does not guarantee that your account can buy it. Continue monitoring your Steam account and invitation email.
- This watches only Valve's reported public inventory for country `AU`. It does not use a Steam account or detect your personal invitation.
- The Steam inventory endpoint is not a stable public contract. If it starts returning unexpected data, the Action logs will warn or fail instead of declaring availability.
- GitHub Actions schedules can be delayed or skipped during high load. Do not rely on this tracker as your only source of purchase notification.
- Do not post your Discord webhook URL in source code or chat. Store it as a GitHub secret.
- The free standard runner benefit applies to a public repository. A private repository uses your plan's included minutes and can have different limits.
