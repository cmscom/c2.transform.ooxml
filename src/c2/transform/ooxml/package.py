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
        self._parts += 1
        if self._parts > config.MAX_PARTS:
            raise LimitReached(f"number of parts ({config.MAX_PARTS})")


class TextSink:
    """The text of a document, up to ``config.MAX_TEXT_CHARS`` characters."""

    def __init__(self, budget: Budget) -> None:
        self.budget = budget
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

    def text(self) -> str:
        return "".join(self._chunks)


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

    Nothing comes from a part that is not in the zip. An element is cleared
    when the caller has had its "end" event: read its text then.
    """
    try:
        zf.getinfo(name)
    except KeyError:
        return
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
