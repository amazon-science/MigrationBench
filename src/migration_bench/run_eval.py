"""Run final eval for MigrationBench.

Sample command:

```
GITHUB_URL=https://github.com/0xShamil/java-xid
GIT_DIFF_FILE=
python run_eval.py --github_url $GITHUB_URL --git_diff_filename $GIT_DIFF_FILE
```
"""

import argparse
import logging

from migration_bench.common import utils
from migration_bench.eval import final_eval


def _parse_args():
    """Parse args."""
    parser = argparse.ArgumentParser()

    # Required arguments
    parser.add_argument(
        "--github_url", type=str, default=None, help="Which repo to evaluate."
    )
    parser.add_argument(
        "--git_diff_filename",
        type=str,
        default=None,
        help="Filename containing git diff to evaluate.",
    )

    # Optional arguments
    parser.add_argument(
        "--base_commit_id",
        type=str,
        default=None,
        help="Which base commit id to use, optional for repositories in the MigrationBench's full dataset.",
    )

    parser.add_argument(
        "--maven_command", type=str, default=None, help="Which maven command to run."
    )
    parser.add_argument(
        "--is_maximal_migration",
        type=int,
        default=1,
        help="Whether to run eval as maximal migration, if not it reduces to minimal migration.",
    )
    parser.add_argument(
        "--require_compiled_java_major_version",
        type=int,
        default=61,
        help="The required compiled java classes' major version, 52 and 61 for Java 8 and 17 respectively.",
    )

    parser.add_argument(
        "--eval_build_success",
        type=int,
        default=1,
        help="Whether to run eval on build success i.e. the maven command.",
    )
    parser.add_argument(
        "--eval_num_tests",
        type=int,
        default=1,
        help="Whether to run eval on non-decreasing number of test cases.",
    )
    parser.add_argument(
        "--eval_list_tests",
        type=int,
        default=1,
        help="Whether to run eval on invariant java test methods.",
    )

    return parser.parse_known_args()


def _maybe_update(config, key, value):
    """Maybe update config."""
    if value is None:
        return
    config.update(
        {
            key: value,
        }
    )


def main():
    """Main."""
    args, _ = _parse_args()

    kwargs = {
        "require_maximal_migration": args.is_maximal_migration,
    }
    keys = (
        "eval_build_success",
        "require_compiled_java_major_version",
        "eval_num_tests",
        "eval_list_tests",
    )
    for key in keys:
        kwargs.update(
            {
                key: getattr(args, key),
            }
        )
    _maybe_update(kwargs, "commit_id", args.base_commit_id)
    _maybe_update(kwargs, "maven_command", args.maven_command)

    success = final_eval.run_eval(args.github_url, args.git_diff_filename, **kwargs)
    logging.info(
        "Migration status %s: (%s, %s)",
        success,
        args.github_url,
        args.git_diff_filename,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    main()
