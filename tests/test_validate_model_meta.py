"""meta.model (model settings exported for the site): passing, failing and missing inputs for validate.check_model_meta."""
import unittest

import validate


def errors_for(meta):
    errors = []
    validate.check_model_meta({"meta": meta}, errors)
    return errors


class ModelMeta(unittest.TestCase):
    def test_model_defaults_pass(self):
        from fplmodel import DEFAULTS
        self.assertEqual(errors_for({"model": {"home": DEFAULTS["home"], "cs_k": DEFAULTS["cs_k"]}}), [])

    def test_range_edges_pass(self):
        self.assertEqual(errors_for({"model": {"home": 1.0, "cs_k": 0.5}}), [])
        self.assertEqual(errors_for({"model": {"home": 1.5, "cs_k": 1.5}}), [])

    def test_older_build_without_the_field_is_not_checked(self):
        self.assertEqual(errors_for({}), [])

    def test_out_of_range_fails(self):
        for model, key in (({"home": 0.95, "cs_k": 0.9}, "home"), ({"home": 1.6, "cs_k": 0.9}, "home"),
                           ({"home": 1.05, "cs_k": 0.4}, "cs_k"), ({"home": 1.05, "cs_k": 1.6}, "cs_k")):
            with self.subTest(model=model):
                errs = errors_for({"model": model})
                self.assertEqual(len(errs), 1)
                self.assertIn(f"meta.model.{key}", errs[0])

    def test_not_a_finite_number_fails(self):
        for bad in (None, "0.9", float("nan"), float("inf"), True):
            with self.subTest(bad=bad):
                self.assertEqual(len(errors_for({"model": {"home": 1.05, "cs_k": bad}})), 1)
                self.assertEqual(len(errors_for({"model": {"home": bad, "cs_k": 0.9}})), 1)

    def test_missing_key_or_wrong_shape_fails(self):
        self.assertEqual(len(errors_for({"model": {"home": 1.05}})), 1)
        self.assertEqual(len(errors_for({"model": {}})), 2)
        self.assertEqual(len(errors_for({"model": [1.05, 0.9]})), 1)


if __name__ == "__main__":
    unittest.main()
