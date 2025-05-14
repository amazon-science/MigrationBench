"""Base abstract syntax tree (AST) parserer and structured AST parser data as output.

A few level of data:

- LineData
- _FileLevelData
    - _ClassLevelData
      - VariableData: Data members, param list, local vars
      - MethodData
    - ClassData


- parse_package_ast
  * parse_packages_from_project_ast
  * parse_packages
- parse_ast
  * parse_classes
"""

import abc
from collections import defaultdict
from dataclasses import dataclass, field as dataclass_field
import logging
import os
from typing import Any, Dict, Optional, Sequence, Tuple, Union

import xml.etree.ElementTree as ET

from self_debug.common import utils
from self_debug.metrics import utils as metric_utils


AstData = Union[None, ET.Element]


CLASS = "Class"
LINE_START = "LineStart"
LINE_END = "LineEnd"
LINE_NUMBER = "line_number"
METHOD = "Method"
METHODS = "Methods"
NAME = "Name"
PARAMETER = "Parameter"
PARAMETERS = "Parameters"
PARENT = "Parent"
PARENTS = "Parents"
PROPERTY = "Property"
PROPERTIES = "Properties"
SIGNATURE = "Signature"
TYPE = "Type"
VARIABLE = "Variable"
VARIABLES = "Variables"


@dataclass
class LineData:
    """Method data."""

    line_start: Optional[int] = None
    line_end: Optional[int] = None

    def __repr__(self):
        if self.line_start == self.line_end or self.line_end is None:
            return str(self.line_start)

        return f"[{self.line_start}, {self.line_end}]"

    def __eq__(self, other) -> bool:
        return isinstance(other, self.__class__) and self.line_start == other.line_start


@dataclass
class _FileLevelData:
    """Data at the file level."""

    name: str
    signature: str

    lines: Optional[LineData] = None

    file_name: Optional[str] = None

    def __repr__(self):
        return f"[{self.file_name}]::`{self.signature}`@{self.lines}"

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, self.__class__)
            and
            # Skip `name`
            self.signature == other.signature
            and self.lines == other.lines
            and self.file_name == other.file_name
        )


@dataclass
class _ClassLevelData(_FileLevelData):
    """Data at the class level."""

    class_name: Optional[str] = None

    def __repr__(self):
        return f"[{self.file_name}]{self.class_name}::`{self.signature}`@{self.lines}"

    def __eq__(self, other) -> bool:
        return super().__eq__(other) and self.class_name == other.class_name


@dataclass
class VariableData(_ClassLevelData):
    """Variable data: `signature` will be used as `type` instead."""


@dataclass
class MethodData(VariableData):
    """Method data: Add param list and local vars."""

    params: Tuple[VariableData] = ()
    local_vars: Tuple[VariableData] = ()

    def __eq__(self, other) -> bool:
        if (
            len(self.params) != len(other.params)
            or len(self.local_vars) != len(other.local_vars)
            or not super().__eq__(other)
        ):
            return False

        for lhs, rhs in zip(self.params, other.params):
            if lhs != rhs:
                return False

        for lhs, rhs in zip(self.local_vars, other.local_vars):
            if lhs != rhs:
                return False

        return True


@dataclass
class ClassData(_FileLevelData):
    """Class data."""

    members: Tuple[VariableData] = ()
    methods: Tuple[MethodData] = ()

    parents: Tuple[_FileLevelData] = ()

    def __eq__(self, other) -> bool:
        if (
            len(self.members) != len(other.members)
            or len(self.methods) != len(other.methods)
            or self.parents != other.parents
            or not super().__eq__(other)
        ):
            return False

        for lhs, rhs in zip(self.members, other.members):
            if lhs != rhs:
                return False

        for lhs, rhs in zip(self.methods, other.methods):
            if lhs != rhs:
                return False

        return True

    def __repr__(self):
        return "\n".join(
            [
                f"// File{'' if self.file_name is None else (' ' + self.file_name)}:",
                f"{self.signature} {{",
                "",
                "// All data members:",
            ]
            + [f"    {m.signature};" for m in self.members]
            + [
                "",
                "// All method members:",
            ]
            + [f"    {m.signature};" for m in self.methods]
            + [
                "}",
                "",
            ]
        )


@dataclass
class ProjectData:
    """Project data."""

    root: str
    fields: Dict[str, Any] = dataclass_field(default_factory=dict)

    # Children.
    tag_counts: defaultdict(int) = dataclass_field(
        default_factory=lambda: defaultdict(int)
    )
    children: defaultdict(tuple[Any]) = dataclass_field(
        default_factory=lambda: defaultdict(tuple)
    )


@dataclass
class PackageData:
    """Package data: Dependencies on those packages, e.g.

    - imports (Java): Versions are in pom.xml
    - using (C#): Versions are in $PROJECT.csproj

    artifact_id is used in `java`, and they have multiple variants, e.g.
    ```
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-cache</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-security</artifactId>
        </dependency>

        <!-- Tests -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    ```
    """

    name: str
    version: Optional[str] = None
    artifact_id: Optional[str] = None

    project_name: Optional[str] = None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(name="{self.name}",version="{self.version},artifact_id="{self.artifact_id}")'  # pylint: disable=line-too-long

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, self.__class__)
            and self.project_name == other.project_name
            and self.name == other.name
            and self.version == other.version
            and self.artifact_id == other.artifact_id
        )


@dataclass
class FileData:
    """File data."""

    class_data: ClassData
    package_data: PackageData = None


class BaseAstParser(abc.ABC):
    """Base AstParser."""

    def __init__(self, root_dir: str, project: Optional[str] = None, **kwargs):
        super().__init__()

        self.root_dir = root_dir
        self.project = project if project is None else project.format(root_dir=root_dir)

        logging.debug(
            "[ctor] %s: (root_dir, project) = (%s, %s).",
            self.__class__.__name__,
            root_dir,
            project,
        )

        self.kwargs = kwargs

        self._ast_cache = {}
        self._metrics = defaultdict(int)

    def reset(self):
        """Reset AST trees."""
        self._ast_cache = {}
        self._metrics = {}

    def dedup_package_data(self, *args, **kwargs) -> Tuple[Tuple[str, Any]]:
        """Dedup package data.

        Unique set of:
        - names
        - name and versions
        """
        del args, kwargs
        return (
            (
                "name",
                lambda pkg: pkg.name,
            ),
            (
                "name-version",
                lambda pkg: f"{pkg.name}==<{pkg.version}>",
            ),
        )

    def run_metrics(self):
        """Get metrics."""
        self._metrics["00-start"] += 1

        if os.path.exists(self.project):
            self._metrics["01-filter--project-exists"] += 1
        else:
            self._metrics["01-filter--project-does-not-exist"] += 1
            self._metrics["02-finish--early"] += 1
            # return self.metrics

        ast = self.parse_project_ast()

        # 1. Project fields.
        project = self.parse_fields_from_project_ast(ast)
        if project is None:
            self._metrics["02-project--03--project-data=<None>"] += 1
        else:
            self._metrics[f"02-project--00--root=<{project.root}>"] += 1
            for name, value in project.fields.items():
                self._metrics[f"02-project--01--00--name=<{name}>"] += 1
                self._metrics[f"02-project--01--01--value-type={type(value)}"] += 1
                if isinstance(value, (str, int, float, list, tuple)):
                    self._metrics[f"02-project--01--02--{name}=<{value}>"] += 1

            self._metrics[
                f"02-project--02--00--tag-uniq-count=<{len(project.tag_counts):04d}>"
            ] += 1
            for tag, count in project.tag_counts.items():
                self._metrics[f"02-project--02--01--tag=<{tag}>"] += 1
                self._metrics[f"02-project--02--02--tag-count=<{tag},{count:02d}>"] += 1

            self._metrics[
                f"02-project--03--00--children-count=<{len(project.children):04d}>"
            ] += 1
            for p_tag, child_elems in project.children.items():
                self._metrics[
                    f"02-project--03--01--child-elem-count=<{len(child_elems):04d}>"
                ] += 1
                for child_elem in child_elems:
                    ch_tag, ch_text = child_elem
                    tag = f"{p_tag}--{ch_tag}"
                    self._metrics[f"02-project--03--02--child-tag=<{tag}>"] += 1
                    self._metrics[
                        f"02-project--03--03--child-tag-value=<{tag},{ch_text}>"
                    ] += 1

        # 2. Packages.
        packages = self.parse_packages(ast)
        self._metrics[f"03-packages-00--len={len(packages):03d}"] += 1

        def _dedup(prefix: str, map_fn: Any) -> int:
            pkgs = set((map_fn(pkg) for pkg in packages))
            for name in pkgs:
                self._metrics[f"{prefix}<{name}>"] += 1
            return len(pkgs)

        named_pkg_fns = self.dedup_package_data()
        index = 0
        for name, pkg_fn in named_pkg_fns:
            prefix = f"03-packages-01--{index:02d}-package--{name}"
            count = _dedup(f"{prefix}=", pkg_fn)
            self._metrics[f"{prefix}--uniq-count=<{count:04d}>"] += 1
            index += 1

        self._metrics["04-finish"] += 1
        return self.metrics

    @property
    def metrics(self):
        """Get metrics."""
        return metric_utils.reformat_metrics(self, self._metrics)

    def parse_fields_from_project_ast(
        self, ast: AstData, **kwargs
    ) -> Optional[ProjectData]:
        """Parse fields from AST."""
        del kwargs

        if ast is None:
            return None

        tag_counts = defaultdict(int)
        children = defaultdict(tuple)
        for child in ast:
            tag = child.tag
            tag_counts[tag] += 1

            # Work on `PropertyGroup` only.
            # if not child.tag.endswith("PropertyGroup"):
            #     continue

            child_elems = []
            for elem in child:
                if child.tag == "ItemGroup" and elem.tag in (
                    "DotNetCliToolReference",
                    "PackageReference",
                    "ProjectReference",
                ):
                    child_elems.append(
                        (
                            f"{elem.tag}::{elem.attrib.get('Include')}",
                            elem.attrib.get("Version", ""),
                        )
                    )
                elif hasattr(elem, "text") and elem.text and elem.text.strip():
                    child_elems.append((elem.tag, elem.text))
            children[tag] += tuple(sorted(child_elems))

        return ProjectData(
            root=ast.tag, fields=ast.attrib, tag_counts=tag_counts, children=children
        )

    @abc.abstractmethod
    def parse_packages_from_project_ast(self, ast: AstData, **kwargs) -> Tuple[str]:
        """Parse packages from AST."""

    def parse_packages(self, ast: AstData = None, **kwargs) -> Tuple[AstData]:
        """Parse packages."""
        if ast is None and kwargs.get("force_run", True):
            ast = self.parse_project_ast()

        return () if ast is None else self.parse_packages_from_project_ast(ast)

    def _parse_file_level(
        self, ast: AstData = None, typ: Any = VariableData, **kwargs
    ) -> Dict[str, Any]:
        line_end = ast.find(LINE_END)
        kwargs = {
            "line_start": ast.find(LINE_START).text,
            "line_end": None if line_end is None else line_end.text,
        }
        lines = LineData(**{k: (v if v is None else int(v)) for k, v in kwargs.items()})

        kwargs = {"lines": lines}
        fields = (NAME, SIGNATURE)
        for field in fields:
            kwargs.update({field.lower(): ast.find(field).text})

        return typ(**kwargs)

    def _parse_vars(
        self, cls: AstData, names: Tuple[str, str], **kwargs
    ) -> Tuple[VariableData]:
        """Parse vars: names is a tuple of the nested fields."""
        del kwargs

        var = []
        for props in cls.findall(names[0]):
            for prop in props.findall(names[1]):
                var.append(self._parse_file_level(prop))

        return tuple(var)

    def _parse_methods(self, cls: AstData = None, **kwargs) -> Tuple[MethodData]:
        result = []
        for methods in cls.findall(METHODS):
            for method in methods.findall(METHOD):
                obj = self._parse_file_level(method, typ=MethodData)

                if kwargs.get(PARAMETERS.lower(), True):
                    obj.params = self._parse_vars(
                        method, (PARAMETERS, PARAMETER), **kwargs
                    )

                if kwargs.get(VARIABLES.lower(), True):
                    obj.local_vars = self._parse_vars(
                        method, (VARIABLES, VARIABLE), **kwargs
                    )

                result.append(obj)
        return result

    def _parse_parents(self, cls: AstData = None, **kwargs) -> Tuple[VariableData]:
        del kwargs

        result = []
        for parents in cls.findall(PARENTS):
            for parent in parents.findall(PARENT):
                result.append(self._parse_file_level(parent, typ=_FileLevelData))

        return tuple(result)

    def parse_classes(
        self, filename: str, ast: AstData = None, **kwargs
    ) -> Tuple[ClassData]:
        """Parse classes."""
        ast = self.parse_ast(filename, ast, **kwargs)

        classes = []
        for cls in ast.findall(CLASS):
            cls_data = self._parse_file_level(cls, ClassData)
            if kwargs.get(PROPERTIES.lower(), True):
                cls_data.members = self._parse_vars(
                    cls, (PROPERTIES, PROPERTY), **kwargs
                )

            if kwargs.get(METHODS.lower(), True):
                cls_data.methods = self._parse_methods(cls, **kwargs)

            if kwargs.get(PARENTS.lower(), True):
                cls_data.parents = self._parse_parents(cls, **kwargs)

            classes.append(cls_data)

        return tuple(classes)

    def _valid_line(
        self, line_start: int, line_end: Optional[int], line_number: Optional[int]
    ) -> bool:
        if line_number is None:
            return True

        if line_end is None:
            line_end = line_start

        return line_start <= line_number <= line_end

    def _member_is_used(self, code_snippet: str, member: VariableData) -> bool:
        """Find out whether a data member is used in a function."""
        return member.name in code_snippet

    def _used_members(
        self,
        filename: str,
        cls: ClassData,
        method: MethodData,
        line_number: Optional[int],
    ) -> Tuple[VariableData]:
        """Find out data members used in a function."""
        if line_number is None:
            return cls.members

        start = method.lines.line_start
        end = method.lines.line_end
        if end is None:
            end = start
        code_snippet = utils.get_snippet(filename, start, before=0, after=end - start)[
            0
        ]

        members = []
        for member in cls.members:
            if self._member_is_used(code_snippet, member):
                members.append(member)

        return members

    def parse_variables(
        self, filename: str, classes: Tuple[ClassData] = None, **kwargs
    ) -> Tuple[Tuple[VariableData]]:
        """Parse variables with 3 sources: 0) Class member 1) Function arguments 2) Local."""

        if classes is None:
            classes = self.parse_classes(filename, **kwargs)

        variables = [[], [], []]
        line_number = kwargs.get(LINE_NUMBER)
        count = 0
        for cls in classes:
            if not self._valid_line(
                cls.lines.line_start, cls.lines.line_end, line_number
            ):
                continue

            for method in cls.methods:
                if not self._valid_line(
                    method.lines.line_start, method.lines.line_end, line_number
                ):
                    continue

                count += 1
                if count != 1:
                    raise ValueError(
                        f"Please double check classes and methods in your def: {count} != 1."
                    )

                # Source 1 & 2
                variables[1] += list(method.params)
                for var in method.local_vars:
                    # Defined before the problematic line number.
                    if self._valid_line(var.lines.line_start, line_number, line_number):
                        variables[2].append(var)

                # Source 0
                variables[0] += self._used_members(filename, cls, method, line_number)

        return tuple((tuple(v) for v in variables))

    @classmethod
    def create_from_config(cls, config: Any, *args, **kwargs):
        """Create from config."""

    def parse_project_ast(self, *args, **kwargs) -> AstData:
        """Project: Parse project."""
        del args, kwargs
        if self.project is None:
            return None

        try:
            return ET.parse(self.project).getroot()
        except Exception as error:
            logging.exception(
                "Unable to parse project (%s) AST: <<<%s>>>", self.project, error
            )
            return None

    @abc.abstractmethod
    def do_parse_ast(self, filename: str, *args, **kwargs) -> AstData:
        """Parse AST for a file."""

    def parse_ast(self, filename: str, ast: AstData = None, **kwargs) -> AstData:
        """Parse AST for a file."""
        if ast is not None:
            return ast

        if filename not in self._ast_cache:
            self._ast_cache[filename] = self.do_parse_ast(filename, **kwargs)

        return self._ast_cache[filename]

    def parse(
        self, filenames: Optional[Sequence[str]] = None, **kwargs
    ) -> Tuple[AstData, Dict[str, AstData]]:
        """Parse ASTs for the project and file(s)."""
        project_ast = self.parse_project_ast()

        ast = {}
        for filename in filenames:
            ast[filename] = self.parse_ast(filename, **kwargs)

        return project_ast, ast
