"""Unit tests for file_utils.py."""

from collections import defaultdict
import logging
import os
import tempfile
import unittest
import xml
import xml.etree.ElementTree as ET

from parameterized import parameterized

from self_debug.common import file_utils, utils

_PWD = os.path.dirname(os.path.abspath(__file__))


_JAVA_VERSION = "${java.version}"


def load_xml(file) -> str:
    """Load xml."""
    return ET.tostring(file_utils.load_xml(file))


class TestUtils(unittest.TestCase):
    """Unit tests for file_utils.py."""

    _JAVA_VERSIONS_POM_00 = (
        {"11"},
        {
            "maven.compiler.source": "11",
            "maven.compiler.target": "11",
        },
    )

    _JAVA_VERSIONS_POM_01 = (
        {"8", "17"},
        {
            "maven.compiler.release": "17",
            "release": "8",
        },
    )

    _JAVA_VERSIONS_POM_02 = (
        {"1.8"},
        {
            "source": "1.8",
            "target": "1.8",
        },
    )

    _JAVA_VERSIONS_POM_06 = _JAVA_VERSIONS_POM_02

    _JAVA_VERSION_08 = "Fatal error compiling: invalid flag: --release"
    _JAVA_VERSIONS_POM_08 = (
        {"1.8", "11", _JAVA_VERSION_08},
        {
            "release": _JAVA_VERSION_08,
            "source": "11",
            "target": "11",
        },
    )

    @parameterized.expand(
        (
            (
                os.path.abspath(__file__),
                None,
                0,
            ),
            # Multi `project`s: Direct parsing doesn't work
            (
                "./testdata/effective-pom.xml",
                (
                    None,
                    None,
                ),
                (
                    {"17"},
                    {
                        "maven.compiler.release": "17",
                    },
                ),
            ),
            # Single `project`: Equivalent to direct parsing
            ("./testdata/effective-pom-01.xml",)
            + (
                (
                    {"1.6"},
                    {
                        "maven.compiler.source": "1.6",
                        "maven.compiler.target": "1.6",
                        "source": "1.6",
                    },
                ),
            )
            * 2,
            ("./testdata/effective-pom-02.xml",)
            + (
                (
                    {"11", "Fatal error compiling: invalid flag: --release"},
                    {
                        "source": "11",
                        "target": "11",
                        "release": "Fatal error compiling: invalid flag: --release",
                    },
                ),
            )
            * 2,
            (
                "./testdata/java_pom_00.xml",
                _JAVA_VERSIONS_POM_00,
                _JAVA_VERSIONS_POM_00,
            ),
            (
                "./testdata/java_pom_00_ns.xml",
                _JAVA_VERSIONS_POM_00,
                _JAVA_VERSIONS_POM_00,
            ),
            (
                "./testdata/java_pom_01.xml",
                _JAVA_VERSIONS_POM_01,
                0,
            ),
            (
                "./testdata/java_pom_01_ns.xml",
                _JAVA_VERSIONS_POM_01,
                0,
            ),
            (
                "./testdata/java_pom_02_xmpp_light.xml",
                _JAVA_VERSIONS_POM_02,
                0,
            ),
            (
                "./testdata/java_pom_02_xmpp_light_no_declaration_01.xml",
                _JAVA_VERSIONS_POM_02,
                0,
            ),
            (
                "./testdata/java_pom_02_xmpp_light_ns.xml",
                _JAVA_VERSIONS_POM_02,
                0,
            ),
            ("./testdata/java_pom_03.xml",)
            + (
                (
                    {"11", "1"},
                    {
                        "maven.compiler.source": "11",
                        "maven.compiler.target": "1",
                        # "maven.compiler.release": "",
                    },
                ),
            )
            * 2,
            (
                "./testdata/java_pom_04.xml",
                (None, None),
                (None, None),
            ),
            (
                "./testdata/java_pom_05.xml",
                None,
                None,
            ),
            (
                "./testdata/java_pom_06.xml",
                _JAVA_VERSIONS_POM_06,
                0,
            ),
            # TODO(sliuxl): Need to find a good example for it.
            (
                "./testdata/java_pom_07_invalid_str.xml",
                None,
                0,
            ),
            (
                "./testdata/java_pom_08_multi_plugins.xml",
                _JAVA_VERSIONS_POM_08,
                0,
            ),
            (
                "./testdata/java_pom_09.xml",
                (
                    {"11", "1."},
                    {
                        "maven.compiler.source": "11",
                        "maven.compiler.target": "1.",
                        # "maven.compiler.release": "  ",
                    },
                ),
                0,
            ),
            (
                "./testdata/java_pom_10.xml",
                (
                    {"1.8"},
                    {
                        "source": "1.8",
                        "target": "1.8",
                        # "encoding": ...,
                    },
                ),
                0,
            ),
            (
                "./testdata/java_pom_11_invalid_version.xml",
                (
                    {
                        "1.you-must-override-the-java.level-property",
                        "1.java",
                        "\${java.version}",
                    },
                    {
                        "maven.compiler.source": "1.you-must-override-the-java.level-property",
                        "maven.compiler.target": "1.java",
                        "maven.compiler.release": "\${java.version}",
                    },
                ),
                0,
            ),
            (
                "./testdata/java_pom_12_start_with_empty_line.xml",
                (
                    None,
                    None,
                ),
                0,
            ),
        )
    )
    def test_get_java_version(self, filename, expected_version, expected_effective_v):
        """Unit tests for get_java_version."""
        self.assertEqual(
            file_utils.get_java_version(os.path.join(_PWD, filename), _PWD),
            expected_version,
        )

        if isinstance(expected_effective_v, int):
            return

        self.assertEqual(
            file_utils.get_effective_java_version(os.path.join(_PWD, filename), _PWD),
            expected_effective_v,
        )

    @parameterized.expand(
        (
            (
                "./testdata/effective-pom.xml",
                {},
                (
                    (
                        None,
                        None,
                    ),
                    None,
                ),
            ),
            (
                "./testdata/effective-pom.xml",
                {
                    "return_int_on_failing_effective": True,
                },
                (
                    -1,
                    None,
                ),
            ),
        )
    )
    def test_get_java_versions__effective(self, filename, kwargs, expected_versions):
        """Unit tests for get_java_versions."""
        filename = os.path.join(_PWD, filename)

        self.assertEqual(
            file_utils.get_java_versions((filename,), _PWD, **kwargs),
            expected_versions[0],
        )

        self.assertEqual(
            file_utils.get_java_versions((filename, ""), _PWD, **kwargs),
            expected_versions[1],
        )

    _JAVA_VERSIONS_POM_00_AND_02 = (
        {"11", "1.8"},
        {
            "maven.compiler.source": "11",
            "maven.compiler.target": "11",
            "source": "1.8",
            "target": "1.8",
        },
    )

    @parameterized.expand(
        (
            (
                (os.path.abspath(__file__),),
                _PWD,
                None,
            ),
            (
                ("./testdata/java_pom_00.xml",),
                _PWD,
                _JAVA_VERSIONS_POM_00,
            ),
            (
                (
                    "./testdata/java_pom_01.xml",
                    "./testdata/java_pom_01_ns.xml",
                ),
                _PWD,
                _JAVA_VERSIONS_POM_01,
            ),
            (
                (
                    "./testdata/java_pom_00.xml",
                    "./testdata/java_pom_02_xmpp_light.xml",
                ),
                _PWD,
                _JAVA_VERSIONS_POM_00_AND_02,
            ),
            (
                (
                    "./testdata/java_pom_02_xmpp_light.xml",
                    "./testdata/java_pom_00.xml",
                ),
                _PWD,
                _JAVA_VERSIONS_POM_00_AND_02,
            ),
            # Nested dirs.
            # - #modules = 1
            (
                ("./testdata/pom.xml",),
                _PWD,
                (
                    {"1.8"},
                    {
                        "source": "1.8",
                        "target": "1.8",
                    },
                ),
            ),
            (
                ("./testdata/subdir/pom.xml",),
                _PWD,
                (
                    {"1.9"},
                    {
                        "source": "1.9",
                        "release": "1.9",
                    },
                ),
            ),
            # Different `root_dir`s:
            (
                ("./testdata/subdir/subsubdir/pom.xml",),
                os.path.join(_PWD, "testdata/subdir/subsubdir"),
                (
                    {_JAVA_VERSION},
                    {
                        "source": _JAVA_VERSION,
                    },
                ),
            ),
            (
                ("./testdata/subdir/subsubdir/pom.xml",),
                os.path.join(_PWD, "testdata/subdir"),
                (
                    {"1.9"},
                    {
                        "source": "1.9",
                    },
                ),
            ),
            (
                ("./testdata/subdir/subsubdir/pom.xml",),
                _PWD,
                (
                    {"1.9"},
                    {
                        "source": "1.9",
                    },
                ),
            ),
            # - #modules = 2
            (
                (
                    "./testdata/pom.xml",
                    "./testdata/subdir/pom.xml",
                ),
                _PWD,
                (
                    {"1.8", "1.9"},
                    {
                        "source": "1.9",
                        "target": "1.8",
                        "release": "1.9",
                    },
                ),
            ),
            (
                (
                    "./testdata/subdir/pom.xml",
                    "./testdata/subdir/subsubdir/pom.xml",
                ),
                os.path.join(_PWD, "testdata/subdir"),
                (
                    {"1.9"},
                    {
                        "source": "1.9",
                        "release": "1.9",
                    },
                ),
            ),
            # - Still valid pom.xml
            (
                (
                    "./testdata/java_pom_00.xml",
                    "./testdata/java_pom_04.xml",
                ),
                _PWD,
                _JAVA_VERSIONS_POM_00,
            ),
            # - Invalid pom.xml
            (
                (
                    "./testdata/java_pom_00.xml",
                    "./testdata/java_pom_05.xml",
                ),
                _PWD,
                None,
            ),
            # - #modules = 3
            (
                (
                    "./testdata/pom.xml",
                    "./testdata/subdir/pom.xml",
                    "./testdata/subdir/subsubdir/pom.xml",
                ),
                _PWD,
                (
                    {"1.8", "1.9"},
                    {
                        "source": "1.9",
                        "target": "1.8",
                        "release": "1.9",
                    },
                ),
            ),
        )
    )
    def test_get_java_versions(self, filenames, root_dir, expected_versions):
        """Unit tests for get_java_versions."""
        self.assertEqual(
            file_utils.get_java_versions(
                [os.path.join(_PWD, f) for f in filenames], root_dir
            ),
            expected_versions,
        )

    @parameterized.expand(
        (
            # Parsed as int.
            (("1",), 8, True, False, False),
            (("2",), 8, True, False, False),
            (("3",), 8, True, False, False),
            (("4",), 8, True, False, False),
            (("5",), 8, True, False, False),
            (("6",), 8, True, False, False),
            (("7",), 8, True, False, False),
            (("8",), 8, False, False, False),  # ***
            (("9",), 8, False, True, False),
            (("10",), 8, False, True, False),
            (("11",), 8, False, True, False),
            (("12",), 8, False, True, False),
            (("13",), 8, False, True, False),
            (("14",), 8, False, True, False),
            (("15",), 8, False, True, False),
            (("16",), 8, False, True, False),
            (("17",), 8, False, True, False),
            (("21",), 8, False, True, False),
            # - Different threshold.
            (("8",), 17, True, False, False),
            (("15",), 17, True, False, False),
            (("16",), 17, True, False, False),
            (("17",), 17, False, False, False),  # ***
            (("21",), 17, False, True, False),
            # Parsed as version.
            (("1.1",), 8, True, False, False),
            (("1.2",), 8, True, False, False),
            (("1.3",), 8, True, False, False),
            (("1.4",), 8, True, False, False),
            (("1.5",), 8, True, False, False),
            (("1.6",), 8, True, False, False),
            (("1.7",), 8, True, False, False),
            (("1.8",), 8, False, False, False),  # ***
            (("1.9",), 8, False, True, False),
            (("1.10",), 8, False, True, False),
            (("1.11",), 8, False, True, False),
            (("1.12",), 8, False, True, False),
            (("1.13",), 8, False, True, False),
            (("1.14",), 8, False, True, False),
            (("1.15",), 8, False, True, False),
            (("1.16",), 8, False, True, False),
            (("1.17",), 8, False, True, False),
            (("1.21",), 8, False, True, False),
            # - Different threshold.
            (("1.5",), 17, True, False, False),
            (("1.6",), 17, True, False, False),
            (("1.8",), 17, True, False, False),
            (("1.16",), 17, True, False, False),
            (("1.17",), 17, False, False, False),  # ***
            (("1.21",), 17, False, True, False),
            # N.A.
            (("",), 8, False, False, False),
            (("${java.version}",), 8, False, False, False),
            (("1.${java.version}",), 8, False, False, False),
            (("1.java",), 8, False, False, False),
            (("1.java.version",), 8, False, False, False),
            (("\${java.version}",), 8, False, False, False),
            (("1.you-must-override-the-java.level-property",), 8, False, False, False),
            (("1.",), 8, False, False, False),
            (("1.",), 17, False, False, False),
            # Multi ones
            (
                (
                    "${java.version}",
                    "1.7",
                ),
                8,
                True,
                False,
                False,
            ),
            (
                (
                    "${java.version}",
                    "1.5",
                    "17",
                ),
                8,
                True,
                True,
                True,
            ),
            (
                (
                    "${java.version}",
                    "${source.version}",
                ),
                8,
                False,
                False,
                False,
            ),
            (
                (
                    "${java.version}",
                    "${source.version}",
                    "1.8",
                    "8",
                ),
                8,
                False,
                False,
                False,
            ),
        )
    )
    def test_reject_older_java_versions(
        self, versions, spec_ge, expected_r0, expected_r1, expected_r2
    ):
        """Unit tests for reject_older_java_versions."""
        self.assertEqual(
            file_utils.reject_older_java_versions(versions, spec_ge), expected_r0
        )
        self.assertEqual(
            file_utils.reject_newer_java_versions(versions, spec_ge), expected_r1
        )

        # No need for `spec_ge`.
        self.assertEqual(
            file_utils.reject_conflicting_java_versions(versions), expected_r2
        )

    @parameterized.expand(
        (
            (
                _PWD,
                {},
                (
                    None,
                    True,
                    defaultdict(
                        int,
                        {
                            "reject-snapshot-00-start": 1,
                            "reject-snapshot-01-no-pom-xml": 1,
                        },
                    ),
                ),
                # Unused
                (
                    False,
                    True,
                    defaultdict(
                        int,
                        {
                            "reject-snapshot-00-start": 1,
                            "reject-snapshot-02-01-java_versions-too-new": 1,
                        },
                    ),
                ),
            )[:-1],
            (
                _PWD,
                {
                    "version": None,
                },
                (
                    None,
                    True,
                    defaultdict(
                        int,
                        {
                            "reject-snapshot-00-start": 1,
                            "reject-snapshot-01-no-pom-xml": 1,
                        },
                    ),
                ),
                (
                    False,
                    True,
                    defaultdict(
                        int,
                        {
                            "reject-snapshot-00-start": 1,
                            "reject-snapshot-03-mvn-clean-verify-failure": 1,
                        },
                    ),
                ),
            )[:-1],
            (
                os.path.join(_PWD, "./testdata/subdir/subsubdir"),
                {},
                (
                    False,
                    True,
                    defaultdict(
                        int,
                        {
                            "reject-snapshot-00-start": 1,
                            "reject-snapshot-03-mvn-clean-verify-failure": 1,
                        },
                    ),
                ),
            ),
            # Actual java dir.
            (
                os.path.join(_PWD, "../lang/java/native"),
                {},
                (
                    False,
                    True,
                    defaultdict(
                        int,
                        {
                            "reject-snapshot-00-start": 1,
                            "reject-snapshot-02-01-java_versions-too-new": 1,
                        },
                    ),
                ),
            ),
            (
                os.path.join(_PWD, "../lang/java/native"),
                {
                    "version": None,
                },
                (
                    False,
                    True,
                    defaultdict(
                        int,
                        {
                            "reject-snapshot-00-start": 1,
                            "reject-snapshot-04-complied-java-version-len__EQ__01": 1,
                            "reject-snapshot-04-complied-java-version-values__EQ__61": 1,
                            "reject-snapshot-05-04-compiled-java_versions-too-new": 1,
                        },
                    ),
                ),
            ),
            # - Passing all filters: Skipping invalid ones
            (
                os.path.join(_PWD, "../lang/java/native"),
                {
                    "version": None,
                    "compiled_version": None,
                },
                (
                    False,
                    False,
                    defaultdict(
                        int,
                        {
                            "reject-snapshot-00-start": 1,
                            "reject-snapshot-10-base-commit-id-found": 1,
                        },
                    ),
                ),
            ),
        )
    )
    def test_reject_java_repo_or_snapshot(self, root_dir, kwargs, expected_reject):
        """Unit tests for reject_java_repo_or_snapshot."""
        self.assertEqual(
            file_utils.reject_java_repo_or_snapshot(
                root_dir, **kwargs, max_maven_attempts=1
            ),
            expected_reject,
        )

    @parameterized.expand(
        (
            (
                "./testdata/Modernize.Web.Mvc.csproj-00",
                "./testdata/Modernize.Web.Mvc.csproj-00",
                False,
            ),
        )
    )
    def test_dedup_csharp_target_framework_attribute(
        self, filename, expected_filename, expected_updated
    ):
        """Unit tests dedup_csharp_target_framework_attribute."""
        _, temp = tempfile.mkstemp()
        try:
            revised_xml, updated = file_utils.dedup_csharp_target_framework_attribute(
                os.path.join(_PWD, filename), temp
            )

            self.assertIsInstance(revised_xml, xml.etree.ElementTree.ElementTree)
            self.assertEqual(updated, expected_updated)

            logging.debug(utils.run_command(f"cat {temp}")[0])

            expected_filename = os.path.join(_PWD, expected_filename)
            if updated:
                self.assertEqual(load_xml(temp), load_xml(expected_filename))
            else:
                self.assertEqual(utils.load_file(temp), "")
        finally:
            os.remove(temp)

    @parameterized.expand(
        (
            # ItemGroup
            (
                "./testdata/AspNetCoreMvcRejitApplication.csproj",
                "./testdata/AspNetCoreMvcRejitApplication.csproj-00",
                None,
                True,
            ),
            (
                "./testdata/AspNetCoreMvcRejitApplication.csproj-00",
                "./testdata/AspNetCoreMvcRejitApplication.csproj-00",
                (),
                False,
            ),
            (
                "./testdata/DotNetCoreAuthExamples.CustomPasswordHasher.csproj",
                "./testdata/DotNetCoreAuthExamples.CustomPasswordHasher.csproj-00",
                [],
                True,
            ),
            # PropertyGroup
            (
                "./testdata/HelloWorld.csproj",
                "./testdata/HelloWorld.csproj-00",
                ("EmbeddedResource",),
                True,
            ),
            (
                "./testdata/HelloWorld.csproj",
                "./testdata/HelloWorld.csproj",
                None,
                False,
            ),
            (
                "./testdata/Naif.Blog.csproj",
                "./testdata/Naif.Blog.csproj-00",
                (),
                True,
            ),
            (
                "./testdata/Naif.Blog.csproj-00",
                "./testdata/Naif.Blog.csproj-00",
                [],
                False,
            ),
            (
                "./testdata/Modernize.Web.Mvc.csproj-00",
                "./testdata/Modernize.Web.Mvc.csproj-00",
                None,
                False,
            ),
            (
                "./testdata/ReflectSoftware.Facebook.Messenger.Common.csproj",
                "./testdata/ReflectSoftware.Facebook.Messenger.Common.csproj-00",
                None,
                True,
            ),
        )
    )
    def test_clean_up_csharp_csproj(
        self, filename, expected_filename, errors, expected_updated
    ):
        """Unit tests clean_up_csharp_csproj."""
        _, temp = tempfile.mkstemp()
        try:
            revised_xml, updated = file_utils.clean_up_csharp_csproj(
                os.path.join(_PWD, filename), temp, errors
            )

            self.assertIsInstance(revised_xml, xml.etree.ElementTree.ElementTree)
            self.assertEqual(updated, expected_updated)

            logging.debug(utils.run_command(f"cat {temp}")[0])

            expected_filename = os.path.join(_PWD, expected_filename)
            if updated:
                self.assertEqual(load_xml(temp), load_xml(expected_filename))
            else:
                self.assertEqual(utils.load_file(temp), "")
        finally:
            os.remove(temp)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    unittest.main()
