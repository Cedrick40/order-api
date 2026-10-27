# Secure Order Processing API

A REST API for managing products, customers, orders and inventory for a small retail shop. It focuses on **correctness and safety**: stock can never be oversold, every change is traceable to a user, and access is controlled by role.

Built as Project 1 of the Arrowstack Backend Development internship (Oct 2026).

## What it does

- **Accounts and roles:** register, log in with JWT, three roles (`customer`, `staff`, `admin`)
- **Catalog and stock:** staff manage products and inventory; customers see only active products and an in-stock flag, never exact quantities
- **Orders:** place, view, confirm and cancel orders. Placing an order is **atomic**: all items are reserved or nothing changes. Prices are copied into the order, so later price changes never alter past orders
- **Safe under concurrency:** stock rows are locked inside a database transaction. Twenty simultaneous buyers for five units result in exactly five orders (proven by an automated test)
- **Audit trail:** every write action records who did it, what changed (before and after) and the request ID, in the same transaction as the change
- **Consistent, friendly errors:** every error uses one JSON shape with a plain-language message
- **Interactive documentation:** Swagger UI generated from the code

## Tech stack

Python 3.11, Django 5.2, Django REST Framework, PostgreSQL, SimpleJWT, drf-spectacular, pytest, pytest-django, coverage.

## Project structure

```
order-api/
├── config/            settings and URL routing
├── apps/
│   ├── accounts/      users, roles, customer profiles, auth endpoints, permissions
│   ├── catalog/       products and inventory
│   ├── orders/        orders, order items, business rules (services.py)
│   └── audit/         audit log, request-ID middleware
├── core/              shared error handler, request context, log filter
├── tests/             automated tests
├── docs/              requirements, design, decisions, work log, evidence map
└── evidence/          screenshots and test output
```

Business rules live in `services.py` files, not in views, so they can be tested without HTTP.

## Getting started

### Prerequisites
- Python 3.11 or newer
- PostgreSQL (any recent version) and its `psql` command
- Git

### 1. Clone and install

```bash
git clone https://github.com/Cedrick40/order-api.git
cd order-api
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create the database

Open `psql` as the `postgres` user and run:

```sql
CREATE DATABASE orderapi;
CREATE USER orderapi_user WITH PASSWORD 'choose-a-password';
ALTER DATABASE orderapi OWNER TO orderapi_user;
ALTER USER orderapi_user CREATEDB;
```

`CREATEDB` lets the test suite create its temporary test database.

### 3. Configure environment variables

Copy the example file and edit it:

```bash
cp .env.example .env
```

| Variable | Meaning |
|---|---|
| `SECRET_KEY` | Random string, **at least 32 characters** (the app refuses to start otherwise) |
| `DEBUG` | `True` for local development |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | The database you created above |
| `DB_HOST`, `DB_PORT` | Usually `localhost` and `5432` |

Generate a key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

`.env` is ignored by Git and must never be committed.

### 4. Create tables and an admin account

```bash
python manage.py migrate
python manage.py createsuperuser
```

The superuser automatically gets the `admin` role.

### 5. Run

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000/api/v1/docs/** for the interactive documentation.

To call protected endpoints in Swagger: log in via `POST /auth/login`, copy the `access` value (without quotes), click **Authorize** and paste it. Access tokens last 15 minutes. Use `POST /auth/refresh` with the refresh token to get a new one.

## Roles

| Action | customer | staff | admin |
|---|---|---|---|
| Register, log in, browse active products | yes | yes | yes |
| Place orders, view own orders, cancel own orders | yes | yes | yes |
| Create/update/deactivate products, adjust stock | no | yes | yes |
| View all orders, confirm orders, cancel any order | no | yes | yes |
| Change a user's role, read the audit log | no | no | yes |

## API overview

All paths are under `/api/v1`.

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/auth/register` | public | Create a customer account |
| POST | `/auth/login` | public | Get access and refresh tokens |
| POST | `/auth/refresh` | public | Get a new access token |
| GET | `/me` | any | Own profile |
| PATCH | `/users/{id}/role` | admin | Change a user's role |
| GET | `/products` | any | List products (`?search=`, paginated) |
| GET | `/products/{id}` | any | Product detail |
| POST | `/products` | staff+ | Create product with initial stock |
| PATCH | `/products/{id}` | staff+ | Update product |
| POST | `/products/{id}/deactivate` | staff+ | Hide a product (products are never deleted) |
| GET | `/products/{id}/stock` | staff+ | View stock |
| POST | `/products/{id}/stock/adjust` | staff+ | Add or remove stock with a reason |
| POST | `/orders` | any | Place an order |
| GET | `/orders` | any | List own orders (staff+: all) |
| GET | `/orders/{id}` | any | Order detail |
| POST | `/orders/{id}/confirm` | staff+ | PENDING to CONFIRMED |
| POST | `/orders/{id}/cancel` | owner / staff+ | Cancel and restore stock |
| GET | `/audit-logs` | admin | Filters: `entity_type`, `entity_id`, `action`, `actor`, `date` |

### Example: place an order

```bash
curl -X POST http://127.0.0.1:8000/api/v1/orders \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"items": [{"product_id": 1, "quantity": 2}]}'
```

Response `201`:

```json
{
  "id": 17,
  "status": "PENDING",
  "total_amount": "100.00",
  "customer_name": "Jane Doe",
  "created_at": "2026-10-13T08:00:00Z",
  "items": [
    {"product_id": 1, "name": "Rice 5kg", "quantity": 2, "unit_price": "50.00", "line_total": "100.00"}
  ]
}
```

The client sends only product ids and quantities. Prices, totals and status are always decided by the server.

### Error format

Every error has the same shape. `message` is written for people, `code` is for programs.

```json
{
  "error": {
    "code": "INSUFFICIENT_STOCK",
    "message": "Sorry, we only have 3 of Rice 5kg in stock, and you asked for 5.",
    "details": {"product_id": 1, "available": 3, "requested": 5}
  }
}
```

| Situation | HTTP | `code` |
|---|---|---|
| Invalid input | 400 | `VALIDATION_ERROR` |
| Same product on two lines of one order | 400 | `DUPLICATE_PRODUCT` |
| Unknown or inactive product in an order | 400 | `PRODUCT_UNAVAILABLE` |
| Missing or expired token | 401 | `NOT_AUTHENTICATED` |
| Wrong role | 403 | `PERMISSION_DENIED` |
| Not found (including another customer's order) | 404 | `NOT_FOUND` |
| Not enough stock | 409 | `INSUFFICIENT_STOCK` |
| Invalid status change | 409 | `INVALID_STATUS_TRANSITION` |
| Unexpected server error | 500 | `SERVER_ERROR` (includes a `request_id`, never a stack trace) |

## Running the tests

```bash
pytest -v
coverage run -m pytest
coverage report -m
```

Current result: **57 tests passing, 96% coverage** of `apps/` and `core/` (update these numbers if you add tests). Highlights:

- `tests/test_concurrency.py`: 20 simultaneous buyers, 5 units of stock, exactly 5 orders succeed
- `tests/test_orders.py::test_crash_midway_rolls_back_stock_and_order`: a failure in the middle of an order leaves no trace
- `tests/test_catalog.py::test_database_itself_refuses_negative_stock`: the database independently refuses bad data
- `tests/test_audit.py::test_every_write_action_produces_exactly_one_audit_entry`

The mapping from every requirement to its evidence is in [`docs/03-evidence-map.md`](docs/03-evidence-map.md).

## Security notes

- Passwords are hashed by Django (PBKDF2); access tokens last 15 minutes, refresh tokens 1 day
- Role checks live in reusable permission classes; customers can never read other customers' orders
- Price and stock rules are enforced twice: in code and as database CHECK constraints
- Secrets come from environment variables; the app refuses to start with a weak `SECRET_KEY`
- Unexpected errors return a generic message plus a request ID; details go only to the server log
- Logs record method, path, status, duration and user id, never request bodies, passwords or tokens
- Use only simulated data. This project is **not production-ready** (see limitations)

## Observability

- Every response carries an `X-Request-ID` header (a client-supplied ID is accepted only if it is a simple safe string)
- Server logs go to the console and `logs/app.log`, tagged with the request ID
- Each audit entry stores the same request ID, so one problem can be traced from the log line to the exact data change

## Design decisions

All design choices and their reasons are in [`docs/decisions.md`](docs/decisions.md). The data model, endpoint design and order flow are in [`docs/02-design.md`](docs/02-design.md).

## Known limitations

- **Accidental double submission:** two identical orders sent seconds apart both succeed (separate orders for the same product are allowed on purpose). An idempotency key would fix this
- **Pending orders hold stock** until confirmed or cancelled; there is no automatic expiry
- **An admin can change their own role,** including demoting the last admin
- **Staff and admin accounts** appear under their email address as the customer name on their own orders
- **No logout / token blacklist:** a refresh token stays valid until it expires
- **No rate limiting** on login attempts
- **Audit immutability is enforced in code and in the API,** but someone with direct database access could still alter rows
- No payments, shipping, notifications, frontend, multi-warehouse or multi-currency support (out of scope by design)

## Next steps

1. Idempotency key on `POST /orders`
2. Block self-demotion and protect the last admin
3. Refresh-token blacklist and login rate limiting
4. Automatic expiry of abandoned pending orders
5. Database trigger to make audit rows truly append-only
6. Docker Compose setup and a CI pipeline running the tests on every push
7. For 10x load: indexes on hot queries, cached product reads, read replica, and writing audit entries through a queue

## Project documents

| File | Contents |
|---|---|
| `docs/01-requirements.md` | Stakeholder, scope, requirements, success metrics |
| `docs/02-design.md` | Architecture, data model, endpoints, order flow |
| `docs/03-evidence-map.md` | Every requirement mapped to tests and screenshots |
| `docs/04-demo-and-submission.md` | Demo script, viva preparation, LinkedIn and resume text |
| `docs/decisions.md` | Decision log |
| `docs/worklog.md` | Dated work log |
| `evidence/` | Screenshots and test output |

## Author

Cedrick Niyibikora 
GitHub: https://github.com/Cedrick40 
LinkedIn: https://linkedin.com/in/cedrick10