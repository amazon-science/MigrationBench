"""Filter repo license.

INPUT=java__v05.6_20250321.pbtxt
OUTPUT=java__v05.8_20250429.pbtxt

INPUT=java__v05.7-full_20250324.pbtxt
OUTPUT=java__v05.8-full_20250429.pbtxt

INPUT=java__v05.7-utg_20250324.pbtxt
OUTPUT=java__v05.8-utg_20250429.pbtxt

python filter_license.py  $INPUT $OUTPUT
"""

import logging
import os
import sys

from self_debug.common import utils
from self_debug.proto import config_pb2

_PWD = os.path.dirname(__file__)

LICENSE = "../../../reference/license/license__java__v05.6_20250321.json"


def main(filename: str, export_filename: str):
    """Main."""
    # Input
    copy_config = utils.load_proto(filename, config_pb2.Config)

    license_data = utils.load_json(LICENSE)
    valid_repos = sorted(license_data.keys())

    # Output
    config = utils.load_proto(filename, config_pb2.Config)
    del config.dataset.dataset_repos[:]

    keep_repos = []
    for dataset in copy_config.dataset.dataset_repos:
        if (
            dataset.HasField("github_repo")
            and dataset.github_repo.github_url in valid_repos
        ):
            keep_repos.append(dataset)
            config.dataset.dataset_repos.add().CopyFrom(dataset)

    logging.info(
        "Export to len = %d <= %d: `%s`.",
        len(keep_repos),
        len(copy_config.dataset.dataset_repos),
        export_filename,
    )

    config.dataset.dataset_partition.partition_repos = len(keep_repos)
    utils.export_proto(config, export_filename)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    main(*sys.argv[1:])
