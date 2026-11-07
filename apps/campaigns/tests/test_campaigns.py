from datetime import time, timedelta
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.campaigns.models import AutomationRule, Campaign, CampaignSettings, ProductWatch
from apps.campaigns.rendering import product_context, render
from apps.campaigns.services import save_campaign
from apps.campaigns.watcher import watch_catalog
from apps.notifications.models import Device, Notification, NotificationPreference
from apps.orders.models import Cart, CartItem
from apps.orders.tests.factories import ShopTestCase, make_product, make_user
from apps.products.models import Product, ProductImage, WishlistItem


def _photo(name='shot.jpg'):
    buffer = BytesIO()
    Image.new('RGB', (80, 80), (240, 240, 240)).save(buffer, format='JPEG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')


def _attach(product):
    return ProductImage.objects.create(product=product, image=_photo(), is_primary=True)


class RenderingTests(ShopTestCase):
    def test_placeholders_fill_from_the_product(self):
        product = make_product(name='Air Max 90', price='4990.00', compare_price='6990.00', stock=4)
        filled = render(
            'Meet your next favorite — {{product_name}} is now available at {{price}}.',
            product_context(product),
        )
        self.assertEqual(filled, 'Meet your next favorite — Air Max 90 is now available at ৳4,990.')


class CampaignApiTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.seller = make_user(role='seller')
        self.customer = make_user()
        self.other = make_user()
        self.product = make_product(name='Air Max 90', price='4990.00', compare_price='6990.00', stock=8)
        _attach(self.product)
        self.api = APIClient()
        self.api.force_authenticate(self.seller)

    def test_templates_are_seeded(self):
        response = self.api.get('/api/v1/campaigns/admin/templates/')
        self.assertEqual(response.status_code, 200)
        names = {row['name'] for row in response.json()}
        self.assertIn('New Arrival', names)
        self.assertTrue(any(row['is_recommended'] for row in response.json() if row['kind'] == 'new_arrival'))

    def test_preview_fills_the_product_name(self):
        response = self.api.post('/api/v1/campaigns/admin/preview/', {
            'title': 'Something New Just Arrived! ✨',
            'body': "Meet your next favorite — {{product_name}} is now available. Don't miss out!",
            'product_id': str(self.product.id),
        }, format='json')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn('Air Max 90', body['body'])
        self.assertTrue(body['image'])

    def test_unknown_placeholder_is_rejected(self):
        response = self.api.post('/api/v1/campaigns/admin/campaigns/', {
            'title': 'Hello {{nope}}', 'body': 'Hi', 'audience': 'all',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'unknown_placeholder')

    def test_estimate_hides_people_who_turned_offers_off(self):
        NotificationPreference.objects.create(user=self.other, offers=False)
        response = self.api.post('/api/v1/campaigns/admin/estimate/', {'audience': 'all'}, format='json')
        self.assertEqual(response.json()['recipients'], 1)

    def test_interested_audience_needs_the_product(self):
        WishlistItem.objects.create(user=self.customer, product=self.product)
        Cart.objects.create(user=self.other)
        CartItem.objects.create(cart=self.other.cart, product=self.product, quantity=1)

        empty = self.api.post('/api/v1/campaigns/admin/estimate/', {'audience': 'interested'}, format='json')
        self.assertEqual(empty.status_code, 400)

        counted = self.api.post('/api/v1/campaigns/admin/estimate/', {
            'audience': 'interested', 'product_id': str(self.product.id),
        }, format='json')
        self.assertEqual(counted.json()['recipients'], 2)

    def test_send_writes_an_inbox_row_with_the_product_photo(self):
        Device.objects.create(user=self.customer, token='tok', platform='android', device_id='phone-1')
        created = self.api.post('/api/v1/campaigns/admin/campaigns/', {
            'kind': 'new_arrival',
            'title': 'Something New Just Arrived! ✨',
            'body': "Meet your next favorite — {{product_name}} is now available. Don't miss out!",
            'cta_label': 'Tap to explore',
            'audience': 'all',
            'product_id': str(self.product.id),
        }, format='json')
        self.assertEqual(created.status_code, 201)
        campaign_id = created.json()['id']

        sent = self.api.post(f'/api/v1/campaigns/admin/campaigns/{campaign_id}/send/')
        self.assertEqual(sent.status_code, 200)
        self.assertEqual(sent.json()['status'], 'sent')
        self.assertEqual(sent.json()['recipients'], 2)

        note = Notification.objects.get(recipient=self.customer, campaign_id=campaign_id)
        self.assertEqual(note.kind, 'product.arrival')
        self.assertIn('Air Max 90', note.body)
        self.assertEqual(note.data['target'], 'product')
        self.assertEqual(note.data['product_slug'], self.product.slug)
        self.assertTrue(note.data['image'])
        self.assertEqual(note.data['cta_label'], 'Tap to explore')

    def test_a_test_send_goes_to_the_chosen_customer_only(self):
        campaign = save_campaign({
            'title': 'Something New Just Arrived! ✨',
            'body': 'Meet {{product_name}}.',
            'product_id': self.product.id,
            'audience': 'all',
            'kind': 'new_arrival',
        }, user=self.seller)
        response = self.api.post(
            f'/api/v1/campaigns/admin/campaigns/{campaign.id}/test/',
            {'customer_id': str(self.customer.id)}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['sent'])
        self.assertEqual(Notification.objects.filter(campaign=campaign).count(), 1)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'draft')

    def test_schedule_and_cancel(self):
        campaign = save_campaign({
            'title': 'Tonight', 'body': 'See {{product_name}}.', 'product_id': self.product.id, 'audience': 'all',
        }, user=self.seller)
        when = timezone.now() + timedelta(hours=2)
        scheduled = self.api.post(
            f'/api/v1/campaigns/admin/campaigns/{campaign.id}/schedule/',
            {'when': when.isoformat()}, format='json',
        )
        self.assertEqual(scheduled.json()['status'], 'scheduled')
        cancelled = self.api.post(f'/api/v1/campaigns/admin/campaigns/{campaign.id}/cancel/')
        self.assertEqual(cancelled.json()['status'], 'cancelled')

    def test_customers_cannot_compose(self):
        guest = APIClient()
        guest.force_authenticate(self.customer)
        response = guest.post('/api/v1/campaigns/admin/campaigns/', {
            'title': 'X', 'body': 'Y', 'audience': 'all',
        }, format='json')
        self.assertEqual(response.status_code, 403)


class CatalogWatchTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_user()
        settings = CampaignSettings.load()
        settings.quiet_start = time(1, 0)
        settings.quiet_end = time(1, 0)
        settings.arrival_settle_minutes = 0
        settings.daily_cap = 5
        settings.save()

    def test_a_new_product_reaches_every_customer_once_it_has_settled(self):
        product = make_product(name='Campus sneakers', price='3200.00')
        Product.objects.filter(pk=product.pk).update(updated_at=timezone.now() - timedelta(minutes=1))
        product.refresh_from_db()

        started = watch_catalog()

        self.assertEqual(started['new_arrival'], 1)
        note = Notification.objects.get(recipient=self.customer, kind='product.arrival')
        self.assertIn('Campus sneakers', note.body)
        self.assertTrue(ProductWatch.objects.get(pk=product.pk).announced_at)

    def test_existing_products_are_not_announced_on_the_first_look(self):
        product = make_product(name='Old favourite', price='1000.00')
        ProductWatch.objects.update_or_create(
            product=product, defaults={'primed': False, 'price': product.price, 'units': 10, 'available': True},
        )
        watch_catalog()
        self.assertFalse(Notification.objects.filter(kind='product.arrival').exists())
        self.assertTrue(ProductWatch.objects.get(pk=product.pk).primed)

    def test_several_new_products_go_out_as_one_digest(self):
        first = make_product(name='One', price='100.00')
        second = make_product(name='Two', price='200.00')
        Product.objects.filter(pk__in=[first.pk, second.pk]).update(updated_at=timezone.now() - timedelta(minutes=1))

        watch_catalog()

        note = Notification.objects.get(recipient=self.customer, kind='product.arrival')
        self.assertIn('2 new arrivals', note.title.lower() + note.body.lower() + note.title)
        self.assertEqual(note.data['target'], 'products')
        self.assertEqual(Campaign.objects.filter(kind='new_arrival').count(), 1)

    def test_almost_gone_reaches_people_who_saved_it(self):
        AutomationRule.objects.filter(trigger='new_arrival').update(enabled=False)
        product = make_product(name='Last pair', price='2000.00', stock=2)
        ProductWatch.objects.create(
            product=product, primed=True, announced_at=timezone.now(),
            units=20, available=True, price=product.price, low_alerted=False,
        )
        WishlistItem.objects.create(user=self.customer, product=product)
        stranger = make_user()

        watch_catalog()

        self.assertTrue(Notification.objects.filter(recipient=self.customer, kind='product.low_stock').exists())
        self.assertFalse(Notification.objects.filter(recipient=stranger, kind='product.low_stock').exists())

    def test_a_small_price_change_is_ignored_until_the_threshold(self):
        AutomationRule.objects.filter(trigger='new_arrival').update(enabled=False)
        product = make_product(name='Jacket', price='950.00', compare_price='1000.00', stock=5)
        ProductWatch.objects.create(
            product=product, primed=True, announced_at=timezone.now(),
            units=5, available=True, price=Decimal('1000.00'),
        )
        WishlistItem.objects.create(user=self.customer, product=product)

        watch_catalog()
        self.assertFalse(Notification.objects.filter(kind='product.price_drop').exists())

        product.price = Decimal('800.00')
        product.save(update_fields=['price'])
        watch_catalog()
        self.assertTrue(Notification.objects.filter(recipient=self.customer, kind='product.price_drop').exists())


class WishlistAndPreferenceTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_user()
        self.product = make_product()
        self.api = APIClient()
        self.api.force_authenticate(self.customer)

    def test_the_phone_can_sync_the_wishlist(self):
        response = self.api.put('/api/v1/products/wishlist/', {
            'product_ids': [str(self.product.id)],
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['product_ids'], [str(self.product.id)])
        self.assertTrue(WishlistItem.objects.filter(user=self.customer, product=self.product).exists())

        removed = self.api.delete(f'/api/v1/products/wishlist/{self.product.id}/')
        self.assertEqual(removed.status_code, 204)

    def test_offers_can_be_turned_off(self):
        response = self.api.put('/api/v1/notifications/preferences/', {'offers': False}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['offers'])
        self.assertFalse(NotificationPreference.objects.get(user=self.customer).offers)
