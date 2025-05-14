"""Unit tests hf_utils.py"""

import logging
import unittest

from parameterized import parameterized

from self_debug.common import utils
from self_debug.datasets import hf_utils
from self_debug.proto import dataset_pb2


KWARGS_00 = {
    "first_n": 3,
}
KWARGS_01 = {
    "first_n": 3,
    "columns": hf_utils.COLUMNS,
}

TEMPLATE_DATASET_TEXTPROTO = """
hf_option: HF_OPTION
dataset_partition {
partition_repos: 3
}
apply_seed_changes: true
"""


class TestHfUtils(unittest.TestCase):
    """Unit tests for hf_utils.py."""

    @parameterized.expand(
        (
            (
                hf_utils.JAVA_FULL,
                {},
                (8, 3),
            ),
            (
                hf_utils.JAVA_FULL,
                KWARGS_00,
                {
                    "base_commit": [
                        "af57b4f8621afd5bf1bd428cd65349eca85e0b8a",
                        "5ae99dc9af5169a5719a031cc1047ac2d3b0e3c2",
                        "3b5939a7c653aae971535ae15fc5bb16f8e43a4d",
                    ],
                    "license": ["Apache-2.0", "MIT", "MIT"],
                    "num_java_files": [79, 47, 7],
                    "num_loc": [26320, 5006, 599],
                    "num_pom_xml": [1, 1, 1],
                    "num_src_test_java_files": [16, 2, 2],
                    "num_test_cases": [-2, 1, 10],
                    "repo": [
                        "0000005/sync2any",
                        "0rtis/mochimo-farm-manager",
                        "0x100/n-loops",
                    ],
                },
            ),
            (
                hf_utils.JAVA_FULL,
                KWARGS_01,
                {
                    "base_commit": [
                        "af57b4f8621afd5bf1bd428cd65349eca85e0b8a",
                        "5ae99dc9af5169a5719a031cc1047ac2d3b0e3c2",
                        "3b5939a7c653aae971535ae15fc5bb16f8e43a4d",
                    ],
                    "repo": [
                        "0000005/sync2any",
                        "0rtis/mochimo-farm-manager",
                        "0x100/n-loops",
                    ],
                },
            ),
            (
                hf_utils.JAVA_SELECTED,
                {},
                (8, 3),
            ),
            (
                hf_utils.JAVA_SELECTED,
                KWARGS_01,
                {
                    "base_commit": [
                        "7e51c59e090484ae4573290099b6936855554064",
                        "4973285e49b48be7b10818fae530159c55af267a",
                        "8c361437de5fe56f45ff6cf6785a033a8e267d2a",
                    ],
                    "repo": [
                        "15093015999/EJServer",
                        "284885166/spring-boot-hashids",
                        "adlered/Picuang",
                    ],
                },
            ),
            (
                hf_utils.JAVA_UTG,
                KWARGS_00,
                {
                    "base_commit": [
                        "c0e059fff4e47719469f436f0db2013d1938283f",
                        "c4cfb889abcca7fe684501be048561cc8b88950c",
                        "54c0546b5df5cfc9ca5dad3752bc2218c207c2fe",
                    ],
                    "license": ["MIT", "MIT", "MIT"],
                    "repo": [
                        "0fca/poolval2",
                        "0rangeFox/AuthLib",
                        "0x100/liquibase-backup-spring-boot-starter",
                    ],
                },
            ),
        )
    )
    def test_load_hf_dataset(self, name, kwargs, expected_dataset):
        """Unit test for load_hf_dataset."""
        hf_ds = hf_utils.load_hf_dataset(name, **kwargs)
        if isinstance(expected_dataset, tuple):
            expected_len, expected_elem_len = expected_dataset
            self.assertEqual(len(hf_ds), expected_len)
            for value in hf_ds.values():
                self.assertEqual(len(value), expected_elem_len)
        else:
            self.assertEqual(hf_ds, expected_dataset)

    @parameterized.expand(
        (
            (
                TEMPLATE_DATASET_TEXTPROTO.replace(
                    "HF_OPTION", "MIGRATION_BENCH_JAVA_FULL"
                ),
                KWARGS_00,
                """
                    hf_option: MIGRATION_BENCH_JAVA_FULL
                    dataset_repos {
                      github_repo {
                        github_url: "https://github.com/0000005/sync2any"
                        commit_id: "af57b4f8621afd5bf1bd428cd65349eca85e0b8a"
                      }
                    }
                    dataset_repos {
                      github_repo {
                        github_url: "https://github.com/0rtis/mochimo-farm-manager"
                        commit_id: "5ae99dc9af5169a5719a031cc1047ac2d3b0e3c2"
                      }
                    }
                    dataset_repos {
                      github_repo {
                        github_url: "https://github.com/0x100/n-loops"
                        commit_id: "3b5939a7c653aae971535ae15fc5bb16f8e43a4d"
                      }
                    }
                    dataset_partition {
                      partition_repos: 3
                    }
                    apply_seed_changes: true
                """,
            ),
            (
                TEMPLATE_DATASET_TEXTPROTO.replace(
                    "HF_OPTION", "MIGRATION_BENCH_JAVA_SELECTED"
                ).replace("true", "false"),
                KWARGS_01,
                """
                    hf_option: MIGRATION_BENCH_JAVA_SELECTED
                    dataset_repos {
                      github_repo {
                        github_url: "https://github.com/15093015999/EJServer"
                        commit_id: "7e51c59e090484ae4573290099b6936855554064"
                      }
                    }
                    dataset_repos {
                      github_repo {
                        github_url: "https://github.com/284885166/spring-boot-hashids"
                        commit_id: "4973285e49b48be7b10818fae530159c55af267a"
                      }
                    }
                    dataset_repos {
                      github_repo {
                        github_url: "https://github.com/adlered/Picuang"
                        commit_id: "8c361437de5fe56f45ff6cf6785a033a8e267d2a"
                      }
                    }
                    dataset_partition {
                      partition_repos: 3
                    }
                    apply_seed_changes: false
                """,
            ),
            (
                TEMPLATE_DATASET_TEXTPROTO.replace(
                    "HF_OPTION", "MIGRATION_BENCH_JAVA_UTG"
                ).replace("apply_seed_changes: true", "# apply_seed_changes: true"),
                KWARGS_00,
                """
                    hf_option: MIGRATION_BENCH_JAVA_UTG
                    dataset_repos {
                      github_repo {
                        github_url: "https://github.com/0fca/poolval2"
                        commit_id: "c0e059fff4e47719469f436f0db2013d1938283f"
                      }
                    }
                    dataset_repos {
                      github_repo {
                        github_url: "https://github.com/0rangeFox/AuthLib"
                        commit_id: "c4cfb889abcca7fe684501be048561cc8b88950c"
                      }
                    }
                    dataset_repos {
                      github_repo {
                        github_url: "https://github.com/0x100/liquibase-backup-spring-boot-starter"
                        commit_id: "54c0546b5df5cfc9ca5dad3752bc2218c207c2fe"
                      }
                    }
                    dataset_partition {
                      partition_repos: 3
                    }
                    ### apply_seed_changes: true
                """,
            ),
        )
    )
    def test_resolve_hf_dataset(self, config, kwargs, expected_config):
        """Unit test for resolve_hf_dataset."""
        config = utils.parse_proto(config, dataset_pb2.Dataset)
        expected_config = utils.parse_proto(expected_config, dataset_pb2.Dataset)

        # Idempotent
        for _ in range(2):
            config = hf_utils.resolve_hf_dataset(config, **kwargs)
            self.assertEqual(config, expected_config)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
