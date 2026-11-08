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
| Word | The body, tables, headers and footers, footnotes and endnotes, inserted tracked changes | Comments, deleted tracked changes, field codes, SmartArt |
| Excel | Sheet names, cell values (text and numbers, the saved results of formulas) | Formulas, comments, phonetic readings |
| PowerPoint | The text of the slides (also in tables and shapes), the speaker notes | Comments, SmartArt |

Embedded documents (such as a workbook in a presentation) and the text
in images are not extracted.

- Word: the body first, then the headers and footers, the footnotes and
  the endnotes. Every paragraph ends a line; tabs and line breaks are
  kept.
- Excel: the sheets in the order of the workbook, hidden sheets too.
  Each sheet starts with its name on a line, then each row is one line
  with its cell values separated by tabs. Dates stay numbers, as they
  are saved.
- PowerPoint: the slides in the order of the presentation, hidden slides
  too, each followed by its notes. Every paragraph ends a line.
- A line break is never written after another one: empty paragraphs and
  empty rows give no empty lines.

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
| Size of the central directory of the zip (about 45,000 entries) | 2 MiB |

- The time limit usually stops the reading first: at the speed measured
  below, reading 64 MiB parts up to 256 MiB in all would take about a
  minute.
- The sizes are counted while the parts are read; the sizes that the zip
  declares are not trusted.
- The size of the central directory is checked before the zip is opened,
  as zipfile will read it; it also limits the number of entries.
- Only parts that are stored or compressed with deflate (as Office writes
  them) are read. A part compressed with another method (such as bzip2,
  LZMA or Zstandard) is treated as a broken part.
- When a limit is reached, the text read so far is returned and a warning
  is logged.
- The shared strings of a workbook are kept in memory while its sheets
  are read; they count toward the length of the text.
- A file that is not a zip (a password-protected document is not one), a
  broken zip or a broken main part gives no text, with a warning. A broken
  part after the main part (a header, a sheet, a slide) keeps the text
  read so far, with a warning. Saving the file in Plone still works.
- The XML is read without entities, DTDs or network access; a part with
  a DOCTYPE is refused.
- A single run of text over about 10 MB is refused by libxml2 as broken
  XML: in the main part, the document gives no text; in a later part, the
  text read so far is kept.
- The log never contains the content of a document.

Measured on 2026-11-08 (Python 3.14, Plone 6.2) with one ordinary 52 MB
part of about 35 million characters: with the default limits, the reading
stopped at the length of the text after about 3 seconds, with a peak of
29 MB of Python memory; with the limits raised, all of its text was read
in about 11 seconds, with a peak of 102 MB. For that document the memory
grew with the text, not with the size of the part. These numbers describe
that document only; for any input, it is the limits above that bound the
reading.

Measured again on 2026-11-09 (Python 3.14, Plone 6.2) with made-up
documents, one at a time, in a process that only reads the file and
extracts its text:

| Document | Peak memory | Time | Stopped by |
|---|---|---|---|
| One body part of about 60 MB, full of text | 75 MB | 0.7 s | The length of the text |
| One part of 70 MiB of small empty elements | 30 MB | 8.6 s | The size of the part (64 MiB) |
| A short body and five headers of about 60 MB each, without text | 29 MB | 30.0 s | The time (30 seconds), before the total size (256 MiB) |
| Shared strings of about 9 million characters, used by 2 million cells | 50 MB | 0.1 s | The length of the text (the shared strings and the text together) |
| About 40 MB of comments and processing instructions | 28 MB | 0.2 s | Nothing |
| A central directory just under 2 MiB (38,003 entries) | 52 MB | 0.1 s | Nothing |

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
