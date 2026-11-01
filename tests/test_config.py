"""環境変数の読み取り。"""

from config import env_int


def test_env_int_invalid_returns_default(monkeypatch) -> None:
    monkeypatch.setenv("TEST_ENV_INT", "abc")
    assert env_int("TEST_ENV_INT", 7) == 7


def test_env_int_empty_returns_default(monkeypatch) -> None:
    monkeypatch.setenv("TEST_ENV_INT", "  ")
    assert env_int("TEST_ENV_INT", 3) == 3


def test_env_int_reads_number(monkeypatch) -> None:
    monkeypatch.setenv("TEST_ENV_INT", "42")
    assert env_int("TEST_ENV_INT", 0) == 42
