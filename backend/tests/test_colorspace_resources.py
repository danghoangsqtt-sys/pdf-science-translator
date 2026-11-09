from __future__ import annotations

import unittest

from pdfminer.psparser import LIT
from pdfminer.pdftypes import PDFStream

from pdf2zh.pdfinterp import PDFPageInterpreterEx


class ColorspaceResourceTests(unittest.TestCase):
    def test_icc_colorspace_missing_stream_is_dropped_not_crashed(self):
        """A page whose ICCBased ColorSpace resource points at damage MuPDF
        itself already reports as "object is not a stream" / "invalid ICC
        colorspace" used to crash the whole translation with KeyError: 'N'
        (stream_value() falls back to an attrs-less PDFStream rather than
        raising, and indexing ["N"] on that finds nothing). The resource is
        now treated the same as any other colour space this build cannot
        explain: dropped, not fatal."""
        interp = PDFPageInterpreterEx(None, None, None)
        interp.init_resources({"ColorSpace": {"CS0": [LIT("ICCBased"), 0]}})
        self.assertNotIn("CS0", interp.csmap)

    def test_icc_colorspace_with_valid_stream_still_resolves(self):
        interp = PDFPageInterpreterEx(None, None, None)
        icc_stream = PDFStream({"N": 3}, b"")
        interp.init_resources({"ColorSpace": {"CS0": [LIT("ICCBased"), icc_stream]}})
        self.assertEqual(interp.csmap["CS0"].ncomponents, 3)


if __name__ == "__main__":
    unittest.main()
