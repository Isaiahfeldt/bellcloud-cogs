import time
import jwt
import pytest
from bellapi.auth import verify_jwt, check_ip, AuthError

SECRET = "test_secret_abc123"


def make_token(guild_id="123", sub="456", exp_offset=300, secret=SECRET):
    return jwt.encode(
        {"iss": "bellbot.xyz", "sub": sub, "guild_id": guild_id,
         "iat": int(time.time()), "exp": int(time.time()) + exp_offset},
        secret, algorithm="HS256"
    )


# --- verify_jwt ---

def test_valid_token_any_guild():
    token = make_token(guild_id="123")
    payload = verify_jwt(token, SECRET, required_guild_id=None)
    assert payload["guild_id"] == "123"
    assert payload["sub"] == "456"


def test_valid_token_guild_scope_match():
    token = make_token(guild_id="123")
    payload = verify_jwt(token, SECRET, required_guild_id="123")
    assert payload["guild_id"] == "123"


def test_token_guild_scope_mismatch():
    token = make_token(guild_id="123")
    with pytest.raises(AuthError) as exc:
        verify_jwt(token, SECRET, required_guild_id="999")
    assert exc.value.status == 403


def test_expired_token():
    token = make_token(exp_offset=-10)
    with pytest.raises(AuthError) as exc:
        verify_jwt(token, SECRET, required_guild_id=None)
    assert exc.value.status == 403


def test_wrong_secret():
    token = make_token(secret="wrong_secret")
    with pytest.raises(AuthError) as exc:
        verify_jwt(token, SECRET, required_guild_id=None)
    assert exc.value.status == 403


def test_malformed_token():
    with pytest.raises(AuthError) as exc:
        verify_jwt("not.a.token", SECRET, required_guild_id=None)
    assert exc.value.status == 403


def test_missing_bearer_prefix_returns_error():
    with pytest.raises(AuthError):
        verify_jwt("", SECRET, required_guild_id=None)


# --- check_ip ---

def test_ip_in_allowlist():
    assert check_ip("1.2.3.4", ["1.2.3.4", "5.6.7.8"]) is True


def test_ip_not_in_allowlist():
    assert check_ip("9.9.9.9", ["1.2.3.4"]) is False


def test_empty_allowlist_blocks_all():
    assert check_ip("1.2.3.4", []) is False
