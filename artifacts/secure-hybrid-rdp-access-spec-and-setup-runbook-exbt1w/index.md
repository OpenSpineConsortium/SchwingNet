# Secure Hybrid RDP Access – Spec & Setup Runbook

Sep 27, 2026 · @greg

## Overview

The P50 accepts Remote Desktop only over Tailscale. Your personal laptop signs in with just the Windows password; every other device must also pass Duo MFA. Nothing on the P50 is reachable from the open internet.

&#91;embedded content: access paths · 3 sources, 1 Duo decision\]

The Duo decision works only if Duo sees the RDP client's Tailscale address. Phase 4 includes a check for this.

### What changed from the original spec

| Area | Original spec | Revised |
| --- | --- | --- |
| Untrusted access | RDP reachable from the public internet, guarded by Duo | No port forwarding; other devices join the tailnet and pass Duo |
| MFA bypass | Whole 100.64.0.0/10 range | Personal laptop's single Tailscale IP (/32) |
| Firewall | Not covered | RDP rules accept only tailnet addresses |
| Tailscale access rules | Not covered | Only your own devices can reach the P50 |
| Key expiry | Said to make the IP static | Disabled on the P50 only, so it never drops off; the IP is stable regardless |
| Lockout protection | None | Duo prompts only on RDP; bypass codes on paper |

## Design rules

Five rules keep the P50 safe. Every step below implements one of them.

1. **No port forwarding.** Port 3389 never opens on the router. The only way in is Tailscale.
2. **Firewall scoped to the tailnet.** Windows accepts RDP only from Tailscale addresses (100.64.0.0/10).
3. **Tailscale limited to your own devices.** The tailnet policy lets only devices signed in as you reach the P50.
4. **One-device MFA bypass.** Duo skips MFA only for the laptop's single Tailscale IP. Every other device gets a Duo prompt.
5. **No self-lockout.** Duo prompts only on RDP, so the P50's own keyboard always works. Bypass codes cover remote emergencies.

Devices that can't run Tailscale are out of scope. If you need one later, put Tailscale on it rather than opening a port.

## Prerequisites

Check these before starting. The first two can stop the whole plan.

| Requirement | Why it matters | How to check |
| --- | --- | --- |
| Windows Pro, Enterprise or Education on the P50 | Windows Home cannot host Remote Desktop | Settings → System → About → Edition |
| Duo Essentials, Advantage or Premier | Duo Free only controls the new-user policy, so the laptop bypass is impossible on Free ([Duo policy docs](https://duo.com/docs/policy)) | Duo Admin Panel → Billing |
| A password on the `grego` account | Duo requires a password logon; RDP won't accept a PIN | Sign out and sign back in with the password, not the PIN |
| Account type known (local or Microsoft) | Microsoft accounts may need extra Duo setup ([Duo FAQ](https://duo.com/docs/rdp-faq)) | Settings → Accounts → Your info |
| Duo Mobile on your phone | Push approvals and passcodes | App store |
| BitLocker recovery key saved offline | Needed if you ever boot to Safe Mode to remove Duo ([Duo instructions](https://duo.com/docs/rdp)) | Phase 0, step 4 |

### Windows 10 on the P50

The P50 uses a 6th-generation Intel CPU, which is not on Microsoft's supported list for Windows 11. Windows 10 extended support ends October 13, 2026, and Duo ends Windows 10 support that same month ([Duo FAQ](https://duo.com/docs/rdp-faq)).

If the P50 is still on Windows 10, pick one before starting. You can upgrade to Windows 11 anyway using Microsoft's unsupported-hardware route, where updates aren't guaranteed. Or you can accept running an unpatched machine that you reach remotely.

## Phase 0: Prep (P50, about 10 minutes)

1. Press Win+R, type `winver`, press Enter. Note whether it's Windows 10 or 11, then check the edition in Settings → System → About.
2. Open Settings → Accounts → Your info. If it says **Local account**, your RDP username is `grego`. If it shows an email address, your RDP username is that email and the password is your Microsoft account password.
3. Sign out, then sign back in using the password (choose Sign-in options if Windows offers a PIN). This confirms the password works and caches it.
4. If BitLocker is on, open PowerShell as administrator and run the command below. Write the 48-digit recovery password on paper and store it away from the laptop.

   ```powershell
   manage-bde -protectors -get C:
   ```
5. Log in to your home router's admin page. Under Port Forwarding (sometimes called Virtual Servers), delete any rule that points at the P50 or at port 3389.
6. Settings → System → Power → Screen and sleep: set "When plugged in, put my device to sleep" to **Never**. A sleeping P50 drops off Tailscale.

## Phase 1: Tailscale (both machines, about 10 minutes)

1. On the P50 and the laptop, install Tailscale from tailscale.com/download. Sign in to both with the same Microsoft account.
2. On the P50, click the Tailscale tray icon → Preferences → turn on **Run unattended**. Without this, the P50 drops off the tailnet after a reboot until someone signs in at its keyboard.
3. In the Tailscale admin console (login.tailscale.com/admin), open **Machines**. On the P50's row, click the ⋯ menu → **Disable key expiry**. Leave key expiry on for the laptop, so a lost laptop eventually loses access.
4. On each machine, open a terminal and run the command below. Write down both addresses: the P50's (`100.x.y.z`) and the laptop's (`100.a.b.c`).

   ```powershell
   tailscale ip -4
   ```
5. From the laptop, check the tunnel works. Use `tailscale ping`, because Windows blocks ordinary ping by default.

   ```powershell
   tailscale ping 100.x.y.z
   ```

## Phase 2: Enable RDP and lock the firewall to the tailnet (P50, about 10 minutes)

1. Settings → System → Remote Desktop → turn **Remote Desktop** on. Keep "Require devices to use Network Level Authentication" checked.
2. If `grego` is an administrator on the P50, it already has RDP rights. If not, add it under **Remote Desktop users** on the same page.
3. Open PowerShell as administrator. Run the first line to restrict the RDP firewall rules to Tailscale addresses, then the second to confirm.

   ```powershell
   Set-NetFirewallRule -DisplayGroup "Remote Desktop" -RemoteAddress 100.64.0.0/10
   Get-NetFirewallRule -DisplayGroup "Remote Desktop" | Get-NetFirewallAddressFilter
   ```

   Every rule listed should show `RemoteAddress : 100.64.0.0/10`.
4. Test before Duo goes in. On the laptop, press Win+R, type `mstsc`, and connect to `100.x.y.z`. Sign in with the username from Phase 0 step 2 and tick **Remember me**. You should land on the P50 desktop.

If step 4 times out, see Troubleshooting before moving on. Don't install Duo until plain RDP works.

## Phase 3: Duo Admin Panel setup (browser, about 15 minutes)

Do this before installing anything on the P50, so the policy is ready when Duo first runs.

1. Log in at admin.duosecurity.com. Go to Applications → Application Catalog, find **Microsoft RDP** (2FA label), and click **+ Add**. Copy the integration key, secret key, and API hostname. Treat the secret key like a password.
2. On the new application's page, set **User access** to all users. New applications allow nobody until you change this. Leave **Username normalization** on Simple, so `DONEPHDGOODPHD\grego` and `grego` count as the same user.
3. Users → **Add User**. Username: `grego`. On the user's page, click **Add Phone**, enter your number, and activate Duo Mobile.
4. On the same user page, generate a few **bypass codes**. Write them on paper and store them with the BitLocker key.
5. Policies → **+ Add Policy**. Name it `Hybrid RDP Access Policy`, then add these sections:
   - **Authentication policy:** Enforce MFA.
   - **New user policy:** Deny access.
   - **Authorized networks:** enter the laptop's address as `100.a.b.c/32`. Choose the option that allows access without MFA from these networks. If there's a "require enrollment" checkbox, leave it on.

   Click **Save**.
6. Return to the Microsoft RDP application page. Under Application policy, click **Apply a policy to all users**, choose `Hybrid RDP Access Policy`, and click **Apply Policy**.
7. Policies → **Policy Calculator**. Pick user `grego` and the Microsoft RDP application. Confirm the effective policy shows your laptop's /32 under authorized networks.

Option labels differ slightly between Duo's new and legacy policy editors. Match on meaning, not exact wording.

## Phase 4: Install Duo on the P50 and check what it sees (about 15 minutes)

1. On the P50, download the installer from `https://dl.duosecurity.com/duo-win-login-latest.exe`. Right-click it → **Run as administrator**.
2. Enter the API hostname and click Next; the installer tests the connection. Then enter the integration key and secret key.
3. Set the integration options exactly like this:

   | Option | Setting | Why |
   | --- | --- | --- |
   | Bypass Duo authentication when offline (FailOpen) | Unchecked (the default) | If Duo's cloud is unreachable, remote logins wait rather than skip MFA |
   | Use auto push to authenticate if available | Checked | Push arrives without clicking |
   | Only prompt for Duo authentication when logging in via RDP | **Checked** | Your lockout protection: the P50's own keyboard never needs Duo |
   | Smart card and UAC options | Leave off | Not needed here |
4. Click Install and reboot if asked.
5. At the P50's keyboard, lock the screen and sign back in. You should see **no** Duo prompt.
6. From the laptop, connect over RDP to `100.x.y.z` as before. You should land on the desktop with no Duo prompt.
7. In the Duo Admin Panel, open Reports → **Authentication Log**. The newest `grego` entry should show the laptop's `100.a.b.c` as the access device IP, allowed without MFA.

If step 7 shows a different IP, stop and fix it before relying on the bypass. Duo's [debug logging guide](https://help.duo.com/s/article/1083) shows exactly which address the P50 sends. Never add your home public IP to authorized networks.

## Phase 5: Tailscale access policy (browser, about 5 minutes)

The default tailnet policy allows every device to reach every other one. This replaces it with "your devices can reach your own devices," which blocks other users and anything shared into your tailnet ([Tailscale grant examples](https://tailscale.com/docs/reference/examples/grants.md)).

1. In the Tailscale admin console, open **Access controls** and switch to the JSON editor.
2. Copy the whole existing policy into a text file as a backup.
3. Delete the default allow-all rule. It sits under `"acls"` or `"grants"` and has `"*"` as both source and destination. Put this grant in its place:

   ```json
   "grants": [
     {
       "src": ["autogroup:member"],
       "dst": ["autogroup:self"],
       "ip": ["*"]
     }
   ]
   ```

   Keep any other sections you already use, such as `"ssh"` or `"tagOwners"`.
4. Click **Save**. Then reconnect from the laptop over RDP to confirm it still works.

If the laptop loses access, paste the backup back in and save. Both machines must be signed in as the same Microsoft account for `autogroup:self` to match.

## Verification tests

Run all six. The setup is done only when each one gives the expected result.

| # | Test | How | Expected |
| --- | --- | --- | --- |
| 1 | Trusted laptop | Laptop on Tailscale, `mstsc` to `100.x.y.z` | Desktop opens, no Duo prompt |
| 2 | Other tailnet device | Phone with Tailscale and Microsoft's Windows App, connect to `100.x.y.z` | Duo push arrives; desktop opens after you approve |
| 3 | Bypass is laptop-only | In the Duo policy, change the laptop's entry to `192.0.2.1/32`, then RDP from the laptop | Duo push arrives. Change it back afterwards |
| 4 | No Tailscale, no RDP | Disconnect Tailscale on the laptop, then `mstsc` to the P50's home-network IP | Connection fails |
| 5 | Internet stays closed | Laptop on a phone hotspot with Tailscale off, `mstsc` to your home public IP | Connection fails |
| 6 | Console needs no Duo | Sign in at the P50's own keyboard | No Duo prompt |

## Troubleshooting and lockout recovery

Most failures come from one of the problems below. Work down the list in order.

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `mstsc` times out over Tailscale | RDP firewall rules not active on the Tailscale network's profile | Admin PowerShell: `Set-NetFirewallRule -DisplayGroup "Remote Desktop" -Profile Any`. The address filter still limits it to the tailnet |
| P50 shows offline in Tailscale after a reboot | Run unattended is off | Turn it on (Phase 1, step 2), then sign in at the P50 once |
| "Your credentials did not work" | Wrong username format, or a PIN instead of the password | Local account: `grego`. Microsoft account: the email plus its password |
| Duo denies with a user or access error | Duo username doesn't match, or User access not granted | Check the username in the Authentication Log; recheck Phase 3, steps 2 and 3 |
| Laptop still gets a Duo prompt | Duo sees a different IP, policy not applied, or plan lacks authorized networks | Phase 4, step 7; Policy Calculator; confirm your Duo plan |
| Microsoft account login breaks after Duo | Known Duo limitation with Microsoft accounts | Switch `grego` to a local account. Don't use Duo's registry workaround: it lets Microsoft accounts skip Duo entirely ([Duo FAQ](https://duo.com/docs/rdp-faq)) |

### If you're locked out

- **Remotely, phone lost or Duo down:** at the Duo prompt choose Passcode and enter a bypass code from Phase 3, step 4.
- **At the P50 itself:** this shouldn't happen with RDP-only mode on. If it does, boot into Safe Mode, which skips Duo, and uninstall it from Programs and Features. You may need the BitLocker recovery key.

### Sources

- [Duo Authentication for Windows Logon and RDP: instructions](https://duo.com/docs/rdp)
- [Duo Windows Logon FAQ](https://duo.com/docs/rdp-faq)
- [Duo policy documentation](https://duo.com/docs/policy)
- [Tailscale grant examples](https://tailscale.com/docs/reference/examples/grants.md)
