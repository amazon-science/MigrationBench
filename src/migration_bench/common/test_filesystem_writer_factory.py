"""Unit test for filesystem_writer_factory.py."""

import logging
import os
import tempfile
from typing import Dict, Sequence, Tuple
import unittest

from parameterized import parameterized

from self_debug.lm import llm_parser_factory
from self_debug.common import filesystem_writer_factory, utils


Pair = llm_parser_factory.FindReplacePair

FILE_DOES_NOT_EXIST = "test_does_not_exist.py"
FILE_NO_CHANGES = "test_no_changes.py"
FILE_WITH_CHANGES = "test_with_changes.py"

C_SHARP_CODE_SNIPPET = """<Project Sdk="Microsoft.NET.Sdk.Web">

  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.EntityFrameworkCore.SqlServer" Version="8.0.2" />
    <PackageReference Include="Microsoft.EntityFrameworkCore" Version="8.0.2" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.Design" Version="8.0.2" />
    <PackageReference Include="Microsoft.CodeAnalysis.Workspaces.Common" Version="4.5.0" />
  </ItemGroup>

  <ItemGroup>
    <ProjectReference Include="..\\Modernize.Web.Common\\Modernize.Web.Common.csproj" />
    <ProjectReference Include="..\\Modernize.Web.Models\\Modernize.Web.Models.csproj" />
    <ProjectReference Include="..\\Modernize.Web.Facade\\Modernize.Web.Facade.csproj" />
  </ItemGroup>

</Project>
"""


class TestPatchChanges(unittest.TestCase):
    """Unit test for filesystem_writer_factory.py."""

    @classmethod
    def setUpClass(cls):
        cls.writer = filesystem_writer_factory.create_filesystem_writer(
            "PairedFileSystemWriter"
        )

    @classmethod
    def tearDownClass(cls):
        pass

    @parameterized.expand(
        (
            # Nothing is found.
            (
                """
  find
                """,
                "find start",
                "world",
                (
                    """
  find
                """,
                    False,
                ),
            ),
            # count = 1.
            (
                """
  find
                """,
                "   find   \n",
                "FIND",
                (
                    """
  FIND
                """,
                    True,
                ),
            ),
            # []
            (
                """
[]
                """,
                "[]",
                "FIND",
                (
                    """
FIND
                """,
                    True,
                ),
            ),
            # ()
            (
                """
()
                """,
                "()",
                "FIND",
                (
                    """
FIND
                """,
                    True,
                ),
            ),
            # ^$
            (
                """
xyz^abc$def
                """,
                "xyz^abc$def",
                "FIND",
                (
                    """
FIND
                """,
                    True,
                ),
            ),
            # {}<> etc is OK.
            (
                """
{}<>[]()'"`^$&.?*+#@-_
                """,
                "{}<>[]()'\"`^$&.?*+#@-_",
                "FIND",
                (
                    """
FIND
                """,
                    True,
                ),
            ),
            # . is not matched as `*`.
            (
                """
  \\s/find#^&*#()$[]{}.?<>`~!@'"+-_\t\r\n\\t\\r\\nanything
  \\s/find#^&*#()$[]{}x?<>`~!@'"+-_\t\r\n\\t\\r\\nanything
  \\s/find#^&*#()$[]{}.?<>`~!@'"+-_\t\r\n\\t\\r\nanything
                """,
                "  \\s/find#^&*#()$[]{}.?<>`~!@'\"+-_\t\r\n\\t\\r\\nanything",
                "FIND",
                (
                    """
  FIND
  \\s/find#^&*#()$[]{}x?<>`~!@'"+-_\t\r\n\\t\\r\\nanything
  \\s/find#^&*#()$[]{}.?<>`~!@'"+-_\t\r\n\\t\\r\nanything
                """,
                    True,
                ),
            ),
            (
                r"""
yield return new PSDriveInfo("Src", REPLACE, "src:\\", "Source Control Drive", Credential);
                """,
                r"""
yield return new PSDriveInfo("Src", REPLACE, "src:\\", "Source Control Drive", Credential);
                """,
                r"""
yield return new PSDriveInfo("Src", null, "src:\\", "Source Control Drive", Credential);
                """,
                (
                    r"""

yield return new PSDriveInfo("Src", null, "src:\\", "Source Control Drive", Credential);
                """
                    + "\n                ",
                    True,
                ),
            ),
            (
                """
<ProjectReference Include=..\Modernize.Web.Common\Modernize.Web.Common.csproj />
                """,
                "<ProjectReference Include=..\Modernize.Web.Common\Modernize.Web.Common.csproj />",
                "<ProjectReference Include=../Modernize.Web.Common/Modernize.Web.Common.csproj />",
                (
                    """
<ProjectReference Include=../Modernize.Web.Common/Modernize.Web.Common.csproj />
                """,
                    True,
                ),
            ),
            (
                """
<ProjectReference Include=..\\Modernize.Web.Common\\Modernize.Web.Common.csproj />
                """,
                "<ProjectReference Include=..\Modernize.Web.Common\Modernize.Web.Common.csproj />",
                "<ProjectReference Include=../Modernize.Web.Common/Modernize.Web.Common.csproj />",
                (
                    """
<ProjectReference Include=../Modernize.Web.Common/Modernize.Web.Common.csproj />
                """,
                    True,
                ),
            ),
            (
                """
<ProjectReference Include=..\\Modernize.Web.Common\\Modernize.Web.Common.csproj />
                """,
                "<ProjectReference Include=..\\Modernize.Web.Common\\Modernize.Web.Common.csproj />",
                "<ProjectReference Include=../Modernize.Web.Common/Modernize.Web.Common.csproj />",
                (
                    """
<ProjectReference Include=../Modernize.Web.Common/Modernize.Web.Common.csproj />
                """,
                    True,
                ),
            ),
            # count = n.
            (
                C_SHARP_CODE_SNIPPET,
                C_SHARP_CODE_SNIPPET,
                "Replaced/block\\M\M\test.csproj()[]{}<>^$.?*+`@#%'\"\t\r\n\\t\\r\\n",
                (
                    "Replaced/block\\M\M\test.csproj()[]{}<>^$.?*+`@#%'\"\t\r\n\\t\\r\\n\n",
                    True,
                ),
            ),
            (
                """
  find

  find 01
02 find
                """,
                "find",
                "FIND",
                (
                    """
  FIND

  FIND 01
02 FIND
                """,
                    True,
                ),
            ),
            # Single vs double quotes
            (
                """
user_parts = user.split('\\\\\\\\', 1)
system_parts = system_parts.split('\\\\', 1)
                """,
                "system_parts = system_parts.split('\\\\', 1)",
                "system_parts = system_parts.split('\\\\', 1) + 'x'",
                (
                    """
user_parts = user.split('\\\\\\\\', 1)
system_parts = system_parts.split('\\\\', 1) + 'x'
                    """[:-4],
                    True,
                ),
            ),
            # - Single
            (
                """
user_parts = user.split('\\\\', 1)
system_parts = system_parts.split('\\\\', 1)
                """,
                "system_parts = system_parts.split('\\\\', 1)",
                "system_parts = system_parts.split('\\\\', 1) + 'x'",
                (
                    """
user_parts = user.split('\\\\', 1)
system_parts = system_parts.split('\\\\', 1) + 'x'
                    """[:-4],
                    True,
                ),
            ),
            # - Double
            (
                """
user_parts = user.split("\\\\", 1)
system_parts = system_parts.split("\\\\", 1)
                """,
                'system_parts = system_parts.split("\\\\", 1)',
                'system_parts = system_parts.split("\\\\", 1) + "x"',
                (
                    """
user_parts = user.split("\\\\", 1)
system_parts = system_parts.split("\\\\", 1) + "x"
                    """[:-4],
                    True,
                ),
            ),
            # - `r"..."`
            (
                """
user_parts = user.split(r"\\\\", 1)
system_parts = system_parts.split(r"\\\\", 1)
                """,
                "system_parts = system_parts.split(r'\\\\', 1)",
                "system_parts = system_parts.split(r'\\\\', 1) + 'x'",
                (
                    """
user_parts = user.split(r"\\\\", 1)
system_parts = system_parts.split(r"\\\\", 1)
                    """[:-4],
                    False,
                ),
            ),
        )
    )
    def test_apply_single_patch(
        self,
        content: str,
        find: str,
        replace: str,
        expected_output: Tuple[str, bool],
    ):
        """Unit test for apply_single_patch."""
        pair = Pair(find=find, replace=replace)
        output = self.writer._apply_single_patch(content, pair)
        logging.debug(output)
        logging.debug(expected_output)
        self.assertEqual(output, expected_output)

    @parameterized.expand(
        (
            (
                # Inputs.
                {
                    # FILE_DOES_NOT_EXIST: None,  # No need to write.
                    FILE_NO_CHANGES: """
Find Start
  find
Find End
                    """,
                    FILE_WITH_CHANGES: """
Find Start
  find
Find End

Find Start
  find1
Find End
                    """,
                },
                {
                    FILE_DOES_NOT_EXIST: None,
                    FILE_NO_CHANGES: (Pair(find="hello", replace="world"),),
                    FILE_WITH_CHANGES: (
                        # Inconsistent.
                        Pair(find=" Find Start ", replace="FIND START"),
                        Pair(find=" Find Start ", replace="SHOULD NOT BE USED AT ALL"),
                        # Duplicate.
                        Pair(find=" Find End", replace="FIND END"),
                        Pair(find=" Find End", replace="FIND END"),
                    ),
                },
                # Outputs.
                {
                    FILE_DOES_NOT_EXIST: None,
                    FILE_NO_CHANGES: False,
                    FILE_WITH_CHANGES: True,
                },
                {
                    FILE_DOES_NOT_EXIST: None,
                    FILE_NO_CHANGES: """
Find Start
  find
Find End
                    """,
                    FILE_WITH_CHANGES: """
FIND START
  find
FIND END

FIND START
  find1
FIND END
                    """,
                },
            ),
        )
    )
    def test_run(
        self,
        files: Dict[str, str],
        pairs: Dict[str, Sequence[Pair]],
        expected_success: Dict[str, bool],
        expected_output_files: Dict[str, str],
    ):
        """Unit test for patch."""

        def _rekey(root_dir, file_to_any):
            """Rekey a dict."""
            return {
                os.path.join(root_dir, key): value for key, value in file_to_any.items()
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            for file, content in files.items():
                tmp_file = os.path.join(temp_dir, file)
                utils.export_file(tmp_file, content)

            # Output.
            success = self.writer.run(_rekey(temp_dir, pairs))
            self.assertEqual(success, _rekey(temp_dir, expected_success))

            expected_feedback = (
                # pylint: disable=line-too-long
                f"[Feedback Start]File to patch doesn't exist: `{os.path.join(temp_dir, FILE_DOES_NOT_EXIST)}`.[Feedback End]\n"
                f"[Feedback Start]Find blocks are not found at all for `{os.path.join(temp_dir, FILE_NO_CHANGES)}`: For all find blocks count = 1.[Feedback End]"
                # pylint: enable=line-too-long
            )
            self.assertEqual(
                self.writer.collect_feedback(reset=False), expected_feedback
            )
            self.assertEqual(
                self.writer.collect_feedback(reset=True), expected_feedback
            )
            self.assertIsNone(self.writer.collect_feedback())
            self.assertIsNone(self.writer.collect_feedback())

            # Side effect.
            output_files = {}
            for file in success:
                if success[file] is None:
                    output_files[file] = None
                else:
                    output_files[file] = utils.load_file(file)
            self.assertEqual(output_files, _rekey(temp_dir, expected_output_files))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    unittest.main()
