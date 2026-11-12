"""One-line headings may use the free width of their column (BUG-022).

arXiv 2307.15299v5 sets "III. PROPOSED APPROACH" in small caps, so the source
line is narrow; "III. ĐỀ XUẤT PHƯƠNG PHÁP TIẾN HÀNH" fitted into that width
came out at 6.06 pt instead of 9.96 pt while the column beside it was empty.
Geometry below is page 3's left column (x 49-301) as pdfminer reports it.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from pdf2zh.converter import glyph_line_boxes, single_line_room

COLUMN_ABOVE = (49.0, 640.0, 301.0, 760.0)
COLUMN_BELOW = (49.0, 480.0, 301.0, 618.0)
SIZE = 9.96


class SingleLineRoomTests(unittest.TestCase):
    def test_a_centred_section_heading_takes_the_column_and_stays_centred(self):
        heading = (113.0, 622.0, 237.0, 632.0)  # centre 175 = column centre
        room = single_line_room(heading, [COLUMN_ABOVE, COLUMN_BELOW],
                                [heading, COLUMN_ABOVE, COLUMN_BELOW], SIZE)
        self.assertEqual(room, (49.0, 301.0, True))

    def test_a_left_aligned_subsection_heading_widens_to_the_right(self):
        heading = (49.0, 622.0, 150.0, 632.0)  # "C. Experimental Setups"
        room = single_line_room(heading, [COLUMN_ABOVE, COLUMN_BELOW],
                                [heading, COLUMN_ABOVE, COLUMN_BELOW], SIZE)
        self.assertEqual(room, (49.0, 301.0, False))

    def test_text_sharing_the_line_keeps_the_heading_in_its_own_width(self):
        heading = (113.0, 622.0, 237.0, 632.0)
        neighbour = (250.0, 621.0, 300.0, 631.0)  # e.g. a margin note
        room = single_line_room(heading, [COLUMN_ABOVE, COLUMN_BELOW],
                                [heading, neighbour, COLUMN_ABOVE, COLUMN_BELOW], SIZE)
        self.assertIsNone(room)

    def test_an_off_centre_line_inside_the_column_is_left_alone(self):
        """A right-hand fragment is neither a centred nor a left heading."""
        fragment = (200.0, 622.0, 290.0, 632.0)
        self.assertIsNone(
            single_line_room(fragment, [COLUMN_ABOVE], [fragment, COLUMN_ABOVE], SIZE)
        )

    def test_a_line_with_no_column_around_it_is_left_alone(self):
        heading = (113.0, 622.0, 237.0, 632.0)
        far_column = (49.0, 100.0, 301.0, 300.0)
        self.assertIsNone(single_line_room(heading, [far_column], [heading, far_column], SIZE))

    def test_the_other_column_is_never_borrowed(self):
        heading = (330.0, 622.0, 450.0, 632.0)  # right column, x 313-540
        right_column = (313.0, 640.0, 540.0, 760.0)
        room = single_line_room(heading, [COLUMN_ABOVE, right_column],
                                [heading, COLUMN_ABOVE, right_column], SIZE)
        self.assertIsNone(room)  # neither left-aligned nor centred in 313-540


    def test_a_table_caption_takes_the_column_of_the_prose_above_its_table(self):
        """"BEST SET OF HYPERPARAMETERS FOR TRANSFORMER" sits 60 pt (7.5 em)
        below the nearest prose paragraph, with the table in between."""
        caption = (93.5, 726.5, 279.1, 734.4)
        prose_above = (72.0, 572.0, 301.0, 666.0)
        room = single_line_room(caption, [prose_above], [caption, prose_above], 7.97)
        self.assertEqual(room, (72.0, 301.0, True))

    def test_protected_lines_in_the_other_column_do_not_block(self):
        """Page 6: the References heading shares its band only with entries in
        the right-hand column, once those are measured line by line."""
        heading = (158.4, 474.3, 214.2, 484.3)
        prose_above = (72.0, 494.0, 301.0, 564.0)
        right_column_entry = (313.0, 476.0, 540.0, 484.0)
        room = single_line_room(heading, [prose_above],
                                [prose_above, right_column_entry], 7.97)
        self.assertEqual(room, (72.0, 301.0, True))


class GlyphLineBoxesTests(unittest.TestCase):
    def test_a_group_in_two_columns_splits_per_line_and_column(self):
        glyphs = [
            SimpleNamespace(x0=x, x1=x + 4, y0=y, y1=y + 8, size=8.0)
            for y in (700.0, 690.0)
            for x in (72.0, 76.0, 80.0, 313.0, 317.0)
        ]
        self.assertEqual(
            glyph_line_boxes(glyphs),
            [(72.0, 690.0, 84.0, 698.0), (313.0, 690.0, 321.0, 698.0),
             (72.0, 700.0, 84.0, 708.0), (313.0, 700.0, 321.0, 708.0)],
        )


if __name__ == "__main__":
    unittest.main()
