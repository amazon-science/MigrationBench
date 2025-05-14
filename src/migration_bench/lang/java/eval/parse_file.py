"""Parse java AST."""

import logging

import javalang

from migration_bench.common import utils


CLASS = "class"
INTERFACE = "interface"
METHOD = "method"

METHOD_ANNOTATION_TEST = "Test"


def get_classes_and_methods(filename: str, content: str = None, add_line: bool = False):
    """Get classes and methods."""
    if content is None:
        content = utils.load_file(filename)

    try:
        tree = javalang.parse.parse(content)
    except Exception as error:
        logging.exception("Unable to parse `%s`: `%s`.", filename, error)
        return None

    nodes = []
    current_class = None
    for _, node in tree:
        if isinstance(node, javalang.tree.ClassDeclaration):
            current_class = node.name
            nodes.append((CLASS, current_class))
        elif isinstance(node, javalang.tree.InterfaceDeclaration):
            current_class = node.name
            nodes.append((INTERFACE, current_class))
        elif isinstance(node, javalang.tree.MethodDeclaration):
            if not current_class:
                raise ValueError(
                    f"Unable to find out class for method `{node.name}`: `{node}`."
                )

            # Method name
            is_test = False
            for annotation in node.annotations:
                if annotation.name == METHOD_ANNOTATION_TEST:
                    is_test = True
                    break

            method_info = [node.name, is_test]

            if add_line:
                method_info.append(node.position.line if node.position else None)

            nodes.append((METHOD, tuple(method_info)))

    return tuple(nodes)


def same_classes_and_methods(
    lhs,
    rhs,
    ignore_line_no: bool = False,
    has_test_annotation: bool = False,
):
    """Diff classes and methods: To compare files before and after commit."""
    if (lhs is None) or (rhs is None):
        return lhs is None and rhs is None

    def _filter_test(item):
        return item[0] != METHOD or item[1][1]

    def _remove_line_no(item):
        if item[0] == METHOD and (item[1][-1] is None or isinstance(item[1][-1], int)):
            return (item[0], item[1][:-1])

        return item

    if has_test_annotation:
        lhs = [l for l in lhs if _filter_test(l)]
        rhs = [l for l in rhs if _filter_test(l)]

    if ignore_line_no:
        lhs = [_remove_line_no(l) for l in lhs]
        rhs = [_remove_line_no(l) for l in rhs]

    logging.debug(lhs)
    logging.debug(rhs)

    return tuple(lhs) == tuple(rhs)
