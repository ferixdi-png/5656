from app.kie.contract import normalize_base_url, parse_result


def test_normalize_base_url():
    assert normalize_base_url("https://example.com/api/v1") == "https://example.com"
    assert normalize_base_url("https://example.com/") == "https://example.com"


def test_parse_result_handles_result_json():
    record = {"resultJson": "{\"resultUrls\": [\"https://x\"]}"}
    parsed = parse_result(record)
    assert parsed["result_urls"] == ["https://x"]


def test_parse_result_tolerates_bad_json():
    record = {"resultJson": "not json https://example.com/file.png"}
    parsed = parse_result(record)
    assert "https://example.com/file.png" in parsed["result_urls"]


def test_parse_failure_empty_message():
    from app.kie.contract import parse_failure

    code, message = parse_failure({"failCode": "X"})
    assert code == "X"
    assert "Ошибка генерации" in message
