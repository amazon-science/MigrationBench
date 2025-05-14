"""Unit tests for builder.py."""

import logging
import os
import unittest

from parameterized import parameterized
from self_debug.proto import builder_pb2

from self_debug.common import utils
from self_debug.lang.base import builder as base_builder
from self_debug.lang.base import builder_factory
from self_debug.lang.java.maven import builder


_POM = "/Users/sliuxl/xmpp-light/pom.xml"

TEXT_PROTO_00 = """
  maven_builder {
    root_dir: "/{root_dir}/java/projects/xmpp-light"
    # build_command: "cd {root_dir}; mvn clean verify"
    require_maven_installed: false
  }
"""

TEXT_PROTO_01 = """
  maven_builder {
    root_dir: "/{root_dir}/java/projects/xmpp-light"
    jdk_path: "/usr/lib/jvm/java-17-amazon-corretto.x86_64"
    build_command: "cd {root_dir}; JAVA_HOME={JAVA_HOME} /tmp/mvn clean verify"
    build_command_sanity_check: "JAVA_HOME={JAVA_HOME} mvn --version"
    require_maven_installed: false
  }
"""

TEXT_PROTO_02 = """
  maven_builder {
    root_dir: "/{root_dir}/java/projects/xmpp-light/"
    jdk_path: "/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.432.b06-1.amzn2.0.1.x86_64/jre"
    build_command: "cd {root_dir}; JAVA_HOME={JAVA_HOME} /tmp/mvn clean verify"
    build_command_sanity_check: "JAVA_HOME={JAVA_HOME} mvn --version"
    require_maven_installed: false
  }
"""


class TestMavenBuilder(unittest.TestCase):
    """Unit tests for builder.py."""

    @parameterized.expand(
        (
            (
                TEXT_PROTO_00,
                {},
                "//java/projects/xmpp-light",
                "//java/projects/xmpp-light/pom.xml",
                "cd //java/projects/xmpp-light; mvn clean verify",
            ),
            (
                TEXT_PROTO_01,
                {
                    "root_dir": "<root_dir>",
                },
                "/<root_dir>/java/projects/xmpp-light",
                "/<root_dir>/java/projects/xmpp-light/pom.xml",
                "cd /<root_dir>/java/projects/xmpp-light; JAVA_HOME=/usr/lib/jvm/java-17-amazon-corretto.x86_64 /tmp/mvn clean verify",  # pylint: disable=line-too-long
            ),
            (
                TEXT_PROTO_02,
                {
                    "root_dir": "<root_dir>/",
                },
                "/<root_dir>//java/projects/xmpp-light/",
                "/<root_dir>//java/projects/xmpp-light/pom.xml",
                "cd /<root_dir>//java/projects/xmpp-light/; JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.432.b06-1.amzn2.0.1.x86_64/jre /tmp/mvn clean verify",  # pylint: disable=line-too-long
            ),
        )
    )
    def test_create_from_config(
        self, text_proto, kwargs, expected_root_dir, expected_project, expected_command
    ):
        """Unit tests for create_from_config."""
        config = utils.parse_proto(text_proto, builder_pb2.Builder)
        mvn_builder = builder_factory.create_builder(config, **kwargs)

        self.assertIsInstance(mvn_builder, builder_factory.BaseBuilder)
        self.assertIsInstance(mvn_builder, builder.MavenBuilder)

        self.assertEqual(mvn_builder.root_dir, expected_root_dir)
        self.assertEqual(mvn_builder.project, expected_project)
        self.assertEqual(mvn_builder.command, expected_command)

    @parameterized.expand(
        (
            (
                "testdata/build_00.txt",
                (
                    base_builder.BuildData(
                        filename=_POM,
                        line_number=None,
                        error_message="Source option 5 is no longer supported. Use 7 or later.",
                    ),
                    base_builder.BuildData(
                        filename=_POM,
                        line_number=None,
                        error_message="Target option 5 is no longer supported. Use 7 or later.",
                    ),
                ),
            ),
            (
                "testdata/build_01.txt",
                (
                    base_builder.BuildData(
                        filename=_POM,
                        line_number=None,
                        error_message=r"""
[ERROR] [ERROR] Some problems were encountered while processing the POMs:
[FATAL] Non-parseable POM /tmp/ported/sd-plus-processing--alliance-base/alliance-pojo/pom.xml: Duplicated tag: 'dependencies' (position: START_TAG seen ...<build>\
    </build>\
<dependencies>... @42:15)  @ line 42, column 15
 @
[ERROR] The build could not read 1 project -> [Help 1]
[ERROR]
[ERROR]   The project  (/tmp/ported/sd-plus-processing--alliance-base/alliance-pojo/pom.xml) has 1 error
[ERROR]     Non-parseable POM /tmp/ported/sd-plus-processing--alliance-base/alliance-pojo/pom.xml: Duplicated tag: 'dependencies' (position: START_TAG seen ...<build>\
    </build>\
<dependencies>... @42:15)  @ line 42, column 15 -> [Help 2]
[ERROR]
[ERROR] To see the full stack trace of the errors, re-run Maven with the -e switch.
[ERROR] Re-run Maven using the -X switch to enable full debug logging.
[ERROR]
[ERROR] For more information about the errors and possible solutions, please read the following articles:
[ERROR] [Help 1] http://cwiki.apache.org/confluence/display/MAVEN/ProjectBuildingException
[ERROR] [Help 2] http://cwiki.apache.org/confluence/display/MAVEN/ModelParseException
                        """.strip(),
                    ),
                ),
            ),
            (
                "testdata/build_02.txt",
                (
                    base_builder.BuildData(
                        filename=_POM,
                        line_number=None,
                        error_message=r"""
[ERROR] [ERROR] Some problems were encountered while processing the POMs:
[ERROR] Non-resolvable import POM: The following artifacts could not be resolved: io.rest-assured:rest-assured-bom:pom:3.1.0 (absent): Could not find artifact io.rest-assured:rest-assured-bom:pom:3.1.0 in spring-snapshots (https://repo.spring.io/snapshot) @ org.springframework.boot:spring-boot-dependencies:3.2.9, /home/hadoop/.m2/repository/org/springframework/boot/spring-boot-dependencies/3.2.9/spring-boot-dependencies-3.2.9.pom, line 2838, column 19
 @
[ERROR] The build could not read 1 project -> [Help 1]
[ERROR]
[ERROR]   The project it.hyseneim:cloud-application:0.0.1-SNAPSHOT (/tmp/ported/sd-plus-processing--cloud-application-starter/pom.xml) has 1 error
[ERROR]     Non-resolvable import POM: The following artifacts could not be resolved: io.rest-assured:rest-assured-bom:pom:3.1.0 (absent): Could not find artifact io.rest-assured:rest-assured-bom:pom:3.1.0 in spring-snapshots (https://repo.spring.io/snapshot) @ org.springframework.boot:spring-boot-dependencies:3.2.9, /home/hadoop/.m2/repository/org/springframework/boot/spring-boot-dependencies/3.2.9/spring-boot-dependencies-3.2.9.pom, line 2838, column 19 -> [Help 2]
[ERROR]
[ERROR] To see the full stack trace of the errors, re-run Maven with the -e switch.
[ERROR] Re-run Maven using the -X switch to enable full debug logging.
[ERROR]
[ERROR] For more information about the errors and possible solutions, please read the following articles:
[ERROR] [Help 1] http://cwiki.apache.org/confluence/display/MAVEN/ProjectBuildingException
[ERROR] [Help 2] http://cwiki.apache.org/confluence/display/MAVEN/UnresolvableModelException
                        """.strip(),
                    ),
                ),
            ),
            (
                "testdata/build_03.txt",
                (
                    base_builder.BuildData(
                        filename=_POM,
                        line_number=None,
                        error_message=r"""
[ERROR] Several versions of tycho plugins are configured [1.7.0, 2.7.5]:
[ERROR] 1.7.0:
[ERROR] \tMavenProject: com.mihnita:ansiconsole:1.4.8-SNAPSHOT @ /tmp/ported/sd-plus-processing--ansi-econsole/pom.xml
[ERROR] \tMavenProject: com.mihnita:net.mihai-nita.ansicon.plugin:1.4.8-SNAPSHOT @ /tmp/ported/sd-plus-processing--ansi-econsole/AnsiConsole/pom.xml
[ERROR] \tMavenProject: com.mihnita:net.mihai-nita.ansicon:1.4.8-SNAPSHOT @ /tmp/ported/sd-plus-processing--ansi-econsole/AnsiConFeature/pom.xml
[ERROR] \tMavenProject: com.mihnita:net.mihai-nita.ansicon.updatesite:1.4.8-SNAPSHOT @ /tmp/ported/sd-plus-processing--ansi-econsole/AnsiConSite/pom.xml
[ERROR] 2.7.5:
[ERROR] \tMavenProject: com.mihnita:net.mihai-nita.ansicon.plugin:1.4.8-SNAPSHOT @ /tmp/ported/sd-plus-processing--ansi-econsole/AnsiConsole/pom.xml
[ERROR] \tMavenProject: com.mihnita:net.mihai-nita.ansicon:1.4.8-SNAPSHOT @ /tmp/ported/sd-plus-processing--ansi-econsole/AnsiConFeature/pom.xml
[ERROR] \tMavenProject: com.mihnita:net.mihai-nita.ansicon.updatesite:1.4.8-SNAPSHOT @ /tmp/ported/sd-plus-processing--ansi-econsole/AnsiConSite/pom.xml
[ERROR] All tycho plugins configured in one reactor must use the same version -> [Help 1]
[ERROR]
[ERROR] To see the full stack trace of the errors, re-run Maven with the -e switch.
[ERROR] Re-run Maven using the -X switch to enable full debug logging.
[ERROR]
[ERROR] For more information about the errors and possible solutions, please read the following articles:
[ERROR] [Help 1] http://cwiki.apache.org/confluence/display/MAVEN/MavenExecutionException
                        """.strip(),
                    ),
                ),
            ),
            (
                "testdata/xmpp-light-00.txt",
                (
                    base_builder.BuildData(
                        filename=_POM,
                        line_number=None,
                        error_message="...",
                    ),
                ),
            ),
            (
                "testdata/xmpp-light-01.txt",
                # pylint: disable=line-too-long
                (
                    base_builder.BuildData(
                        filename="/Users/sliuxl/xmpp-light/src/main/java/ua/tumakha/yuriy/xmpp/light/service/impl/UserServiceImpl.java",
                        line_number=55,
                        column_number=31,
                        error_message="incompatible types: java.lang.Long cannot be converted to ua.tumakha.yuriy.xmpp.light.domain.User",
                        variables=(
                            ("userRepository", ("userId",)),
                            ("        userRepository.delete(", "u", "serId);"),
                        ),
                    ),
                    base_builder.BuildData(
                        filename="/Users/sliuxl/xmpp-light/src/main/java/ua/tumakha/yuriy/xmpp/light/service/impl/UserServiceImpl.java",
                        line_number=60,
                        column_number=35,
                        error_message=(
                            "method findOne in interface org.springframework.data.repository.query.QueryByExampleExecutor<T> cannot be applied to given types;\n"
                            "  required: org.springframework.data.domain.Example<S>\n"
                            "  found:    java.lang.Long\n"
                            "  reason: cannot infer type-variable(s) S\n"
                            "    (argument mismatch; java.lang.Long cannot be converted to org.springframework.data.domain.Example<S>)"
                        ),
                        variables=(
                            ("userRepository",),
                            (
                                "        User user = userRepository",
                                ".",
                                "findOne(userId);",
                            ),
                        ),
                    ),
                    base_builder.BuildData(
                        filename="/Users/sliuxl/xmpp-light/src/main/java/ua/tumakha/yuriy/xmpp/light/web/IndexController.java",
                        line_number=41,
                        column_number=5,
                        error_message="method does not override or implement a method from a supertype",
                        variables=((), ("    ", "@", "Override")),
                    ),
                    base_builder.BuildData(
                        filename="/Users/sliuxl/xmpp-light/src/main/java/ua/tumakha/yuriy/xmpp/light/WebSecurityConfig.java",
                        line_number=30,
                        column_number=25,
                        error_message=(
                            "cannot find symbol\n"
                            "  symbol:   method formLogin((login)->l[...]All())\n"
                            "  location: variable requests of type org.springframework.security.config.annotation.web.configurers.ExpressionUrlAuthorizationConfigurer<org.springframework.security.config.annotation.web.builders.HttpSecurity>.ExpressionInterceptUrlRegistry"
                        ),
                        variables=(
                            (),
                            (
                                "                        ",
                                ".",
                                "formLogin(login -> login",
                            ),
                        ),
                    ),
                ),
                # pylint: enable=line-too-long
            ),
            (
                "testdata/xmpp-light-02-pom.txt",
                (
                    # pylint: disable=line-too-long
                    base_builder.BuildData(
                        filename=_POM,
                        line_number=None,
                        error_message=(
                            "[ERROR] Failed to execute goal on project xmpp-light: Could not resolve dependencies for project ua.tumakha.yuriy.xmpp:xmpp-light:war:0.8-SNAPSHOT: The following artifacts could not be resolved: org.springframework.boot:spring-boot-starter-security:jar:6.0.7 (absent): org.springframework.boot:spring-boot-starter-security:jar:6.0.7 was not found in https://repo.maven.apache.org/maven2 during a previous attempt. This failure was cached in the local repository and resolution is not reattempted until the update interval of central has elapsed or updates are forced -> [Help 1]\n"
                            "[ERROR]\n"
                            "[ERROR] To see the full stack trace of the errors, re-run Maven with the -e switch.\n"
                            "[ERROR] Re-run Maven using the -X switch to enable full debug logging.\n"
                            "[ERROR]\n"
                            "[ERROR] For more information about the errors and possible solutions, please read the following articles:\n"
                            "[ERROR] [Help 1] http://cwiki.apache.org/confluence/display/MAVEN/DependencyResolutionException"
                        ),
                    ),
                    # pylint: enable=line-too-long
                ),
            ),
            (
                "testdata/xmpp-light-03-success.txt",
                (),
            ),
        )
    )
    def test_extract_build_errors(self, filename, expected_errors):
        """Unit tests for extract_build_errors."""
        pwd = os.path.dirname(os.path.abspath(__file__))
        content = utils.load_file(os.path.join(pwd, filename))

        mvn_builder = builder.MavenBuilder(
            "<JDK_PATH>", "/Users/sliuxl/xmpp-light/", require_maven_installed=False
        )
        errors = mvn_builder.extract_build_errors(
            base_builder.CmdData(stdout=content, return_code=0)
        )

        self.assertEqual(len(errors), len(expected_errors))
        for error, expected_error in zip(errors, expected_errors):
            logging.info(error)
            logging.debug(expected_error)

            if filename in (
                "testdata/build_00.txt",
                "testdata/build_01.txt",
                "testdata/build_02.txt",
                "testdata/build_03.txt",
                "testdata/xmpp-light-00.txt",
                "testdata/xmpp-light-02-pom.txt",
            ):
                self.assertEqual(error.filename, _POM)
                self.assertIsNone(error.line_number)
                self.assertIsNone(error.column_number)
            else:
                self.assertTrue(error.filename.endswith(".java"))
                self.assertIsNotNone(error.line_number)
                self.assertIsNotNone(error.column_number)
                if filename == "testdata/xmpp-light-01.txt":
                    logging.debug(
                        "Variables: `%s` vs `%s`.",
                        error.variables,
                        expected_error.variables,
                    )
                    # self.assertEqual(error.variables, expected_error.variables)

            self.assertIsNotNone(error.error_message)
            self.assertIsNone(error.error_code)
            self.assertIsNone(error.code_snippet)

            self.assertIsNone(error.root_dir)
            self.assertIsNone(error.project)

        if filename == "testdata/xmpp-light-00.txt":
            return
        self.assertEqual(errors, expected_errors)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format=utils.LOGGING_FORMAT)
    unittest.main()
