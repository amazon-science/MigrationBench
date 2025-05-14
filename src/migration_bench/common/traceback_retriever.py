import re
from typing import List


class TracebackFileExtractor:
    def __init__(self, root_dir: str):
        """
        Initialize the extractor with the root directory to filter files.

        :param root_dir: The substring used to identify relevant files in the traceback logs.
        """
        self.root_dir = root_dir

    def extract_files(self, traceback_log: str) -> List[str]:
        """
        Extract file names containing the specified root_dir from a traceback log.

        :param traceback_log: A string containing the traceback log.
        :return: A list of file paths containing the specified root_dir.
        """
        # Regular expression to match file paths with the specified root_dir as a standalone segment
        file_pattern = re.compile(
            r'File "([^"]*?{0}[^"]*)"'.format(re.escape(self.root_dir))
        )
        return file_pattern.findall(traceback_log)


# Example usage
if __name__ == "__main__":
    sample_log = """
Traceback (most recent call last):
  File "/home/ubuntu/Python2Projects/python-ntlm/python3_intermediate/ntlm_examples/test_ntlmauth.py", line 12, in <module>
    from ntlm import HTTPNtlmAuthHandler
ModuleNotFoundError: No module named 'ntlm'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/ubuntu/Python2Projects/python-ntlm/python3_intermediate/ntlm_examples/test_ntlmauth.py", line 19, in <module>
    from ntlm import HTTPNtlmAuthHandler
  File "/home/ubuntu/Python2Projects/python-ntlm/python3_intermediate/ntlm/HTTPNtlmAuthHandler.py", line 16, in <module>
    from urllib import addinfourl
ImportError: cannot import name 'addinfourl' from 'urllib' (/opt/conda/lib/python3.10/urllib/__init__.py)
    """
    extractor = TracebackFileExtractor("/home/ubuntu/Python2Projects/python-ntlm")
    files = extractor.extract_files(sample_log)
    print("Extracted files:", files)
