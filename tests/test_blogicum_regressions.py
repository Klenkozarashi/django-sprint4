import re
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import path, reverse
from django.utils import timezone

from blog.models import Category, Comment, Post
from blogicum.urls import handler404, handler500, urlpatterns

pytestmark = pytest.mark.django_db
PASSWORD = 'Local-check-83!sunrise'


def failing_view(request):
    raise RuntimeError('Test error handler')


urlpatterns = [*urlpatterns, path('test-server-error/', failing_view)]


@pytest.fixture
def author():
    return get_user_model().objects.create_user(
        username='regression-author', email='author@example.com',
        password=PASSWORD,
    )


@pytest.fixture
def post(author):
    category = Category.objects.create(
        title='Проверка', slug='regression', description='Тестовая категория',
    )
    return Post.objects.create(
        author=author, category=category, title='Тестовая публикация',
        text='Содержимое публикации', pub_date=timezone.now(),
    )


def test_registration_login_and_logout(client):
    response = client.post(reverse('registration'), {
        'username': 'new-reader', 'password1': PASSWORD, 'password2': PASSWORD,
    })
    assert response.status_code == 302
    assert response.url == reverse('login')
    assert client.post(reverse('login'), {
        'username': 'new-reader', 'password': PASSWORD,
    }).status_code == 302
    assert '_auth_user_id' in client.session
    response = client.post(reverse('logout'))
    assert response.status_code == 200
    assert 'Вы вышли из системы' in response.content.decode()
    assert '_auth_user_id' not in client.session


def test_password_reset_file_backend(client, author, tmp_path):
    with override_settings(
        EMAIL_BACKEND='django.core.mail.backends.filebased.EmailBackend',
        EMAIL_FILE_PATH=tmp_path,
    ):
        response = client.post(reverse('password_reset'), {
            'email': author.email,
        })
    assert response.status_code == 302
    messages = list(tmp_path.iterdir())
    assert len(messages) == 1
    message = messages[0].read_text()
    reset_url = re.search(r'http://testserver(/auth/reset/\S+)', message)[1]
    response = client.get(reset_url)
    assert response.status_code == 302
    response = client.post(response.url, {
        'new_password1': PASSWORD + 'new', 'new_password2': PASSWORD + 'new',
    })
    assert response.status_code == 302
    author.refresh_from_db()
    assert author.check_password(PASSWORD + 'new')
    assert client.login(username=author.username, password=PASSWORD + 'new')


def test_password_change(client, author):
    client.force_login(author)
    response = client.post(reverse('password_change'), {
        'old_password': PASSWORD,
        'new_password1': PASSWORD + 'new',
        'new_password2': PASSWORD + 'new',
    })
    assert response.status_code == 302
    author.refresh_from_db()
    assert author.check_password(PASSWORD + 'new')
    assert '_auth_user_id' in client.session


def test_delete_requires_owner_and_confirmation(client, author, post):
    outsider = get_user_model().objects.create_user(username='outsider')
    delete_url = reverse('blog:delete_post', args=[post.pk])
    edit_url = reverse('blog:edit_post', args=[post.pk])
    client.force_login(outsider)
    for url in (edit_url, delete_url):
        response = client.post(url, {'title': 'Подмена'})
        assert response.status_code == 302
        assert response.url == reverse('blog:post_detail', args=[post.pk])
    post.refresh_from_db()
    assert post.title == 'Тестовая публикация'
    client.force_login(author)
    response = client.get(delete_url)
    assert response.status_code == 200
    assert post.text in response.content.decode()
    assert Post.objects.filter(pk=post.pk).exists()
    assert client.post(delete_url).status_code == 302
    assert not Post.objects.filter(pk=post.pk).exists()


def test_comment_belongs_to_url_post_and_owner(client, author, post):
    other_post = Post.objects.create(
        author=author, category=post.category, title='Второй пост',
        text='Другой пост', pub_date=timezone.now(),
    )
    comment = Comment.objects.create(author=author, post=post, text='Ответ')
    client.force_login(author)
    for action in ('edit_comment', 'delete_comment'):
        url = reverse('blog:' + action, args=[other_post.pk, comment.pk])
        assert client.get(url).status_code == 404
        assert client.post(url, {'text': 'Подмена'}).status_code == 404
    outsider = get_user_model().objects.create_user(username='other-reader')
    client.force_login(outsider)
    for action in ('edit_comment', 'delete_comment'):
        url = reverse('blog:' + action, args=[post.pk, comment.pk])
        assert client.post(url, {'text': 'Подмена'}).status_code == 404
    comment.refresh_from_db()
    assert comment.text == 'Ответ'
    client.force_login(author)
    url = reverse('blog:delete_comment', args=[post.pk, comment.pk])
    assert client.get(url).status_code == 200
    assert Comment.objects.filter(pk=comment.pk).exists()


def test_hidden_post_cannot_be_commented_by_outsider(client, author, post):
    post.is_published = False
    post.save()
    outsider = get_user_model().objects.create_user(username='hidden-reader')
    client.force_login(outsider)
    url = reverse('blog:add_comment', args=[post.pk])
    assert client.post(url, {'text': 'Недоступный пост'}).status_code == 404
    assert not post.comments.exists()


def test_scheduled_post_becomes_public(client, author, post):
    post.pub_date = timezone.now() + timedelta(days=1)
    post.save()
    url = reverse('blog:post_detail', args=[post.pk])
    assert client.get(url).status_code == 404
    client.force_login(author)
    assert client.get(url).status_code == 200
    client.logout()
    post.pub_date = timezone.now() - timedelta(seconds=1)
    post.save()
    assert client.get(url).status_code == 200


def test_csrf_and_server_error_handlers():
    client = Client(enforce_csrf_checks=True, raise_request_exception=False)
    response = client.post(reverse('registration'), {})
    assert response.status_code == 403
    assert 'pages/403csrf.html' in [t.name for t in response.templates]
    with override_settings(ROOT_URLCONF=__name__, DEBUG=False):
        response = client.get('/test-server-error/')
    assert response.status_code == 500
    assert 'pages/500.html' in [t.name for t in response.templates]
