"""Formulas are never rewritten by the translation model (BUG-020).

The DE paper (arXiv 2307.15299v5, page 2) states its problem as
"For objective function f: X ⊆ ℝⁿ → ℝ where X ≠ ∅ find s ∈ X s.t.
f(s) ≤ f(x) ∀x ∈ X where f(s) ≠ −∞". The brackets of f(s) were set in the
upright text font, travelled to the model as prose between a dozen formula
markers, and came back as "s, ≤ f, x" with every marker intact.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from pdf2zh.converter import attaches_to_formula, is_translatable_segment
from pdf2zh.rules import looks_like_formula_line


def glyph(x0: float, x1: float, y0: float = 600.0, size: float = 10.0):
    return SimpleNamespace(x0=x0, x1=x1, y0=y0, size=size)


class FormulaLineTests(unittest.TestCase):
    def test_the_de_problem_statement_keeps_its_source_text(self):
        # As the converter now builds it: f(s) <= f(x) is one placeholder.
        line = "For objective function {v0} : {v1} where {v2} find {v3} s.t. {v4} where {v5}"
        self.assertTrue(looks_like_formula_line(line))
        self.assertFalse(is_translatable_segment(line, set()))

    def test_the_statement_as_it_was_split_before_the_fix(self):
        line = ("For objective function {v0} : {v1} where {v2} find {v3} s.t. {v4} "
                "({v5}) {v6} ({v7}) {v8} where {v9} ({v10}) {v11}")
        self.assertTrue(looks_like_formula_line(line))

    def test_an_enumeration_of_symbols_is_a_formula_line(self):
        self.assertTrue(looks_like_formula_line("Each {v37} 1{v38} 2{v39} and {v40}"))

    def test_sentences_that_carry_formulas_are_still_translated(self):
        for sentence in (
            # From the same page: long runs of words between the formulas.
            (
                "Suppose {v12} has {v13} parameters. An {v14} - sized candidate solution "
                "population is initialized, with each candidate solution modeled as {v15}, "
                "a {v16}-parameter vector."
            ),
            (
                "Each index {v18} with {v19} 1{v20} 2{v21} represents a parameter to be "
                "manipulated approximate a solution to the objective function [21]."
            ),
            # Few formulas: a short sentence, not a formula line.
            "Let {v1} be {v2} and {v3}.",
            "where {v1} is the mean and {v2} the variance",
        ):
            with self.subTest(sentence=sentence[:30]):
                self.assertFalse(looks_like_formula_line(sentence))
                self.assertTrue(is_translatable_segment(sentence, set()))

    def test_words_must_stay_fewer_than_half_again_the_formulas(self):
        self.assertTrue(looks_like_formula_line("if {v1} then {v2} else {v3} for {v4}"))
        self.assertFalse(
            looks_like_formula_line("if a {v1} then b {v2} else c {v3} for d {v4}")
        )


class FlushBracketTests(unittest.TestCase):
    """attaches_to_formula decides whether "(" or a digit joins the formula."""

    def test_a_bracket_set_against_the_function_name_attaches(self):
        f = glyph(100.0, 104.9)
        self.assertTrue(attaches_to_formula(f, glyph(105.0, 108.9)))
        # A thin space, as math mode sets it after a comma.
        self.assertTrue(attaches_to_formula(f, glyph(106.5, 110.0)))

    def test_a_word_space_does_not_attach(self):
        """Prose such as "Factor C1 (applies...)": the bracket is spaced off."""
        subscript = glyph(100.0, 103.0, size=7.0)
        self.assertFalse(attaches_to_formula(subscript, glyph(105.5, 109.0)))

    def test_the_next_line_does_not_attach(self):
        end_of_line = glyph(300.0, 305.0, y0=600.0)
        self.assertFalse(attaches_to_formula(end_of_line, glyph(305.0, 309.0, y0=588.0)))


if __name__ == "__main__":
    unittest.main()
