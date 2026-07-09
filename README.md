# MyEdenred Portugal for Home Assistant

Unofficial Home Assistant custom integration for MyEdenred Portugal. It signs in
to the MyEdenred web services used by the Portugal portal, reads the current
available balance for each returned card, and exposes those balances as Home
Assistant sensors in EUR.

This project is not affiliated with or endorsed by Edenred.

## Project Docs

- [Security policy](SECURITY.md)
- [Contributing guide](CONTRIBUTING.md)
- [Safe browser capture guide](docs/safe-browser-capture.md)

## Features

- UI-based setup from `Settings > Devices & Services`
- Native support for MyEdenred's 5-digit verification-code login
- Stores your credentials and active session token in the Home Assistant config entry
- Refreshes card balances on a configurable interval, with 30 minutes as the default
- Starts a Home Assistant reauthentication flow when the session expires
- Creates one balance sensor per returned MyEdenred card
- Available through HACS

## Current Scope

Version `0.2.0` currently includes:

- available balance for each returned Portugal card
- masked card number as a sensor attribute
- card status when the upstream response provides it
- configurable refresh interval from the options flow

Out of scope for now:

- recent transactions
- card lifecycle actions

## Installation

### HACS

Once the integration appears in the HACS default catalog, search for
`MyEdenred Portugal` in `HACS > Integrations`, install it, and restart Home
Assistant.

Until that external review and catalog scan are complete, install it as a HACS
custom repository instead:

[![Open this repository in Home Assistant HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=taduo&repository=ha-myedenred-pt&category=Integration)

1. Open HACS in Home Assistant.
2. Go to `Integrations`.
3. Open the three-dot menu and choose `Custom repositories`.
4. Add `https://github.com/taduo/ha-myedenred-pt`.
5. Choose category `Integration`.
6. Search for `MyEdenred Portugal` in HACS and install it.
7. Restart Home Assistant.

### Manual install

1. Copy the `custom_components/myedenred_pt` folder into your Home Assistant
   `custom_components` directory.
2. Restart Home Assistant.

## Configuration

1. In Home Assistant, open `Settings > Devices & Services`.
2. Click `Add Integration`.
3. Search for `MyEdenred Portugal`.
4. Enter your MyEdenred `Username` and `Password`.
5. Enter the 5-digit verification code sent by MyEdenred.
6. Finish the flow and wait for the first refresh.

If the session later expires, Home Assistant marks the integration as requiring
reauthentication. Open the integration, confirm that MyEdenred should send a
new code, and enter that code. If the account password has changed, the same
flow prompts for the new password before sending the code.

The integration creates one sensor per returned card:

- `Available balance`

Each sensor also exposes these attributes:

- `balance_text`
- `masked_card_number`
- `card_status`
- `data_source`
- `last_refresh`

## Options

After the integration is added, you can change the refresh interval from the
integration options in Home Assistant.

Available presets:

- `15 minutes`
- `30 minutes`
- `60 minutes`
- `120 minutes`

## Notes About Login

The current implementation now matches a sanitized browser capture taken on
July 9, 2026 from the live Portugal portal:

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

The frontend app also sends these query params with API requests:

- `appVersion=1.0`
- `appType=PORTAL`
- `channel=WEB`

Protected JSON requests use the raw session token in the `Authorization`
header. If those endpoints change or stop returning usable JSON, the integration
also contains a fallback HTML balance parser for the observed dashboard
selector `.card-balance.autoNumeric`.

Password login may return either a session token directly or an MFA challenge.
For a challenge, the integration asks for MyEdenred's 5-digit code and exchanges
it for the session token. Polling never attempts password login, so an expired
token cannot cause unsolicited verification messages; it instead starts Home
Assistant's standard reauthentication process.

The password and session token are stored in the Home Assistant config entry.
Protect Home Assistant backups and the `.storage` directory accordingly.

If MyEdenred adds mandatory CAPTCHA or significantly changes the login flow,
this integration may need to be updated.

## Local Validation

From the repository root:

```bash
PYTHONPYCACHEPREFIX=.pycache python3 -m compileall custom_components tests
```

If you want to run the test suite locally, use a project-only virtual
environment so the installs stay inside this repository and do not affect your
other Python work. Local validation expects Python 3.12 or newer.

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements_test.txt
python -m pytest
deactivate
```

Home Assistant installs any runtime dependencies declared in
`custom_components/myedenred_pt/manifest.json` inside its own environment, so
you do not need to install project dependencies globally on your machine.

## Legal

Use this integration at your own risk. Balance data comes from the MyEdenred
Portugal portal and can change if the site or authentication flow changes.
