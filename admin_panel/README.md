# PickOrbeet Admin Panel

Custom admin panel for PickOrbeet E-commerce platform built with Next.js.

## Tech Stack

- **Framework**: Next.js 14
- **Styling**: Tailwind CSS
- **State Management**: Redux Toolkit
- **Icons**: Lucide React
- **Charts**: Chart.js
- **Print**: react-to-print

## Features

### Dashboard
- Real-time sales statistics
- Order overview
- Quick actions

### Order Management
- View all orders (online & in-shop)
- Update order status
- Print shipping vouchers
- Order history tracking

### POS (Point of Sale)
- Barcode scanning support
- Quick product search
- Cart management
- Receipt printing (POS thermal)
- Cash, Card, Mobile Banking payments

### Products
- Product listing with filters
- Add/Edit products
- Stock management
- Low stock alerts

### Categories
- Category management
- Subcategory support
- Category images

### Reports
- Sales reports (date range)
- Top selling products
- Category-wise sales
- Stock reports
- Daily sales breakdown

### Staff Management
- Role-based access control
- Super Admin, Accountant, Seller roles
- Staff account management

## Setup

### Install Dependencies

```bash
npm install
```

### Environment Variables

Create `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### Run Development Server

```bash
npm run dev
```

The panel is served by Django at `/admin/` (locally `http://127.0.0.1:8777/admin/`).

## Role-Based Access

| Feature | Super Admin | Accountant | Seller |
|---------|-------------|------------|--------|
| Dashboard | ✓ | ✓ | ✓ |
| Orders | ✓ | ✓ | ✓ |
| POS | ✓ | ✗ | ✓ |
| Products | ✓ | ✓ | ✓ |
| Categories | ✓ | ✗ | ✓ |
| Low Stock | ✓ | ✓ | ✓ |
| Reports | ✓ | ✓ | ✗ |
| Payments | ✓ | ✓ | ✗ |
| Staff Management | ✓ | ✗ | ✗ |

## Project Structure

```
admin-panel/
├── src/
│   ├── components/
│   │   └── layout/
│   │       ├── AdminLayout.jsx
│   │       ├── Header.jsx
│   │       └── Sidebar.jsx
│   ├── lib/
│   │   └── api.js
│   ├── pages/
│   │   ├── dashboard.jsx
│   │   ├── orders/
│   │   ├── pos.jsx
│   │   ├── products/
│   │   ├── categories.jsx
│   │   ├── low-stock.jsx
│   │   ├── reports.jsx
│   │   ├── staff.jsx
│   │   └── login.jsx
│   ├── store/
│   │   ├── store.js
│   │   └── slices/
│   └── styles/
│       └── globals.css
└── public/
```
