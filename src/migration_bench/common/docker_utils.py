"""Docker utilities for running evaluations in containers."""

import logging
import os
import subprocess
from typing import Optional

# Docker image name
DOCKER_IMAGE = "migration-bench:latest"

# Container working directory
CONTAINER_WORKSPACE = "/workspace/eval"


def is_docker_available() -> bool:
    """Check if Docker is available on the system."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def build_docker_image(dockerfile_path: str = None, context_path: str = None) -> bool:
    """Build the Docker image for MigrationBench.

    Args:
        dockerfile_path: Path to Dockerfile (default: use repo root)
        context_path: Build context path (default: use repo root)

    Returns:
        True if build succeeded, False otherwise
    """
    if dockerfile_path is None:
        # Try to find Dockerfile in repo root
        import migration_bench
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(migration_bench.__file__)))
        dockerfile_path = os.path.join(repo_root, "Dockerfile")
        context_path = repo_root

    if not os.path.exists(dockerfile_path):
        logging.error("Dockerfile not found at: %s", dockerfile_path)
        return False

    logging.info("Building Docker image: %s", DOCKER_IMAGE)
    logging.info("Context path: %s", context_path)

    try:
        result = subprocess.run(
            ["docker", "build", "-t", DOCKER_IMAGE, "-f", dockerfile_path, context_path],
            check=False,
            text=True,
        )

        if result.returncode == 0:
            logging.info("Successfully built Docker image: %s", DOCKER_IMAGE)
            return True
        else:
            logging.error("Failed to build Docker image")
            return False
    except Exception as error:
        logging.error("Error building Docker image: %s", error)
        return False


def check_image_exists() -> bool:
    """Check if the MigrationBench Docker image exists."""
    try:
        result = subprocess.run(
            ["docker", "images", "-q", DOCKER_IMAGE],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, Exception) as error:
        logging.warning("Error checking Docker image: %s", error)
        return False


def run_eval_in_docker(
    github_url: str,
    git_diff_file: Optional[str] = None,
    migrated_root_dir: Optional[str] = None,
    commit_id: Optional[str] = None,
    **kwargs
) -> bool:
    """Run evaluation inside a Docker container.

    Args:
        github_url: GitHub repository URL
        git_diff_file: Path to git diff file (on host)
        migrated_root_dir: Path to migrated repo directory (on host)
        commit_id: Git commit ID to evaluate
        **kwargs: Additional arguments passed to run_eval

    Returns:
        True if evaluation succeeded, False otherwise
    """
    if not is_docker_available():
        logging.error("Docker is not available. Please install Docker.")
        return False

    # Prepare volume mounts and command arguments
    volumes = []
    docker_git_diff_file = None
    docker_migrated_root_dir = None

    # Mount git diff file if provided
    if git_diff_file and os.path.exists(git_diff_file):
        host_diff_file = os.path.abspath(git_diff_file)
        docker_git_diff_file = "/data/diff.patch"
        volumes.append(f"{host_diff_file}:{docker_git_diff_file}:ro")

    # Mount migrated directory if provided
    if migrated_root_dir and os.path.exists(migrated_root_dir):
        host_migrated_dir = os.path.abspath(migrated_root_dir)
        docker_migrated_root_dir = "/data/migrated_repo"
        volumes.append(f"{host_migrated_dir}:{docker_migrated_root_dir}:ro")

    # Build command
    cmd = [
        "docker", "run",
        "--rm",  # Remove container after execution
        "-e", f"GITHUB_URL={github_url}",
    ]

    # Add volume mounts
    for volume in volumes:
        cmd.extend(["-v", volume])

    # Add image name
    cmd.append(DOCKER_IMAGE)

    # Add Python script and arguments
    cmd.extend(["python3", "-m", "migration_bench.run_eval"])
    cmd.extend(["--github_url", github_url])

    if docker_git_diff_file:
        cmd.extend(["--git_diff_filename", docker_git_diff_file])

    if docker_migrated_root_dir:
        cmd.extend(["--migrated_root_dir", docker_migrated_root_dir])

    if commit_id:
        cmd.extend(["--base_commit_id", commit_id])

    # Add optional arguments
    if "maven_command" in kwargs and kwargs["maven_command"]:
        cmd.extend(["--maven_command", kwargs["maven_command"]])

    if "require_maximal_migration" in kwargs:
        cmd.extend(["--is_maximal_migration", str(int(kwargs["require_maximal_migration"]))])

    if "require_compiled_java_major_version" in kwargs:
        cmd.extend(["--require_compiled_java_major_version", str(kwargs["require_compiled_java_major_version"])])

    if "eval_build_success" in kwargs:
        cmd.extend(["--eval_build_success", str(int(kwargs["eval_build_success"]))])

    if "eval_num_tests" in kwargs:
        cmd.extend(["--eval_num_tests", str(int(kwargs["eval_num_tests"]))])

    if "eval_list_tests" in kwargs:
        cmd.extend(["--eval_list_tests", str(int(kwargs["eval_list_tests"]))])

    logging.info("Running evaluation in Docker container...")
    logging.debug("Docker command: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, flush=True)

        # Parse result from output (check both stdout and stderr)
        # Look for success indicator in logs
        success = False
        combined_output = (result.stdout or "") + "\n" + (result.stderr or "")
        for line in combined_output.splitlines():
            if "[single] Migration success (count) `True`" in line:
                success = True
                break
            elif "[single] Migration success (count) `False`" in line:
                success = False
                break

        return success

    except Exception as error:
        logging.error("Error running Docker container: %s", error)
        return False


def _run_single_prediction_in_docker(args):
    """Helper function to run a single prediction in Docker (for multiprocessing).

    Args:
        args: Tuple of (prediction_dict, kwargs)

    Returns:
        Boolean indicating success
    """
    pred, kwargs = args
    github_url = pred.get("github_url")
    git_diff_file = pred.get("git_diff_file")
    migrated_root_dir = pred.get("migrated_root_dir")
    git_diff_content = pred.get("git_diff")
    commit_id = pred.get("base_commit_id")

    # Handle git_diff content (write to temp file if provided)
    temp_diff_file = None
    if git_diff_content and not git_diff_file:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.diff', delete=False) as f:
            f.write(git_diff_content)
            temp_diff_file = f.name
            git_diff_file = temp_diff_file

    try:
        result = run_eval_in_docker(
            github_url=github_url,
            git_diff_file=git_diff_file,
            migrated_root_dir=migrated_root_dir,
            commit_id=commit_id,
            **kwargs
        )
        return result
    finally:
        # Clean up temp diff file
        if temp_diff_file and os.path.exists(temp_diff_file):
            os.remove(temp_diff_file)


def run_batch_eval_in_docker(
    predictions_file: str,
    **kwargs
) -> int:
    """Run batch evaluation by spawning multiple Docker containers in parallel.

    Each container evaluates ONE repository with ONE mounted directory.
    This is much more efficient than mounting all repos into a single container.

    Args:
        predictions_file: Path to predictions JSON file (on host)
        **kwargs: Additional arguments passed to run_eval
                 - max_workers: Number of parallel Docker containers (default: 1)

    Returns:
        Number of successful evaluations
    """
    if not is_docker_available():
        logging.error("Docker is not available. Please install Docker.")
        return 0

    if not check_image_exists():
        logging.warning("Docker image not found. Building image...")
        if not build_docker_image():
            logging.error("Failed to build Docker image")
            return 0

    if not os.path.exists(predictions_file):
        logging.error("Predictions file not found: %s", predictions_file)
        return 0

    # Load predictions
    import json
    with open(predictions_file, 'r') as f:
        predictions = json.load(f)

    if not predictions:
        logging.info("[batch-docker] No predictions to process.")
        return 0

    # Extract max_workers from kwargs (default to 1)
    max_workers = kwargs.pop("max_workers", 1)

    logging.info(
        "[batch-docker] Processing %d predictions with %d parallel Docker containers.",
        len(predictions), max_workers
    )

    # Prepare arguments for each prediction
    pred_args = [(pred, kwargs) for pred in predictions]

    # Run predictions in parallel using multiprocessing
    count = 0
    if max_workers == 1:
        # Sequential execution
        for args in pred_args:
            if _run_single_prediction_in_docker(args):
                count += 1
    else:
        # Parallel execution with multiprocessing
        import multiprocessing as mp
        pool = mp.Pool(max_workers)
        try:
            results = pool.map(_run_single_prediction_in_docker, pred_args)
            count = sum(results)
        except KeyboardInterrupt:
            logging.info("Interrupted by user, shutting down...")
            pool.terminate()
            pool.join()
        finally:
            pool.close()
            pool.join()

    logging.info(
        "[batch-docker] Final eval result: Success = %d out of %d.",
        count, len(predictions)
    )
    return count
