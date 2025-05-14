"""Unit tests for maven_utils.py."""

import logging
import os
import unittest

from parameterized import parameterized

from self_debug.common import maven_utils, utils


_PWD = os.path.dirname(os.path.abspath(__file__))


class TestMavenUtils(unittest.TestCase):
    """Unit tests for maven_utils.py."""

    @parameterized.expand(
        (
            (
                "cd {root_dir}",
                {},
                ("cd {root_dir}", False),
            ),
            # Replaced
            (
                "cd {root_dir}; mvn compile",
                {},
                ("cd {root_dir}; mvn dependency:resolve", True),
            ),
            (
                "cd {root_dir}; mvn compile; mvn clean compile",
                {},
                ("cd {root_dir}; mvn compile; mvn dependency:resolve", True),
            ),
            # - Extra space
            (
                "cd {root_dir}; mvn     compile",
                {},
                ("cd {root_dir}; mvn dependency:resolve", True),
            ),
            # Not replaced
            (
                "cd {root_dir}; mvn compile",
                {
                    "new_partial_command": "mvn compile",
                },
                ("cd {root_dir}; mvn compile", False),
            ),
            # - Extra space
            (
                "cd {root_dir}; mvn     compile",
                {
                    "new_partial_command": "mvn compile",
                },
                ("cd {root_dir}; mvn compile", True),
            ),
        )
    )
    def test_replace_maven_command(self, command, kwargs, expected_command):
        """Unit tests replace_maven_command."""
        self.assertEqual(
            maven_utils.replace_maven_command(command, **kwargs), expected_command
        )

    @parameterized.expand(
        # pylint: disable=line-too-long
        (
            (
                "testdata/maven_dep.txt",
                None,
            ),
            (
                "testdata/maven_dep_00.txt",
                (
                    {
                        "org.springframework.boot:spring-boot-starter:jar:2.5.4:compile -- module spring.boot.starter [auto]",
                        "org.springframework.boot:spring-boot:jar:2.5.4:compile -- module spring.boot [auto]",
                        "org.springframework:spring-context:jar:5.3.9:compile -- module spring.context [auto]",
                        "org.springframework:spring-aop:jar:5.3.9:compile -- module spring.aop [auto]",
                        "org.springframework:spring-beans:jar:5.3.9:compile -- module spring.beans [auto]",
                        "org.springframework:spring-expression:jar:5.3.9:compile -- module spring.expression [auto]",
                        "org.springframework.boot:spring-boot-autoconfigure:jar:2.5.4:compile -- module spring.boot.autoconfigure [auto]",
                        "org.springframework.boot:spring-boot-starter-logging:jar:2.5.4:compile -- module spring.boot.starter.logging [auto]",
                        "ch.qos.logback:logback-classic:jar:1.2.5:compile -- module logback.classic (auto)",
                        "ch.qos.logback:logback-core:jar:1.2.5:compile -- module logback.core (auto)",
                    },
                    {
                        "org.springframework.boot:spring-boot-starter:jar:2.5.4:compile",
                        "org.springframework.boot:spring-boot:jar:2.5.4:compile",
                        "org.springframework:spring-context:jar:5.3.9:compile",
                        "org.springframework:spring-aop:jar:5.3.9:compile",
                        "org.springframework:spring-beans:jar:5.3.9:compile",
                        "org.springframework:spring-expression:jar:5.3.9:compile",
                        "org.springframework.boot:spring-boot-autoconfigure:jar:2.5.4:compile",
                        "org.springframework.boot:spring-boot-starter-logging:jar:2.5.4:compile",
                        "ch.qos.logback:logback-classic:jar:1.2.5:compile",
                        "ch.qos.logback:logback-core:jar:1.2.5:compile",
                    },
                ),
            ),
            (
                "testdata/maven_dep_01.txt",
                (
                    {
                        "com.github.javaparser:javaparser-core:jar:3.25.10:compile -- module com.github.javaparser.core [auto]",
                        "junit:junit:jar:4.8.2:test -- module junit (auto)",
                    },
                    {
                        "com.github.javaparser:javaparser-core:jar:3.25.10:compile",
                        "junit:junit:jar:4.8.2:test",
                    },
                ),
            ),
            (
                "testdata/maven_dep_02.txt",
                (
                    {
                        "none",
                    },
                    {
                        "none",
                    },
                ),
            ),
        )
        # pylint: enable=line-too-long
    )
    def test_parse_maven_dependency(self, filename, expected_deps):
        """Unit tests parse_maven_dependency."""
        self.assertEqual(
            maven_utils.parse_maven_dependency(os.path.join(_PWD, filename)),
            expected_deps,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    unittest.main()
