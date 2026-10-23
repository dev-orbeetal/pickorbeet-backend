"""
URL patterns for orders app.
"""
from django.urls import path
from .views import (
    CartView, AddToCartView, UpdateCartItemView, ClearCartView,
    CheckoutView,     CustomerOrderListView, CustomerOrderDetailView,
    CustomerOrderSummaryView, CustomerOrderDeliveryView, CustomerCancelOrderView,
    TrackOrderView, AdminOrderListView, AdminOrderDetailView,
    UpdateOrderStatusView, InShopOrderView,
    ValidateCouponView, ApplyCouponToCartView,
    AdminCouponListCreateView, AdminCouponDetailView, AdminCouponStatsView,
    PublicDeliveryOptionsView, AdminDeliveryOptionListCreateView, AdminDeliveryOptionDetailView
)
from apps.shipping.views import AdminBookShipmentView, AdminRefreshShipmentView, CustomerRefreshShipmentView

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
    path('my-orders/summary/', CustomerOrderSummaryView.as_view(), name='customer_order_summary'),
    path('my-orders/<uuid:pk>/', CustomerOrderDetailView.as_view(), name='customer_order_detail'),
    path('my-orders/<uuid:pk>/cancel/', CustomerCancelOrderView.as_view(), name='customer_order_cancel'),
    path('my-orders/<uuid:pk>/delivery/', CustomerOrderDeliveryView.as_view(), name='customer_order_delivery'),
    path('my-orders/<uuid:pk>/shipment/refresh/', CustomerRefreshShipmentView.as_view(),
         name='customer_shipment_refresh'),
    
    # Order tracking (public)
    path('track/', TrackOrderView.as_view(), name='track_order'),
    
    # Admin order endpoints
    path('admin/', AdminOrderListView.as_view(), name='admin_order_list'),
    path('admin/<uuid:pk>/', AdminOrderDetailView.as_view(), name='admin_order_detail'),
    path('admin/<uuid:pk>/status/', UpdateOrderStatusView.as_view(), name='update_order_status'),
    path('admin/<uuid:pk>/shipment/', AdminBookShipmentView.as_view(), name='admin_book_shipment'),
    path('admin/<uuid:pk>/shipment/refresh/', AdminRefreshShipmentView.as_view(), name='admin_refresh_shipment'),
    path('admin/in-shop/', InShopOrderView.as_view(), name='in_shop_order'),
    
    # Admin coupon management
    path('admin/coupons/', AdminCouponListCreateView.as_view(), name='admin_coupon_list'),
    path('admin/coupons/<uuid:pk>/', AdminCouponDetailView.as_view(), name='admin_coupon_detail'),
    path('admin/coupons/<uuid:pk>/stats/', AdminCouponStatsView.as_view(), name='admin_coupon_stats'),
    
    # Delivery options
    path('delivery-options/', PublicDeliveryOptionsView.as_view(), name='public_delivery_options'),
    path('admin/delivery-options/', AdminDeliveryOptionListCreateView.as_view(), name='admin_delivery_options'),
    path('admin/delivery-options/<uuid:pk>/', AdminDeliveryOptionDetailView.as_view(), name='admin_delivery_option_detail'),
]
