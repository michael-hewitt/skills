---
name: reload-macos-permissions
description: Make a macOS privacy (TCC) permission change take effect for already-running processes without restarting the app or its child agents, and diagnose grants that seem stuck. Use when the user granted or revoked access in System Settings (Downloads/Documents/Desktop, Full Disk Access, Accessibility, Screen Recording) but a running process still behaves as if it lacks access, or says "the permission didn't take effect", "I don't want to restart the app/agents", "TCC", "restart tccd", or "Full Disk Access isn't working".
---

# Reload macOS permissions (TCC)

## First: check whether it already works — don't fix what isn't broken

File-access permissions are evaluated **live, per request**, against the TCC database.
Granting Downloads/Documents/Desktop or Full Disk Access applies to already-running
processes **immediately, with no restart of anything**. So before bouncing tccd, prove
the access actually fails. Test the real path from a process in the affected tree:

```bash
ls ~/Downloads >/dev/null 2>&1 && echo "READ OK" || echo "READ DENIED"
t=~/Downloads/.tcc-probe-$$; echo ok >"$t" 2>/dev/null && rm -f "$t" && echo "WRITE OK" || echo "WRITE DENIED"
```

If both say OK, there is nothing to do — report that and stop.

## Diagnose: read the actual grants

TCC decides based on the **responsible app bundle** (e.g. `com.stablyai.orca`), not the
child binary. Check what the database says (`auth_value`: 0=denied, 2=allowed, 3=limited):

```bash
# Per-user permissions (Downloads/Documents/Desktop/Accessibility/etc.)
sqlite3 "$HOME/Library/Application Support/com.apple.TCC/TCC.db" \
  "select client,service,auth_value,datetime(last_modified,'unixepoch','localtime') \
   from access where client like '%<bundle-id>%' order by last_modified"

# System permissions (Full Disk Access, Screen Recording) — needs sudo / Full Disk Access
sudo sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" \
  "select client,service,auth_value from access where service='kTCCServiceSystemPolicyAllFiles'"
```

Full Disk Access (`kTCCServiceSystemPolicyAllFiles=2`) covers every folder, so a per-folder
row is irrelevant when FDA is allowed.

## Fix: force a fresh evaluation without restarting the app

If the database shows the grant but a process still acts denied, tccd is holding a stale
in-memory decision. Bounce it — it is launchd-managed and relaunches instantly:

```bash
sudo killall tccd    # kills both the user (uid 501) and system (root) tccd; both auto-restart
```

This clears tccd's cache and forces the next request to re-read the database. It does **not**
touch the target app or any of its child agents, so long-running agents keep running.

Verify with the probe from "First" above.

## Scope — what this cannot do

`killall tccd` only fixes the tccd-cache layer. It will **not** override:

- A permission an app reads once at **its own startup** and caches internally.
- A hardened-runtime **entitlement**.

For those, only relaunching the *target app* helps. Note that for an app whose agents run
under a **separate supervisor daemon** (e.g. Orca), quitting and reopening the GUI does not
kill the agents, so an app relaunch is usually harmless anyway.

Accessibility and Screen Recording historically needed an app relaunch; on current macOS a
tccd bounce plus a fresh request often suffices — try it before restarting the app.

## Inspect live decisions (optional)

To see tccd's actual allow/deny and which bundle it attributed the request to:

```bash
/usr/bin/log show --info --debug --last 10m --style compact \
  --predicate 'subsystem == "com.apple.TCC" AND eventMessage CONTAINS "Handling access request"' \
  | grep -i '<bundle-id>'
```

Look for `Auth Right: Allowed`/`Denied` and the `responsible_path=` on each line.
