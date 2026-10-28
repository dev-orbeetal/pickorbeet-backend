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
from django.db.models import Count, Q
from decimal import Decimal
from .models import Order, OrderItem, OrderStatusHistory, Cart, CartItem, Coupon, CouponUsage, DeliveryOption
from .serializers import (
    CartSerializer, CartItemSerializer, AddToCartSerializer, UpdateCartItemSerializer,
    OrderListSerializer, OrderDetailSerializer, CheckoutSerializer,
    InShopOrderSerializer, OrderStatusUpdateSerializer, TrackOrderSerializer,
    OrderStatusHistorySerializer, CouponSerializer, CouponCreateSerializer,
    ValidateCouponSerializer, ApplyCouponSerializer, DeliveryOptionSerializer,
    DeliveryUpdateSerializer,
)
from apps.products.models import Product, ProductVariant
from apps.reports.models import StockMovement
from apps.products.variants import variant_options


def snapshot_options(variant):
    return variant_options(variant) if variant else []
from apps.accounts.permissions import IsStaffUser, IsSeller, IsSuperAdmin
from apps.shipping.services import status_group
from apps.notifications.services import notify_order_placed
from apps.orders.emails import notify_order_placed_email
from .services import DeliveryUpdateError, change_order_status, update_delivery_details


def public_shipment_summary(order):
    """Courier details safe to show on the public tracking page."""
    shipment = getattr(order, 'shipment', None)
    if shipment is None or not shipment.consignment_id:
        return None
    events = []
    for event in shipment.events.all()[:12]:
        events.append({
            'source': event.source,
            'status': event.status,
            'status_group': status_group(event.status) if event.status else None,
            'message': event.message,
            'occurred_at': event.occurred_at,
            'created_at': event.created_at,
        })
    return {
        'courier': shipment.courier,
        'courier_name': shipment.get_courier_display(),
        'tracking_code': shipment.tracking_code,
        'tracking_url': shipment.tracking_url,
        'status': shipment.status,
        'status_group': status_group(shipment.status),
        'status_label': shipment.status_label,
        'status_message': shipment.status_message,
        'status_updated_at': shipment.status_updated_at,
        'events': events,
    }


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

        # Order the whole cart, or only the lines the customer selected.
        cart_items = cart.items.select_related('product', 'variant')
        item_ids = data.get('item_ids')
        if item_ids:
            cart_items = cart_items.filter(id__in=set(item_ids))
        cart_items = list(cart_items)
        if item_ids and len(cart_items) != len(set(item_ids)):
            return Response(
                {'error': 'Some selected items are no longer in your cart.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not cart_items:
            return Response(
                {'error': 'Cart is empty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        subtotal = sum((item.total_price for item in cart_items), Decimal('0'))
        
        # Validate coupon if provided
        coupon = None
        discount_amount = Decimal('0')
        coupon_code = data.get('coupon_code', '').strip().upper()
        
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code)
                can_use, message = coupon.can_be_used_by(
                    request.user if request.user.is_authenticated else None,
                    subtotal
                )
                if can_use:
                    discount_amount = coupon.calculate_discount(subtotal)
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
                subtotal=subtotal,
                discount=discount_amount,
                coupon=coupon,
                coupon_code=coupon_code if coupon else None,
                notes=data.get('notes', ''),
                payment_method=data.get('payment_method'),
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
            for cart_item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    variant=cart_item.variant,
                    product_name=cart_item.product.name,
                    product_sku=cart_item.product.sku,
                    size=cart_item.variant.size if cart_item.variant else cart_item.product.size,
                    color=cart_item.variant.color if cart_item.variant else cart_item.product.color,
                    options=snapshot_options(cart_item.variant),
                    quantity=cart_item.quantity,
                    unit_price=cart_item.unit_price,
                    compare_price=cart_item.product.compare_price,
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
            
            # Remove the ordered lines; unselected lines stay in the cart
            CartItem.objects.filter(id__in=[item.id for item in cart_items]).delete()

        notify_order_placed(order)
        notify_order_placed_email(order)

        return Response({
            'message': 'Order created successfully',
            'order': OrderDetailSerializer(order).data
        }, status=status.HTTP_201_CREATED)


# Order Views for Customers
OPEN_ORDER_STATUSES = ['pending', 'confirmed', 'processing', 'shipped', 'out_for_delivery']


class CustomerOrderListView(generics.ListAPIView):
    """List orders for authenticated customer. ``?order_status=a,b`` filters by status."""
    serializer_class = OrderListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            Order.objects.filter(user=self.request.user)
            .select_related('shipment')
            .prefetch_related('items__product__images')
        )
        statuses = self.request.query_params.get('order_status')
        if statuses:
            wanted = {value.strip() for value in statuses.split(',') if value.strip()}
            if 'open' in wanted:
                wanted.discard('open')
                wanted.update(OPEN_ORDER_STATUSES)
            queryset = queryset.filter(order_status__in=wanted)
        search = (self.request.query_params.get('search') or '').strip()[:80]
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search)
                | Q(tracking_number__icontains=search)
                | Q(shipment__tracking_code__icontains=search)
                | Q(shipment__consignment_id__icontains=search)
                | Q(items__product_name__icontains=search)
                | Q(items__product_sku__icontains=search)
            ).distinct()
        return queryset


class CustomerOrderSummaryView(APIView):
    """Order counts by status for the account dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = (
            Order.objects.filter(user=request.user)
            .values('order_status')
            .annotate(count=Count('id'))
        )
        counts = {value: 0 for value, _ in Order.ORDER_STATUS_CHOICES}
        for row in rows:
            counts[row['order_status']] = row['count']
        return Response({
            'total': sum(counts.values()),
            'counts': counts,
            # "open" is everything still on its way to the customer
            'open': sum(counts[s] for s in OPEN_ORDER_STATUSES),
            'delivered': counts['delivered'],
            'cancelled': counts['cancelled'],
            'returned': counts['refunded'],
        })


CANCELLABLE_STATUSES = {'pending', 'confirmed', 'processing'}


class CustomerCancelOrderView(APIView):
    """Customer: cancel an order that has not been handed to the courier."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = (
            Order.objects.filter(pk=pk, user=request.user)
            .select_related('shipment')
            .prefetch_related('items__product__images')
            .first()
        )
        if order is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        shipment = getattr(order, 'shipment', None)
        booked = shipment is not None and bool(shipment.consignment_id)
        if order.order_status not in CANCELLABLE_STATUSES or booked:
            return Response(
                {'error': 'This order can no longer be cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        change_order_status(order, 'cancelled', note='Cancelled by customer', changed_by=request.user)
        return Response(OrderListSerializer(order, context={'request': request}).data)


class CustomerOrderDetailView(generics.RetrieveAPIView):
    """Get single order for authenticated customer."""
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).select_related('shipment')


class CustomerOrderDeliveryView(APIView):
    """Customer: change the delivery details of a pending order."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        order = Order.objects.filter(pk=pk, user=request.user).first()
        if order is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = DeliveryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            update_delivery_details(order, serializer.validated_data, changed_by=request.user)
        except DeliveryUpdateError as exc:
            return Response({'error': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        order = Order.objects.select_related('shipment').get(pk=pk)
        return Response(OrderDetailSerializer(order, context={'request': request}).data)


def _find_trackable_order(data):
    """Match an order number, the internal reference, or a Steadfast tracking code."""
    phone = (data.get('phone') or '').strip()

    def narrowed(queryset):
        if not phone:
            return queryset
        return queryset.filter(Q(shipping_phone=phone) | Q(guest_phone=phone))

    base = Order.objects.select_related('shipment')
    order_number = (data.get('order_number') or '').strip()
    if order_number:
        hit = narrowed(base.filter(order_number=order_number)).first()
        if hit:
            return hit
    tracking_number = (data.get('tracking_number') or '').strip()
    if tracking_number:
        hit = narrowed(base.filter(tracking_number=tracking_number)).first()
        if hit:
            return hit
    code = (data.get('tracking_code') or '').strip()
    if code:
        return narrowed(base.filter(
            Q(shipment__tracking_code__iexact=code) | Q(shipment__consignment_id=code)
        )).first()
    return None


class TrackOrderView(APIView):
    """Track an order by its number, internal reference, or Steadfast tracking code."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TrackOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order = _find_trackable_order(serializer.validated_data)
        if order is None:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'id': str(order.pk),
            'order_number': order.order_number,
            'tracking_number': order.tracking_number,
            'order_status': order.order_status,
            'payment_status': order.payment_status,
            'created_at': order.created_at,
            'shipped_at': order.shipped_at,
            'delivered_at': order.delivered_at,
            'status_history': OrderStatusHistorySerializer(
                order.status_history.all(), many=True
            ).data,
            'shipment': public_shipment_summary(order),
        })


# Admin/Staff Order Views
class AdminOrderListView(generics.ListAPIView):
    """Admin: List all orders."""
    serializer_class = OrderListSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['order_status', 'payment_status', 'order_type']
    search_fields = ['order_number', 'tracking_number', 'shipping_name', 'shipping_phone',
                     'shipment__tracking_code', 'shipment__consignment_id']
    ordering_fields = ['created_at', 'total']

    def get_queryset(self):
        return Order.objects.all().select_related('shipment').prefetch_related('items__product__images')


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
        
        order = change_order_status(
            order,
            serializer.validated_data['status'],
            note=serializer.validated_data.get('note', ''),
            changed_by=request.user,
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
                    options=snapshot_options(item['variant']),
                    quantity=item['quantity'],
                    unit_price=item['unit_price'],
                    compare_price=item['product'].compare_price,
                )
                
                # Update stock
                if item['variant']:
                    prev = item['variant'].stock_quantity
                    item['variant'].stock_quantity = max(0, item['variant'].stock_quantity - item['quantity'])
                    item['variant'].save(update_fields=['stock_quantity'])
                    StockMovement.objects.create(
                        product=item['product'], variant=item['variant'],
                        movement_type='out', quantity=-item['quantity'],
                        previous_stock=prev, new_stock=item['variant'].stock_quantity,
                        reason='sale', reference_order=order,
                        note=f'In-shop order #{order.order_number}',
                        created_by=request.user,
                    )
                else:
                    prev = item['product'].stock_quantity
                    item['product'].stock_quantity = max(0, item['product'].stock_quantity - item['quantity'])
                    item['product'].save(update_fields=['stock_quantity'])
                    StockMovement.objects.create(
                        product=item['product'], variant=None,
                        movement_type='out', quantity=-item['quantity'],
                        previous_stock=prev, new_stock=item['product'].stock_quantity,
                        reason='sale', reference_order=order,
                        note=f'In-shop order #{order.order_number}',
                        created_by=request.user,
                    )
            
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
