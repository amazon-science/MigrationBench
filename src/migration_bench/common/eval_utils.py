"""Eval utils for maximal migration."""

import glob
import logging
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from packaging.version import Version

from migration_bench.common import utils

DEPENDENCY_VERSION = Path(__file__).parent.parent / "reference/dependency_version.json"


# pylint: disable=invalid-name


def preprocess_xml(file_path):
    """Preprocess xml."""
    content = utils.load_file(file_path) or ""

    # Remove leading whitespace and blank lines
    content = re.sub(r"^\s+", "", content, flags=re.MULTILINE)
    return content


def extract_dependencies(pom_file):
    """Extract deps."""
    # Preprocess the XML content
    xml_content = preprocess_xml(pom_file)

    # Parse the preprocessed content
    root = ET.fromstring(xml_content)

    # Define the namespace
    ns = {"maven": "http://maven.apache.org/POM/4.0.0"}

    dependencies = set()
    for dep in root.findall(".//maven:dependency", ns):
        group_id = dep.find("maven:groupId", ns).text
        artifact_id = dep.find("maven:artifactId", ns).text
        dependencies.add(f"{group_id}:{artifact_id}")

    return dependencies


def generate_dependency_tree(working_dir):
    """Generate dependency tree."""
    try:
        with open(os.path.join(working_dir, "dependency-tree.txt"), "w") as outfile:
            res = subprocess.run(
                ["mvn", "dependency:tree"],
                stdout=outfile,
                stderr=subprocess.STDOUT,
                cwd=working_dir,
            )
            if res.returncode != 0:
                logging.warning("Error generating dependency-tree")
                return None
        return os.path.join(working_dir, "dependency-tree.txt")
    except subprocess.CalledProcessError as error:
        logging.warning("Error generating dependency-tree: `%s`.", error)
        return None


def get_effective_versions(dt_path, interested_deps):
    """Get effective version."""
    dep_versions = {}

    dt = (utils.load_file(dt_path) or "").splitlines()
    for line in dt:
        if line.startswith(r"[INFO] +- ") or line.startswith(r"[INFO] \- "):
            dep_plus_version = line.split(" ")[-1].strip()
            artifact_list = dep_plus_version.split(":")
            if len(artifact_list) != 5:
                logging.warning("Invalid dependency version: `%s`.", dep_plus_version)
            else:
                group_id = artifact_list[0]
                artifact_id = artifact_list[1]
                version = artifact_list[3]
                if group_id + ":" + artifact_id in interested_deps:
                    dep_versions[group_id + ":" + artifact_id] = version
    return dep_versions


def compare_versions(v1, v2):
    """Compare versions."""

    def normalize(v):
        parts = re.findall(r"\d+", v)
        return [int(x) for x in parts[:3]] + [0] * (3 - len(parts))

    norm1 = normalize(v1)
    norm2 = normalize(v2)

    return norm1 >= norm2


def compare_major_versions(v1, v2):
    """Compare major versions."""
    try:
        v1 = Version(v1)
        v2 = Version(v2)
        return v1.major >= v2.major
    except:

        def normalize(v):
            parts = re.findall(r"\d+", v)
            return [int(x) for x in parts[:3]] + [0] * (3 - len(parts))

        norm1 = normalize(v1)
        norm2 = normalize(v2)
        return norm1[0] >= norm2[0]


def check_version(working_dir, dependency_version_path=None, check_major_version=True):
    """Check version."""
    if dependency_version_path is None:
        dependency_version_path = DEPENDENCY_VERSION

    pom_paths = glob.glob(os.path.join(working_dir, "**", "pom.xml"), recursive=True)
    interested_deps = set()
    for pom_path in pom_paths:
        try:
            interested_deps.update(extract_dependencies(pom_path))
        except ET.ParseError as error:
            logging.warning("Error parsing pom.xml: `%s`.", error)
            logging.warning("Please ensure the file is well-formed XML and try again.")
            return False

    dependency_tree = generate_dependency_tree(working_dir)

    if not dependency_tree:
        logging.warning("Failed to generate effective POM. Exiting.")
        return False

    dep_versions = get_effective_versions(dependency_tree, interested_deps)

    expected_versions = utils.load_json(dependency_version_path) or {}

    results = []
    eval_status = True

    for dep, transformed_version in dep_versions.items():
        original_version = expected_versions.get(dep, "N/A")
        if original_version != "N/A":
            if check_major_version:
                valid_update = compare_major_versions(
                    transformed_version, original_version
                )
            else:
                valid_update = compare_versions(transformed_version, original_version)
        else:
            valid_update = None

        if valid_update is False:
            eval_status = False
            results.append(
                {
                    "dependency": dep,
                    "expected-version": original_version,
                    "transformed-version": transformed_version,
                    "valid-version-update": valid_update,
                }
            )
    subprocess.run(["rm", dependency_tree], check=True)
    logging.warning(
        "Check version completed # = %d: `%s`.", len(dep_versions), working_dir
    )
    if results:
        logging.warning(
            "The following dependencies didn't achieve the required versions."
        )
        logging.warning(results)

    return eval_status


if __name__ == "__main__":
    # repo_dir = "/local/home/linbol/s3-bucket/linbol-debugger-java-v01-10-20250124-135538--nodes040x01--r-p7oxgd/java__lite_20250121--pbtxt/init-yellow--success-false/laf-vertx-000-pom.xml-20250124-155513-oef3hs8g/laf-vertx"
    repo_dir = "/local/home/linbol/s3-bucket/linbol-debugger-java-v01-10-20250124-135538--nodes040x01--r-p7oxgd/java__lite_20250121--pbtxt/init-yellow--success-true/xmpp-light-000-pom.xml-20250124-155741-2f38tuyr/xmpp-light"
    print(check_version(repo_dir, DEPENDENCY_VERSION))
