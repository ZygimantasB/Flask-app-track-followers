"""
Test file to verify the fixes made to the GitHub followers tracker.
Run with: python test_fixes.py
"""
import unittest
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestUsernameValidation(unittest.TestCase):
    """Test username validation functions."""

    def test_sanitize_username_valid(self):
        """Test that valid usernames pass sanitization."""
        from github_api import _sanitize_username

        # Valid usernames
        self.assertEqual(_sanitize_username("octocat"), "octocat")
        self.assertEqual(_sanitize_username("user-name"), "user-name")
        self.assertEqual(_sanitize_username("User123"), "User123")
        self.assertEqual(_sanitize_username("a"), "a")

    def test_sanitize_username_invalid(self):
        """Test that invalid usernames are rejected."""
        from github_api import _sanitize_username

        # Invalid usernames
        self.assertIsNone(_sanitize_username(""))
        self.assertIsNone(_sanitize_username(None))
        self.assertIsNone(_sanitize_username("-invalid"))  # starts with hyphen
        self.assertIsNone(_sanitize_username("a" * 40))  # too long
        self.assertIsNone(_sanitize_username(123))  # not a string

    def test_sanitize_username_removes_special_chars(self):
        """Test that special characters are removed."""
        from github_api import _sanitize_username

        # Characters that should be stripped
        self.assertEqual(_sanitize_username("user\"injection"), "userinjection")
        self.assertEqual(_sanitize_username("user'name"), "username")
        self.assertEqual(_sanitize_username("user<script>"), "userscript")

    def test_app_username_validation(self):
        """Test the Flask app username validation."""
        from app import _is_valid_github_username

        # Valid
        self.assertTrue(_is_valid_github_username("octocat"))
        self.assertTrue(_is_valid_github_username("user-name"))
        self.assertTrue(_is_valid_github_username("User123"))

        # Invalid
        self.assertFalse(_is_valid_github_username(""))
        self.assertFalse(_is_valid_github_username(None))
        self.assertFalse(_is_valid_github_username("-invalid"))
        self.assertFalse(_is_valid_github_username("a" * 40))
        self.assertFalse(_is_valid_github_username("user name"))  # space
        self.assertFalse(_is_valid_github_username("user@name"))  # special char


class TestDataManager(unittest.TestCase):
    """Test data manager functions."""

    def test_normalize_username(self):
        """Test username normalization."""
        from data_manager import _normalize_username

        self.assertEqual(_normalize_username("  OctoCat  "), "octocat")
        self.assertEqual(_normalize_username("USER"), "user")
        self.assertEqual(_normalize_username(""), "")

    def test_load_ignore_list_deduplication(self):
        """Test that ignore list deduplication works."""
        from data_manager import load_ignore_list, save_ignore_list, IGNORE_LIST_FILE
        import tempfile
        import os

        # Create a test file with duplicates
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("user1\n")
            f.write("USER1\n")  # duplicate (case-insensitive)
            f.write("user2\n")
            f.write("  user2  \n")  # duplicate with whitespace
            temp_path = f.name

        # Temporarily swap the file path
        original_file = IGNORE_LIST_FILE
        import data_manager
        data_manager.IGNORE_LIST_FILE = temp_path

        try:
            ignore_list = load_ignore_list()
            # Should be deduplicated
            self.assertEqual(len(ignore_list), 2)
            self.assertIn("user1", ignore_list)
            self.assertIn("user2", ignore_list)
        finally:
            data_manager.IGNORE_LIST_FILE = original_file
            os.unlink(temp_path)


class TestUtils(unittest.TestCase):
    """Test utility functions."""

    def test_chunks(self):
        """Test the chunks generator."""
        from utils import chunks

        # Test basic chunking
        result = list(chunks([1, 2, 3, 4, 5], 2))
        self.assertEqual(result, [[1, 2], [3, 4], [5]])

        # Test with exact fit
        result = list(chunks([1, 2, 3, 4], 2))
        self.assertEqual(result, [[1, 2], [3, 4]])

        # Test with empty list
        result = list(chunks([], 2))
        self.assertEqual(result, [])

        # Test invalid chunk size
        with self.assertRaises(ValueError):
            list(chunks([1, 2], 0))

        with self.assertRaises(ValueError):
            list(chunks([1, 2], -1))


class TestThrottling(unittest.TestCase):
    """Test request throttling."""

    def test_throttle_thread_safety(self):
        """Test that throttling works correctly with multiple threads."""
        from github_api import throttle_requests, MIN_REQUEST_INTERVAL
        import threading
        import time

        results = []
        lock = threading.Lock()

        def make_request():
            start = time.time()
            throttle_requests()
            end = time.time()
            with lock:
                results.append(end - start)

        # Run multiple threads
        threads = [threading.Thread(target=make_request) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # At least some requests should have been delayed
        # (this is a basic sanity check)
        self.assertEqual(len(results), 5)


if __name__ == '__main__':
    # Run with verbosity
    unittest.main(verbosity=2)
