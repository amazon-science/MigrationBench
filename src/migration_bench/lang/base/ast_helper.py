"""Abstract syntax tree (AST) parserer helper."""

import itertools
import logging
import os
from typing import Dict, Optional, Tuple

from self_debug.common import utils
from self_debug.lang.base import ast_parser, builder

ClassData = ast_parser.ClassData
VariableData = ast_parser.VariableData


class AstHelper:
    """Ast helper."""

    def __init__(
        self, parser: ast_parser.BaseAstParser, root_dirs: Tuple[str], **kwargs
    ):
        root_dirs = [os.path.realpath(d) for d in root_dirs]
        self.root_dirs = tuple(
            d[:-1] if d.endswith(os.path.sep) else d for d in root_dirs
        )

        self.parser = parser

        logging.debug(
            "[ctor] %s: root_dirs = `%s`.", self.__class__.__name__, root_dirs
        )

        self.kwargs = kwargs

    @property
    def enabled(self):
        """Whether it's enabled."""
        config = self.kwargs.get("config")
        enable = True
        if config:
            enable = config.enable_ast

        return enable and self._parsable()

    @property
    def enabled_for_package_upgrade(self):
        """Whether it's enabled for package upgrade."""
        config = self.kwargs.get("config")
        enable = True
        if config:
            enable = config.enable_package_upgrade

        return enable and self._parsable()

    def _parsable(self):
        """Whether it can parse AST info for anything."""
        return self.parser is not None

    def _ast_parsable(self, build_error: builder.BuildData):
        """Whether it can parse AST info for the build error."""
        return (
            self._parsable()
            and build_error.filename
            and build_error.line_number is not None
        )

    def maybe_retrieve_class(
        self, cls: VariableData, use_name: bool, search_dirs: Tuple[str] = None
    ) -> Tuple[Optional[str], str, Optional[str]]:
        """Retrieve class based on its name."""
        search_dirs = search_dirs or self.root_dirs
        if isinstance(search_dirs, str):
            search_dirs = (search_dirs,)

        def _get_class_name():
            if use_name:
                name = cls.name
            else:
                name = cls.signature

            log = logging.debug
            name = name.strip()
            if not use_name:
                # Normalize: `String a`.
                # - String a = "bla bla";
                if "=" in name:
                    name = name.split("=")[-2]
                # - String a("bla bla");
                if "(" in name:
                    name = name.split("(")[0]

                name = name.strip().split()
                if len(name) >= 2:
                    name = name[-2:][0]
                else:
                    log = logging.warning

            # Normalize: `Template a`.
            # - Template<int> a;
            if "<" in name:
                # TODO(sliuxl): Do we need to retrieve both types in this case.
                name = name.split("<")[0]

            log("Retrieve name `%s` <= `%s`.", name, cls.signature)
            return name

        name = _get_class_name()

        used_dir = None
        for work_dir in search_dirs:
            command = f"find {work_dir} -name {name}.java"
            output, _ = utils.run_command(command, check=False)
            if output:
                used_dir = work_dir
                break
            logging.warning("Unable to find `%s.java` in `%s`.", name, work_dir)

        return output, name, used_dir

    def maybe_retrieve_classes(
        self,
        classes: Tuple[VariableData],
        name: str,
        build_error: builder.BuildData,
        use_name: bool,
        search_dirs: Tuple[str] = None,
    ) -> Optional[str]:
        """Retrieve class based on its name."""
        logging.debug("Retrieve classes (%s) for `%s`:", name, build_error)

        # Candidate files.
        filenames = []
        for _, clz in enumerate(classes):
            # TODO(sliuxl): NOT search for built in libs yet.
            output, ext_name, _ = self.maybe_retrieve_class(clz, use_name, search_dirs)

            if output.strip():
                ext_filenames = output.strip().splitlines()
                if len(ext_filenames) != 1:
                    logging.warning(
                        "Multiple classes with the same name (len = %d): <<<%s>>>",
                        len(ext_filenames),
                        ext_filenames,
                    )
                filenames += ext_filenames
            else:
                logging.warning(
                    "Unable to find `%s.java` <= `%s`.", ext_name, clz.signature
                )
        ext_filenames = sorted(list(set(o for o in filenames if o)))

        # Get APIs from files.
        apis = []
        for ext_filename in ext_filenames:
            ext_classes = self.parser.parse_classes(ext_filename)
            ext_text = "\n".join(str(cls) for cls in ext_classes)

            short_filename = ext_filename
            for w_dir in self.root_dirs:
                w_dir += os.path.sep
                if short_filename.startswith(w_dir):
                    short_filename = short_filename.replace(w_dir, "./")
                    break
            apis.append(f"File: `{short_filename}`\n```{ext_text}```")

        apis = "\n".join(apis)
        if apis:
            logging.debug(
                "Retrieve classes (%s) for `%s`: <<<\n%s>>>", name, build_error, apis
            )
        return apis

    def get_base_classes(self, build_error: builder.BuildData) -> Tuple[ClassData, str]:
        """Get base classes based on build error."""
        if not self._ast_parsable(build_error):
            return ""

        classes = self.parser.parse_classes(build_error.filename)
        cls = None
        for clz in classes:
            if clz.lines.line_start <= build_error.line_number <= clz.lines.line_end:
                cls = clz
                break
        classes = (cls,)

        parents = self.maybe_retrieve_classes(
            cls.parents, "parent", build_error, use_name=True
        )

        return classes, parents

    def get_variables(self, classes: Tuple[ClassData], build_error: builder.BuildData):
        """Get variables based on build error."""
        if not self._ast_parsable(build_error):
            return ""

        # Vars: (prop, input params, locals)
        variables = self.parser.parse_variables(
            build_error.filename, classes, line_number=build_error.line_number
        )
        names = set()
        uniq_vars = []
        for var in itertools.chain.from_iterable(variables):
            if var.name not in names:
                uniq_vars.append(var)
                names.add(var.name)

        return self.maybe_retrieve_classes(
            uniq_vars, "variables", build_error, use_name=False
        )

    def run(self, build_error: builder.BuildData) -> Dict[str, str]:
        """Get prompt info for build error."""
        if self._parsable():
            self.parser.reset()

        if not self.enabled or not self._ast_parsable(build_error):
            return {}

        classes, output = self.get_base_classes(build_error)
        return {
            "AST__base_classes": output,
            "AST__variables": self.get_variables(classes, build_error),
        }
