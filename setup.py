"""Install library."""

import os
from setuptools import setup, find_packages

# Read README.md if it exists, otherwise use short description
long_description = "MigrationBench: Repository-Level Code Migration Benchmark"
readme_path = os.path.join(os.path.dirname(__file__), "README.md")
if os.path.exists(readme_path):
    with open(readme_path, "r") as fh:
        long_description = fh.read()

setup(
    name="MigrationBench",
    version="0.1.0",
    description="MigrationBench",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "migration_bench": ["reference/*"],
    },
    python_requires=">=3.9",
    install_requires=[
        "datasets>=3.0.0",
        "gitpython>=3.1.0",
        "javalang>=0.13.0",
        "parameterized>=0.8.0",
        "protobuf>=3.20.0",
        "pylint>=2.14.0",
        "pytz>=2024.1",
        "packaging>=21.0",
        "requests>=2.28.0",
    ],
)
