"""Тесты SSRF-валидации LLM_BASE_URL и флага LLM_ALLOW_PRIVATE."""

import pytest
from pydantic import ValidationError

from bot.config import Settings


def make_settings(**overrides) -> Settings:
    """Settings с заглушками обязательных полей, без чтения .env."""
    base = dict(
        vk_group_token='test-token',
        vk_group_id='12345',
        vk_bot_name='testbot',
        llm_base_url='https://llm.example.com/v1',
        _env_file=None,
    )
    base.update(overrides)
    return Settings(**base)


def test_private_192_168_url_rejected_by_default():
    with pytest.raises(ValidationError):
        make_settings(llm_base_url='http://192.168.1.100:8000/v1')


@pytest.mark.parametrize('url', [
    'http://10.0.0.5:8000/v1',
    'http://172.16.0.1/v1',
    'http://127.0.0.1:8000/v1',
    'http://localhost:8000/v1',
])
def test_other_private_urls_rejected_by_default(url):
    with pytest.raises(ValidationError):
        make_settings(llm_base_url=url)


def test_public_url_accepted_by_default():
    settings = make_settings(llm_base_url='https://llm.example.com/v1')
    assert settings.llm_base_url == 'https://llm.example.com/v1'


def test_llm_allow_private_default_is_false():
    assert make_settings().llm_allow_private is False


def test_llm_allow_private_true_allows_private_url():
    settings = make_settings(
        llm_base_url='http://192.168.1.100:8000/v1',
        llm_allow_private=True,
    )
    assert settings.llm_base_url == 'http://192.168.1.100:8000/v1'


def test_llm_allow_private_true_still_validates_scheme():
    with pytest.raises(ValidationError):
        make_settings(llm_base_url='ftp://192.168.1.100/v1', llm_allow_private=True)
