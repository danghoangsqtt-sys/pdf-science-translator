from __future__ import annotations

import unittest

from pdf2zh.rules import drawing_shape, figure_labels, occluded_glyphs, visible_words

FIGURE = (0, 0, 400, 300)


def word(x0, y0, x1, y1, text):
    return (x0, y0, x1, y1, text, 0, 0, 0)


class FigureLabelTests(unittest.TestCase):
    def test_label_in_a_box_is_one_centred_unit_and_ticks_stay_source(self):
        words = [
            word(20, 20, 60, 28, "Training"),
            word(62, 20, 80, 28, "Data"),
            word(20, 200, 26, 208, "0.5"),
            word(40, 200, 46, 208, "x"),
            word(300, 200, 320, 208, "MSE"),
        ]
        shapes = [(10, 10, 100, 40, True)]
        labels = figure_labels(words, FIGURE, shapes)
        self.assertEqual([label.text for label in labels], ["Training Data"])
        label = labels[0]
        self.assertTrue(label.enclosed)
        # Room is the box minus a small inset, never less than the label.
        self.assertLess(label.bounds[0], 20)
        self.assertGreater(label.bounds[2], 80)
        self.assertLessEqual(label.bounds[2], 100)

    def test_stacked_lines_in_one_box_form_one_label(self):
        words = [
            word(30, 20, 70, 28, "Population"),
            word(28, 29, 74, 37, "Initialization"),
        ]
        labels = figure_labels(words, FIGURE, [(20, 15, 85, 42, True)])
        self.assertEqual([label.text for label in labels], ["Population Initialization"])

    def test_labels_in_separate_boxes_do_not_merge(self):
        words = [
            word(20, 20, 50, 28, "Model"),
            word(20, 31, 50, 39, "Crossover"),
        ]
        shapes = [(15, 17, 60, 29.5, True), (15, 29.5, 60, 42, True)]
        labels = figure_labels(words, FIGURE, shapes)
        self.assertEqual(sorted(label.text for label in labels), ["Crossover", "Model"])

    def test_box_holding_another_word_is_not_lent_to_the_label(self):
        words = [
            word(20, 20, 60, 28, "Encoder"),
            word(20, 50, 60, 58, "Decoder"),
        ]
        labels = figure_labels(words, FIGURE, [(10, 10, 100, 70, True)])
        self.assertEqual(len(labels), 2)
        self.assertFalse(any(label.enclosed for label in labels))
        for label in labels:
            # Widened only into free space, never into the other label.
            self.assertLess(label.bounds[3] - label.bounds[1], 12)

    def test_overprinted_glyph_leaves_the_label_untranslated(self):
        words = [
            word(184, 176, 205, 183, "Fitness"),
            word(193, 175, 196, 180, "Z"),
        ]
        self.assertEqual(figure_labels(words, (0, 0, 400, 300), []), [])

    def test_name_line_above_a_description_stays_source(self):
        words = [
            word(20, 20, 60, 28, "Word2vec"),
            word(62, 20, 90, 28, "(NPLM)、NLPS"),
            word(20, 29, 50, 37, "Static"),
            word(52, 29, 70, 37, "word"),
            word(72, 29, 110, 37, "representations"),
        ]
        labels = figure_labels(words, FIGURE, [(10, 10, 130, 45, True)])
        self.assertEqual([label.text for label in labels], ["Static word representations"])
        label = labels[0]
        # The box still holds the name line, so the translation keeps to its
        # own row instead of spreading over it.
        self.assertFalse(label.enclosed)
        self.assertGreaterEqual(label.bounds[1], 28)

    def test_words_outside_the_figure_are_ignored(self):
        words = [word(500, 20, 540, 28, "Caption")]
        self.assertEqual(figure_labels(words, FIGURE, []), [])

    def test_diamond_lends_only_its_inscribed_box(self):
        diamond = {
            "rect": (0, 0, 80, 40),
            "type": "s",
            "closePath": True,
            "items": [
                ("l", (40, 0), (80, 20)),
                ("l", (80, 20), (40, 40)),
                ("l", (40, 40), (0, 20)),
                ("l", (0, 20), (40, 0)),
            ],
        }
        shape = drawing_shape(diamond)
        self.assertIsNotNone(shape)
        self.assertFalse(shape[4])
        labels = figure_labels(
            [word(30, 16, 50, 24, "Terminate")], FIGURE, [shape]
        )
        self.assertEqual(len(labels), 1)
        # The diamond's corners are not available to the translation.
        self.assertGreater(labels[0].bounds[0], 10)
        self.assertLess(labels[0].bounds[2], 70)

    def test_open_connector_is_not_a_shape(self):
        connector = {
            "rect": (0, 0, 200, 100),
            "type": "s",
            "closePath": False,
            "items": [("l", (0, 0), (200, 0)), ("l", (200, 0), (200, 100))],
        }
        self.assertIsNone(drawing_shape(connector))
        box = {"rect": (0, 0, 50, 20), "type": "s", "items": [("re", (0, 0, 50, 20))]}
        self.assertEqual(drawing_shape(box), (0.0, 0.0, 50.0, 20.0, True))

    def test_decision_branch_words_are_translated(self):
        words = [word(300, 100, 312, 107, "Yes"), word(20, 100, 26, 107, "x")]
        self.assertEqual([label.text for label in figure_labels(words, FIGURE, [])], ["Yes"])

    def test_left_aligned_list_lines_are_separate_left_labels(self):
        words = [
            word(20, 100, 50, 108, "Statistical"),
            word(52, 100, 80, 108, "methods"),
            word(20, 110, 55, 118, "Probability"),
            word(57, 110, 90, 118, "estimation"),
        ]
        labels = figure_labels(words, FIGURE, [])
        self.assertEqual(
            [label.text for label in labels],
            ["Statistical methods", "Probability estimation"],
        )
        for label in labels:
            self.assertFalse(label.centred)
            self.assertEqual(label.bounds[0], 20)

    def test_centred_wrapped_label_outside_a_shape_stays_one_label(self):
        words = [word(213, 100, 230, 108, "Best"), word(205, 110, 238, 118, "Individual")]
        labels = figure_labels(words, FIGURE, [])
        self.assertEqual([label.text for label in labels], ["Best Individual"])
        self.assertTrue(labels[0].centred)


class OccludedGlyphTests(unittest.TestCase):
    @staticmethod
    def trace(seqno, text, x0, y0, width=4.0):
        chars = [
            (ord(ch), 0, (x0 + i * width, y0 + 6), (x0 + i * width, y0, x0 + (i + 1) * width, y0 + 8))
            for i, ch in enumerate(text)
        ]
        return {"seqno": seqno, "type": 0, "chars": chars}

    @staticmethod
    def fill(seqno, rect, fill=(1.0, 1.0, 1.0)):
        return {
            "seqno": seqno,
            "type": "f",
            "fill": fill,
            "fill_opacity": 1.0,
            "rect": rect,
            "items": [("re", rect, 1)],
        }

    def test_text_under_a_later_fill_is_hidden_and_text_on_top_is_not(self):
        traces = [self.trace(1, "Z", 50, 50), self.trace(3, "Fit", 60, 50)]
        drawings = [self.fill(2, (40, 40, 100, 70))]
        hidden = occluded_glyphs(traces, drawings)
        self.assertEqual([glyph[4] for glyph in hidden], ["Z"])
        words = [word(50, 50, 54, 58, "Z"), word(60, 50, 72, 58, "Fit")]
        self.assertEqual([w[4] for w in visible_words(words, hidden)], ["Fit"])

    def test_glyph_at_a_shape_edge_stays_visible(self):
        traces = [self.trace(1, "No", 98, 50)]
        drawings = [self.fill(2, (40, 40, 100, 70))]
        self.assertEqual(occluded_glyphs(traces, drawings), [])

    def test_glyph_outside_a_diamond_but_inside_its_box_stays_visible(self):
        diamond = {
            "seqno": 2,
            "type": "f",
            "fill": (1.0, 1.0, 1.0),
            "rect": (0, 0, 80, 40),
            "items": [
                ("l", (40, 0), (80, 20)),
                ("l", (80, 20), (40, 40)),
                ("l", (40, 40), (0, 20)),
                ("l", (0, 20), (40, 0)),
            ],
        }
        corner = self.trace(1, "A", 2, 2)
        centre = self.trace(1, "B", 38, 16)
        hidden = occluded_glyphs([corner, centre], [diamond])
        self.assertEqual([glyph[4] for glyph in hidden], ["B"])

    def test_translucent_fill_hides_nothing(self):
        drawings = [dict(self.fill(2, (40, 40, 100, 70)), fill_opacity=0.3)]
        self.assertEqual(occluded_glyphs([self.trace(1, "Z", 50, 50)], drawings), [])

    def test_converter_drops_only_the_first_matching_copy(self):
        from types import SimpleNamespace

        from pdf2zh.converter import take_hidden_glyph

        def glyph():
            return SimpleNamespace(x0=50.0, x1=54.0, y0=50.0, y1=58.0, get_text=lambda: "T")

        hidden = [(50.0, 49.0, 54.0, 59.0, "T")]
        self.assertTrue(take_hidden_glyph(glyph(), hidden))
        # The visible duplicate drawn later at the same spot is kept.
        self.assertFalse(take_hidden_glyph(glyph(), hidden))


class FigureLabelPlacementTests(unittest.TestCase):
    def test_one_line_translation_is_centred_in_a_two_line_box(self):
        from pdf2zh.converter import vertical_centre_shift

        # One line whose ink spans baseline-2 .. baseline+8, sitting on the
        # first source line's baseline at the top of a 0..40 box.
        shift = vertical_centre_shift(30.0, {0: (-2.0, 8.0)}, [0.0], 0.0, 40.0)
        self.assertAlmostEqual(30.0 + shift - 2.0 + 30.0 + shift + 8.0, 40.0)


if __name__ == "__main__":
    unittest.main()
