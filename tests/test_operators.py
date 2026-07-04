import unittest

from audit_engine.dsl.operators import OPERATORS, register_operator


class TestOperators(unittest.TestCase):
    def test_eq(self):
        op = OPERATORS["eq"]
        self.assertTrue(op(1, 1))
        self.assertTrue(op("abc", "abc"))
        self.assertFalse(op(1, 2))
        self.assertFalse(op("abc", "def"))

    def test_ne(self):
        op = OPERATORS["ne"]
        self.assertTrue(op(1, 2))
        self.assertTrue(op("abc", "def"))
        self.assertFalse(op(1, 1))
        self.assertFalse(op("abc", "abc"))

    def test_gt(self):
        op = OPERATORS["gt"]
        self.assertTrue(op(5, 3))
        self.assertFalse(op(3, 5))
        self.assertFalse(op(5, 5))

    def test_gte(self):
        op = OPERATORS["gte"]
        self.assertTrue(op(5, 3))
        self.assertTrue(op(5, 5))
        self.assertFalse(op(3, 5))

    def test_lt(self):
        op = OPERATORS["lt"]
        self.assertTrue(op(3, 5))
        self.assertFalse(op(5, 3))
        self.assertFalse(op(5, 5))

    def test_lte(self):
        op = OPERATORS["lte"]
        self.assertTrue(op(3, 5))
        self.assertTrue(op(5, 5))
        self.assertFalse(op(5, 3))

    def test_in(self):
        op = OPERATORS["in"]
        self.assertTrue(op("a", ["a", "b", "c"]))
        self.assertTrue(op(1, [1, 2, 3]))
        self.assertFalse(op("d", ["a", "b", "c"]))
        self.assertFalse(op(4, [1, 2, 3]))

    def test_not_in(self):
        op = OPERATORS["not_in"]
        self.assertTrue(op("d", ["a", "b", "c"]))
        self.assertFalse(op("a", ["a", "b", "c"]))

    def test_contains(self):
        op = OPERATORS["contains"]
        self.assertTrue(op("hello world", "world"))
        self.assertTrue(op("abc123", "123"))
        self.assertFalse(op("hello", "world"))

    def test_not_contains(self):
        op = OPERATORS["not_contains"]
        self.assertTrue(op("hello", "world"))
        self.assertFalse(op("hello world", "world"))

    def test_is_null(self):
        op = OPERATORS["is_null"]
        self.assertTrue(op(None, None))
        self.assertTrue(op("", None))
        self.assertFalse(op("value", None))

    def test_is_not_null(self):
        op = OPERATORS["is_not_null"]
        self.assertTrue(op("value", None))
        self.assertFalse(op(None, None))
        self.assertFalse(op("", None))
        self.assertFalse(op(" ", None))

    def test_regex(self):
        op = OPERATORS["regex"]
        self.assertTrue(op("abc123", r"\d+"))
        self.assertTrue(op("hello@example.com", r"@"))
        self.assertFalse(op("abc", r"\d+"))

    def test_not_regex(self):
        op = OPERATORS["not_regex"]
        self.assertTrue(op("abc", r"\d+"))
        self.assertFalse(op("abc123", r"\d+"))

    def test_any_contains(self):
        op = OPERATORS["any_contains"]
        self.assertTrue(op(["apple", "banana", "cherry"], "banana"))
        self.assertTrue(op(["apple", "banana", "cherry"], "app"))
        self.assertFalse(op(["apple", "banana", "cherry"], "grape"))

    def test_none_contains(self):
        op = OPERATORS["none_contains"]
        self.assertTrue(op(["apple", "banana"], "grape"))
        self.assertFalse(op(["apple", "banana"], "apple"))

    def test_coexists_with_str(self):
        op = OPERATORS["coexists_with"]
        self.assertTrue(op(["a", "b", "c"], "b"))
        self.assertFalse(op(["a", "c"], "b"))

    def test_coexists_with_dict(self):
        op = OPERATORS["coexists_with"]
        self.assertTrue(op(["apple", "banana"], {"med_list_name": "banana"}))
        self.assertFalse(op(["apple", "cherry"], {"med_list_name": "banana"}))

    def test_not_exists(self):
        op = OPERATORS["not_exists"]
        self.assertTrue(op(["a", "c"], "b"))
        self.assertFalse(op(["a", "b", "c"], "b"))

    def test_not_between(self):
        op = OPERATORS["not_between"]
        self.assertTrue(op(1, [5, 10]))
        self.assertTrue(op(15, [5, 10]))
        self.assertFalse(op(7, [5, 10]))

    def test_len_gt(self):
        op = OPERATORS["len_gt"]
        self.assertTrue(op([1, 2, 3, 4], 3))
        self.assertTrue(op("abcd", 3))
        self.assertFalse(op([1, 2], 3))
        self.assertFalse(op("ab", 3))

    def test_len_gte(self):
        op = OPERATORS["len_gte"]
        self.assertTrue(op([1, 2, 3], 3))
        self.assertTrue(op("abc", 3))
        self.assertFalse(op([1, 2], 3))

    def test_register_custom_operator(self):
        register_operator("custom_add", lambda a, b: a + b)
        self.assertIn("custom_add", OPERATORS)
        self.assertEqual(OPERATORS["custom_add"](2, 3), 5)


if __name__ == "__main__":
    unittest.main()
