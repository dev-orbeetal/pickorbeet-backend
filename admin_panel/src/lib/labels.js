const LABELS = {
  pending: 'Pending',
  confirmed: 'Confirmed',
  processing: 'Processing',
  shipped: 'Shipped',
  out_for_delivery: 'Out for delivery',
  delivered: 'Delivered',
  cancelled: 'Cancelled',
  refunded: 'Refunded',
  paid: 'Paid',
  failed: 'Failed',
  completed: 'Completed',
  online: 'Online',
  in_shop: 'In-shop',
  cash: 'Cash',
  card: 'Card',
  cod: 'Cash on delivery',
  sslcommerz: 'SSLCommerz',
  mobile_banking: 'Mobile banking',
};

export function statusLabel(value) {
  if (!value) return '';
  const key = String(value);
  if (LABELS[key]) return LABELS[key];
  return key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
