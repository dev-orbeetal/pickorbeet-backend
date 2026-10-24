"""A customer only sees their own thread, and a staff reply comes back to them."""
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from apps.orders.tests.factories import ShopTestCase, make_order, make_user
from apps.support.models import Message


class SupportThreadTests(ShopTestCase):
    def test_a_customer_cannot_read_another_customers_thread(self):
        owner = make_user(first_name='Nadia')
        other = make_user()
        accountant = make_user(role='accountant')
        owner_api = APIClient()
        other_api = APIClient()
        accountant_api = APIClient()
        owner_api.force_authenticate(owner)
        other_api.force_authenticate(other)
        accountant_api.force_authenticate(accountant)

        opened = owner_api.get('/api/v1/support/conversation/')
        self.assertEqual(opened.status_code, 200, opened.content)
        self.assertEqual(opened.json()['profile']['display_name'], 'Nadia Rahman')
        self.assertTrue(opened.json()['profile']['avatar'])
        self.assertIn('Hi Nadia!', opened.json()['messages'][0]['body'])
        sent = owner_api.post('/api/v1/support/messages/', {'body': 'Where is my parcel?'}, format='json')
        self.assertEqual(sent.status_code, 201, sent.content)

        theirs = other_api.get('/api/v1/support/conversation/')
        self.assertEqual(theirs.status_code, 200, theirs.content)
        self.assertNotEqual(theirs.json()['id'], opened.json()['id'])
        self.assertFalse(any(row['body'] == 'Where is my parcel?' for row in theirs.json()['messages']))

        hidden = other_api.get(f"/api/v1/support/inbox/{opened.json()['id']}/")
        self.assertEqual(hidden.status_code, 403)
        self.assertEqual(accountant_api.get('/api/v1/support/inbox/').status_code, 403)

    def test_track_topic_stores_the_requested_order_card(self):
        customer = make_user()
        older = make_order(user=customer, status='shipped')
        newer = make_order(user=customer, status='pending')
        client = APIClient()
        client.force_authenticate(customer)

        tracked = client.post('/api/v1/support/messages/', {
            'topic': 'track_order',
            'order_number': older.order_number,
        }, format='json')
        self.assertEqual(tracked.status_code, 201, tracked.content)
        card = tracked.json()['order']
        self.assertEqual(card['id'], str(older.id))
        self.assertEqual(card['order_number'], older.order_number)
        self.assertEqual(card['product_name'], older.items.first().product_name)
        self.assertEqual(card['status'], 'shipped')
        self.assertTrue(card['expected_delivery'])
        stored = Message.objects.get(pk=tracked.json()['id'])
        self.assertEqual(stored.order_id, older.id)
        self.assertEqual(stored.topic, Message.TRACK_ORDER)

        latest = client.post('/api/v1/support/messages/', {'topic': 'track_order'}, format='json')
        self.assertEqual(latest.json()['order']['id'], str(newer.id))

        payment = client.post('/api/v1/support/messages/', {'topic': 'payment'}, format='json')
        self.assertIsNone(payment.json()['order'])

    def test_staff_reply_is_visible_to_that_customer(self):
        customer = make_user()
        stranger = make_user()
        seller = make_user(role='seller')
        customer_api = APIClient()
        stranger_api = APIClient()
        staff_api = APIClient()
        customer_api.force_authenticate(customer)
        stranger_api.force_authenticate(stranger)
        staff_api.force_authenticate(seller)

        opened = customer_api.get('/api/v1/support/conversation/')
        conversation_id = opened.json()['id']
        reply = staff_api.post(
            f'/api/v1/support/inbox/{conversation_id}/reply/',
            {'body': 'It ships today.'},
            format='json',
        )
        self.assertEqual(reply.status_code, 201, reply.content)
        self.assertEqual(reply.json()['author'], 'agent')

        seen = customer_api.get('/api/v1/support/conversation/')
        self.assertTrue(any(row['body'] == 'It ships today.' for row in seen.json()['messages']))
        self.assertFalse(any(
            row['body'] == 'It ships today.'
            for row in stranger_api.get('/api/v1/support/conversation/').json()['messages']
        ))
        note = Notification.objects.get(recipient=customer, kind='support.reply')
        self.assertEqual(note.title, 'Nadia Rahman')
        self.assertEqual(note.data['target'], 'support')
        self.assertFalse(Notification.objects.filter(recipient=stranger, kind='support.reply').exists())
