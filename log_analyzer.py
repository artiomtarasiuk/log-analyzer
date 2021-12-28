#!/usr/bin/env python3
import argparse
import gzip
import json
import logging
import os
import re
import sys
from collections import defaultdict, namedtuple
from datetime import date, datetime
from statistics import median
from string import Template
from typing import AnyStr, Dict, List, Match, Optional, Tuple, Union

DEFAULT_CONFIG = {"REPORT_SIZE": 1000, "REPORT_DIR": "./reports", "LOG_DIR": "./log"}
ConfigType = Dict[str, Union[str, int]]
ReportDataType = List[Dict[str, Union[str, int, float]]]
LogMetadata = namedtuple(
    "LogMetadata", ("path_to_file", "file_name", "file_date", "file_extension")
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=str, default="./config.json", help="Path to config file"
    )
    return parser.parse_args()


def parse_config(config_path: str, default_config: ConfigType) -> ConfigType:
    if not os.path.exists(config_path):
        raise FileNotFoundError("Invalid config.json path")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError as err:
        raise Exception(f"Unable to decode JSON: {err}")
    if not config:
        logging.info("Provided config file is empty, applying default configuration")
        return default_config
    return {**default_config, **config}


def set_logging(config: ConfigType) -> None:
    log_format = "[%(asctime)s] %(levelname).1s %(message)s"
    date_fmt = "%Y.%m.%d %H:%M:%S"
    file_name = config["LOG_FILE"] if "LOG_FILE" in config else None
    logging.basicConfig(
        level=logging.INFO, format=log_format, datefmt=date_fmt, filename=file_name
    )


def parse_log_filename(match: Optional[Match[AnyStr]]) -> Tuple[Optional[date], str]:
    file_date_str, file_extension = tuple(match.groupdict().values())
    try:
        file_date = datetime.strptime(file_date_str, "%Y%m%d").date()
    except ValueError:
        logging.info(f"Unable to parse date from {file_date_str}")
        file_date = None
    return file_date, file_extension


def get_latest_log(log_directory: str) -> Optional[LogMetadata]:
    file_name_pattern = re.compile(
        r"nginx-access-ui\.log-(?P<date>\d{8})(?P<extension>\.gz|$)"
    )
    latest_log = None
    latest_date = datetime.min.date()
    for log_file in os.listdir(log_directory):
        match = file_name_pattern.search(log_file)
        if not match:
            continue
        file_date, file_extension = parse_log_filename(match)
        if not file_date:
            continue
        if file_date > latest_date:
            latest_date = file_date
            latest_log = LogMetadata(
                path_to_file=os.path.join(log_directory, log_file),
                file_name=log_file,
                file_date=latest_date,
                file_extension=file_extension,
            )
    return latest_log


def build_report_path(report_directory: str, file_date: date) -> str:
    dt_str = file_date.strftime("%Y.%m.%d")
    report_name = f"report-{dt_str}.html"
    return os.path.join(report_directory, report_name)


def parse_log_records(
    log_metadata: LogMetadata, error_threshold: float
) -> Dict[str, List[float]]:
    func = gzip.open if log_metadata.file_extension == ".gz" else open
    with func(log_metadata.path_to_file, "rb") as f:
        pattern = re.compile(
            r'(?:POST|GET|HEAD|PUT|OPTIONS)\s+(?P<url>.+)\s+HTTP\/\d\.\d"\s.+\s'
            r"(?P<request_time>\d+\.\d+)$"
        )
        data = defaultdict(list)
        total_lines_count = 0
        total_failed_lines_count = 0
        for line_idx, line in enumerate(f, start=1):
            record = line.decode("utf-8")
            match = re.search(pattern, record)
            if not match:
                total_failed_lines_count += 1
                continue
            url, request_time = tuple(match.groupdict().values())
            data[url].append(float(request_time))
            total_lines_count += 1
        failed_lines_ratio = total_failed_lines_count / total_lines_count
        if failed_lines_ratio > error_threshold:
            raise Exception(
                f"Unable to parse log file. High failed lines ratio: {failed_lines_ratio}"
            )
        return data


def build_report_object(url_stats: Dict[str, List[float]]) -> ReportDataType:
    report_data = []
    count_total = sum(len(request_times) for _, request_times in url_stats.items())
    time_sum_total = sum(
        request_time
        for _, request_times in url_stats.items()
        for request_time in request_times
    )
    for url, request_times in url_stats.items():
        count_url = len(request_times)
        time_sum_url = sum(request_times)
        obj = {
            "url": url,
            "count": count_url,
            "count_perc": round(count_url / count_total * 100, 3),
            "time_sum": round(time_sum_url, 3),
            "time_perc": round(time_sum_url / time_sum_total * 100, 3),
            "time_avg": round(time_sum_url / count_url, 3),
            "time_max": sorted(request_times, reverse=False)[-1],
            "time_med": round(median(request_times), 3),
        }
        report_data.append(obj)
    return report_data


def filter_report(report_data: ReportDataType, report_size: int) -> ReportDataType:
    final_report_data = sorted(report_data, key=lambda x: x["time_sum"], reverse=True)
    return final_report_data[:report_size]


def dump_final_report(
    path_to_template: str,
    path_to_report: str,
    report_data: List[Dict[str, Union[str, int, float]]],
):
    with open(path_to_template, "r") as f:
        template = Template(f.read())
    report = template.safe_substitute(table_json=json.dumps(report_data))
    with open(path_to_report, "w") as f:
        f.write(report)


def main(default_config: ConfigType):
    args = parse_args()
    config = parse_config(args.config, default_config)
    set_logging(config)
    log_metadata = get_latest_log(config["LOG_DIR"])
    if not log_metadata:
        logging.info("No logs found to be processed")
        sys.exit(0)
    path_to_report = build_report_path(config["REPORT_DIR"], log_metadata.file_date)
    if os.path.exists(path_to_report):
        logging.info(
            f"Report for the latest date {log_metadata.file_date} already exists"
        )
    error_threshold = config.get("ERROR_THRESHOLD", 0.1)
    url_stats = parse_log_records(log_metadata, error_threshold=error_threshold)
    if not url_stats:
        logging.info("Unable to generate report: no related records found")
        sys.exit(0)
    report_data = build_report_object(url_stats)
    final_report_data = filter_report(report_data, config["REPORT_SIZE"])
    path_to_template = os.path.join(config["REPORT_DIR"], "report.html")
    dump_final_report(path_to_template, path_to_report, final_report_data)


if __name__ == "__main__":
    try:
        main(DEFAULT_CONFIG)
    except Exception as e:
        logging.exception(e)
