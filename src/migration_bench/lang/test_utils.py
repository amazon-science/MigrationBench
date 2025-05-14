"""Unit test for E2E."""

import logging
import os
import shutil
import tempfile
import unittest

from self_debug.common import utils


C_SHARP_PROJECT = "mvc/Modernize.Web/Modernize.Web.Mvc/Modernize.Web.Mvc.csproj"


class TestUtils(unittest.TestCase):
    """Unit test for E2E."""

    def setUp(self):
        super().setUp()
        self.temp_dir = None

    def tearDown(self):
        """Clean up."""
        if self.temp_dir is None:
            return

        logging.info("Removing temp dir: `%s`.", self.temp_dir)
        shutil.rmtree(self.temp_dir)

    def set_up_project(self, zip_filename: str, pwd: str = "") -> str:
        """Set up project with the given zip file."""
        self.temp_dir = tempfile.mkdtemp()
        temp_dir = self.temp_dir
        logging.info("Creating temp dir: `%s`.", temp_dir)

        if pwd:
            zip_filename = os.path.join(pwd, zip_filename)
        # Prepare the repo as a dataset: Copy zipped project.
        self.assertTrue(
            utils.run_command(["cp", zip_filename, temp_dir], shell=False)[-1]
        )

        zip_filename = os.path.basename(zip_filename)
        self.assertTrue(utils.run_command(f"cd {temp_dir}; unzip {zip_filename}")[-1])

        # Generate root dir.
        root_dir = os.path.join(temp_dir, zip_filename.replace(".zip", ""))

        logging.info("Unzip `%s`: `%s`.", zip_filename, root_dir)

        return os.path.abspath(root_dir)
