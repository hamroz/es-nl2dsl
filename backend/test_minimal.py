"""
Minimal test to verify Django test setup is working.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_simple_user_creation(db_with_migrations):
    """Test creating a user in the database"""
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )
    assert user.username == 'testuser'
    assert user.email == 'test@example.com'
    assert User.objects.count() == 1


class SimpleTestCase(TestCase):
    """Test case using Django's TestCase"""
    
    @pytest.fixture(autouse=True)
    def setup_db(self, db_with_migrations):
        """Ensure database is setup with migrations"""
        pass
    
    def test_user_model_creation(self):
        """Test creating a user using Django TestCase"""
        user = User.objects.create_user(
            username='testuser2',
            email='test2@example.com', 
            password='testpass123'
        )
        self.assertEqual(user.username, 'testuser2')
        self.assertEqual(user.email, 'test2@example.com')
        self.assertEqual(User.objects.count(), 1)