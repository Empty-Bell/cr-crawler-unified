def test_parse_local_html():
def test_save_to_csv(tmp_path):
import os
import csv
import tempfile
import unittest

from cr_crawler_washer import parse_html_file, save_to_csv


class CrawlerWasherTests(unittest.TestCase):
    def test_parse_local_html(self):
        # use one of the bundled snippet files for a deterministic sample
        sample = os.path.join(os.path.dirname(__file__),
                              "div class=chart-wrapper is-collapse1.txt")
        self.assertTrue(os.path.exists(sample), "sample HTML file should be present")
        headers, data = parse_html_file(sample)
        # basic sanity checks
        self.assertIsInstance(headers, list)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1, "should extract at least one product")
        self.assertTrue(any("Overall" in h for h in headers))

    def test_save_to_csv(self):
        headers = ["A", "B", "Category"]
        rows = [{"A": 1, "B": 2, "Category": "foo"}]
        tmpdir = tempfile.gettempdir()
        out_file = os.path.join(tmpdir, "out_test.csv")
        if os.path.exists(out_file):
            os.remove(out_file)
        save_to_csv(headers, rows, filename=out_file)
        self.assertTrue(os.path.exists(out_file))
        with open(out_file, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, headers)
            records = list(reader)
            self.assertEqual(records[0]["Category"], "foo")


if __name__ == "__main__":
    unittest.main()
