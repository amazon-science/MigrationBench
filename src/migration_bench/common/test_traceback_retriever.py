import unittest
from migration_bench.common.traceback_retriever import (
    TracebackFileExtractor,
)  # Assuming the class is in traceback_file_extractor.py


class TestTracebackFileExtractor(unittest.TestCase):
    def setUp(self):
        """Set up common test variables."""
        self.root_dir = "root_dir"
        self.extractor = TracebackFileExtractor(self.root_dir)

    def test_extract_files_single_match(self):
        """Test extracting files when there is one match."""
        log = """
        Traceback (most recent call last):
          File "/root_dir/project/module.py", line 10, in <module>
            main()
        """
        expected = ["/root_dir/project/module.py"]
        self.assertEqual(self.extractor.extract_files(log), expected)

    def test_extract_files_multiple_matches(self):
        """Test extracting files when there are multiple matches."""
        log = """
        Traceback (most recent call last):
          File "/root_dir/project/module.py", line 10, in <module>
            main()
          File "/root_dir/project/main.py", line 25, in main
            func()
        """
        expected = ["/root_dir/project/module.py", "/root_dir/project/main.py"]
        self.assertEqual(self.extractor.extract_files(log), expected)

    def test_extract_files_no_match(self):
        """Test extracting files when there are no matches."""
        log = """
        Traceback (most recent call last):
          File "/other_dir/lib/utils.py", line 10, in <module>
            main()
        """
        expected = []
        self.assertEqual(self.extractor.extract_files(log), expected)

    def test_extract_files_partial_match(self):
        """Test extracting files when some lines contain matches and others do not."""
        log = """
        Traceback (most recent call last):
          File "/root_dir/project/module.py", line 10, in <module>
            main()
          File "/other_dir/lib/utils.py", line 25, in func
            raise ValueError("An error occurred")
        """
        expected = ["/root_dir/project/module.py"]
        self.assertEqual(self.extractor.extract_files(log), expected)

    def test_extract_files_empty_log(self):
        """Test extracting files from an empty log."""
        log = ""
        expected = []
        self.assertEqual(self.extractor.extract_files(log), expected)

    def test_extract_files_full_match(self):
        """Test extracting files when fully match."""
        log = """
        Traceback (most recent call last):
          File "/root_dir", line 10, in <module>
            main()
        """
        expected = ["/root_dir"]
        self.assertEqual(self.extractor.extract_files(log), expected)


if __name__ == "__main__":
    unittest.main()
