"""Run self debugging with LLM.

Inputs:
- config_file: A text proto file to construct objects.
- max_iterations: How many iterations to run, to override config.max_iterations if provided.
- dry_run: Whether a dry run only, skipping checking out a new branch and LLM calls.

Sample command:

```
python run_self_debugging.py \
    --config_file configs/java_config.pbtxt \
    --max_iterations 3 \
    # --dry_run 1
```

"""

import argparse
import datetime
import logging

from self_debug.proto import config_pb2

from self_debug.common import utils
from self_debug import self_debugging


_FORMAT_ITERATION = "02d"
_FORMAT_TIMESTAMP = "%Y%m%d-%H%M%S"


def _parse_args():
    """Parse args."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_file", type=str, default=None, help="Config file.")

    parser.add_argument(
        "--max_iterations", type=int, default=None, help="Max iterations."
    )
    parser.add_argument(
        "--repeat", type=int, default=None, help="How many times to repeat job."
    )
    parser.add_argument("--dry_run", type=int, default=0, help="Dry run.")
    return parser.parse_known_args()


def run(config: config_pb2.Config, max_iterations: int, tag: str, dry_run: bool):
    """Main function to run LLM."""
    # Find out the package dir from the Brazil workspace dir.
    if "happytrails_builder" in dir(config.builder) and config.builder.HasField(
        "happytrails_builder"
    ):
        kwargs = {}
    else:
        kwargs = {}
    self_debugging_runner = self_debugging.SelfDebugging.create_from_config(
        config, **kwargs
    )

    if max_iterations is None:
        max_iterations = config.max_iterations

    repo = self_debugging_runner.repo
    # 1. Create a new branch as needed.
    branch = None
    if (config.repo.source_branch or config.repo.branch) and not dry_run:
        if config.repo.git_clean:
            repo.clean()
        if config.repo.git_restore:
            repo.restore()

        kwargs = {
            "source_branch": config.repo.source_branch,
            "timestamp": datetime.datetime.now().strftime(_FORMAT_TIMESTAMP),
            "max_iterations": f"{max_iterations}{tag}",
        }
        branch = config.repo.branch.format(**kwargs)
        repo.new_branch(branch, config.repo.source_branch, checkout=True)

    logging.info("git log: %s.", repo.log(2))
    logging.info("git branch: %s.", repo.branch())
    logging.info("git status: %s.", repo.status())

    # 2. Run iterations.
    try:
        if config.builder.HasField("maven_builder"):
            self_debugging_runner.update_jdk_related()
            self_debugging_runner.repo.commit_all("set JDK version to 17 in pom.xml")
        proto, build_errors = self_debugging_runner.run(max_iterations, dry_run=dry_run)
        proto = proto.final_state_metrics
        iteration, success = proto.iterations, proto.state.success
    except Exception as error:
        logging.exception("Job failed with error: <<<%s>>>", error)
        iteration, success, build_errors = "unknown", False, None
    logging.info(
        "Job status: success = %s @%s, errors = %d.",
        success,
        iteration,
        -1 if build_errors is None else len(build_errors),
    )

    # 3. Final branch rename.
    if branch:
        if success:
            new_branch = f"{branch}--success-at{iteration:{_FORMAT_ITERATION}}"
        else:
            if isinstance(iteration, int):
                new_branch = f"{branch}--fail-at{iteration:{_FORMAT_ITERATION}}"
            else:
                new_branch = f"{branch}--fail-{iteration}"
        success = repo.rename_branch(new_branch, branch)
        logging.info("git rename = %s: %s <== %s.", success, new_branch, branch)

    logging.info("Done for %d iterations.", max_iterations)


def main():
    """Main."""
    args, _ = _parse_args()
    config = utils.load_proto(args.config_file, config_pb2.Config)
    logging.info("Config: <<<%s>>>", config)

    repeat = args.repeat
    if repeat is None:
        repeat = config.repeat
    for rep in range(repeat):
        logging.info("Repeat job %02d/ %02d ...", rep, repeat)

        tag = f"-run{rep:{_FORMAT_ITERATION}}" if repeat > 1 else ""
        run(config, args.max_iterations, tag, bool(args.dry_run))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    main()
