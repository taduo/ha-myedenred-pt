# Contributing

Thanks for helping with `ha-myedenred-pt`.

## Local Setup

Use a project-local virtual environment if you want to run checks locally:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements_test.txt
```

Home Assistant installs the runtime dependency from
`custom_components/myedenred_pt/manifest.json` in its own environment, so you
do not need to install that package globally on your machine.

## Validation

From the repository root:

```bash
PYTHONPYCACHEPREFIX=.pycache python3 -m compileall custom_components tests
python -m pytest
```

Local test runs expect Python `3.12` or newer.

## Change Guidelines

- Keep changes focused and easy to review.
- Add or update tests when changing config flow, auth handling, API parsing, or
  sensor attributes.
- Update translations when adding new config-flow errors or user-visible strings.
- Prefer Home Assistant patterns already used in this repo instead of
  introducing parallel abstractions.

## Security-Sensitive Areas

Please be extra careful around:

- credential handling in `config_flow.py`
- token and session handling in `client.py`
- upstream URLs and request parameters
- anything that could leak private account data into logs or state

When touching credential handling:

- normalize `Username` before storage or comparison
- preserve `Password` exactly as entered
- do not log credentials, tokens, or full card numbers
- treat upstream auth messages as untrusted user-facing content

## Pull Requests

Helpful PRs usually include:

- a short explanation of the user-visible change
- tests or a note explaining why tests were not added
- any observed upstream MyEdenred login or API assumptions
