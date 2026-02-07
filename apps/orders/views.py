"""
Views for orders app.
"""
from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal
from .models import Order, OrderItem, OrderStatusHistory, Cart, CartItem, Coupon, CouponUsage, DeliveryOption
from .serializers import (
    CartSerializer, CartItemSerializer, AddToCartSerializer, UpdateCartItemSerializer,
    OrderListSerializer, OrderDetailSerializer, CheckoutSerializer,
    InShopOrderSerializer, OrderStatusUpdateSerializer, TrackOrderSerializer,
    OrderStatusHistorySerializer, CouponSerializer, CouponCreateSerializer,
    ValidateCouponSerializer, ApplyCouponSerializer, DeliveryOptionSerializer
)
from apps.products.models import Product, ProductVariant
from apps.accounts.permissions import IsStaffUser, IsSeller, IsSuperAdmin


# Cart Views
class CartView(APIView):
    """Get or create cart for user/session."""
    permission_classes = [AllowAny]

    def get_cart(self, request):
        if request.user.is_authenticated:
            cart, _ = Cart.objects.get_or_create(user=request.user)
        else:
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key
            cart, _ = Cart.objects.get_or_create(session_key=session_key)
        return cart

    def get(self, request):
        cart = self.get_cart(request)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data)


class AddToCartView(APIView):
    """Add item to cart."""
    permission_classes = [AllowAny]

    def get_cart(self, request):
        if request.user.is_authenticated:
            cart, _ = Cart.objects.get_or_create(user=request.user)
        else:
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key
            cart, _ = Cart.objects.get_or_create(session_key=session_key)
        return cart

    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        cart = self.get_cart(request)
        product_id = serializer.validated_data['product_id']
        variant_id = serializer.validated_data.get('variant_id')
        quantity = serializer.validated_data['quantity']
        
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, product=product)
            except ProductVariant.DoesNotExist:
                return Response(
                    {'error': 'Variant not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Check stock
        available_stock = variant.stock_quantity if variant else product.stock_quantity
        if available_stock < quantity:
            return Response(
                {'error': 'Insufficient stock'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Add or update cart item
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={'quantity': quantity}
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
        
        return Response(CartSerializer(cart, context={'request': request}).data)


class UpdateCartItemView(APIView):
    """Update cart item quantity."""
    permission_classes = [AllowAny]

    def patch(self, request, item_id):
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            cart_item = CartItem.objects.get(id=item_id)
        except CartItem.DoesNotExist:
            return Response(
                {'error': 'Cart item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        cart_item.quantity = serializer.validated_data['quantity']
        cart_item.save()
        
        return Response(CartSerializer(cart_item.cart, context={'request': request}).data)

    def delete(self, request, item_id):
        try:
            cart_item = CartItem.objects.get(id=item_id)
            cart = cart_item.cart
            cart_item.delete()
            return Response(CartSerializer(cart, context={'request': request}).data)
        except CartItem.DoesNotExist:
            return Response(
                {'error': 'Cart item not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class ClearCartView(APIView):
    """Clear all items from cart."""
    permission_classes = [AllowAny]

    def delete(self, request):
        if request.user.is_authenticated:
            Cart.objects.filter(user=request.user).delete()
        else:
            session_key = request.session.session_key
            if session_key:
                Cart.objects.filter(session_key=session_key).delete()
        return Response({'message': 'Cart cleared'})


# Checkout View
class CheckoutView(APIView):
    """Process checkout and create order."""
    permission_classes = [AllowAny]

    def get_cart(self, request):
        if request.user.is_authenticated:
            return Cart.objects.filter(user=request.user).first()
        session_key = request.session.session_key
        if session_key:
            return Cart.objects.filter(session_key=session_key).first()
        return None

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        cart = self.get_cart(request)
        if not cart or not cart.items.exists():
            return Response(
                {'error': 'Cart is empty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        # Validate coupon if provided
        coupon = None
        discount_amount = Decimal('0')
        coupon_code = data.get('coupon_code', '').strip().upper()
        
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code)
                can_use, message = coupon.can_be_used_by(
                    request.user if request.user.is_authenticated else None,
                    cart.subtotal
                )
                if can_use:
                    discount_amount = coupon.calculate_discount(cart.subtotal)
                else:
                    return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
            except Coupon.DoesNotExist:
                return Response({'error': 'Invalid coupon code.'}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Create order
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                guest_email=data.get('guest_email'),
                guest_phone=data.get('guest_phone'),
                guest_name=data.get('guest_name'),
                order_type='online',
                shipping_name=data['shipping_name'],
                shipping_phone=data['shipping_phone'],
                shipping_address_line1=data['shipping_address_line1'],
                shipping_address_line2=data.get('shipping_address_line2', ''),
                shipping_city=data['shipping_city'],
                shipping_district=data['shipping_district'],
                shipping_postal_code=data.get('shipping_postal_code', ''),
                subtotal=cart.subtotal,
                discount=discount_amount,
                coupon=coupon,
                coupon_code=coupon_code if coupon else None,
                notes=data.get('notes', ''),
            )
            
            # Set billing address if different
            if data.get('use_different_billing'):
                order.billing_name = data.get('billing_name')
                order.billing_phone = data.get('billing_phone')
                order.billing_address_line1 = data.get('billing_address_line1')
                order.billing_address_line2 = data.get('billing_address_line2')
                order.billing_city = data.get('billing_city')
                order.billing_district = data.get('billing_district')
                order.billing_postal_code = data.get('billing_postal_code')
            
            order.save()
            
            # Create order items (stock is reduced when order is confirmed)
            for cart_item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    variant=cart_item.variant,
                    product_name=cart_item.product.name,
                    product_sku=cart_item.product.sku,
                    size=cart_item.variant.size if cart_item.variant else cart_item.product.size,
                    color=cart_item.variant.color if cart_item.variant else cart_item.product.color,
                    quantity=cart_item.quantity,
                    unit_price=cart_item.unit_price,
                )
            
            # Create initial status history
            OrderStatusHistory.objects.create(
                order=order,
                status='pending',
                note='Order placed'
            )
            
            # Record coupon usage
            if coupon:
                CouponUsage.objects.create(
                    coupon=coupon,
                    user=request.user if request.user.is_authenticated else None,
                    order=order,
                    discount_amount=discount_amount
                )
                coupon.times_used += 1
                coupon.save()
            
            # Clear cart
            cart.items.all().delete()
        
        return Response({
            'message': 'Order created successfully',
            'order': OrderDetailSerializer(order).data
        }, status=status.HTTP_201_CREATED)


# Order Views for Customers
class CustomerOrderListView(generics.ListAPIView):
    """List orders for authenticated customer."""
    serializer_class = OrderListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)


class CustomerOrderDetailView(generics.RetrieveAPIView):
    """Get single order for authenticated customer."""
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)


class TrackOrderView(APIView):
    """Track order by order number or tracking number."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TrackOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        query = Q()
        
        if data.get('order_number'):
            query |= Q(order_number=data['order_number'])
        if data.get('tracking_number'):
            query |= Q(tracking_number=data['tracking_number'])
        
        if data.get('phone'):
            query &= (Q(shipping_phone=data['phone']) | Q(guest_phone=data['phone']))
        
        try:
            order = Order.objects.get(query)
            return Response({
                'order_number': order.order_number,
                'tracking_number': order.tracking_number,
                'order_status': order.order_status,
                'payment_status': order.payment_status,
                'created_at': order.created_at,
                'shipped_at': order.shipped_at,
                'delivered_at': order.delivered_at,
                'status_history': OrderStatusHistorySerializer(
                    order.status_history.all(), many=True
                ).data
            })
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )


# Admin/Staff Order Views
class AdminOrderListView(generics.ListAPIView):
    """Admin: List all orders."""
    serializer_class = OrderListSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['order_status', 'payment_status', 'order_type']
    search_fields = ['order_number', 'tracking_number', 'shipping_name', 'shipping_phone']
    ordering_fields = ['created_at', 'total']

    def get_queryset(self):
        return Order.objects.all().prefetch_related('items')


class AdminOrderDetailView(generics.RetrieveDestroyAPIView):
    """Admin: Get or delete single order."""
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = Order.objects.all()

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        # Only allow deletion of pending or cancelled orders
        if order.order_status not in ['pending', 'cancelled']:
            return Response(
                {'error': 'Can only delete pending or cancelled orders'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


class UpdateOrderStatusView(APIView):
    """Admin: Update order status with automatic stock management."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def _reduce_stock(self, order):
        """Reduce stock for all items in the order."""
        if order.stock_reduced:
            return
        for item in order.items.select_related('product', 'variant').all():
            if item.variant:
                item.variant.stock_quantity = max(0, item.variant.stock_quantity - item.quantity)
                item.variant.save(update_fields=['stock_quantity'])
            else:
                item.product.stock_quantity = max(0, item.product.stock_quantity - item.quantity)
                item.product.save(update_fields=['stock_quantity'])
        order.stock_reduced = True

    def _restore_stock(self, order):
        """Restore stock for all items in the order."""
        if not order.stock_reduced:
            return
        for item in order.items.select_related('product', 'variant').all():
            if item.variant:
                item.variant.stock_quantity += item.quantity
                item.variant.save(update_fields=['stock_quantity'])
            else:
                item.product.stock_quantity += item.quantity
                item.product.save(update_fields=['stock_quantity'])
        order.stock_reduced = False

    def post(self, request, pk):
        serializer = OrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        new_status = serializer.validated_data['status']
        note = serializer.validated_data.get('note', '')
        
        # Statuses where stock should be deducted
        STOCK_DEDUCTED_STATUSES = {'confirmed', 'processing', 'shipped', 'out_for_delivery', 'delivered'}
        
        with transaction.atomic():
            order.order_status = new_status
            
            # Update timestamps
            if new_status == 'confirmed':
                order.confirmed_at = timezone.now()
            elif new_status == 'shipped':
                order.shipped_at = timezone.now()
            elif new_status == 'delivered':
                order.delivered_at = timezone.now()
                order.payment_status = 'paid'
            elif new_status == 'refunded':
                order.payment_status = 'refunded'
            
            # Stock management: reduce when entering confirmed+ statuses, restore when going back
            if new_status in STOCK_DEDUCTED_STATUSES:
                self._reduce_stock(order)
            else:
                # pending, cancelled, refunded → restore stock if it was reduced
                self._restore_stock(order)
            
            order.save()
            
            # Create status history
            OrderStatusHistory.objects.create(
                order=order,
                status=new_status,
                note=note,
                changed_by=request.user
            )
        
        return Response(OrderDetailSerializer(order, context={'request': request}).data)


class InShopOrderView(APIView):
    """Create in-shop order (POS)."""
    permission_classes = [IsAuthenticated, IsSeller]

    def post(self, request):
        serializer = InShopOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        items_data = data['items']
        
        with transaction.atomic():
            # Calculate subtotal
            subtotal = 0
            order_items = []
            
            for item_data in items_data:
                product = Product.objects.get(id=item_data['product_id'])
                variant = None
                if item_data.get('variant_id'):
                    variant = ProductVariant.objects.get(id=item_data['variant_id'])
                
                unit_price = variant.effective_price if variant else product.price
                quantity = item_data['quantity']
                subtotal += unit_price * quantity
                
                order_items.append({
                    'product': product,
                    'variant': variant,
                    'quantity': quantity,
                    'unit_price': unit_price,
                })
            
            # Create order
            order = Order.objects.create(
                guest_name=data.get('customer_name', 'Walk-in Customer'),
                guest_phone=data.get('customer_phone', ''),
                guest_email=data.get('customer_email', ''),
                order_type='in_shop',
                order_status='delivered',
                payment_status='paid',
                shipping_name=data.get('customer_name', 'Walk-in Customer'),
                shipping_phone=data.get('customer_phone', ''),
                shipping_address_line1='In-Shop Purchase',
                shipping_city='Dhaka',
                shipping_district='Dhaka',
                subtotal=subtotal,
                discount=data.get('discount', 0),
                delivery_charge=0,
                payment_method=data['payment_method'],
                processed_by=request.user,
                notes=data.get('notes', ''),
                delivered_at=timezone.now(),
                stock_reduced=True,
            )
            
            # Create order items and update stock immediately for in-shop orders
            for item in order_items:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    variant=item['variant'],
                    product_name=item['product'].name,
                    product_sku=item['product'].sku,
                    size=item['variant'].size if item['variant'] else item['product'].size,
                    color=item['variant'].color if item['variant'] else item['product'].color,
                    quantity=item['quantity'],
                    unit_price=item['unit_price'],
                )
                
                # Update stock
                if item['variant']:
                    item['variant'].stock_quantity = max(0, item['variant'].stock_quantity - item['quantity'])
                    item['variant'].save(update_fields=['stock_quantity'])
                else:
                    item['product'].stock_quantity = max(0, item['product'].stock_quantity - item['quantity'])
                    item['product'].save(update_fields=['stock_quantity'])
            
            # Create status history
            OrderStatusHistory.objects.create(
                order=order,
                status='delivered',
                note='In-shop purchase completed',
                changed_by=request.user
            )
        
        return Response({
            'message': 'In-shop order created successfully',
            'order': OrderDetailSerializer(order).data
        }, status=status.HTTP_201_CREATED)


# Coupon Views
class ValidateCouponView(APIView):
    """Validate a coupon code for the current cart."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ValidateCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        code = serializer.validated_data['code'].upper()
        subtotal = serializer.validated_data.get('subtotal', 0)
        
        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            return Response({
                'valid': False,
                'error': 'Invalid coupon code.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user if request.user.is_authenticated else None
        can_use, message = coupon.can_be_used_by(user, subtotal)
        
        if not can_use:
            return Response({
                'valid': False,
                'error': message
            }, status=status.HTTP_400_BAD_REQUEST)
        
        discount_amount = coupon.calculate_discount(subtotal) if subtotal else 0
        
        return Response({
            'valid': True,
            'message': message,
            'coupon': {
                'code': coupon.code,
                'name': coupon.name,
                'discount_type': coupon.discount_type,
                'discount_value': str(coupon.discount_value),
                'minimum_order_amount': str(coupon.minimum_order_amount),
                'maximum_discount': str(coupon.maximum_discount) if coupon.maximum_discount else None,
            },
            'discount_amount': str(discount_amount)
        })


class ApplyCouponToCartView(APIView):
    """Apply coupon to current cart and return updated totals."""
    permission_classes = [AllowAny]

    def get_cart(self, request):
        if request.user.is_authenticated:
            return Cart.objects.filter(user=request.user).first()
        session_key = request.session.session_key
        if session_key:
            return Cart.objects.filter(session_key=session_key).first()
        return None

    def post(self, request):
        serializer = ApplyCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        code = serializer.validated_data['code'].upper()
        cart = self.get_cart(request)
        
        if not cart or not cart.items.exists():
            return Response({
                'error': 'Cart is empty'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            return Response({
                'valid': False,
                'error': 'Invalid coupon code.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user if request.user.is_authenticated else None
        can_use, message = coupon.can_be_used_by(user, cart.subtotal)
        
        if not can_use:
            return Response({
                'valid': False,
                'error': message
            }, status=status.HTTP_400_BAD_REQUEST)
        
        discount_amount = coupon.calculate_discount(cart.subtotal)
        
        return Response({
            'valid': True,
            'message': f'Coupon "{coupon.code}" applied successfully!',
            'coupon': CouponSerializer(coupon).data,
            'cart_subtotal': str(cart.subtotal),
            'discount_amount': str(discount_amount),
            'total_after_discount': str(cart.subtotal - discount_amount)
        })


# Admin Coupon Management Views
class AdminCouponListCreateView(generics.ListCreateAPIView):
    """Admin: List and create coupons."""
    permission_classes = [IsAuthenticated, IsStaffUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['discount_type', 'is_active', 'first_order_only', 'new_users_only']
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['created_at', 'valid_from', 'valid_until', 'times_used']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CouponCreateSerializer
        return CouponSerializer

    def get_queryset(self):
        return Coupon.objects.all()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AdminCouponDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: Get, update, delete coupon."""
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = Coupon.objects.all()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return CouponCreateSerializer
        return CouponSerializer


class AdminCouponStatsView(APIView):
    """Admin: Get coupon statistics."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request, pk):
        try:
            coupon = Coupon.objects.get(pk=pk)
        except Coupon.DoesNotExist:
            return Response({'error': 'Coupon not found'}, status=status.HTTP_404_NOT_FOUND)
        
        usages = CouponUsage.objects.filter(coupon=coupon)
        total_discount_given = sum(u.discount_amount for u in usages)
        
        return Response({
            'coupon': CouponSerializer(coupon).data,
            'total_times_used': coupon.times_used,
            'total_discount_given': str(total_discount_given),
            'unique_users': usages.values('user').distinct().count(),
            'recent_usages': [
                {
                    'order_number': u.order.order_number,
                    'user_email': u.user.email if u.user else 'Guest',
                    'discount_amount': str(u.discount_amount),
                    'used_at': u.used_at
                }
                for u in usages.order_by('-used_at')[:10]
            ]
        })


# Delivery Option Views
class PublicDeliveryOptionsView(generics.ListAPIView):
    """Public: List active delivery options for checkout."""
    serializer_class = DeliveryOptionSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return DeliveryOption.objects.filter(is_active=True)


class AdminDeliveryOptionListCreateView(generics.ListCreateAPIView):
    """Admin: List and create delivery options."""
    serializer_class = DeliveryOptionSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = DeliveryOption.objects.all()


class AdminDeliveryOptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: Get, update, or delete a delivery option."""
    serializer_class = DeliveryOptionSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = DeliveryOption.objects.all()
