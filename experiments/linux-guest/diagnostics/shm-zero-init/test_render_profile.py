import ast
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('tested_profile', HERE / 'render-tested-profile.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        guest = HERE.parents[1] / 'guest' / 'steam'
        self.launcher = (guest / 'ideck-steam').read_bytes()
        self.helper = (guest / 'namespace-check.py').read_bytes()
        self.library_fixture = b'not an executable; renderer does not load it'

    def test_refuses_changed_launcher(self):
        with self.assertRaisesRegex(ValueError, 'launcher'):
            profile.render(self.launcher + b'# changed\n', self.helper, self.library_fixture)

    def test_refuses_changed_namespace_helper(self):
        with self.assertRaisesRegex(ValueError, 'namespace_helper'):
            profile.render(self.launcher, self.helper + b'# changed\n', self.library_fixture)

    def test_refuses_unpinned_library(self):
        with self.assertRaisesRegex(ValueError, 'zero_library'):
            profile.render(self.launcher, self.helper, self.library_fixture)

    def test_render_matches_actual_run27_scripts_and_preserves_guards(self):
        # Only the inert library fixture hash is substituted. The two source
        # pins and expected outputs are those of the actual ARM64 run27.
        with patch.dict(profile.PINS, zero_library=hashlib.sha256(self.library_fixture).hexdigest()):
            result = profile.render(self.launcher, self.helper, self.library_fixture)
        self.assertEqual({name: hashlib.sha256(data).hexdigest() for name, data in result.items()}, {
            'ideck-steam-desktop-v11': 'e864839b710ee1db8ddcd3c86f82d5db3484ee3fdeadec904c8b8491e62f4f1d',
            'namespace-zero-watchdog-500m.py': 'dd3c87333e166b7d31673a81adbc4cb9ef574203d1d9d1c25c56251069271e72',
        })
        def safety_functions(source):
            return {n.name: ast.dump(n, include_attributes=False)
                    for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name != 'launch'}
        self.assertEqual(safety_functions(self.helper), safety_functions(result['namespace-zero-watchdog-500m.py']))


if __name__ == '__main__':
    unittest.main()
