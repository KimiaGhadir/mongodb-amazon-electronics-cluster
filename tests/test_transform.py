import json
import sys

sys.path.insert(0, "src")

from common import flatten_categories, transform_record


def test_required_patterns_on_supplied_sample():
    raw = json.loads(open("data/sample_500.jsonl", encoding="utf8").readline())
    transformed = transform_record(raw)
    assert isinstance(transformed["categories"], list)
    assert isinstance(transformed["details"], list)
    assert all(set(pair) >= {"k", "v"} for pair in transformed["details"])


def test_category_hierarchy_is_recursively_flattened_and_deduplicated():
    value = ["Electronics", ["Computers", ["Laptops"]], "Electronics"]
    assert flatten_categories(value) == ["Electronics", "Computers", "Laptops"]


def test_dynamic_detail_objects_are_serialized_to_scalar_values():
    raw = {
        "categories": ["Electronics"],
        "details": {"Simple": "x", "Nested": {"a": 1}},
    }
    transformed = transform_record(raw)
    assert {"k": "Simple", "v": "x"} in transformed["details"]
    nested = next(item["v"] for item in transformed["details"] if item["k"] == "Nested")
    assert isinstance(nested, str)
    assert json.loads(nested) == {"a": 1}
