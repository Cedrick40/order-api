# 01 — Requirements: Secure Order Processing API

| | |
|---|---|
| **Author** | Cedrick Niyibikora |
| **Date** | 2026-10-07 |
| **Version** | 0.1 (draft) |
| **Project** | Arrowstack Backend Development Internship, Project 1 |
| **Stack** | Python, Django, Django REST Framework, PostgreSQL, JWT |

---

## 1. Purpose and business context

Small retail businesses often track stock and orders in notebooks or spreadsheets. This causes **overselling** (two customers buy the last item), **untraceable changes** (nobody knows who edited stock), and **no access control** (everyone sees everything).

This project delivers a REST API that manages products, customers, orders and inventory, with validation, role-based authorization, transactional order processing and an audit trail.

**Primary stakeholder (assumed):** the owner/manager of a small retail shop.
**Decision the output enables:** "Can I trust my stock numbers and see exactly who changed what?"
**Measurable benefit:** zero oversold items and 100% of changes traceable to a user.

> **Assumption A1:** the stakeholder is a fictional small retail shop. All data is simulated (no real customer data).

---

## 2. Users and roles

| Role | Who | Can do |
|---|---|---|
| `customer` | Shopper | Register, browse active products, place orders, view/cancel **own** orders |
| `staff` | Shop employee | Everything a customer can, plus manage products, adjust stock, view all orders, confirm orders |
| `admin` | Owner/manager | Everything staff can, plus manage users/roles and read the audit log |

---

## 3. Scope

### In scope
- User registration, login, token refresh (JWT)
- Role-based access control
- Product and customer management
- Inventory tracking with stock adjustments
- Order placement, viewing, confirmation and cancellation
- Audit log of all state-changing actions
- Uniform, structured error responses
- Automated tests and auto-generated API documentation

### Out of scope (deliberately)
- Payments and invoicing
- Shipping and delivery tracking
- Email/SMS notifications (Project 2 covers notifications)
- Frontend or mobile UI
- Multi-warehouse or multi-currency support

---

## 4. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| **Auth** | | |
| FR-01 | A user can register with email and password (password min 8 chars, validated) | Must |
| FR-02 | A user can log in and receive access + refresh JWT tokens | Must |
| FR-03 | A user can obtain a new access token using a valid refresh token | Must |
| FR-04 | Every endpoint except register/login requires authentication | Must |
| FR-05 | Access is restricted by role as defined in Section 2 | Must |
| **Catalog** | | |
| FR-06 | Staff/admin can create, update and deactivate products (name, SKU, price) | Must |
| FR-07 | SKU must be unique; price must be greater than 0 | Must |
| FR-08 | Any authenticated user can list and view **active** products (paginated) | Must |
| **Inventory** | | |
| FR-09 | Each product has exactly one inventory record with a non-negative quantity | Must |
| FR-10 | Staff/admin can adjust stock (add/remove) with a stated reason; stock can never go below 0 | Must |
| **Orders** | | |
| FR-11 | A customer can place an order with one or more items (product + quantity ≥ 1) | Must |
| FR-12 | Order placement is **atomic**: all items are reserved and the order is created, or nothing changes | Must |
| FR-13 | If any item has insufficient stock, the whole order is rejected with a clear error | Must |
| FR-14 | Each order item stores a **price snapshot** so later price changes don't alter past orders | Must |
| FR-15 | Order total is calculated by the server, never trusted from the client | Must |
| FR-16 | A customer sees only their own orders; staff/admin see all | Must |
| FR-17 | Staff/admin can confirm a `PENDING` order | Must |
| FR-18 | A `PENDING` or `CONFIRMED` order can be cancelled; cancelling restores stock | Must |
| FR-19 | Invalid status transitions are rejected (e.g. cancelling an already-cancelled order) | Must |
| **Audit** | | |
| FR-20 | Every create/update/delete/stock change/order action writes an audit entry (actor, action, entity, before/after, timestamp, request ID) | Must |
| FR-21 | Only admin can read audit entries; entries cannot be edited or deleted through the API | Must |
| **Errors & validation** | | |
| FR-22 | All errors use one JSON shape: `{"error": {"code", "message", "details"}}` | Must |
| FR-23 | All input is validated server-side; invalid input returns 400 with field-level details | Must |
| **Nice-to-have (extension candidates)** | | |
| FR-24 | Rate limiting on login | Could |
| FR-25 | `/health` and basic metrics endpoint | Could |
| FR-26 | Low-stock threshold flag | Could |

### Order status flow
```
PENDING ──confirm──> CONFIRMED
   │                    │
   └────cancel──────────┴────> CANCELLED (stock restored)
```

---

## 5. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-01 | Passwords are hashed (never stored or logged in plain text) |
| NFR-02 | Access tokens are short-lived (e.g. 15 minutes) |
| NFR-03 | Production-style error responses never expose stack traces |
| NFR-04 | Logs are structured and include a request ID |
| NFR-05 | List endpoints are paginated |
| NFR-06 | Automated test coverage of core modules ≥ 85% |
| NFR-07 | A mentor can set up and run the project using only the README |
| NFR-08 | Secrets (DB password, signing key) come from environment variables, never from Git |

---

## 6. Success metrics (how we will prove it works)

| # | Metric | Target | Evidence |
|---|---|---|---|
| M1 | Overselling under concurrency | 20 parallel orders for 5 units → exactly 5 succeed, stock = 0, never negative | Concurrency test output |
| M2 | Audit completeness | 100% of write actions produce one audit row | Audit test results |
| M3 | Error consistency | 100% of error responses match the standard shape | Error-handling tests |
| M4 | Access control | Customer A can never read Customer B's order | Permission tests |
| M5 | Test coverage | ≥ 85% on core modules | Coverage report |
| M6 | Reproducibility | Fresh clone runs from README in under 15 minutes | Fresh-clone check log |

---

## 7. Constraints and assumptions

- **C1:** Individual work, roughly 8 days for this project within a 4-week internship (Oct 1 – Nov 1, 2026).
- **C2:** Free, open-source tools only.
- **C3:** Only simulated data; no real customer information.
- **A2:** Single currency, single warehouse, single shop.
- **A3:** Stock is **reserved at order placement** (deducted immediately) rather than at confirmation.
- **A4:** Deactivated products are hidden from customers but remain in historical orders.

---

## 8. Edge cases to handle

- Order with an empty items list
- Quantity of 0, negative, or non-integer
- Same product listed twice in one order: the API does not create the order; it replies with a clear message asking whether this was a mistake and how to fix it (see D2)
- Unknown or deactivated product in an order
- Two customers ordering the last unit simultaneously
- Cancelling an order twice
- Customer requesting another customer's order: the API replies with a plain-language message ("We couldn't find that order on your account") that does not reveal whether the order exists (see D3)
- Expired, malformed or missing token
- Stock adjustment that would go negative
- Price changed after the order was placed

---

## 9. Acceptance criteria → evidence map

*(Evidence column is filled in as the project progresses.)*

| Requirement | Verified by | Evidence file | Status |
|---|---|---|---|
| FR-01 – FR-05 | Auth and permission tests | | ☐ |
| FR-06 – FR-10 | Catalog and inventory tests | | ☐ |
| FR-11 – FR-19 | Order tests incl. concurrency | | ☐ |
| FR-20 – FR-21 | Audit tests | | ☐ |
| FR-22 – FR-23 | Validation and error tests | | ☐ |
| NFR-06 | Coverage report | | ☐ |
| NFR-07 | Fresh-clone run | | ☐ |

---

## 10. Risks

| Risk | Mitigation |
|---|---|
| Scope creep | Out-of-scope list above; extensions only after core is done |
| Race conditions on stock | Row locking inside a database transaction + concurrency test |
| Documentation left to the end | Dated work log updated every session |
| Overrunning time and starving Projects 2 and 3 | Hard stop at Day 8 |

---

## 11. Decisions

| ID | Decision | Reason |
|---|---|---|
| D1 | Keep the generic small retail shop as the stakeholder *(default, change if you prefer)* | Keeps scope simple |
| D2 | If the same product appears twice in one order, do not create the order. Reply: "Product X appears twice (lines 1 and 3). Was this a mistake? Combine them into one line with quantity N and send again." | Protects the customer from accidental double quantities; the API is stateless, so the user fixes and resubmits |
| D3 | Error messages always give a clear, human-readable reason. The HTTP status code is still sent for programs, but the `message` field is written for people. For someone else's order the message is "We couldn't find that order on your account." | Friendly to users without leaking whether another customer's order exists |
| D4 | One customer profile per user login *(default, change if you prefer)* | Simplest model; every order has an authenticated owner |