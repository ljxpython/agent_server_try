from __future__ import annotations

from app.auth.openfga import is_tuple_already_exists_error


def test_is_tuple_already_exists_error_true() -> None:
    assert (
        is_tuple_already_exists_error(
            400,
            "cannot write a tuple which already exists: user: 'user:test', relation: 'member', object: 'tenant:t1'",
        )
        is True
    )


def test_is_tuple_already_exists_error_true_for_phrase_variant() -> None:
    assert (
        is_tuple_already_exists_error(
            400,
            "cannot write tuple which already exists: user: 'user:test', relation: 'member', object: 'tenant:t1'",
        )
        is True
    )


def test_is_tuple_already_exists_error_false_for_other_400() -> None:
    assert is_tuple_already_exists_error(400, "write_failed_due_to_invalid_input: malformed tuple") is False


def test_is_tuple_already_exists_error_false_for_non_400() -> None:
    assert (
        is_tuple_already_exists_error(
            500,
            "cannot write a tuple which already exists",
        )
        is False
    )
