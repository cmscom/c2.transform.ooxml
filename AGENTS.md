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
  - `package.py`: the zip, the relationships and the XML, read within
    the limits (`Budget`, `TextSink`).
  - `word.py`, `excel.py`, `powerpoint.py`: the text of each format.
  - `extract.py`: `extract_text`, which chooses the format and turns
    errors into an empty text and limits into the text read so far.
  - `transform.py`: the `ooxml_to_text` transform.
  - `setuphandlers.py`: install and uninstall (`post_handler`s).
- `tests/`: pytest tests (not shipped in the wheel or the sdist).
  - `builders.py`: builds the test documents.

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

## Releasing

Releases are made with zest.releaser on a maintainer's machine and published
to PyPI by `.github/workflows/release.yml` with Trusted Publishing; no PyPI
token is used. The version is kept only in `pyproject.toml`.

1. Install the tools of the `release` extra in a virtual environment that
   has pip (check-manifest builds the sdist in an isolated environment made
   with pip):

   ```shell
   pip install "zest.releaser[recommended]" zestreleaser.towncrier zest.pocompile
   ```

   On an up-to-date `main` with a clean working tree, run `fullrelease`.
   It runs check-manifest and pyroma, writes the news fragments into
   `CHANGELOG.md`, sets the version, commits, makes the tag (such as
   `1.0.0b1`, without `v`), sets the next development version and asks
   whether to push. Answer yes: it runs `git push` and `git push --tags`.
   It does not upload anything (`release = false`).
2. The tag starts the Release workflow on GitHub Actions: the tests of
   `plone-package.yml`, then the build (it stops if the tag is not the
   version in `pyproject.toml`).
3. The `publish` job waits for a reviewer of the `pypi` environment to
   approve it, then uploads the sdist and the wheel to PyPI.
4. The `github-release` job signs them with Sigstore and makes a GitHub
   Release with the section of this version from `CHANGELOG.md` and the
   files. Versions with `a`, `b` or `rc` are marked as pre-releases.

Once, before the first release:

- On PyPI, add a pending trusted publisher for the project: project
  `c2.transform.ooxml`, owner `cmscom`, repository `c2.transform.ooxml`,
  workflow `release.yml`, environment `pypi`.
- On GitHub, add the environment `pypi` with required reviewers.
