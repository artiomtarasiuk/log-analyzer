import json
import os.path
import unittest
from datetime import datetime

import log_analyzer


class TestLogAnalyzer(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.test_dir = "./test/"
        self.template_dir = os.path.join("./reports/", "report.html")
        with open("./config.json", "r") as f:
            self.default_config = json.load(f)
        self.test_file_date = datetime(2021, 12, 25).date()
        self.test_log_metadata = log_analyzer.LogMetadata(
            path_to_file="./test/nginx-access-ui.log-20211225",
            file_name="nginx-access-ui.log-20211225",
            file_extension="",
            file_date=datetime(2021, 12, 25).date(),
        )
        self.test_url_stats = {"test.com": [0.39, 0.133, 0.199, 0.704]}
        self.test_report_data = [
            {
                "count": 4,
                "count_perc": 100.0,
                "time_avg": 0.356,
                "time_max": 0.704,
                "time_med": 0.294,
                "time_perc": 100.0,
                "time_sum": 1.426,
                "url": "test.com",
            }
        ]

    def test_parse_args(self):
        args = log_analyzer.parse_args()
        self.assertEqual(args.config, "./config.json")

    def test_parse_config(self):
        args = log_analyzer.parse_args()
        config = log_analyzer.parse_config(args.config, {})
        self.assertEqual(config, self.default_config)

    def test_parse_config_missing(self):
        args = log_analyzer.parse_args()
        args.__setattr__("config", "unknown.json")
        with self.assertRaises(FileNotFoundError):
            log_analyzer.parse_config(args.config, {})

    def test_get_latest_log(self):
        got = log_analyzer.get_latest_log(self.test_dir)
        self.assertEqual(got, self.test_log_metadata)

    def test_build_report_path(self):
        got = log_analyzer.build_report_path(self.test_dir, self.test_file_date)
        self.assertEqual(got, os.path.join(self.test_dir, "report-2021.12.25.html"))

    def test_parse_log_records(self):
        got = log_analyzer.parse_log_records(
            self.test_log_metadata, error_threshold=0.1
        )
        self.assertEqual(got, self.test_url_stats)

    def test_build_report_object(self):
        got = log_analyzer.build_report_object(self.test_url_stats)
        self.assertEqual(got, self.test_report_data)

    def test_filter_report(self):
        got = log_analyzer.filter_report(self.test_report_data, 1)
        self.assertEqual(got, self.test_report_data)

    def test_dump_final_report(self):
        path_to_report = log_analyzer.build_report_path(
            self.test_dir, self.test_file_date
        )
        log_analyzer.dump_final_report(
            self.template_dir, path_to_report, self.test_report_data
        )
        report_file = os.path.join(self.test_dir, "report-2021.12.25.html")
        self.assertTrue(os.path.exists(report_file))
        os.remove(report_file)


if __name__ == "__main__":
    unittest.main()
