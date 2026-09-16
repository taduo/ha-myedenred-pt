# MyEdenred Portugal for Home Assistant

> [!WARNING]
> **This project is archived and no longer maintained.**
>
> MyEdenred Portugal uses OTP-based authentication and the authenticated session
> expires after a short period. Testing did not find a reliable way to keep that
> session alive for unattended Home Assistant use. Requiring frequent OTP
> reauthentication defeats the purpose of the integration, so development has
> been discontinued.
>
> The source code remains available for reference and for anyone who wants to
> fork or continue the work.

Unofficial Home Assistant custom integration for MyEdenred Portugal. It signs in
to the MyEdenred web services used by the Portugal portal, reads the current
available balance for each returned card, and exposes those balances as Home
Assistant sensors in EUR.

This project is not affiliated with or endorsed by Edenred.

## Project Status

This integration is **retired** and is no longer recommended for installation.
No further releases, compatibility fixes, or authentication-flow updates are
planned.

The main blocker is the short-lived MyEdenred authenticated session. The
integration can complete the OTP login flow, but the resulting session expires
after a relatively short period and could not be kept alive reliably enough for
an unattended Home Assistant integration.

## Project Docs

- [Security policy](SECURITY.md)
- [Contributing guide](CONTRIBUTING.md)
- [Safe browser capture guide](docs/safe-browser-capture.md)

## Features in the Final Version

- UI-based setup from `Settings > Devices & Services`
- Native support for MyEdenred's 5-digit verification-code login
- Stores your credentials and active session token in the Home Assistant config entry
- Refreshes card balances on a configurable interval, with 30 minutes as the default
- Starts a Home Assistant reauthentication flow when the session expires
- Creates one balance sensor per returned MyEdenred card

## Final Scope

Version `0.2.0` included:

- available balance for each returned Portugal card
- masked card number as a sensor attribute
- card status when the upstream response provides it
- configurable refresh interval from the options flow

The following remained out of scope:

- recent transactions
- card lifecycle actions

## Installation

This integration is no longer recommended for new installations and is no
longer being developed or maintained.

The repository is retained as a reference implementation. If you want to
experiment with it, fork the repository and treat the code as unsupported.

## Historical Configuration

The integration was configured through Home Assistant using:

1. `Settings > Devices & Services`
2. `Add Integration`
3. `MyEdenred Portugal`
4. MyEdenred username and password
5. The 5-digit verification code sent by MyEdenred

When the session later expired, Home Assistant marked the integration as
requiring reauthentication. This recurring short session lifetime is the main
reason the project was retired.

The integration created one sensor per returned card:

- `Available balance`

Each sensor also exposed these attributes:

- `balance_text`
- `masked_card_number`
- `card_status`
- `data_source`
- `last_refresh`

## Options

The integration supported these refresh interval presets:

- `15 minutes`
- `30 minutes`
- `60 minutes`
- `120 minutes`

## Notes About Login

The final implementation matched a sanitized browser capture taken on July 9,
2026 from the live Portugal portal:

- login endpoint:
  `https://www.myedenred.pt/edenred-customer/v2/authenticate/default`
- verification endpoint:
  `https://www.myedenred.pt/edenred-customer/v2/authenticate/default/challenge`
- verification-code resend endpoint:
  `https://www.myedenred.pt/edenred-customer/v2/authenticate/challenge/resend`
- cards endpoint:
  `https://www.myedenred.pt/edenred-customer/v2/protected/card/list`
- balance detail endpoint:
  `https://www.myedenred.pt/edenred-customer/v2/protected/card/{id}/accountmovement`

The frontend app also sent these query params with API requests:

- `appVersion=1.0`
- `appType=PORTAL`
- `channel=WEB`

Protected JSON requests used the raw session token in the `Authorization`
header. The integration also contained a fallback HTML balance parser for the
observed dashboard selector `.card-balance.autoNumeric`.

Password login could return either a session token directly or an MFA
challenge. For a challenge, the integration asked for MyEdenred's 5-digit code
and exchanged it for the session token. Polling never attempted password login,
so an expired token did not cause unsolicited verification messages; it instead
started Home Assistant's standard reauthentication process.

The password and session token were stored in the Home Assistant config entry.
Protect Home Assistant backups and the `.storage` directory accordingly.

## Local Validation

From the repository root:

```bash
PYTHONPYCACHEPREFIX=.pycache python3 -m compileall custom_components tests
```

To run the historical test suite locally, use a project-only virtual
environment. Local validation expects Python 3.12 or newer.

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements_test.txt
python -m pytest
deactivate
```

## Legal

Use this code at your own risk. Balance data comes from the MyEdenred Portugal
portal and may no longer match the current site or authentication flow.
