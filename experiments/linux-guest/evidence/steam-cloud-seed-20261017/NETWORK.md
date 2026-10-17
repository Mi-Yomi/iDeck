# Exact download destinations and owner-side network settings

The observed failures are recorded in the preceding
[`steam-cloud-20261017` evidence](../steam-cloud-20261017/README.md).
No failed download was retried and no network/security configuration was changed
while preparing this clarification. These are ordinary official URLs, without
credentials, query strings or signed private redirect URLs.

| Request | Exact observed hostname and URL | Observation |
| --- | --- | --- |
| First locked Steam component | `client-update.fastly.steamstatic.com` — `https://client-update.fastly.steamstatic.com/bins_hardware_all.zip.58d828f4b4d9969be201b7731579a74bae0c3ea8` | Python installer exited 1: `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>`. No ZIP received; the HTTPS tunnel failed before an origin response. |
| GUI Release metadata and binary request | `api.github.com` — `https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/650023557` | Existing shell `gh api` returned `Get "https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/650023557": Forbidden`, including with `Accept: application/octet-stream`. No HTTP status/body or redirect destination was received. This is not proof of GitHub credential rejection or of the same exact tunnel error as Steam. |

The existing GitHub connector independently returned valid asset metadata with
the expected size and digest. That connector's fetch capability rejects binary
responses. An allowlist change does not itself add binary support to that tool.

For the current locked download operation, the minimum destination allowlist is:

| Hostname | Allowed operation | Scope |
| --- | --- | --- |
| `client-update.fastly.steamstatic.com` | HTTPS 443, GET | The 17 exact component paths in `locked-downloads.json`; all are pinned by size/SHA-256 in `ipa/steam-client.lock.json`. |
| `api.github.com` | HTTPS 443, GET | Only `/repos/Mi-Yomi/iDeck/releases/assets/650023557` is needed for this GUI asset route, using the existing authorized repository connection. |
| `release-assets.githubusercontent.com` | HTTPS 443, GET | GitHub's documented release-asset delivery host, if the API returns a redirect. Its actual asset URL/redirect was **not observed** in this task. |

`GET` is sufficient for the downloaders. `HEAD` may optionally be allowed for
diagnostics. `github.com` is needed only if choosing the browser-download route
instead of the API route; its ordinary, non-signed URL is
`https://github.com/Mi-Yomi/iDeck/releases/download/ideck-debian-gui-v1-local-20261017/ideck-debian-gui-v1.tar`.
It is already used by the working Git transport but was not tested as a binary
fallback. Do not broaden to wildcard Steam/GitHub domains. The other two Steam
redirect hosts allowed by installer code are not required by the current URLs
and no redirect to them was observed.

The Steam manifest URL is
`https://client-update.fastly.steamstatic.com/steam_client_steamdeck_publicbeta_linuxarm64`.
It is lock provenance; the existing `download` operation uses the committed lock
and does **not** fetch or update that manifest. No new manifest capture is needed.
This allowlist covers locked downloads only, not Valve self-update, login,
Store/Community, games or an eventual Steam guest runtime network policy.

The owner/environment administrator should review the selected cloud
environment's **Internet access** controls: enable **Allow Codex to access
internet**, keep a restricted domain mode, add the three exact hosts under
**Additional allowed domains**, and permit GET to the paths above over HTTPS.
Save/publish or republish through the normal environment UI, then verify in a
new task if required by the platform. Workspace **Agent Security** requirements
also apply and may require an administrator's narrow exception. This session
already reports network enabled; the effective upstream rule causing each
denial is not visible here, so these changes are a configuration request, not
a guaranteed diagnosis. See [OpenAI cloud environment documentation](https://learn.chatgpt.com/docs/environments/cloud-environments).

Apply only the network configuration through those controls. Keep the environment
private and do not include task disks or Steam client/cache bytes in a shared
image, published artifact or environment snapshot. Preserve existing approved
Git/Debian access rather than replacing its policy with this download-only list.

If the environment exposes HTTP-method restrictions, GET is enough; no broader
write-method access is needed for downloads. The older cloud interface documents
method filters separately in [OpenAI internet-access documentation](https://learn.chatgpt.com/docs/cloud/internet-access).
The managed HTTPS proxy must allow its normal tunnel to the approved destinations
on port 443. Keep that proxy and normal TLS verification. No direct-connect,
proxy substitution, system firewall/LSM/sysctl, CEF sandbox or guest security
change is requested or performed. No new token/network secret is needed by the
public Steam CDN. Preserve existing authorized GitHub access; do not share or
create tokens in chat.

GitHub documents either direct binary delivery or a 302 redirect for this API
operation and requires repository **Contents: read** for private resources:
[release asset API](https://docs.github.com/en/rest/releases/assets#get-a-release-asset).
The release delivery hostname is documented in
[GitHub's network requirements](https://docs.github.com/en/actions/reference/runners/github-hosted-runners#communication-requirements-for-github-hosted-runners).
Those documents establish the potential redirect host; they do not establish an
actual redirect for this blocked task. No signed URL is retained or disclosed.
