# Decision Log
- 2026-10-07 D2: Duplicate product lines in an order are not auto-merged; the API asks the user whether it was a mistake. Reason: avoids accidental extra quantity.
- 2026-10-07 D3: Error messages are written in plain language. Reason: clear to users, and does not reveal whether another customer's order exists.

- 2026-10-07 D5: Custom User model with email as login, set before the first migration. Reason: changing it later is painful.
- 2026-10-07 D6: Business rules live in service functions, not in views. Reason: testable without HTTP and easy to explain.
- 2026-10-07 D7: Lock inventory rows with select_for_update inside a transaction. Reason: prevents overselling when orders arrive at the same time.
- 2026-10-07 D8: URL versioning with /api/v1/. Reason: allows future changes without breaking existing clients.
- 2026-10-07 D9: Money stored as Decimal, never float. Reason: avoids rounding errors.
- 2026-10-07 D10: Products are deactivated, never deleted. Reason: keeps order history intact.
- 2026-10-07 D11: Audit entry written in the same transaction as the change. Reason: the change and its record can never disagree.
- 2026-10-07 D12: HTTP 409 for stock and status conflicts. Reason: the request is valid but conflicts with the current state.

- 2026-10-07 D13: Secrets and DB settings come from a .env file, never from Git. A .env.example documents the variables. Reason: security and reproducibility.
- 2026-10-07 D14: Tests use pytest + pytest-django. Reason: less boilerplate than unittest and easy coverage reports.