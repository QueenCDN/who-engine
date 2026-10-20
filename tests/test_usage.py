"""Нормализация usage: протобуф, pydantic и запасные варианты."""
import unittest
from types import SimpleNamespace

from who_engine.providers.base import normalize_usage


class FakeField:
    def __init__(self, name):
        self.name = name


class FakeDescriptor:
    def __init__(self, names):
        self.fields = [FakeField(name) for name in names]


class FakeProtobuf:
    """Повторяет поведение protobuf: есть DESCRIPTOR, а vars() бесполезен."""

    DESCRIPTOR = FakeDescriptor(
        ['completion_tokens', 'prompt_tokens', 'total_tokens', 'tools'])

    def __init__(self):
        self.completion_tokens = 1
        self.prompt_tokens = 643
        self.total_tokens = 908
        self.tools = ['search', 'code']


class PydanticLike:
    def model_dump(self, mode='json'):
        return {'total_tokens': 42}


class UsageTests(unittest.TestCase):
    def test_none_gives_empty(self):
        self.assertEqual(normalize_usage(None), {})

    def test_protobuf_fields_are_extracted(self):
        result = normalize_usage(FakeProtobuf())
        self.assertEqual(result['total_tokens'], 908)
        self.assertEqual(result['prompt_tokens'], 643)
        self.assertEqual(result['tools'], ['search', 'code'])

    def test_protobuf_wins_over_dunder_dict(self):
        """У протобуфа есть __dict__, но в нём служебные атрибуты модуля."""
        result = normalize_usage(FakeProtobuf())
        self.assertNotIn('__module__', result)
        self.assertNotIn('__doc__', result)

    def test_model_dump_preferred(self):
        self.assertEqual(normalize_usage(PydanticLike()), {'total_tokens': 42})

    def test_plain_object_falls_back_to_vars(self):
        result = normalize_usage(SimpleNamespace(total_tokens=7, obj=object()))
        self.assertEqual(result, {'total_tokens': 7})

    def test_unknown_object_is_described(self):
        self.assertIn('repr', normalize_usage(object()))

    def test_result_is_json_serialisable(self):
        import json
        json.dumps(normalize_usage(FakeProtobuf()), ensure_ascii=False)


if __name__ == '__main__':
    unittest.main()
