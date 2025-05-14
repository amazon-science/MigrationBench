"""Abstract syntax tree (AST) parser factory."""

import logging
from typing import Any

from self_debug.common import utils
from self_debug.lang.base import ast_parser

from self_debug.lang.java import ast_parser as java_ast_parser


BaseAstParser = ast_parser.BaseAstParser

AstData = ast_parser.AstData
ClassData = ast_parser.ClassData
PackageData = ast_parser.PackageData


def create_ast_parser(option: Any, *args, **kwargs) -> BaseAstParser:
    """Create ast_parser based on name: Option can be a string (infer class name) or a config."""
    logging.info("[factory] Create ast_parser: `%s`.", option)

    classes = (java_ast_parser.JavaAstParser,)

    if not isinstance(option, str):
        args = ("ast_parser",) + args

    return utils.create_instance(option, classes, *args, **kwargs)
