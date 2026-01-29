"""Install library."""

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
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
        "numpy>=1.26.0",
        "parameterized>=0.8.0",
        "protobuf>=3.20.0",
        "pydantic>=2.0.0",
        "pylint>=2.14.0",
        "pytz>=2024.1",
        "packaging>=21.0",
        "requests>=2.28.0",
    ],
)
