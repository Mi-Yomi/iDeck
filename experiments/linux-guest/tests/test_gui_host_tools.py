"""Portable extracted-tool invocation, without running fixture executables."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from gui_host_tools import command


class PortableHostTools(unittest.TestCase):
    def test_pinned_loader_library_pair_and_unmodified_arguments(self):
        with tempfile.TemporaryDirectory(prefix='space in path ') as tmp:
            host=Path(tmp)/'host';lib=host/'usr/lib/x86_64-linux-gnu';lib.mkdir(parents=True)
            loader=lib/'ld-linux-x86-64.so.2';loader.write_bytes(b'fixture')
            tool=host/'usr/bin/tool';tool.parent.mkdir();tool.write_bytes(b'fixture')
            args=[tool,'-d','path with spaces']
            self.assertEqual(command(host,args),[str(loader),'--library-path',str(lib),str(tool),'-d','path with spaces'])
            self.assertEqual(args[0],tool)

    def test_missing_or_external_tool_and_loader_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);host=root/'host';lib=host/'usr/lib/x86_64-linux-gnu';lib.mkdir(parents=True)
            external=root/'outside';external.write_bytes(b'fixture')
            tool=host/'tool';tool.write_bytes(b'fixture')
            with self.assertRaises(ValueError):command(host,[tool])
            loader=lib/'ld-linux-x86-64.so.2';loader.write_bytes(b'fixture')
            with self.assertRaises(ValueError):command(host,[external])
            tool.unlink();tool.symlink_to(external)
            with self.assertRaises(ValueError):command(host,[tool])
            loader.unlink();loader.symlink_to(external)
            with self.assertRaises(ValueError):command(host,[tool])
