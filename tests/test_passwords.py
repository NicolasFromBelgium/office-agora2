"""Password hashing and verification."""

from agora.services.passwords import hash_password, verify_password


def test_hash_and_verify() -> None:
    hashed = hash_password("ChangeMe!OfficeAgora", rounds=4)
    assert hashed != "ChangeMe!OfficeAgora"
    assert verify_password("ChangeMe!OfficeAgora", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_verify_corrupt_hash() -> None:
    assert verify_password("x", "not-a-hash") is False
