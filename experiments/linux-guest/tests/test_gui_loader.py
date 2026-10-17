"""Validate the exact inventory passed to the real guest glibc audit."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from check_gui_vm import validate_loader_paths

class LoaderInventoryChecks(unittest.TestCase):
    def test_real_coreutils_bracket_executable_is_valid(self):
        paths=['/usr/bin/[','/usr/bin/test','/usr/bin/g++']
        self.assertEqual(validate_loader_paths(paths),paths)

    def test_invalid_or_repeated_inventory_is_rejected(self):
        for paths in ([],['bin/sh'],['/usr/../bin/sh'],['/usr/bin/a\nexit'],
                      ['/usr/bin/a\0b'],[True],['/bin/sh','/bin/sh'],['/bin/a']*1025):
            with self.subTest(paths=str(paths)[:80]),self.assertRaises(ValueError):
                validate_loader_paths(paths)
