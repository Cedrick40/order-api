# Work Log
## 2026-10-07
- Read the handbook and wrote the feasibility study.
- Wrote requirements (docs/01-requirements.md) and settled decisions D1–D4.
- Created the repo and first commit.

- Wrote design doc (docs/02-design.md): data model, endpoints, error design, order flow, security plan.
- Recorded design decisions D5-D12 in decisions.md.

- Set up virtual environment, Django project, 4 apps, PostgreSQL database.
- Created custom User model (email login, role field) before first migration.
- First smoke test passing.

- Built core error handler with standard error shape and friendly messages.
- Built accounts: register, login (JWT), refresh, /me, admin role change.
- Added permission classes (IsStaffRole, IsAdminRole) and 10 passing tests.

- Built products and inventory (models, DB constraints, services, serializers, viewset).
- Verified manually in Swagger and with curl (DELETE returns 405).
- 28 tests passing, coverage report saved to evidence/.