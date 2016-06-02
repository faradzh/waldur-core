from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.utils import timezone
from django.core.cache import cache

from mock import patch

from rest_framework import test, status
from rest_framework.authtoken.models import Token


class TokenAuthenticationTest(test.APITransactionTestCase):
    def setUp(self):
        self.username = 'test'
        self.password = 'secret'
        self.auth_url = 'http://testserver' + reverse('auth-password')
        self.test_url = 'http://testserver/api/'
        get_user_model().objects.create_user(self.username, 'admin@example.com', self.password)

    def tearDown(self):
        cache.clear()

    def test_user_can_authenticate_with_token(self):
        response = self.client.post(self.auth_url, data={'username': self.username, 'password': self.password})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        token = response.data['token']
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)
        response = self.client.get(self.test_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_use_expired_token(self):
        response = self.client.post(self.auth_url, data={'username': self.username, 'password': self.password})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        token = response.data['token']
        lifetime = settings.NODECONDUCTOR.get('TOKEN_LIFETIME', timezone.timedelta(hours=1))
        mocked_now = timezone.now() + lifetime
        with patch('django.utils.timezone.now', lambda: mocked_now):
            self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)
            response = self.client.get(self.test_url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(response.data['detail'], 'Token has expired.')

    def test_token_creation_time_is_updated_on_every_request(self):
        response = self.client.post(self.auth_url, data={'username': self.username, 'password': self.password})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data['token']
        created1 = Token.objects.values_list('created', flat=True).get(key=token)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)
        self.client.get(self.test_url)
        created2 = Token.objects.values_list('created', flat=True).get(key=token)
        self.assertTrue(created1 < created2)

    def test_account_is_blocked_after_five_failed_attempts(self):
        for attempt in range(5):
            response = self.client.post(self.auth_url, data={'username': self.username, 'password': 'WRONG'})
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # this one should fail with a different error message
        self.client.post(self.auth_url, data={'username': self.username, 'password': 'WRONG'})
        self.assertEqual(response.data['detail'], 'Username is locked out. Try in 10 minutes.')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_token_is_recreated_on_successful_authentication(self):
        response = self.client.post(self.auth_url, data={'username': self.username, 'password': self.password})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token1 = response.data['token']

        lifetime = settings.NODECONDUCTOR.get('TOKEN_LIFETIME', timezone.timedelta(hours=1))
        mocked_now = timezone.now() + lifetime
        with patch('django.utils.timezone.now', lambda: mocked_now):
            response = self.client.post(self.auth_url, data={'username': self.username, 'password': self.password})
            token2 = response.data['token']
            self.assertNotEqual(token1, token2)

    def test_not_expired_token_creation_time_is_updated_on_authentication(self):
        response = self.client.post(self.auth_url, data={'username': self.username, 'password': self.password})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token1 = response.data['token']
        created1 = Token.objects.values_list('created', flat=True).get(key=token1)

        response = self.client.post(self.auth_url, data={'username': self.username, 'password': self.password})
        token2 = response.data['token']
        created2 = Token.objects.values_list('created', flat=True).get(key=token2)

        self.assertEqual(token1, token2)
        self.assertTrue(created1 < created2)
