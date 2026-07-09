# Safe Browser Capture for MyEdenred

Use this guide to confirm the live MyEdenred endpoints without sharing private
data.

## Important Safety Rules

Never send any of these values:

- your email or username
- your password
- cookies
- authorization tokens
- full card numbers
- balances
- transaction descriptions
- names or personal details

If you see any of those values, replace them before sharing:

- username or email -> `<username>`
- password -> `<password>`
- token or authorization value -> `<token>`
- cookie value -> `<cookie>`
- card number -> `<card_number>`
- card id -> `<card_id>`
- balance -> `<balance>`
- personal name -> `<name>`

Do not upload a full HAR file. HAR files often contain secrets.

## What We Need

We only need confirmation of:

1. the login endpoint
2. the MFA challenge and resend endpoints, when present
3. the cards list endpoint
4. the balance detail endpoint
5. whether the site uses JSON or only HTML for the balance

## Browser Steps

These steps work in Chrome, Edge, and most Chromium browsers.

1. Open a new private or incognito window.
2. Open [https://www.myedenred.pt/](https://www.myedenred.pt/).
3. Press `F12` to open Developer Tools.
4. Open the `Network` tab.
5. Turn on `Preserve log`.
6. Turn on `Disable cache` if that option is visible.
7. In the filter box, type `api` first.
8. Sign in normally.
9. After login finishes, look for requests matching these likely paths:
   - `/edenred-customer/v2/authenticate/default`
   - `/edenred-customer/v2/authenticate/default/challenge`
   - `/edenred-customer/v2/authenticate/challenge/resend`
   - `/edenred-customer/v2/protected/card/list`
   - `/edenred-customer/v2/protected/card/<card_id>/accountmovement`
10. If those do not appear, clear the filter and look for:
   - `authenticate`
   - `card`
   - `movement`
   - `balance`
   - `myCards`

## What To Copy Safely

For each relevant request, copy only:

- request method
- request URL path
- HTTP status
- request query parameter names only
- request body key names only
- response top-level JSON key names
- one level of nested key names under `data`

Do not copy actual values.

## Safe Examples

### Login request

Safe:

```text
POST /edenred-customer/v2/authenticate/default
Status: 200
Query params: appVersion, appType, channel
Request JSON keys: userId, password
Response JSON keys: data, message
Response data keys: token, customer, appVersionInfo, onBoardApplied
Authorization style after login: raw token header
```

For MFA-enabled accounts, the first login response can safely be described as:

```text
POST /edenred-customer/v2/authenticate/default
Request JSON keys: userId, password
Response data keys: challengeId, challengeMessage, resendTries

POST /edenred-customer/v2/authenticate/default/challenge
Request JSON keys: userId, password, authenticationMfaProcessId, token
Response data keys: token, customer, appVersionInfo, onBoardApplied

POST /edenred-customer/v2/authenticate/challenge/resend
Request JSON keys: authenticationMfaProcessId
Response data keys: challengeId, challengeMessage, resendTries
```

Do not include the challenge ID, verification code, challenge message, or
returned token. Even masked destination messages should be replaced with
`<masked_destination>`.

Unsafe:

```text
POST /edenred-customer/v2/authenticate/default?appVersion=1.0
Body: {"userId":"myemail@example.com","password":"secret"}
Response: {"data":{"token":"eyJ...","customer":{"name":"..."} } }
```

### Cards list request

Safe:

```text
GET /edenred-customer/v2/protected/card/list
Status: 200
Request headers present: Authorization
Response JSON keys: data, message
Response data item keys: id, number, ownerName, status, product, productDetails
```

### Account movement or balance request

Safe:

```text
GET /edenred-customer/v2/protected/card/<card_id>/accountmovement
Status: 200
Request headers present: Authorization
Response JSON keys: data, message
Response data keys: account, movementList
Response data.account keys: cardNumber, availableBalance, cardHolderFirstName, cardHolderLastName, cardActivated, iban
Response data.movementList item keys: transactionDate, transactionName, amount, balance, category, transactionType
```

## If You Only See HTML

If no useful JSON requests appear, check the main page after login:

1. Click the document request for the logged-in page.
2. Open `Response`.
3. Search for `card-balance` or `autoNumeric`.
4. Only report whether this selector exists:
   - `.card-balance.autoNumeric`
5. If you can, report whether there is one balance element or several.

Do not paste the whole page.

Safe example:

```text
No usable JSON balance endpoint found.
Authenticated HTML contains `.card-balance.autoNumeric`.
Visible balance elements: 2
```

## Reply Template

Reply in this exact format and replace anything sensitive with placeholders:

```text
Login
- Method:
- Path:
- Status:
- Query param names:
- Request JSON keys:
- Response top-level keys:
- Response data keys:

MFA challenge
- Challenge required: yes/no
- Validation method and path:
- Validation request JSON keys:
- Validation response top-level keys:
- Validation response data keys:
- Resend method and path:
- Resend request JSON keys:
- Resend response data keys:

Cards list
- Method:
- Path:
- Status:
- Header names present:
- Response top-level keys:
- Response data item keys:

Balance detail
- Method:
- Path:
- Status:
- Header names present:
- Response top-level keys:
- Response data keys:
- Response account keys:
- Response movement item keys:

Fallback HTML
- JSON endpoints found: yes/no
- `.card-balance.autoNumeric` present: yes/no
- Number of visible balance elements:
```

## Minimum We Need To Move Forward

If you want the shortest possible capture, send only:

- login path
- cards list path
- balance detail path
- whether `Authorization` is required
- whether `.card-balance.autoNumeric` exists after login
