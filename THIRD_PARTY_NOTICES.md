# Third-party notices

PDF Translate is developed and maintained by **dhsystem**. It is a modified
version of the works below and, like them, is licensed under the GNU Affero
General Public License version 3 (see [LICENSE](LICENSE)).

## VI-Translate

This project continues from [VI-Translate](https://github.com/breslee1707/VI-Translate)
by **Lê Ngọc Gia Huy** (huyg.ai), AGPL-3.0. Carried over and since modified here:
the preservation rules and fixes in the PDF core (`backend/pdf2zh/`), the
supported CLI (`backend/scripts/translate_pdf.py`), much of the regression
suite (`backend/tests/`), the Handoff mode, the agent skill (`SKILL.md`,
`references/`) and the Android app (`frontend/android/`), whose Android port was
contributed to VI-Translate by **Lizi** ([whooslizi](https://github.com/whooslizi)).
The commit history of those parts is kept in this repository.

## PDFMathTranslate

`backend/pdf2zh/` is a preservation-focused core fork derived from
[PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate) version
1.9.11. It retains the PDF parsing, formula handling, layout detection,
rendering, and cache code, and is licensed under the GNU Affero General Public
License version 3.

## BabelDOC

The core uses [BabelDOC](https://github.com/funstory-ai/BabelDOC) version 0.2.33
for pinned layout-model and font assets. BabelDOC is licensed under the GNU
Affero General Public License version 3.

## Online translation services (legacy builds)

Builds that use Google Translate send document text to that web service. Google
does not sponsor or endorse this project, and service availability and usage
remain subject to Google's terms. The Windows offline edition sends nothing.
