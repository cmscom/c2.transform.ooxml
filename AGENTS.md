# Notes for contributors and coding agents

## Rules

- This is a public package. Write code, comments, documentation, commit
  messages and pull requests in English. `README-ja.md` is the Japanese
  version of `README.md`; change both together.
- Do not add design documents, specs or plans to the repository.
- Record user-facing changes as towncrier fragments in `news/`
  (`news/+<name>.<type>` or `news/<issue>.<type>`, types as in
  `pyproject.toml`), not in `CHANGELOG.md`.
- The only dependencies are Plone's own packages and lxml. Do not add
  other libraries.

## Layout

- `src/c2/transform/ooxml/`: the package. `c2` and `c2.transform` are
  PEP 420 namespace packages, so they have no `__init__.py`.
  - `config.py`: MIME types (importing it adds them to `mimetypes`), the
    transform name and the limits.
- `tests/`: pytest tests (not shipped in the wheel or the sdist).

## Development

Run the tests and the linters with tox:

```shell
tox -e py314-Plone62      # one Python and Plone version
tox -e ruff-check         # lint and format check
tox -e ruff-fix           # fix and format
tox -e mypy               # type check src and tests
tox                       # the whole matrix
```

Extra arguments go to pytest, for example
`tox -e py314-Plone62 -- tests/test_config.py`. Write expected values in
tests as literals.

## Test documents

The tests build their documents (zip files with XML parts) in
`tests/builders.py`. Do not add documents of unknown origin, and do not
use names of real people or organizations, or real data, in them.
