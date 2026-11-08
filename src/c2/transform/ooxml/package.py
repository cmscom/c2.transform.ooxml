"""Read the parts of an Office Open XML package, within limits.

The XML is parsed with lxml's ``iterparse``: elements are cleared once they
are read, so a large part does not stay in memory. Entities are not
resolved, nothing is loaded from the network, and a part with a DOCTYPE is
refused (Office Open XML does not use one).
"""

from c2.transform.ooxml import config
from collections.abc import Callable
from collections.abc import Iterator
from dataclasses import dataclass
from lxml import etree
from typing import IO
from urllib.parse import unquote

import io
import posixpath
import time
import zipfile


# Check the time every this many parse events.
TIME_CHECK_EVERY = 1000
# Read the parts in chunks of this size.
CHUNK_SIZE = 64 * 1024

_TRANSITIONAL = "http://schemas.openxmlformats.org"
_STRICT = "http://purl.oclc.org/ooxml"

# The namespaces of the elements, in Transitional and in Strict documents.
NS: dict[str, frozenset[str]] = {
    "w": frozenset({
        f"{_TRANSITIONAL}/wordprocessingml/2006/main",
        f"{_STRICT}/wordprocessingml/main",
    }),
    "s": frozenset({
        f"{_TRANSITIONAL}/spreadsheetml/2006/main",
        f"{_STRICT}/spreadsheetml/main",
    }),
    "p": frozenset({
        f"{_TRANSITIONAL}/presentationml/2006/main",
        f"{_STRICT}/presentationml/main",
    }),
    "a": frozenset({
        f"{_TRANSITIONAL}/drawingml/2006/main",
        f"{_STRICT}/drawingml/main",
    }),
    "r": frozenset({
        f"{_TRANSITIONAL}/officeDocument/2006/relationships",
        f"{_STRICT}/officeDocument/relationships",
    }),
    "mc": frozenset({f"{_TRANSITIONAL}/markup-compatibility/2006"}),
    "rel": frozenset({f"{_TRANSITIONAL}/package/2006/relationships"}),
}


class LimitReached(Exception):
    """A limit of the size, the number of parts, the text or the time."""


class UnsupportedCompression(ValueError):
    """A part compressed with another method than deflate (or stored).

    zipfile decompresses bzip2, LZMA and Zstandard data without a limit on
    the size of the output, before the bytes can be counted. Office
    writes deflate, so other methods are refused as a broken part.
    """


# The compression methods of the parts that are read.
READABLE_COMPRESSION = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})


class Budget:
    """What one document may still use. The limits are read from ``config``."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._deadline = clock() + config.TIME_LIMIT_SECONDS
        self._bytes = 0
        self._parts = 0

    def check_time(self) -> None:
        if self._clock() > self._deadline:
            raise LimitReached(f"time ({config.TIME_LIMIT_SECONDS} seconds)")

    def take_bytes(self, n: int) -> None:
        self._bytes += n
        if self._bytes > config.MAX_TOTAL_BYTES:
            raise LimitReached(f"total size ({config.MAX_TOTAL_BYTES} bytes)")

    def take_part(self) -> None:
        # Also here, so that many small parts cannot pass the time limit.
        self.check_time()
        self._parts += 1
        if self._parts > config.MAX_PARTS:
            raise LimitReached(f"number of parts ({config.MAX_PARTS})")


class TextSink:
    """The text of a document, up to ``config.MAX_TEXT_CHARS`` characters."""

    def __init__(self, budget: Budget) -> None:
        self.budget = budget
        # Set by the extractors once the main part is read: an error after
        # it keeps the text written so far.
        self.main_read = False
        self._chunks: list[str] = []
        self._length = 0

    def write(self, text: str) -> None:
        room = config.MAX_TEXT_CHARS - self._length
        if len(text) > room:
            if room > 0:
                self._chunks.append(text[:room])
                self._length += room
            raise LimitReached(f"text length ({config.MAX_TEXT_CHARS} characters)")
        self._chunks.append(text)
        self._length += len(text)

    def charge(self, n: int) -> None:
        """Count ``n`` characters that are kept elsewhere (the shared strings
        of a workbook), so that they and the text share one limit.

        Without the raise here, the next ``write`` would stop at the limit
        anyway; it matters when the shared strings alone go over it.
        """
        if self._length + n > config.MAX_TEXT_CHARS:
            raise LimitReached(f"text length ({config.MAX_TEXT_CHARS} characters)")
        self._length += n

    def text(self) -> str:
        return "".join(self._chunks)


class UncheckableZip(ValueError):
    """The central directory of a zip cannot be checked before it is read
    (this Python's zipfile does not have the function it is checked with).
    """


# zipfile's own reading of the end records (Zip64 included): a private
# function of zipfile, in Python 3.10 to 3.14.
_ZIPFILE_END_RECORD = "_EndRecData"


def _zipfile_name(name: str) -> object:
    try:
        return getattr(zipfile, name)
    except AttributeError:
        raise UncheckableZip(name) from None


def check_central_directory(data: bytes) -> None:
    """Raise ``LimitReached`` when the central directory of the zip ``data``
    is too large, before zipfile reads it.

    ZipFile reads the size of the central directory from the end records
    (with this same function, Zip64 included), reads that many bytes and
    makes its entries from them only, at least 46 bytes each: limiting the
    size limits the entries too, however the start of the directory is
    found. Without that function, ``UncheckableZip`` is raised. A zip
    without end records is left to zipfile, which refuses it before it
    makes any entry.
    """
    end_record = _zipfile_name(_ZIPFILE_END_RECORD)
    ecd_size = int(_zipfile_name("_ECD_SIZE"))  # type: ignore[call-overload]
    try:
        endrec = end_record(io.BytesIO(data))  # type: ignore[operator]
    except OSError:
        return
    if not endrec:
        return
    if int(endrec[ecd_size]) > config.MAX_CENTRAL_DIRECTORY_BYTES:
        raise LimitReached(
            f"size of the central directory ({config.MAX_CENTRAL_DIRECTORY_BYTES})"
        )


def is_el(element: etree._Element, ns: str, local: str) -> bool:
    """Is ``element`` the element ``local`` of the namespace ``ns`` (a key
    of ``NS``), in a Transitional or a Strict document?"""
    tag = element.tag
    if not isinstance(tag, str) or not tag.endswith("}" + local):
        return False
    return tag[1 : -len(local) - 1] in NS[ns]


def r_id(element: etree._Element) -> str | None:
    """The ``r:id`` attribute, in a Transitional or a Strict document."""
    for uri in NS["r"]:
        value = element.get(f"{{{uri}}}id")
        if value is not None:
            return str(value)
    return None


@dataclass(frozen=True)
class Relationship:
    rel_id: str
    # The last part of the relationship type, such as "header".
    kind: str
    # The name of the part in the zip.
    target: str


class _CountingReader:
    """Count the bytes of a part as they are decompressed.

    The size that the zip declares is not used: a part stops at the limit
    whatever its header says.
    """

    def __init__(self, stream: IO[bytes], budget: Budget) -> None:
        self._stream = stream
        self._budget = budget
        self._size = 0

    def read(self, n: int = CHUNK_SIZE) -> bytes:
        if n is None or n < 0 or n > CHUNK_SIZE:
            n = CHUNK_SIZE
        # Also here: a part with few parse events is still read in chunks.
        self._budget.check_time()
        data = self._stream.read(n)
        self._size += len(data)
        if self._size > config.MAX_PART_BYTES:
            raise LimitReached(f"part size ({config.MAX_PART_BYTES} bytes)")
        self._budget.take_bytes(len(data))
        return data


def iter_xml(
    zf: zipfile.ZipFile, name: str, budget: Budget
) -> Iterator[tuple[str, etree._Element]]:
    """The ("start" or "end", element) events of the part ``name``.

    Nothing comes from a part that is not in the zip. A part that is not
    stored or deflated raises ``UnsupportedCompression`` before it is
    opened. An element is cleared when the caller has had its "end" event:
    read its text then.
    """
    try:
        info = zf.getinfo(name)
    except KeyError:
        return
    if info.compress_type not in READABLE_COMPRESSION:
        raise UnsupportedCompression(f"compression method {info.compress_type}")
    budget.take_part()
    with zf.open(name) as stream:
        reader = _CountingReader(stream, budget)
        events = etree.iterparse(
            reader,
            events=("start", "end"),
            resolve_entities=False,
            no_network=True,
            huge_tree=False,
            load_dtd=False,
            # Comments and PIs have no events here, so they would stay in
            # the tree until their parent ends.
            remove_comments=True,
            remove_pis=True,
        )
        checked = False
        for count, (event, element) in enumerate(events, 1):
            if not checked:
                if element.getroottree().docinfo.doctype:
                    raise ValueError("a part with a DOCTYPE")
                checked = True
            if count % TIME_CHECK_EVERY == 0:
                budget.check_time()
            yield event, element
            if event == "end":
                element.clear()
                # Drop the elements read before it, too. The root has no
                # parent, but a comment or a PI before it is its previous
                # sibling: those stay.
                parent = element.getparent()
                if parent is not None:
                    while element.getprevious() is not None:
                        del parent[0]


def without_fallback(
    events: Iterator[tuple[str, etree._Element]],
) -> Iterator[tuple[str, etree._Element]]:
    """The events outside ``mc:Fallback``, which repeats ``mc:Choice``."""
    skipping = 0
    for event, element in events:
        if is_el(element, "mc", "Fallback"):
            skipping += 1 if event == "start" else -1
        elif not skipping:
            yield event, element


def _rels_name(part: str) -> str:
    folder, name = posixpath.split(part)
    return posixpath.join(folder, "_rels", f"{name}.rels")


def _resolve(part: str, target: str) -> str | None:
    """The name in the zip of ``target``, relative to ``part``, or None
    when it points outside the package."""
    target = unquote(target)
    if target.startswith("/"):
        name = posixpath.normpath(target.lstrip("/"))
    else:
        name = posixpath.normpath(posixpath.join(posixpath.dirname(part), target))
    if name.startswith("../") or name in ("..", ".", ""):
        return None
    return name


def relationships(zf: zipfile.ZipFile, part: str, budget: Budget) -> list[Relationship]:
    """The internal relationships of ``part`` ("" for the package itself)."""
    found = []
    for event, element in iter_xml(zf, _rels_name(part), budget):
        if event != "start" or not is_el(element, "rel", "Relationship"):
            continue
        if element.get("TargetMode") == "External":
            continue
        target = _resolve(part, element.get("Target") or "")
        if target is None:
            continue
        kind = (element.get("Type") or "").rsplit("/", 1)[-1]
        found.append(Relationship(element.get("Id") or "", kind, target))
    return found


def main_part(zf: zipfile.ZipFile, budget: Budget) -> str | None:
    """The name of the main part (the "officeDocument" of the package)."""
    for rel in relationships(zf, "", budget):
        if rel.kind == "officeDocument":
            return rel.target
    return None
