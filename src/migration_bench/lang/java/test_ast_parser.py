"""Unit tests for ast_parser.py."""

from collections import defaultdict
import logging
import os
import unittest

from parameterized import parameterized
from self_debug.proto import ast_parser_pb2

from self_debug.common import utils
from self_debug.lang.base import ast_parser_factory
from self_debug.lang.java import ast_parser


ClassData = ast_parser.ClassData
LineData = ast_parser.LineData
MethodData = ast_parser.MethodData
PackageData = ast_parser.PackageData
VariableData = ast_parser.VariableData

TEXT_PROTO = """
  java_ast_parser {
    root_dir: "/xyz/root"
  }
"""

CLASS_STR_USER = """// File:
@Entity(name = "user") public class User {

// All data members:
    @Id
@GeneratedValue
private Long id;;
    @Size(min = 2, max = 20)
@Column(unique = true, nullable = false)
private String username;;
    @Column(nullable = false, length = 1024)
private String password;;
    @Column(nullable = false, columnDefinition = "tinyint(1) default 0")
private boolean admin;;

// All method members:
     public Long getId();
     public void setId(Long id);
     public String getUsername();
     public void setUsername(String username);
     public String getPassword();
     public void setPassword(String password);
     public boolean isAdmin();
     public void setAdmin(boolean admin);
}
"""

CLASS_STR_CONFIG = """// File:
@Configuration @EnableWebSecurity public class WebSecurityConfig implements Empty {

// All data members:
    @Autowired
private UserDetailsService userDetailsService;;

// All method members:
    @Bean  SecurityFilterChain filterChain(HttpSecurity http) throws Exception;
    @Autowired public void configureGlobal(AuthenticationManagerBuilder auth) throws Exception;
}
"""


class TestJavaAstParser(unittest.TestCase):
    """Unit tests for ast_parser.py."""

    def test_create_from_config(self):
        """Unit tests for create_from_config."""
        config = utils.parse_proto(TEXT_PROTO, ast_parser_pb2.AstParser)
        java_ast_parser = ast_parser_factory.create_ast_parser(
            config, root_dir="<root_dir>"
        )

        self.assertIsInstance(java_ast_parser, ast_parser_factory.BaseAstParser)
        self.assertIsInstance(java_ast_parser, ast_parser.JavaAstParser)

        self.assertEqual(java_ast_parser.root_dir, "<root_dir>")
        self.assertEqual(java_ast_parser.project, "<root_dir>/pom.xml")

    @parameterized.expand(
        (
            # pylint: disable=line-too-long
            (
                "native/pom.xml",
                # 2 packages.
                (
                    PackageData(
                        name="com.github.javaparser",
                        version="3.25.10",
                        artifact_id="javaparser-core",
                    ),
                    PackageData(name="junit", version="4.8.2", artifact_id="junit"),
                ),
            ),
            (
                "testdata/xmpp-light.xml",
                # 19 packages.
                (
                    PackageData(
                        name="org.springframework.boot",
                        version=None,
                        artifact_id="spring-boot-starter-web",
                    ),
                    PackageData(
                        name="org.springframework.boot",
                        version=None,
                        artifact_id="spring-boot-starter-tomcat",
                    ),
                    PackageData(
                        name="org.springframework.boot",
                        version=None,
                        artifact_id="spring-boot-starter-data-jpa",
                    ),
                    PackageData(
                        name="org.springframework.boot",
                        version=None,
                        artifact_id="spring-boot-starter-cache",
                    ),
                    PackageData(
                        name="org.springframework.boot",
                        version=None,
                        artifact_id="spring-boot-starter-security",
                    ),
                    PackageData(
                        name="org.springframework.boot",
                        version=None,
                        artifact_id="spring-boot-starter-thymeleaf",
                    ),
                    PackageData(
                        name="org.springframework.boot",
                        version=None,
                        artifact_id="spring-boot-starter-validation",
                    ),
                    PackageData(
                        name="io.github.jpenren",
                        version="3.2.0",
                        artifact_id="thymeleaf-spring-data-dialect",
                    ),
                    PackageData(
                        name="jakarta.persistence",
                        version=None,
                        artifact_id="jakarta.persistence-api",
                    ),
                    PackageData(
                        name="org.webjars", version="3.3.7-1", artifact_id="bootstrap"
                    ),
                    PackageData(
                        name="org.webjars", version="3.1.1", artifact_id="jquery"
                    ),
                    PackageData(
                        name="org.webjars", version="2.15.0", artifact_id="momentjs"
                    ),
                    PackageData(
                        name="org.webjars",
                        version=None,
                        artifact_id="webjars-locator-core",
                    ),
                    PackageData(
                        name="org.apache.vysper",
                        version="0.7",
                        artifact_id="vysper-core",
                    ),
                    PackageData(
                        name="org.apache.vysper.extensions",
                        version="0.7",
                        artifact_id="xep0060-pubsub",
                    ),
                    PackageData(
                        name="org.apache.vysper.extensions",
                        version="0.7",
                        artifact_id="xep0045-muc",
                    ),
                    PackageData(
                        name="com.mysql", version=None, artifact_id="mysql-connector-j"
                    ),
                    PackageData(
                        name="de.svenkubiak", version="0.4.1", artifact_id="jBCrypt"
                    ),
                    PackageData(
                        name="org.springframework.boot",
                        version=None,
                        artifact_id="spring-boot-starter-test",
                    ),
                ),
            ),
            # pylint: enable=line-too-long
        )
    )
    def test_parse_packages(self, filename, expected_packages):
        """Unit tests for parse_packages."""
        project = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        java_ast_parser = ast_parser.JavaAstParser(
            os.path.dirname(project), project=project
        )

        packages = java_ast_parser.parse_packages()
        for pkg in packages:
            logging.debug(pkg)
        self.assertEqual(packages, expected_packages)

    @parameterized.expand(
        (
            # pylint: disable=line-too-long
            (
                "native/pom.xml",
                defaultdict(
                    int,
                    {
                        "JavaAstParser::00-start": 1,
                        "JavaAstParser::01-filter--project-exists": 1,
                        # Project
                        "JavaAstParser::02-project--00--root=<{http://maven.apache.org/POM/4.0.0}project>": 1,
                        "JavaAstParser::02-project--01--00--name=<{http://www.w3.org/2001/XMLSchema-instance}schemaLocation>": 1,
                        "JavaAstParser::02-project--01--01--value-type=<class 'str'>": 1,
                        "JavaAstParser::02-project--01--02--{http://www.w3.org/2001/XMLSchema-instance}schemaLocation=<http://maven.apache.org/POM/4.0.0 http://maven.apache.org/maven-v4_0_0.xsd>": 1,
                        "JavaAstParser::02-project--02--00--tag-uniq-count=<0012>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}artifactId>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}build>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}dependencies>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}distributionManagement>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}groupId>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}modelVersion>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}name>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}packaging>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}properties>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}reporting>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}url>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}version>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}artifactId,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}build,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}dependencies,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}distributionManagement,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}groupId,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}modelVersion,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}name,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}packaging,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}properties,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}reporting,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}url,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}version,01>": 1,
                        "JavaAstParser::02-project--03--00--children-count=<0012>": 1,
                        "JavaAstParser::02-project--03--01--child-elem-count=<0000>": 11,
                        "JavaAstParser::02-project--03--01--child-elem-count=<0003>": 1,
                        "JavaAstParser::02-project--03--02--child-tag=<{http://maven.apache.org/POM/4.0.0}properties--{http://maven.apache.org/POM/4.0.0}maven.compiler.source>": 1,
                        "JavaAstParser::02-project--03--02--child-tag=<{http://maven.apache.org/POM/4.0.0}properties--{http://maven.apache.org/POM/4.0.0}maven.compiler.target>": 1,
                        "JavaAstParser::02-project--03--02--child-tag=<{http://maven.apache.org/POM/4.0.0}properties--{http://maven.apache.org/POM/4.0.0}project.build.sourceEncoding>": 1,
                        # Tag Value.
                        "JavaAstParser::02-project--03--03--child-tag-value=<{http://maven.apache.org/POM/4.0.0}properties--{http://maven.apache.org/POM/4.0.0}maven.compiler.source,17>": 1,
                        "JavaAstParser::02-project--03--03--child-tag-value=<{http://maven.apache.org/POM/4.0.0}properties--{http://maven.apache.org/POM/4.0.0}maven.compiler.target,17>": 1,
                        "JavaAstParser::02-project--03--03--child-tag-value=<{http://maven.apache.org/POM/4.0.0}properties--{http://maven.apache.org/POM/4.0.0}project.build.sourceEncoding,UTF-8>": 1,
                        # Packages
                        "JavaAstParser::03-packages-00--len=002": 1,
                        "JavaAstParser::03-packages-01--00-package--name--uniq-count=<0002>": 1,
                        "JavaAstParser::03-packages-01--00-package--name=<com.github.javaparser>": 1,
                        "JavaAstParser::03-packages-01--00-package--name=<junit>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact--uniq-count=<0002>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<com.github.javaparser~javaparser-core>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<junit~junit>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version--uniq-count=<0002>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<com.github.javaparser~javaparser-core==<3.25.10>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<junit~junit==<4.8.2>>": 1,
                        "JavaAstParser::04-finish": 1,
                    },
                ),
            ),
            (
                "testdata/xmpp-light.xml",
                defaultdict(
                    int,
                    {
                        "JavaAstParser::00-start": 1,
                        "JavaAstParser::01-filter--project-exists": 1,
                        # Project
                        "JavaAstParser::02-project--00--root=<{http://maven.apache.org/POM/4.0.0}project>": 1,
                        "JavaAstParser::02-project--01--00--name=<{http://www.w3.org/2001/XMLSchema-instance}schemaLocation>": 1,
                        "JavaAstParser::02-project--01--01--value-type=<class 'str'>": 1,
                        "JavaAstParser::02-project--01--02--{http://www.w3.org/2001/XMLSchema-instance}schemaLocation=<http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd>": 1,
                        "JavaAstParser::02-project--02--00--tag-uniq-count=<0012>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}artifactId>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}build>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}dependencies>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}dependencyManagement>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}description>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}groupId>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}modelVersion>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}name>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}packaging>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}parent>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}properties>": 1,
                        "JavaAstParser::02-project--02--01--tag=<{http://maven.apache.org/POM/4.0.0}version>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}artifactId,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}build,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}dependencies,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}dependencyManagement,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}description,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}groupId,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}modelVersion,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}name,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}packaging,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}parent,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}properties,01>": 1,
                        "JavaAstParser::02-project--02--02--tag-count=<{http://maven.apache.org/POM/4.0.0}version,01>": 1,
                        "JavaAstParser::02-project--03--00--children-count=<0012>": 1,
                        "JavaAstParser::02-project--03--01--child-elem-count=<0000>": 9,
                        "JavaAstParser::02-project--03--01--child-elem-count=<0001>": 1,
                        "JavaAstParser::02-project--03--01--child-elem-count=<0002>": 1,
                        "JavaAstParser::02-project--03--01--child-elem-count=<0003>": 1,
                        "JavaAstParser::02-project--03--02--child-tag=<{http://maven.apache.org/POM/4.0.0}build--{http://maven.apache.org/POM/4.0.0}finalName>": 1,
                        "JavaAstParser::02-project--03--02--child-tag=<{http://maven.apache.org/POM/4.0.0}parent--{http://maven.apache.org/POM/4.0.0}artifactId>": 1,
                        "JavaAstParser::02-project--03--02--child-tag=<{http://maven.apache.org/POM/4.0.0}parent--{http://maven.apache.org/POM/4.0.0}groupId>": 1,
                        "JavaAstParser::02-project--03--02--child-tag=<{http://maven.apache.org/POM/4.0.0}parent--{http://maven.apache.org/POM/4.0.0}version>": 1,
                        "JavaAstParser::02-project--03--02--child-tag=<{http://maven.apache.org/POM/4.0.0}properties--{http://maven.apache.org/POM/4.0.0}java.version>": 1,
                        "JavaAstParser::02-project--03--02--child-tag=<{http://maven.apache.org/POM/4.0.0}properties--{http://maven.apache.org/POM/4.0.0}thymeleaf-layout-dialect.version>": 1,
                        "JavaAstParser::02-project--03--03--child-tag-value=<{http://maven.apache.org/POM/4.0.0}build--{http://maven.apache.org/POM/4.0.0}finalName,xmpplight>": 1,
                        "JavaAstParser::02-project--03--03--child-tag-value=<{http://maven.apache.org/POM/4.0.0}parent--{http://maven.apache.org/POM/4.0.0}artifactId,spring-boot-starter-parent>": 1,
                        "JavaAstParser::02-project--03--03--child-tag-value=<{http://maven.apache.org/POM/4.0.0}parent--{http://maven.apache.org/POM/4.0.0}groupId,org.springframework.boot>": 1,
                        "JavaAstParser::02-project--03--03--child-tag-value=<{http://maven.apache.org/POM/4.0.0}parent--{http://maven.apache.org/POM/4.0.0}version,3.2.4>": 1,
                        "JavaAstParser::02-project--03--03--child-tag-value=<{http://maven.apache.org/POM/4.0.0}properties--{http://maven.apache.org/POM/4.0.0}java.version,17>": 1,
                        "JavaAstParser::02-project--03--03--child-tag-value=<{http://maven.apache.org/POM/4.0.0}properties--{http://maven.apache.org/POM/4.0.0}thymeleaf-layout-dialect.version,2.0.3>": 1,
                        # Packages
                        "JavaAstParser::03-packages-00--len=019": 1,
                        ###
                        # Names: # =  8
                        "JavaAstParser::03-packages-01--00-package--name--uniq-count=<0008>": 1,
                        "JavaAstParser::03-packages-01--00-package--name=<com.mysql>": 1,
                        "JavaAstParser::03-packages-01--00-package--name=<de.svenkubiak>": 1,
                        "JavaAstParser::03-packages-01--00-package--name=<io.github.jpenren>": 1,
                        "JavaAstParser::03-packages-01--00-package--name=<jakarta.persistence>": 1,
                        "JavaAstParser::03-packages-01--00-package--name=<org.apache.vysper.extensions>": 1,
                        "JavaAstParser::03-packages-01--00-package--name=<org.apache.vysper>": 1,
                        "JavaAstParser::03-packages-01--00-package--name=<org.springframework.boot>": 1,
                        "JavaAstParser::03-packages-01--00-package--name=<org.webjars>": 1,
                        # Name and artifact ids: # = 19
                        "JavaAstParser::03-packages-01--01-package--name-artifact--uniq-count=<0019>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<com.mysql~mysql-connector-j>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<de.svenkubiak~jBCrypt>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<io.github.jpenren~thymeleaf-spring-data-dialect>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<jakarta.persistence~jakarta.persistence-api>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.apache.vysper.extensions~xep0045-muc>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.apache.vysper.extensions~xep0060-pubsub>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.apache.vysper~vysper-core>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.springframework.boot~spring-boot-starter-cache>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.springframework.boot~spring-boot-starter-data-jpa>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.springframework.boot~spring-boot-starter-security>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.springframework.boot~spring-boot-starter-test>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.springframework.boot~spring-boot-starter-thymeleaf>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.springframework.boot~spring-boot-starter-tomcat>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.springframework.boot~spring-boot-starter-validation>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.springframework.boot~spring-boot-starter-web>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.webjars~bootstrap>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.webjars~jquery>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.webjars~momentjs>": 1,
                        "JavaAstParser::03-packages-01--01-package--name-artifact=<org.webjars~webjars-locator-core>": 1,
                        # Name, artifact id and versions: # = 19
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version--uniq-count=<0019>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<com.mysql~mysql-connector-j==<None>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<de.svenkubiak~jBCrypt==<0.4.1>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<io.github.jpenren~thymeleaf-spring-data-dialect==<3.2.0>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<jakarta.persistence~jakarta.persistence-api==<None>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.apache.vysper.extensions~xep0045-muc==<0.7>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.apache.vysper.extensions~xep0060-pubsub==<0.7>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.apache.vysper~vysper-core==<0.7>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.springframework.boot~spring-boot-starter-cache==<None>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.springframework.boot~spring-boot-starter-data-jpa==<None>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.springframework.boot~spring-boot-starter-security==<None>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.springframework.boot~spring-boot-starter-test==<None>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.springframework.boot~spring-boot-starter-thymeleaf==<None>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.springframework.boot~spring-boot-starter-tomcat==<None>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.springframework.boot~spring-boot-starter-validation==<None>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.springframework.boot~spring-boot-starter-web==<None>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.webjars~bootstrap==<3.3.7-1>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.webjars~jquery==<3.1.1>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.webjars~momentjs==<2.15.0>>": 1,
                        "JavaAstParser::03-packages-01--02-package--name-artifact-version=<org.webjars~webjars-locator-core==<None>>": 1,
                        ###
                        "JavaAstParser::04-finish": 1,
                    },
                ),
            ),
            # pylint: enable=line-too-long
        )
    )
    def test_run_metrics(self, filename, expected_metrics):
        """Unit tests for run_metrics."""
        project = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        java_ast_parser = ast_parser.JavaAstParser(
            os.path.dirname(project), project=project
        )

        metrics = java_ast_parser.run_metrics()
        for name, value in sorted(metrics.items()):
            logging.debug("%s: %d", name, value)
        self.assertEqual(metrics, expected_metrics)

    @parameterized.expand(
        (
            # pylint: disable=line-too-long
            (
                "testdata/User.java",
                {
                    # "method": "setId",
                    "line_number": 34,
                },
                (
                    ClassData(
                        name="User",
                        signature='@Entity(name = "user") public class User',
                        lines=LineData(
                            line_start=12,
                            line_end=61,
                        ),
                        parents=(),
                        members=(
                            VariableData(
                                name="id",
                                signature="@Id\n@GeneratedValue\nprivate Long id;",
                                lines=LineData(line_start=17),
                            ),
                            VariableData(
                                name="username",
                                signature="@Size(min = 2, max = 20)\n@Column(unique = true, nullable = false)\nprivate String username;",
                                lines=LineData(line_start=21),
                            ),
                            VariableData(
                                name="password",
                                signature="@Column(nullable = false, length = 1024)\nprivate String password;",
                                lines=LineData(line_start=24),
                            ),
                            VariableData(
                                name="admin",
                                signature='@Column(nullable = false, columnDefinition = "tinyint(1) default 0")\nprivate boolean admin;',
                                lines=LineData(line_start=27),
                            ),
                        ),
                        methods=(
                            MethodData(
                                name="getId",
                                signature=" public Long getId()",
                                lines=LineData(line_start=29, line_end=31),
                                params=(),
                                local_vars=(),
                            ),
                            MethodData(
                                name="setId",
                                signature=" public void setId(Long id)",
                                lines=LineData(line_start=33, line_end=35),
                                params=(
                                    VariableData(
                                        name="id",
                                        signature="Long id",
                                        lines=LineData(line_start=33),
                                    ),
                                ),
                                local_vars=(),
                            ),
                            MethodData(
                                name="getUsername",
                                signature=" public String getUsername()",
                                lines=LineData(line_start=37, line_end=39),
                                params=(),
                                local_vars=(),
                            ),
                            MethodData(
                                name="setUsername",
                                signature=" public void setUsername(String username)",
                                lines=LineData(line_start=41, line_end=43),
                                params=(
                                    VariableData(
                                        name="username",
                                        signature="String username",
                                        lines=LineData(line_start=41),
                                    ),
                                ),
                                local_vars=(),
                            ),
                            MethodData(
                                name="getPassword",
                                signature=" public String getPassword()",
                                lines=LineData(line_start=45, line_end=47),
                                params=(),
                                local_vars=(),
                            ),
                            MethodData(
                                name="setPassword",
                                signature=" public void setPassword(String password)",
                                lines=LineData(line_start=49, line_end=51),
                                params=(
                                    VariableData(
                                        name="password",
                                        signature="String password",
                                        lines=LineData(line_start=49),
                                    ),
                                ),
                                local_vars=(),
                            ),
                            MethodData(
                                name="isAdmin",
                                signature=" public boolean isAdmin()",
                                lines=LineData(line_start=53, line_end=55),
                                params=(),
                                local_vars=(),
                            ),
                            MethodData(
                                name="setAdmin",
                                signature=" public void setAdmin(boolean admin)",
                                lines=LineData(line_start=57, line_end=59),
                                params=(
                                    VariableData(
                                        name="admin",
                                        signature="boolean admin",
                                        lines=LineData(line_start=57),
                                    ),
                                ),
                                local_vars=(),
                            ),
                        ),
                    ),
                ),
                (CLASS_STR_USER,),
                (
                    (
                        VariableData(
                            name="id",
                            signature="@Id\n@GeneratedValue\nprivate Long id;",
                            lines=LineData(line_start=17),
                        ),
                    ),
                    (
                        VariableData(
                            name="id",
                            signature="Long id",
                            lines=LineData(line_start=33),
                        ),
                    ),
                    (),
                ),
            ),
            (
                "testdata/WebSecurityConfig.java",
                {
                    "line_number": 44,
                },
                (
                    ClassData(
                        name="WebSecurityConfig",
                        signature="@Configuration @EnableWebSecurity public class WebSecurityConfig implements Empty",
                        lines=LineData(
                            line_start=18,
                            line_end=51,
                        ),
                        parents=(
                            VariableData(
                                name="Empty",
                                signature="Empty",
                                lines=LineData(line_start=20),
                            ),
                        ),
                        members=(
                            VariableData(
                                name="userDetailsService",
                                signature="@Autowired\nprivate UserDetailsService userDetailsService;",
                                lines=LineData(line_start=23),
                            ),
                        ),
                        methods=(
                            MethodData(
                                name="filterChain",
                                signature="@Bean  SecurityFilterChain filterChain(HttpSecurity http) throws Exception",
                                lines=LineData(
                                    line_start=25,
                                    line_end=39,
                                ),
                                params=(
                                    VariableData(
                                        name="http",
                                        signature="HttpSecurity http",
                                        lines=LineData(line_start=26),
                                    ),
                                ),
                                local_vars=(),
                            ),
                            MethodData(
                                name="configureGlobal",
                                signature="@Autowired public void configureGlobal(AuthenticationManagerBuilder auth) throws Exception",
                                lines=LineData(
                                    line_start=41,
                                    line_end=49,
                                ),
                                params=(
                                    VariableData(
                                        name="auth",
                                        signature="AuthenticationManagerBuilder auth",
                                        lines=LineData(line_start=42),
                                    ),
                                ),
                                local_vars=(
                                    VariableData(
                                        name="used",
                                        signature="String used",
                                        lines=LineData(line_start=43),
                                    ),
                                    VariableData(
                                        name="unused",
                                        signature="String unused",
                                        lines=LineData(line_start=48),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
                (CLASS_STR_CONFIG,),
                (
                    (
                        VariableData(
                            name="userDetailsService",
                            signature="@Autowired\nprivate UserDetailsService userDetailsService;",
                            lines=LineData(line_start=23),
                        ),
                    ),
                    (
                        VariableData(
                            name="auth",
                            signature="AuthenticationManagerBuilder auth",
                            lines=LineData(line_start=42),
                        ),
                    ),
                    # One single local var is defined before.
                    (
                        VariableData(
                            name="used",
                            signature="String used",
                            lines=LineData(line_start=43),
                        ),
                    ),
                ),
            ),
            # pylint: enable=line-too-long
        )
    )
    def test_parse_classes_variables(
        self, filename, kwargs, expected_classes, expected_strs, expected_variables
    ):
        """Unit tests for parse_ast, parse_classes and parse_variables."""
        filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        java_ast_parser = ast_parser.JavaAstParser("project")

        logging.info("Classes:")
        classes = java_ast_parser.parse_classes(filename)
        for cls in classes:
            logging.info(cls)
        self.assertEqual(classes, expected_classes)

        self.assertEqual(len(classes), len(expected_strs))
        for cls, expected_str in zip(classes, expected_strs):
            self.assertEqual(str(cls), expected_str)

        logging.info("Variables:")
        variables = java_ast_parser.parse_variables(filename, classes, **kwargs)
        for var in variables:
            logging.info(var)
        self.assertEqual(variables, expected_variables)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    unittest.main()
