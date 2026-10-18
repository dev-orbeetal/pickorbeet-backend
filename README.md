# Pickorbeet E-commerce Backend

Django REST API backend for Pickorbeet clothing e-commerce platform.

## Tech Stack

- **Framework**: Django 5.0
- **API**: Django REST Framework
- **Database**: PostgreSQL
- **Admin**: Django Jazzmin
- **Authentication**: JWT (SimpleJWT)
- **Payment**: SSLCommerz

## Setup Instructions

### 1. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Variables

Copy `.env.example` to `.env` and update the values:

```bash
cp .env.example .env
```

### 4. Database Setup

Create PostgreSQL database:

```sql
CREATE DATABASE pickorbeet_db;
```

### 5. Run Migrations

```bash
python manage.py migrate
```

### 6. Create Superuser

```bash
python manage.py createsuperuser
```

### 7. Run Development Server

```bash
python manage.py runserver 8000
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/login/` - Login
- `POST /api/v1/auth/register/` - Register
- `POST /api/v1/auth/logout/` - Logout
- `GET /api/v1/auth/profile/` - Get profile

### Products
- `GET /api/v1/products/` - List products
- `GET /api/v1/products/<slug>/` - Product detail
- `GET /api/v1/products/categories/` - List categories
- `GET /api/v1/products/featured/` - Featured products

### Orders
- `GET /api/v1/orders/cart/` - Get cart
- `POST /api/v1/orders/cart/add/` - Add to cart
- `POST /api/v1/orders/checkout/` - Checkout
- `POST /api/v1/orders/track/` - Track order

### Payments
- `POST /api/v1/payments/initiate/` - Initiate payment

### Reports (Admin)
- `GET /api/v1/reports/dashboard/` - Dashboard stats
- `POST /api/v1/reports/sales/` - Sales report
- `GET /api/v1/reports/stock/` - Stock report

## Admin Panel

Access Django admin at: `http://localhost:8000/admin/`

## API Documentation

- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`

## Project Structure

```
server/
├── core/                 # Project settings
├── apps/
│   ├── accounts/        # User management
│   ├── products/        # Product catalog
│   ├── orders/          # Orders & cart
│   ├── payments/        # SSLCommerz integration
│   └── reports/         # Analytics & reports
├── static/              # Static files
├── media/               # Uploaded files
└── templates/           # HTML templates
```
