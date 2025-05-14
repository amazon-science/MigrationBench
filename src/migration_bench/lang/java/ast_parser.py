"""Java AST parser."""

import logging
import os
import tempfile
from typing import Any, Tuple
import xml.etree.ElementTree as ET

from self_debug.common import utils
from self_debug.lang.base import ast_parser


AstData = ast_parser.AstData
ClassData = ast_parser.ClassData
LineData = ast_parser.LineData
MethodData = ast_parser.MethodData
PackageData = ast_parser.PackageData
VariableData = ast_parser.VariableData


PACKAGE_NAME = "Include"
PACKAGE_VERSION = "Version"

ROOT_DIR = "root_dir"

JAVA_AST_BINARY = "lang/java/native/target/qct-ast-parser-1.0-jar-with-dependencies.jar"


class JavaAstParser(ast_parser.BaseAstParser):
    """Java AstParser."""

    def __init__(self, root_dir: str, **kwargs):
        project = kwargs.pop("project", "{root_dir}/pom.xml")
        super().__init__(root_dir, project, **kwargs)

        self.mvn = kwargs.get("mvn_path", "mvn")
        logging.debug("[ctor] %s: mvn = `%s`.", self.__class__.__name__, self.mvn)

    @classmethod
    def create_from_config(cls, config: Any, *args, **kwargs):
        """Create from config."""
        del args

        root_dir = kwargs.pop("root_dir", config.root_dir)
        mvn_path = kwargs.get("mvn_path", config.mvn_path)
        return JavaAstParser(root_dir, mvn_path=mvn_path)

    def dedup_package_data(self, *args, **kwargs) -> Tuple[Tuple[str, Any]]:
        """Dedup package data.

        Unique set of:
        - names
        - name and artifact ids
        - name, artifact id and versions
        """
        del args, kwargs

        return super().dedup_package_data()[:1] + (
            (
                "name-artifact",
                lambda pkg: f"{pkg.name}~{pkg.artifact_id}",
            ),
            (
                "name-artifact-version",
                lambda pkg: f"{pkg.name}~{pkg.artifact_id}==<{pkg.version}>",
            ),
        )

    def parse_packages_from_project_ast(
        self, ast: AstData, **kwargs
    ) -> Tuple[PackageData]:
        """Extract packages."""
        del kwargs

        namespaces = (
            {"": "http://maven.apache.org/POM/4.0.0"},
            None,
        )

        for namespace in namespaces:
            packages = []
            for dependencies in ast.findall("dependencies", namespace):
                for dep in dependencies.findall("dependency", namespace):
                    fields = {
                        "artifact_id": dep.find("artifactId", namespace),
                        "name": dep.find("groupId", namespace),
                        "version": dep.find("version", namespace),
                    }
                    if not all(value is None for value in fields.values()):
                        fields = {
                            field: (None if value is None else value.text)
                            for field, value in fields.items()
                        }
                        packages.append(ast_parser.PackageData(**fields))

            if packages:
                return tuple(packages)

        return ()

    def do_parse_ast(self, filename: str, *args, **kwargs) -> AstData:
        """Parse AST for a file."""
        # Work dir is `.../src`.
        work_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../..")
        work_dir = os.path.abspath(work_dir)

        with tempfile.TemporaryDirectory() as temp_dir:
            export_path = os.path.join(temp_dir, f"{os.path.basename(filename)}.xml")
            binary_path = os.path.join(work_dir, JAVA_AST_BINARY)
            command = "; ".join(
                [
                    # f"cd {os.path.join(work_dir, 'lang/java/native')}",
                    # f"{self.mvn} clean install",
                    f"java -jar {binary_path} -input_files {filename} -export_path {export_path} "
                    f"-add_line true -add_var true",
                ]
            )
            _, success = utils.run_command(command, check=False)

            if success:
                try:
                    return ET.parse(export_path).getroot()
                except Exception as error:
                    logging.exception(
                        "Unable to parse (%s) AST: <<<%s>>>", filename, error
                    )

        return None
