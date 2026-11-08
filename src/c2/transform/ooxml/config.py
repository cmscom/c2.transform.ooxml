import mimetypes


PROJECTNAME = "c2.transform.ooxml"
SITE_CHARSET = "utf-8"
TRANSFORM_NAME = "ooxml_to_text"

# Limits for one document. When one is reached, the text read so far is
# returned and a warning is logged.
# The size of one part after decompression (counted while reading).
MAX_PART_BYTES = 64 * 1024 * 1024
# The size of all the parts read, after decompression.
MAX_TOTAL_BYTES = 256 * 1024 * 1024
# The number of parts read.
MAX_PARTS = 5000
# The length of the text returned.
MAX_TEXT_CHARS = 10_000_000
# The time spent on one document.
TIME_LIMIT_SECONDS = 30.0
# Checked before zipfile reads the central directory of the zip: the
# number of entries and the size of the central directory.
MAX_ENTRIES = 10_000
MAX_CENTRAL_DIRECTORY_BYTES = 16 * 1024 * 1024

_WORD = "application/vnd.openxmlformats-officedocument.wordprocessingml"
_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml"
_POWERPOINT = "application/vnd.openxmlformats-officedocument.presentationml"

ooxml_mimetypes = (
    {
        "name": "Office Word 2007 XML document",
        "mimetypes": (f"{_WORD}.document",),
        "extensions": ("docx",),
    },
    {
        "name": "Office Word 2007 XML template",
        "mimetypes": (f"{_WORD}.template",),
        "extensions": ("dotx",),
    },
    {
        "name": "Office Word 2007 XML macro enabled document",
        "mimetypes": ("application/vnd.ms-word.document.macroEnabled.12",),
        "extensions": ("docm",),
    },
    {
        "name": "Office Word 2007 XML macro enabled template",
        "mimetypes": ("application/vnd.ms-word.template.macroEnabled.12",),
        "extensions": ("dotm",),
    },
    {
        "name": "Office Excel 2007 XML workbook",
        "mimetypes": (f"{_EXCEL}.sheet",),
        "extensions": ("xlsx",),
    },
    {
        "name": "Office Excel 2007 XML template",
        "mimetypes": (f"{_EXCEL}.template",),
        "extensions": ("xltx",),
    },
    {
        "name": "Office Excel 2007 XML macro-enabled workbook",
        "mimetypes": ("application/vnd.ms-excel.sheet.macroEnabled.12",),
        "extensions": ("xlsm",),
    },
    {
        "name": "Office Excel 2007 XML macro-enabled template",
        "mimetypes": ("application/vnd.ms-excel.template.macroEnabled.12",),
        "extensions": ("xltm",),
    },
    {
        "name": "Office Powerpoint 2007 XML presentation",
        "mimetypes": (f"{_POWERPOINT}.presentation",),
        "extensions": ("pptx",),
    },
    {
        "name": "Office Powerpoint 2007 XML template",
        "mimetypes": (f"{_POWERPOINT}.template",),
        "extensions": ("potx",),
    },
    {
        "name": "Office Powerpoint 2007 XML slideshow",
        "mimetypes": (f"{_POWERPOINT}.slideshow",),
        "extensions": ("ppsx",),
    },
    {
        "name": "Office Powerpoint 2007 macro-enabled XML presentation",
        "mimetypes": ("application/vnd.ms-powerpoint.presentation.macroEnabled.12",),
        "extensions": ("pptm",),
    },
    {
        "name": "Office Powerpoint 2007 macro-enabled XML template",
        "mimetypes": ("application/vnd.ms-powerpoint.template.macroEnabled.12",),
        "extensions": ("potm",),
    },
    {
        "name": "Office Powerpoint 2007 macro-enabled XML slideshow",
        "mimetypes": ("application/vnd.ms-powerpoint.slideshow.macroEnabled.12",),
        "extensions": ("ppsm",),
    },
)

for mt in ooxml_mimetypes:
    mt["globs"] = tuple("*." + ext for ext in mt["extensions"])
    mt["icon_path"] = "application.png"
    # plone.namedfile guesses a missing content type with the standard library.
    # Older Pythons do not know all these types and slim images have no
    # /etc/mime.types, so they are added on import, in every process.
    mimetypes.add_type(mt["mimetypes"][0], "." + mt["extensions"][0])

del mimetypes
