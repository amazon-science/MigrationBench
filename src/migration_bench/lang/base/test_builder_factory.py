"""Unit test for builder_factory.py."""

import logging
import unittest

from parameterized import parameterized
from self_debug.proto import builder_pb2

from self_debug.common import utils
from self_debug.lang.base import builder_factory

from self_debug.lang.java.maven import builder as maven_builder


MAVEN_BUILDER_ARGS = (
    "$JDK_PATH",
    "/java/project_dir",
)
MAVEN_BUILDER_KWARGS = {"require_maven_installed": False}


MAVEN_TEXT_PROTO = """
  maven_builder {
    root_dir: "/tmp/java/projects/xmpp-light"
    require_maven_installed: false
  }
"""


class TestBuilder(unittest.TestCase):
    """Unit test for Builder."""

    @parameterized.expand(
        (
            # From args, kwargs.
            (
                ("MavenBuilder",) + MAVEN_BUILDER_ARGS,
                MAVEN_BUILDER_KWARGS,
                maven_builder.MavenBuilder,
                "/java/project_dir",
                "cd /java/project_dir; mvn clean verify",
            ),
            (
                ("maven_builder",) + MAVEN_BUILDER_ARGS,
                MAVEN_BUILDER_KWARGS,
                maven_builder.MavenBuilder,
                "/java/project_dir",
                "cd /java/project_dir; mvn clean verify",
            ),
            # From config.
            (
                (utils.parse_proto(MAVEN_TEXT_PROTO, builder_pb2.Builder),),
                {},
                maven_builder.MavenBuilder,
                "/tmp/java/projects/xmpp-light",
                "cd /tmp/java/projects/xmpp-light; mvn clean verify",
            ),
        )
    )
    def test_create_builder(
        self, args, kwargs, expected_class, expected_root_dir, expected_command
    ):
        """Unit test for create_builder."""
        builder = builder_factory.create_builder(*args, **kwargs)

        self.assertIsInstance(builder, builder_factory.BaseBuilder)
        self.assertIsInstance(builder, expected_class)

        self.assertEqual(builder.root_dir, expected_root_dir)
        self.assertEqual(builder.command, expected_command)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format=utils.LOGGING_FORMAT)
    unittest.main()
