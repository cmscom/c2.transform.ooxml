# c2.transform.ooxml

[日本語](README-ja.md)

Make Office Open XML files (Word, Excel and PowerPoint files such as
`.docx`, `.xlsx` and `.pptx`) searchable in Plone.

The add-on registers one transform, `ooxml_to_text`, in
`portal_transforms`. Plone's search (and any add-on that calls
`portal_transforms.convertTo("text/plain", ...)`) then gets the text of
these files. The text is read with Python's `zipfile` and lxml only: no
Java, no LibreOffice, no other service and no other library.

Only the text is extracted; the structure of the document (headings,
tables, layout) is not kept.

## Formats

| Extension | MIME type |
|---|---|
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `.dotx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.template` |
| `.docm` | `application/vnd.ms-word.document.macroEnabled.12` |
| `.dotm` | `application/vnd.ms-word.template.macroEnabled.12` |
| `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| `.xltx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.template` |
| `.xlsm` | `application/vnd.ms-excel.sheet.macroEnabled.12` |
| `.xltm` | `application/vnd.ms-excel.template.macroEnabled.12` |
| `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` |
| `.potx` | `application/vnd.openxmlformats-officedocument.presentationml.template` |
| `.ppsx` | `application/vnd.openxmlformats-officedocument.presentationml.slideshow` |
| `.pptm` | `application/vnd.ms-powerpoint.presentation.macroEnabled.12` |
| `.potm` | `application/vnd.ms-powerpoint.template.macroEnabled.12` |
| `.ppsm` | `application/vnd.ms-powerpoint.slideshow.macroEnabled.12` |

Documents in the Strict form of ISO/IEC 29500 are read as well. Macros
are never read or run.

Not supported: `.xlsb` (a binary format, not XML) and the old binary
formats `.doc`, `.xls` and `.ppt`.

## What text is extracted

| Format | Extracted | Not extracted |
|---|---|---|
| Word | The body, tables, headers and footers, footnotes and endnotes, inserted tracked changes | Comments, deleted tracked changes, field codes |
| Excel | Sheet names, cell values (text and numbers, the saved results of formulas) | Formulas, comments, phonetic readings |
| PowerPoint | The text of the slides (also in tables and shapes), the speaker notes | Comments |

- Word: the body first, then the headers and footers, the footnotes and
  the endnotes. Every paragraph ends a line; tabs and line breaks are
  kept.
- Excel: the sheets in the order of the workbook, hidden sheets too.
  Each sheet starts with its name on a line, then each row is one line
  with its cell values separated by tabs. Dates stay numbers, as they
  are saved.
- PowerPoint: the slides in the order of the presentation, hidden slides
  too, each followed by its notes. Every paragraph ends a line.

## Limits and errors

A malicious or broken file must not stop or slow down Plone. These limits
apply to one document:

| Limit | Value |
|---|---|
| Size of one part after decompression | 64 MiB |
| Size of all the parts read, after decompression | 256 MiB |
| Number of parts read | 5,000 |
| Length of the text | 10,000,000 characters |
| Time | 30 seconds |

- The sizes are counted while the parts are read; the sizes that the zip
  declares are not trusted.
- When a limit is reached, the text read so far is returned and a warning
  is logged.
- A file that is not a zip (a password-protected document is not one), a
  broken zip or broken XML gives no text, with a warning. Saving the file
  in Plone still works.
- The XML is read without entities, DTDs or network access; a part with
  a DOCTYPE is refused.
- The log never contains the content of a document.

## Installation

Add `c2.transform.ooxml` to the dependencies of your project, then
activate "c2.transform.ooxml" in the Add-ons control panel. The install
registers the MIME types if the site does not know them yet, and the
transform.

**Install either this package or c2.transform.msoffice, not both.**
Both handle these MIME types, and which one Plone uses would then be
hard to predict. Choose c2.transform.msoffice if you also need the old
formats (`.doc`, `.xls`, `.ppt`); choose c2.transform.ooxml if Office Open
XML is enough and you do not want Java.

### Index the existing files

Installing does not index the files that are already in the site (on a
large site that could take hours). Index them again afterwards, in one of
two ways:

- The whole catalog: in the ZMI, `portal_catalog` > Advanced >
  "Clear and Rebuild" (`manage_catalogRebuild`).
- Only the Office Open XML files, for example with
  `bin/zconsole run <zope.conf> reindex_ooxml.py`:

  ```python
  from c2.transform.ooxml.config import ooxml_mimetypes
  from zope.component.hooks import setSite

  import transaction

  portal = app.Plone  # the id of your site
  setSite(portal)
  types = [m["mimetypes"][0] for m in ooxml_mimetypes]
  for brain in portal.portal_catalog.unrestrictedSearchResults(mime_type=types):
      brain._unrestrictedGetObject().reindexObject(idxs=["SearchableText"])
  transaction.commit()
  ```

### Uninstall

Deactivate the add-on in the Add-ons control panel. The transform is
removed; the MIME types stay, because other add-ons may use them.

## Compatibility

Plone 6.0, 6.1 and 6.2 on Python 3.10 to 3.14 (Plone 6.0 and 6.1 up to
Python 3.13).

## License

GPL version 2 or later.
