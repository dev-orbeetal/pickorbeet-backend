# Notifications

The inbox is the source of truth. The WebSocket and Firebase Cloud Messaging only deliver a row that is already saved. A missed push or a dropped socket still shows up the next time the app, website, or admin panel opens the inbox.

Guests who check out without an account do not get a device or a socket. Staff still get a "new order" row. In-shop POS orders are not announced.

## What you need on the server

1. Redis, reachable at `REDIS_URL` (default `redis://127.0.0.1:6379/0`).
2. The existing Gunicorn process keeps serving `/api/`.
3. A Daphne process for the socket only:

```bash
daphne -b 127.0.0.1 -p 8016 core.asgi:application
```

4. A Celery worker so checkout and payment callbacks are not blocked on push:

```bash
celery -A core worker -l info
```

5. Nginx forwards `/ws/` to Daphne and upgrades the connection. Point `daphne_backend` at the Daphne port.

```nginx
location /ws/ {
    proxy_pass http://127.0.0.1:8016;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 3600s;
}
```

`python manage.py runserver` uses Daphne as well, so local development can open the socket without a second process. Celery still needs Redis unless `CELERY_TASK_ALWAYS_EAGER=True`.

Apply the new tables with:

```bash
python manage.py migrate notifications
```

## Firebase (phone push)

Push is skipped, and the inbox still works, until these exist. Do not commit the credential files.

1. Create a Firebase project and add the Android app `com.pickorbeet.pickorbeet` and the iOS app.
2. Download `google-services.json` into `pickorbeet-app/android/app/`. The Android build applies the Google Services plugin only when that file is present.
3. Download `GoogleService-Info.plist` into `pickorbeet-app/ios/Runner/` and add it to the Runner target.
4. In Firebase, generate a service-account JSON. Put it on the server outside the git tree and set `FIREBASE_CREDENTIALS` to its absolute path.
5. For iOS delivery, upload an APNs authentication key in the Firebase project settings.

The phone app asks for notification permission, registers its FCM token at `PUT /api/v1/notifications/devices/`, and deletes it on logout. The website and the admin panel use the socket and the inbox only. They do not register for browser push.

## Socket

Clients connect to `ws(s)://<api-host>/ws/notifications/?token=<access>`. When `NEXT_PUBLIC_API_URL` is a same-origin path such as `/api/v1`, the socket uses the page's own origin. A missing or expired access token is closed with code `4401`. The client refreshes the access token and connects again. Each signed-in user joins `notifications_<user id>`.

Messages:

- `{"type": "notification.created", "notification": {...}, "unread_count": 1}`
- `{"type": "notification.read", "unread_count": 0}`

The socket does not replay history. On connect, clients load `GET /api/v1/notifications/`.
