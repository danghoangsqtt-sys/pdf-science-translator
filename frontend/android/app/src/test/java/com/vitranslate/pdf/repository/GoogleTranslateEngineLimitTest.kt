package com.vitranslate.pdf.repository

import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class GoogleTranslateEngineLimitTest {
    @Test
    fun acceptsTheExactRequestBoundary() {
        requireGoogleQueryFits("a".repeat(MAX_GOOGLE_QUERY_CHARACTERS - 1))
        requireGoogleQueryFits("a".repeat(MAX_GOOGLE_QUERY_CHARACTERS))
    }

    @Test
    fun rejectsTheWholeSegmentInsteadOfDroppingItsTail() {
        val source = "a".repeat(MAX_GOOGLE_QUERY_CHARACTERS) + "Ω"
        val error = assertThrows(SegmentTooLongException::class.java) {
            requireGoogleQueryFits(source)
        }
        assertTrue(error.message?.contains("5001") == true)
    }

    @Test
    fun countsUtf16ExactlyLikeThePreviousTakeOperation() {
        val source = "a".repeat(MAX_GOOGLE_QUERY_CHARACTERS - 1) + "😀"
        assertThrows(SegmentTooLongException::class.java) {
            requireGoogleQueryFits(source)
        }
    }
}