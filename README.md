# Order Fulfillment & Inventory Management Platform

An enterprise-grade, secure, and scalable REST API platform engineered with **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0**, and **Alembic**.

This backend platform demonstrates advanced real-world engineering patterns including **concurrency-safe inventory reservations**, **PostgreSQL row-level locking (`with_for_update`)**, **strict order state machine enforcement**, **dual-transaction inter-warehouse transfers**, **RFC-compliant idempotency**, and **fine-grained role- and warehouse-level authorization (RBAC)**.

---

## 🌟 Key Highlights

- **Concurrency & Race Condition Safety:** Uses pessimistic row-level locking (`SELECT ... FOR UPDATE`) and deterministic product sorting to guarantee zero overselling, zero negative inventory, and complete deadlock elimination under heavy concurrent ordering.
- **Clean 5-Tier Architecture:** Complete separation of concerns:
  `Routes` ➔ `Dependencies` ➔ `Services` ➔ `Repositories` ➔ `Models` ➔ `Database`.
- **Order State Machine:** Deterministic workflow from `PENDING` to `DELIVERED`, rejecting illegal state transitions with automatic inventory release upon cancellation.
- **Atomic Stock Transfers:** Dual inventory transactions (`TRANSFER_OUT` and `TRANSFER_IN`) wrapped in an atomic database transaction.
- **Automated Restocking on Returns:** Complete customer return merchandise authorization (RMA) workflow that inspects and restocks inventory upon warehouse receipt.
- **JWT Security & Token Rotation:** Secure bcrypt password hashing, short-lived access tokens, refresh token rotation with family revocation detection, and token blacklisting on logout.
- **RFC-Compliant Idempotency:** Header-driven (`Idempotency-Key`) deduplication preventing duplicate orders and double-adjustments on network retries.
- **Immutable Audit Trail:** Append-only transaction ledger (`inventory_transactions`) and system event audit log (`audit_logs`).
- **Comprehensive Pytest Suite:** 43 automated tests covering 100% of functional requirements, RBAC boundaries, negative tests, and multi-threaded concurrency race conditions.

---

## 🛠️ Technology Stack

| Component | Technology | Description |
|---|---|---|
| **Language** | Python 3.11+ / 3.14 | Modern async Python backend |
| **Framework** | FastAPI 0.115+ | High-performance asynchronous web framework |
| **ORM** | SQLAlchemy 2.0 | Type-safe declarative database models and queries |
| **Migrations** | Alembic 1.13+ | Automated database versioning and schema migrations |
| **Validation** | Pydantic V2 | High-speed data parsing and validation |
| **Database** | PostgreSQL 16 | Primary relational database with ACID compliance |
| **Caching/Broker** | Redis 7 | Distributed locking, idempotency cache, and message broker |
| **Testing** | Pytest & pytest-asyncio | Test suite with multi-threaded concurrency verification |
| **Containerization**| Docker & Docker Compose | Containerized application, database, and cache |

---

## 🏛️ System Architecture

```
Routes (API Endpoints)
  ↓
Dependencies (JWT Auth, RBAC Role Checks, Warehouse Scoping, Idempotency)
  ↓
Services (Domain Logic, State Machines, Concurrency Orchestration, Notifications)
  ↓
Repositories (Database Queries, Pagination, SELECT ... FOR UPDATE Locks)
  ↓
Models (SQLAlchemy Declarative Schemas with Database Constraints)
  ↓
PostgreSQL 16 Engine / Alembic Migrations
```

Detailed diagrams and specifications:
- [Architecture & State Machine Documentation](docs/ARCHITECTURE.md)
- [Entity-Relationship Diagram & Schema Spec](docs/ER_DIAGRAM.md)
- [Concurrency, Transactions & Locking Strategy](docs/CONCURRENCY_STRATEGY.md)

---

## 👥 Role-Based Access Control (RBAC)

The platform enforces 4 distinct roles:

1. **Admin (`ADMIN`)**:
   - Full global access to products, warehouses, user assignments, inventory, orders, audit logs, and analytics.
2. **Warehouse Manager (`WAREHOUSE_MANAGER`)**:
   - Scoped access: Can only manage and adjust inventory for warehouses assigned to their account (`warehouse_users` table).
   - Can update warehouse details, view low-stock items, process inter-warehouse transfers, and view warehouse dashboards.
3. **Fulfillment Agent (`FULFILLMENT_AGENT`)**:
   - Scoped access: Can only view and fulfill orders belonging to authorized warehouses.
   - Executes order fulfillment states: `Start Processing` ➔ `Pack Order` ➔ `Ship Order` ➔ `Mark Delivered`.
   - Inactive agents are blocked from receiving order assignments.
4. **Customer (`CUSTOMER`)**:
   - Register, login, browse active products, place orders, cancel own orders (prior to fulfillment), request returns for delivered orders, and view own spending dashboard.

---

## 🔄 Order State Machine

Orders progress strictly through the following lifecycle. Illegal jumps (e.g., `Delivered` ➔ `Processing`) are rejected with `INVALID_ORDER_STATUS`:

```
Pending
   ↓ (Payment Confirmed)
Confirmed
   ↓ (Fulfillment Starts)
Processing
   ↓ (Items Packed)
Packed
   ↓ (Dispatched - Stock Deducted from Reserved, SALE tx logged)
Shipped
   ↓ (Delivered to Customer)
Delivered
   ↓ (Optional Return Request)
Returned
```

**Alternative Terminal States:**
- `Cancelled`: Allowed only in `Pending` or `Confirmed`. Automatically executes an atomic transaction releasing reserved inventory back to available stock with a `RELEASE` transaction.
- `Failed`: Order marked as failed due to payment or logistics issues.

---

## 🔒 Concurrency & Row-Level Locking Strategy

To prevent race conditions and overselling when multiple users simultaneously order the last remaining inventory:
1. **Pessimistic Row-Level Lock**: The repository executes `SELECT ... FOR UPDATE` on the target inventory row.
2. **Sequential Blocking**: Concurrent transactions for the same warehouse-product pair block until the first transaction commits or rolls back.
3. **Deadlock Elimination**: Product IDs are sorted in ascending order before acquiring locks, preventing circular wait conditions.
4. **Database-Level Invariant**: A check constraint (`CONSTRAINT chk_available_qty_non_negative CHECK (available_quantity >= 0)`) prevents stock from ever dropping below 0.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL 16 (or SQLite for local development)
- Docker & Docker Compose (optional, for containerized run)

### Method 1: Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd "Order Fulfillment & Inventory Management Platform"
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # On Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   *(Default `.env` is pre-configured with SQLite for instant local execution or PostgreSQL connection string).*

5. **Apply database migrations:**
   ```bash
   alembic upgrade head
   ```

6. **Start the FastAPI development server:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

7. **Access the Interactive API Documentation:**
   - Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
   - ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### Method 2: Docker Compose Deployment

Run the complete multi-container stack (FastAPI + PostgreSQL 16 + Redis 7):

```bash
docker compose up -d --build
```

The stack automatically boots PostgreSQL with persistent volumes, waits for health checks, runs Alembic migrations, and launches the FastAPI application on port 8000.

---

## 🧪 Running Automated Tests

Run the complete 43-test automated test suite using Pytest:

```bash
# Run all tests with verbose output
pytest -v

# Run with short traceback
pytest -v --tb=short

# Run concurrency race condition test specifically
pytest tests/test_concurrency_locking.py -v
```

### Test Suite Summary:
```
tests/test_auth.py ......................... 9 Passed (Auth, Token Rotation, Inactive User, Logout)
tests/test_rbac_warehouses.py .............. 6 Passed (Warehouse CRUD, User Assignments, Scoping)
tests/test_products.py ..................... 6 Passed (Product CRUD, Duplicate SKU, Inactive check)
tests/test_inventory.py .................... 7 Passed (Adjust, Atomic Dual-Transfer, Low Stock, Ledger)
tests/test_orders.py ....................... 6 Passed (Calculations, Price Invariance, Workflow, Cancel)
tests/test_concurrency_locking.py .......... 1 Passed (Multi-threaded race condition reservation)
tests/test_idempotency.py .................. 2 Passed (Key caching, retry protection, payload conflict)
tests/test_returns.py ...................... 2 Passed (RMA lifecycle, restock upon receipt)
tests/test_dashboard.py .................... 4 Passed (Admin, Manager, Customer metrics, Notifications)
============================================ 43 passed in 78s ============================================
```

---

## 📬 Postman Collection

A complete Postman collection is included in:
`postman/order_fulfillment_platform.postman_collection.json`

### Key features:
- Automatically captures and populates `{{access_token}}` and `{{refresh_token}}` variables upon login.
- Includes pre-built JSON payloads for all endpoints.
- Demonstrates idempotency keys and error handling.

---

## 📋 API Endpoints Reference

### 🔐 Authentication (`/api/auth`)
| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/auth/register` | Register new customer or user account | No |
| `POST` | `/api/auth/login` | Login and obtain access & refresh tokens | No |
| `POST` | `/api/auth/refresh` | Rotate and issue new token pair | No |
| `POST` | `/api/auth/logout` | Revoke refresh token | No |
| `GET` | `/api/auth/me` | Current profile and warehouse authorizations | Bearer Token |
| `POST` | `/api/auth/change-password` | Update password & invalidate active tokens | Bearer Token |

### 📦 Product Management (`/api/products`)
| Method | Endpoint | Description | Permissions |
|---|---|---|---|
| `POST` | `/api/products` | Create product (unique SKU) | Admin |
| `GET` | `/api/products` | List products (search, category, status, min/max price) | Public |
| `GET` | `/api/products/{id}` | Get product details | Public |
| `PUT` | `/api/products/{id}` | Update product details | Admin |
| `PATCH` | `/api/products/{id}/activate` | Activate product | Admin |
| `PATCH` | `/api/products/{id}/deactivate` | Deactivate product (blocks new orders) | Admin |
| `GET` | `/api/products/categories` | List categories | Public |
| `POST` | `/api/products/categories` | Create category | Admin |

### 🏬 Warehouse Management (`/api/warehouses`)
| Method | Endpoint | Description | Permissions |
|---|---|---|---|
| `POST` | `/api/warehouses` | Create warehouse | Admin |
| `GET` | `/api/warehouses` | List warehouses (scoped by authorization) | Authenticated |
| `GET` | `/api/warehouses/{id}` | Get warehouse details | Scoped User |
| `PUT` | `/api/warehouses/{id}` | Update warehouse | Admin / Manager |
| `PATCH` | `/api/warehouses/{id}/activate` | Activate warehouse | Admin |
| `PATCH` | `/api/warehouses/{id}/deactivate` | Deactivate warehouse | Admin |
| `POST` | `/api/warehouses/{id}/users` | Assign user to warehouse | Admin |
| `DELETE` | `/api/warehouses/{id}/users/{uid}` | Remove user warehouse authorization | Admin |

### 📊 Inventory Management (`/api/inventory`)
| Method | Endpoint | Description | Permissions |
|---|---|---|---|
| `GET` | `/api/inventory` | List inventory across warehouses | Scoped User |
| `GET` | `/api/inventory/low-stock` | Retrieve items where stock <= reorder level | Scoped User |
| `GET` | `/api/inventory/{product_id}` | Breakdown of product across warehouses | Authenticated |
| `POST` | `/api/inventory/adjust` | Adjust stock level (SET, INCREASE, DECREASE, DAMAGE) | Admin / Manager |
| `POST` | `/api/inventory/transfer` | Atomic dual-transaction transfer between warehouses | Admin / Manager |
| `GET` | `/api/inventory/transactions` | Immutable transaction audit trail | Admin / Manager |

### 🛒 Orders & Fulfillment (`/api/orders`)
| Method | Endpoint | Description | Permissions |
|---|---|---|---|
| `POST` | `/api/orders` | Create order & reserve stock (Idempotent) | Customer / Admin |
| `GET` | `/api/orders` | List orders (pagination, status, date, warehouse) | Scoped User |
| `GET` | `/api/orders/{id}` | Detailed order view with items & history | Scoped User |
| `PATCH` | `/api/orders/{id}/status` | Transition status via state machine | Scoped User |
| `POST` | `/api/orders/{id}/cancel` | Cancel order & release reserved stock | Customer / Admin |
| `POST` | `/api/orders/{id}/assign` | Assign order to fulfillment agent | Admin / Manager |
| `POST` | `/api/orders/{id}/payment` | Process payment confirmation | Customer / Admin |
| `POST` | `/api/orders/{id}/start-processing` | Fulfillment shortcut: Confirmed -> Processing | Fulfillment Agent |
| `POST` | `/api/orders/{id}/pack` | Fulfillment shortcut: Processing -> Packed | Fulfillment Agent |
| `POST` | `/api/orders/{id}/ship` | Fulfillment shortcut: Packed -> Shipped | Fulfillment Agent |
| `POST` | `/api/orders/{id}/deliver` | Fulfillment shortcut: Shipped -> Delivered | Fulfillment Agent |

### 🔁 Returns (`/api/returns`)
| Method | Endpoint | Description | Permissions |
|---|---|---|---|
| `POST` | `/api/returns` | Submit return request for delivered order | Customer |
| `GET` | `/api/returns` | List return requests | Scoped User |
| `GET` | `/api/returns/{id}` | View return request details | Scoped User |
| `PATCH` | `/api/returns/{id}/status` | Approve, reject, or receive & restock items | Admin / Manager |

### 🔔 Notifications & Auditing
| Method | Endpoint | Description | Permissions |
|---|---|---|---|
| `GET` | `/api/notifications` | List user notifications | Authenticated |
| `PATCH` | `/api/notifications/{id}/read`| Mark single notification as read | Authenticated |
| `PATCH` | `/api/notifications/read-all` | Mark all notifications as read | Authenticated |
| `GET` | `/api/audit-logs` | View immutable system audit trail | Admin |

### 📈 Dashboards (`/api/dashboard`)
| Method | Endpoint | Description | Permissions |
|---|---|---|---|
| `GET` | `/api/dashboard/admin` | Total revenue, order metrics, low stock counts | Admin |
| `GET` | `/api/dashboard/warehouse-manager` | Warehouse stock, pending orders, shipments | Admin / Manager |
| `GET` | `/api/dashboard/customer` | Customer order volume, active orders, spending | Customer |

---

## 🛡️ Standardized Error Response Format

All error responses strictly adhere to the requested schema:

```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_INVENTORY",
    "message": "Insufficient inventory for product SKU-PHONE-01. Requested: 50, Available: 5",
    "details": null
  }
}
```

### Supported HTTP Status Codes:
- `400 Bad Request`: Domain validation failure (`INSUFFICIENT_INVENTORY`, `INVALID_ORDER_STATUS`, `PRODUCT_INACTIVE`)
- `401 Unauthorized`: Missing, expired, or invalid JWT token (`UNAUTHORIZED`)
- `403 Forbidden`: Role permission denied or warehouse access denied (`FORBIDDEN`, `WAREHOUSE_ACCESS_DENIED`, `USER_INACTIVE`)
- `404 Not Found`: Target entity not found (`NOT_FOUND`)
- `409 Conflict`: Unique constraint violation or idempotency key payload mismatch (`CONFLICT`, `DUPLICATE_IDEMPOTENCY_KEY`)
- `422 Validation Error`: Pydantic schema validation error (`VALIDATION_ERROR`)
- `500 Internal Server Error`: Unhandled server exception (`INTERNAL_SERVER_ERROR`)

---

## 📄 License
This project is licensed under the MIT License.
