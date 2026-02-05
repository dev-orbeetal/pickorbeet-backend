"""
URL patterns for orders app.
"""
from django.urls import path
from .views import (
    CartView, AddToCartView, UpdateCartItemView, ClearCartView,
    CheckoutView, CustomerOrderListView, CustomerOrderDetailView,
    TrackOrderView, AdminOrderListView, AdminOrderDetailView,
    UpdateOrderStatusView, InShopOrderView,
    ValidateCouponView, ApplyCouponToCartView,
    AdminCouponListCreateView, AdminCouponDetailView, AdminCouponStatsView
)

urlpatterns = [
    # Cart endpoints
    path('cart/', CartView.as_view(), name='cart'),
    path('cart/add/', AddToCartView.as_view(), name='add_to_cart'),
    path('cart/item/<uuid:item_id>/', UpdateCartItemView.as_view(), name='update_cart_item'),
    path('cart/clear/', ClearCartView.as_view(), name='clear_cart'),
    
    # Coupon endpoints (public)
    path('coupons/validate/', ValidateCouponView.as_view(), name='validate_coupon'),
    path('coupons/apply/', ApplyCouponToCartView.as_view(), name='apply_coupon'),
    
    # Checkout
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    
    # Customer orders
    path('my-orders/', CustomerOrderListView.as_view(), name='customer_orders'),
    path('my-orders/<uuid:pk>/', CustomerOrderDetailView.as_view(), name='customer_order_detail'),
    
    # Order tracking (public)
    path('track/', TrackOrderView.as_view(), name='track_order'),
    
    # Admin order endpoints
    path('admin/', AdminOrderListView.as_view(), name='admin_order_list'),
    path('admin/<uuid:pk>/', AdminOrderDetailView.as_view(), name='admin_order_detail'),
    path('admin/<uuid:pk>/status/', UpdateOrderStatusView.as_view(), name='update_order_status'),
    path('admin/in-shop/', InShopOrderView.as_view(), name='in_shop_order'),
    
    # Admin coupon management
    path('admin/coupons/', AdminCouponListCreateView.as_view(), name='admin_coupon_list'),
    path('admin/coupons/<uuid:pk>/', AdminCouponDetailView.as_view(), name='admin_coupon_detail'),
    path('admin/coupons/<uuid:pk>/stats/', AdminCouponStatsView.as_view(), name='admin_coupon_stats'),
]
