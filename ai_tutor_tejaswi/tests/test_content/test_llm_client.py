from content.llm_client import MockLLMClient


def test_mock_returns_string():
    client = MockLLMClient(["hello"])
    assert client.generate("prompt") == "hello"


def test_mock_returns_dict_for_schema():
    client = MockLLMClient([{"key": "value"}])
    result = client.generate("prompt", response_schema={})
    assert result == {"key": "value"}


def test_mock_cycles_responses():
    client = MockLLMClient(["a", "b"])
    assert client.generate("p") == "a"
    assert client.generate("p") == "b"
    assert client.generate("p") == "a"  # wraps


def test_mock_empty_returns_defaults():
    client = MockLLMClient()
    assert client.generate("p") == ""
    assert client.generate("p", response_schema={}) == {}
