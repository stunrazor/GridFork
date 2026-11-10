# License operations (founder runbook)

GridFork is BSL 1.1: non-production use is free, production use needs a paid
license (`LICENSE`, licensor Mark Albert Santos). This file is how to run that.

## How the gate behaves

| `GRIDFORK_ENV` | Key | Result |
|---|---|---|
| unset / anything but `production` | — | Free. Boots and serves. This is dev, test, evaluation, and the public demo. |
| `production` | valid, unexpired, canary-bound | Boots and serves. |
| `production` | missing / invalid / expired | **Refuses to boot.** Uvicorn exits with the reason. |

`GET /license/status` reports `{mode, licensed, reason, canary}` publicly and
never exposes secrets. Check it on any deployment instead of guessing.

## Issuing a customer key

The signing secret lives ONLY with you (password manager, never the repo):

```powershell
$env:GRIDFORK_LICENSE_SECRET = "<secret-from-password-manager>"
python scripts/issue_license.py --sub buyer@example.com --days 365
```

Send the printed `GF1.…` key to the customer. They set on their production
deployment:

- `GRIDFORK_ENV=production`
- `GRIDFORK_LICENSE_KEY=<the key>`
- `GRIDFORK_LICENSE_SECRET=<see below>`

Verification is HMAC, so deployments also hold the secret (it is the verify
key). If it ever leaks, generate a new secret, reissue every customer key,
and have them update: old keys stop verifying the moment the secret changes.
Keep a dated list of issued subjects so rotation is a mail-merge, not archaeology.

## The build canary

`GF-CANARY-edd38bf08e448991e83549147420714b`

Embedded in `license_gate.py` as a functional ingredient, not a comment:

- Every issued key binds to it (`payload.canary` must match) — strip or
  rotate the canary and all keys stop verifying.
- The module asserts its shape at import; mangle or delete it and the
  process fails to boot with a clear error.
- `/license/status` exposes it, so any running copy can be fingerprinted.

## Google Alert tripwire (your clicks, 2 min)

This detects **public copies, leaks, or pastes** containing the canary — a
mirror, a pasted config, docs quoting it. It does NOT detect private
production use (nothing indexed, nothing to alert on).

1. Go to `google.com/alerts` (logged into the Google account you read).
2. In **Create an alert about...**, paste exactly (quotes included):
   `"GF-CANARY-edd38bf08e448991e83549147420714b"`
3. **Show options**: How often → **As-it-happens**; Sources → **Automatic**;
   Language → English; Region → Any Region; How many → **All results**;
   Deliver to → `stunrazor@gmail.com`.
4. **Create Alert.** The string will eventually index from this repo itself —
   expect one baseline hit at that address and ignore it.

When an alert fires on an unfamiliar URL: open it, confirm it is your code or
output, screenshot with date, then enforce (takedown request or license
conversation). An alert is a lead, not proof — verify before acting.

## Honesty notes (read before relying on any of this)

1. The gate ships in published source: anyone can delete it. It deters
   honest users, fails loudly, and makes removal willful and visible in a
   diff. It is a legal tripwire, not DRM.
2. The HMAC secret on deployments can be extracted by the deployment owner.
   That is accepted: exposure enables forging, rotation kills forged keys,
   and BSL is the actual enforcement.
3. Alerts see only publicly indexed pages. No alerts does not mean no
   unlicensed use; it means no public traces.
