"""Run final eval for MigrationBench.

Sample command:


0. Batch job

```
PREDICTIONS=$file.json
python run_eval.py --predictions_filename $PREDICTIONS
```


1. Single job

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
    # - Batch job: Prioritized over single job as long as predictions_filename is not `None`
    parser.add_argument(
        "--predictions_filename",
        type=str,
        default=None,
        help="A .json file containing `github_url` and `git_diff`/`migrated_root_dir`.",
    )

    # - Single job
    parser.add_argument(
        "--github_url", type=str, default=None, help="Which repo to evaluate."
    )
    parser.add_argument(
        "--git_diff_filename",
        type=str,
        default=None,
        help="Filename containing git diff to evaluate.",
    )
    parser.add_argument(
        "--migrated_root_dir",
        type=str,
        default=None,
        help="Path to the migrated repo root directory.",
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
    parser.add_argument(
        "--max_workers",
        type=int,
        default=1,
        help="Maximum number of worker processes for parallel batch evaluation. Use 1 for sequential processing.",
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

    if args.predictions_filename:
        if args.max_workers > 1:
            eval_func = final_eval.run_batch_eval_parallel
            kwargs["max_workers"] = args.max_workers
            eval_mode = "batch-parallel"
        else:
            eval_func = final_eval.run_batch_eval
            eval_mode = "batch"
        eval_args = (args.predictions_filename,)
    else:
        eval_func = final_eval.run_eval
        eval_args = (args.github_url, args.git_diff_filename, args.migrated_root_dir)
        eval_mode = "single"

    count = eval_func(*eval_args, **kwargs)
    logging.info(
        "[%s] Migration success (count) `%s`: `%s`.", eval_mode, count, eval_args
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    main()
