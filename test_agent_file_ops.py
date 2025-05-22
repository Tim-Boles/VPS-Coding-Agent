import unittest
from pathlib import Path
import shutil
import sys
import os

# Add the parent directory of 'agent.py' to the Python path
# This assumes 'agent.py' is in the root of the repository where the tests are run from.
# If agent.py is in a subdirectory, this might need adjustment.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

try:
    import agent
    from agent import read_text_file, write_text_file
except ImportError as e:
    print(f"Failed to import agent module or its functions: {e}")
    print("Make sure agent.py is in the same directory or PYTHONPATH is set correctly.")
    # To help diagnose, let's see current sys.path and cwd
    print(f"Current sys.path: {sys.path}")
    print(f"Current working directory: {os.getcwd()}")
    # List files in current directory to see if agent.py is there
    print(f"Files in CWD: {os.listdir('.')}")
    # If agent.py is in a subdir like 'src', then one might do:
    # sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
    # Or ensure the test runner (e.g. VSCode) is configured to run from the project root.
    # For the purpose of this tool, assuming agent.py is at the root.
    raise

class TestAgentFileOps(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # This check is to ensure agent and its AGENT_FILES_WORKSPACE are loaded
        # before we try to patch it.
        if 'agent' not in sys.modules:
            raise unittest.SkipTest("Agent module not loaded, skipping tests.")
        cls.original_workspace = agent.AGENT_FILES_WORKSPACE
        cls.test_workspace = Path("agent_files_test_workspace_unique_read").resolve()
        # Set the workspace for the agent module globally for the duration of these tests
        agent.AGENT_FILES_WORKSPACE = cls.test_workspace

    @classmethod
    def tearDownClass(cls):
        # Restore the original workspace path in the agent module
        agent.AGENT_FILES_WORKSPACE = cls.original_workspace
        if cls.test_workspace.exists():
            shutil.rmtree(cls.test_workspace)

    def setUp(self):
        # Ensure the test workspace directory exists and is clean for each test
        if self.test_workspace.exists():
            shutil.rmtree(self.test_workspace)
        self.test_workspace.mkdir(parents=True, exist_ok=True)

        # Populate with files using the agent's write_text_file for consistency
        # This implicitly tests _resolve_safe_path for writing as well.
        # Note: write_text_file returns a success/error message, not content.
        # We assume it works correctly based on its own tests or prior validation.

        # Root level files
        write_text_file("file1.txt", "This is file1 in root")
        write_text_file("common_name.txt", "Root common") # For shallowest check

        # Files in 'data' directory
        write_text_file("data/file2.txt", "This is file2 in data")
        write_text_file("data/common_name.txt", "Data common")

        # Files in 'another_dir' directory
        write_text_file("another_dir/common_name.txt", "This is common_name in another_dir")

        # Files in 'data/deeper' directory
        write_text_file("data/deeper/common_name.txt", "This is common_name in data/deeper")

    def tearDown(self):
        # The test_workspace is cleaned up in setUp for each test,
        # and fully removed in tearDownClass.
        # If individual tests create specific files that need cleanup beyond this,
        # they can do so here. For now, setUp handles general cleanliness.
        pass

    def test_read_file_by_name_in_root(self):
        content = read_text_file("file1.txt")
        self.assertEqual(content, "This is file1 in root")

    def test_read_file_by_relative_path(self):
        content = read_text_file("data/file2.txt")
        self.assertEqual(content, "This is file2 in data")

    def test_read_file_by_name_ambiguous_shallowest_first(self):
        # common_name.txt exists in root, data/, and another_dir/
        # _resolve_safe_path should pick the one in root (shallowest)
        content = read_text_file("common_name.txt")
        self.assertEqual(content, "Root common")

    def test_read_file_by_name_specific_deeper_path(self):
        content = read_text_file("data/deeper/common_name.txt")
        self.assertEqual(content, "This is common_name in data/deeper")

    def test_read_non_existent_file_by_name(self):
        result = read_text_file("nonexistentfile.txt")
        self.assertIn("Error: File not found", result)

    def test_read_non_existent_file_by_path(self):
        result = read_text_file("data/nonexistentfile.txt")
        self.assertIn("Error: File not found", result)

    def test_read_file_outside_workspace_attempt_simple_traverse(self):
        # This path will be resolved to AGENT_FILES_WORKSPACE/../../../etc/passwd
        # The security check in _resolve_safe_path should prevent it.
        result = read_text_file("../../../etc/passwd")
        self.assertIn("Error: Invalid or disallowed file path", result)

    def test_read_file_outside_workspace_attempt_absolute(self):
        # Absolute paths are not explicitly checked before _resolve_safe_path,
        # but _resolve_safe_path prepends AGENT_FILES_WORKSPACE, then resolves.
        # (base_path / relative_filepath).resolve()
        # If relative_filepath is absolute like /etc/passwd, base_path / "/etc/passwd" becomes "/etc/passwd".
        # Then the security check (base_path not in resolved_path.parents) should catch it.
        result = read_text_file("/etc/passwd")
        self.assertIn("Error: Invalid or disallowed file path", result)
        
    def test_read_directory_instead_of_file(self):
        # Attempt to read a directory as if it were a file
        # 'data' is a directory created in setUp
        result = read_text_file("data")
        # The exact error message might depend on OS and Python version,
        # but it should indicate it's not a file or not found as a file.
        # Current `read_text_file` checks `safe_path.is_file()`.
        self.assertIn("Error: File not found or is not a regular file", result)


if __name__ == '__main__':
    # This allows running the tests directly from the command line
    unittest.main()
