"""Tes untuk helper pembulatan angka yang disuntik ke prompt LLM.

Tujuan: LLM tidak pernah melihat angka berekor panjang (mis. 28.42351)
sehingga jawaban yang mengutipnya juga rapi (28.42).
"""
from services.advisor.formatting import round_numbers


def test_rounds_float_to_two_decimals():
    assert round_numbers({"rsi": 28.42351}) == {"rsi": 28.42}


def test_leaves_int_str_none_untouched():
    src = {"shares": 1000, "ticker": "BBRI", "trend": None}
    assert round_numbers(src) == {"shares": 1000, "ticker": "BBRI", "trend": None}


def test_bool_not_treated_as_number():
    src = {"found": True, "active": False}
    assert round_numbers(src) == {"found": True, "active": False}


def test_rounds_nested_dict_and_list():
    src = {
        "indicators": {"RSI_14": 1.234567, "MA_20": 4123.98765},
        "items": [{"pe": 9.14235}, {"pbv": 2.001999}],
    }
    assert round_numbers(src) == {
        "indicators": {"RSI_14": 1.23, "MA_20": 4123.99},
        "items": [{"pe": 9.14}, {"pbv": 2.0}],
    }


def test_rounds_top_level_float_and_list():
    assert round_numbers(3.14159) == 3.14
    assert round_numbers([1.111, 2.999]) == [1.11, 3.0]


def test_custom_ndigits():
    assert round_numbers({"x": 1.23456}, ndigits=3) == {"x": 1.235}


def test_does_not_mutate_input():
    src = {"rsi": 28.42351, "nested": {"pe": 9.14235}}
    round_numbers(src)
    assert src == {"rsi": 28.42351, "nested": {"pe": 9.14235}}
