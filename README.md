# paath-relay

Publisher for the PAATH cert relay: a GitHub Actions cron issues the `paath.duckdns.org`
certificate (ACME DNS-01 via DuckDNS), signs an owner-signed bundle, and commits
`bundle.txt`. The PAATH app fetches, verifies, and installs it. See
`docs/superpowers/specs/2026-09-01-paath-cert-relay-design.md` in the PAATH repo.

## One-time setup (owner)

1. **Create the repo** `paath-relay` (public) and copy in `renew.yml` (as
   `.github/workflows/renew.yml`), `publish.py`, and `requirements.txt`.

2. **Generate the signing keypair and AES key** (private key never leaves your machine):

   ```bash
   # ECDSA P-256 signing key (private stays local; public is pinned in the APK)
   openssl ecparam -name prime256v1 -genkey -noout -out paath-relay-signing.key
   openssl pkey -in paath-relay-signing.key -pubout -outform DER | base64 -w0 ; echo
   #   ^ this base64 string -> PaathConfig.RELAY_SIGN_PUBKEY_B64 in the PAATH app

   # 32-byte AES key (baked in the APK AND stored as an Actions secret)
   openssl rand -hex 32
   #   ^ this hex -> PaathConfig.RELAY_BUNDLE_AES_KEY_HEX AND the BUNDLE_AES_KEY secret
   ```

3. **Add repo Actions secrets** (Settings > Secrets and variables > Actions):
   - `DUCKDNS_TOKEN` — the token for the **paath-only** DuckDNS account.
   - `SIGNING_KEY_PEM` — the full contents of `paath-relay-signing.key`.
   - `BUNDLE_AES_KEY` — the hex from step 2.
   - `ACME_EMAIL` — any contact email for Let's Encrypt.

   Never commit `paath-relay-signing.key`. Delete it after storing the secret, or keep it
   offline as your only copy.

4. **Run the workflow once** (Actions > renew-paath-cert > Run workflow). Confirm
   `bundle.txt` appears and is one line of `base64.base64`.

5. **Wire the app:** paste the two values from step 2 into `PaathConfig`
   (`RELAY_SIGN_PUBKEY_B64`, `RELAY_BUNDLE_AES_KEY_HEX`), rebuild the APK.

6. **Confirm on-device** with the cert source set to Relay (Settings > Certificate >
   long-press > Relay > FETCH NOW): the log shows `relay: installed cert ...` and the car
   plays video in Drive. Only then flip `PaathConfig.DEFAULT_CERT_SOURCE` to
   `CERT_SOURCE_RELAY`.

The cron re-issues every ~60 days; installs fetch when their local cert has < 30 days left.
