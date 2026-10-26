from friday.core.redaction import redact


def test_redacts_nested_secret_fields():
    value = {"provider": {"api_key": "secret-value"}, "safe": "visible"}
    assert redact(value) == {"provider": {"api_key": "[REDACTED]"}, "safe": "visible"}


def test_redacts_key_shaped_text():
    assert redact("token sk-project_abcdefghijklmnopqrstuvwxyz") == "token [REDACTED]"

