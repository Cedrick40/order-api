# Decision Log
- 2026-10-07 D2: Duplicate product lines in an order are not auto-merged; the API asks the user whether it was a mistake. Reason: avoids accidental extra quantity.
- 2026-10-07 D3: Error messages are written in plain language. Reason: clear to users, and does not reveal whether another customer's order exists.