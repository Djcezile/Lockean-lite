# Private ntfy Mobile Push

- Date: 2026-10-09
- Status: accepted
- Scope: watchdog delivery only; no trading-policy change

## Context

The first unattended-automation release exposed a destination-agnostic HTTPS
webhook and its setup text suggested common team-chat webhooks. The operator
does not use Slack or Google Workspace and requested SMS or phone push.

Direct SMS would require a provider account, a sending number or service,
billable message delivery, phone-number handling, and at least one additional
credential. Those dependencies add no trading evidence and are unnecessary for
the immediate goal: a visible lifecycle alert on the operator's phone.

## Decision

Use the hosted `ntfy.sh` service for the first mobile-push destination:

1. `Set-LockeanLitePush.ps1` creates 32 bytes (256 bits) with the platform
   cryptographic random-number generator.
2. The bytes form a private topic named `lockean-<64 lowercase hex digits>`.
3. The full HTTPS destination is converted to a `SecureString` and exported
   with current-user Windows DPAPI to the existing notification secret path.
4. The topic is shown once and copied to the Windows clipboard so the operator
   can subscribe in the ntfy mobile app.
5. `notification.py` recognizes only an exact `ntfy.sh` host with one topic
   path of at least 32 safe characters and no port, credentials, query, or
   fragment. It sends the fixed sanitized alert as UTF-8 text with a static
   title and high priority.
6. Other HTTPS webhook destinations keep the existing JSON `text` payload.

ntfy documents that topics are created on demand, require no sign-up on the
public server, and must be treated like passwords because anyone who knows the
topic can publish or subscribe:

- <https://docs.ntfy.sh/publish/>
- <https://docs.ntfy.sh/subscribe/phone/>

## Security boundary

The random topic is a bearer secret, not an authenticated private mailbox. Its
256-bit random suffix provides confidentiality through unguessability; it must
not be committed, logged, screenshotted, or pasted into chat. The destination
is protected at rest by the same user-scoped DPAPI boundary as the original
webhook configuration. Transport errors expose only stable local error codes.

Alert content remains intentionally account-independent: event code, market
date, and a fixed lifecycle explanation. It excludes credentials, endpoint,
account identifiers, balances, positions, raw exceptions, and broker payloads.

The public ntfy service is an external delivery dependency. It learns the
delivery request's network metadata and notification content. A self-hosted or
authenticated relay can replace it later without changing the watchdog event
model.

## Consequences

- The operator gets native mobile push without Slack, Google Workspace, an SMS
  provider, or a new account.
- The phone must install ntfy and subscribe to the generated topic before the
  deployment verification test.
- Re-running the push setup rotates the topic; the phone must subscribe to the
  newly displayed value before re-verification.
- This improves delivery destination, not host independence. If the Windows
  host is off or offline, the local watchdog still cannot publish an alert.
- SMS remains deferred unless push proves inadequate enough to justify its
  account, credential, privacy, and cost overhead.

## Verification evidence required

The deployment remains fail-closed. Activation requires the exact commit to
pass the complete regression suite, dry-run scheduler gate, simulated event,
and a live `watchdog_test` delivery. The operator confirms the phone received
that live push before treating notification setup as complete.
