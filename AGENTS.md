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

Releases are made only by `.github/workflows/release.yml` on GitHub
Actions; nothing is needed on a maintainer's machine. It publishes to PyPI
with Trusted Publishing, so no PyPI token is used. The version is kept only
in `pyproject.toml`. The steps that need code are in
`.github/scripts/release.py`, tested by `tests/test_release_script.py`.

1. Make sure that `main` has the news fragments of the release in `news/`.
   The first release is `1.0.0a1`; `pyproject.toml` has `1.0.0a1.dev0`
   before it.
2. In GitHub: **Actions**, **Release**, **Run workflow**, branch `main`,
   enter the version (such as `1.0.0b2`: PEP 440 in its normalized form,
   without `v`) and run it.
3. `prepare` stops unless the version is after the one in `pyproject.toml`,
   has no tag yet, is neither a development version nor both a pre-release
   and a post-release (such as `1.0.0b2.post1`), and the run is on `main`,
   with news fragments. Then it writes the fragments into `CHANGELOG.md`,
   sets the version, commits "Preparing release <version>" as
   github-actions[bot] and makes the annotated tag `<version>`.
   `push-release` pushes both to GitHub.
4. `test` runs the tests of `plone-package.yml` on that commit, and
   `build` builds and checks the sdist and the wheel.
5. `publish` waits for a reviewer of the `pypi` environment. Review the
   deployment and approve it; it then uploads to PyPI.
6. `sign` signs the files with Sigstore, and `github-release` makes a
   GitHub Release with them, their signatures and the section of this
   version from `CHANGELOG.md`. Versions with `a`, `b` or `rc` are marked
   as pre-releases.
7. `development` sets the next development version (`1.0.0b2` gives
   `1.0.0b3.dev0`, `1.0.0` gives `1.0.1.dev0`, `1.0.0.post1` gives
   `1.0.0.post2.dev0`) and commits "Back to development: <version>".
   `push-development` pushes it. If `main` has moved since the release
   commit, it stops without pushing and says in its log how to do it by
   hand.

Only `push-release`, `push-development` and `github-release` can write to
the repository. They run only `actions/checkout`,
`actions/download-artifact`, `git` and `gh`. The push jobs get the commits
of the jobs before them as git bundles and push them only if each is one
commit on the expected parent that changes only the expected files
(`pyproject.toml`, `CHANGELOG.md` and removed news fragments for the
release, `pyproject.toml` for the development version). Keep it so: do not
add steps with other actions or tools to these jobs.

Only one release runs at a time. A run started while another release runs
waits (GitHub keeps only the latest waiting run and cancels older ones),
then starts from the `main` of the time it was started; its `push-release`
fails because `main` has moved, and nothing is pushed. Run the workflow
again.

The `setup-uv` steps pin uv with `version` and `checksum`. When you change
the version, change the checksum with it.

### When a release fails or is rejected

- Before `push-release` pushed, nothing has changed: fix the cause and run
  the workflow again.
- After `push-release` pushed, but before `publish` ran (the tests or the
  build failed, or the deployment was rejected): PyPI has nothing of this
  version. Delete the tag (`git push origin :refs/tags/<version>` and
  `git tag -d <version>`), revert "Preparing release <version>" on `main`
  (this brings the news fragments back) and push, fix the cause, and run
  the workflow again with the same version.
- If `publish` ran, look at <https://pypi.org/project/c2.transform.ooxml/> for
  the files of this version. If even one of them is there, do not delete
  the tag: PyPI never accepts the same file again. Re-run `publish` to
  upload the missing files (it skips the existing ones), then re-run the
  jobs after it. A re-run uses the files of the same run: before you go
  on, check that the sha256 of each file that PyPI has already is the one
  of the file in the `dist` artifact of the run. To fix the release itself, release the next version.
  Do not build the files again for a release that stopped half way:
  building the same commit again gives other sha256 for the wheel and the
  sdist, and `skip-existing` does not check that they match. Use the
  `dist` artifact of the run that stopped.
- If a re-run of `github-release` fails because the release already
  exists, add the missing files to it with
  `gh release upload <version> <files> --clobber` (the files of the
  `dist` artifact and their `.sigstore.json` of the `signatures` artifact
  of the run), or delete the GitHub Release and re-run the job.
- If `push-development` failed, re-run it, or set the development version
  by hand as its log says: on an up-to-date `main`, run
  `uv run --no-project --python 3.12 --with packaging .github/scripts/release.py back-to-development <version>`,
  commit `pyproject.toml` with the message
  "Back to development: <the printed version without .dev0>" and push.

### Settings needed once

- PyPI: the trusted publisher of `c2.transform.ooxml` is owner `cmscom`,
  repository `c2.transform.ooxml`, workflow `release.yml`, environment
  `pypi`.
- GitHub: the environment `pypi` with required reviewers. The workflow runs
  on the branch `main`, so a deployment rule of the environment must allow
  `main` (not only tags).
- `push-release` and `push-development` push to `main` with `GITHUB_TOKEN`.
  If `main` gets a branch protection rule or a ruleset, it must let these
  pushes through (as an exception for GitHub Actions); otherwise the
  release stops at the push. Check this when you add the protection.
  Commits pushed with `GITHUB_TOKEN` do not start other workflows, so
  `plone-package.yml` does not run again for them; the release runs those
  tests itself.
