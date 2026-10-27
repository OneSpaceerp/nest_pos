# Nest POS

Retail point of sale for ERPNext v16 by **nsdLabs** (Nest Software Development · info@nsd-eg.com).

- Fast till: catalog, keyboard-wedge and camera scanning, receipt-tape cart, split tender with change,
  hold/resume, returns against original rows, X report and blind/denominated closing.
- Native accounting: direct Sales Invoices (default) or POS Invoices with ERPNext consolidation. ERPNext posts
  every ledger row.
- Shopper PWA (`/nest-pos/customer/`): price check by scanning, basket hand-off code, cashier inbox with atomic
  claim and exactly-once import.
- Phone as a paired scanner for a desktop cart.
- Offline cash sales through a durable outbox with server re-validation and a review queue.
- English and Arabic (RTL), light and dark, installable staff and shopper PWAs, and a Desk page inside
  Frappe's own Dock and Sidebar.

Docs (in the Nest source tree): `docs/installation.md`, `docs/architecture.md`, `docs/feature-parity-matrix.md`,
`docs/verification.md`, `docs/offline-policy.md`, `docs/api.md`.

Requires Frappe and ERPNext v16.52+ (v16 only). Works with or without Nest Restaurant on the same site.

**Status:** integration-test verification on a real bench is still pending — see `docs/verification.md`.

Code under `nest_pos/core/`, `nest_pos/kit/` and `frontend/src/shared/` is vendored from `nest_shared/`; edit it
there and run `tools/vendor_shared.py`.

Licence: not yet decided by the publisher; see `license.txt`.
