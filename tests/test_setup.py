from Acquisition import aq_base
from c2.transform.ooxml import PACKAGE_NAME
from plone.base.interfaces import INonInstallable
from Products.CMFPlone.controlpanel.browser.quickinstaller import InstallerView
from Products.CMFPlone.Portal import PloneSite
from Products.GenericSetup.tool import SetupTool
from Products.PortalTransforms.TransformEngine import TransformTool
from zope.component import getUtility

import logging
import pytest


TRANSFORM_NAME = "ooxml_to_text"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPSM = "application/vnd.ms-powerpoint.slideshow.macroEnabled.12"
DEFAULT_PROFILE = "profile-c2.transform.ooxml:default"
UNINSTALL_PROFILE = "profile-c2.transform.ooxml:uninstall"


def portal_mimetype(transforms: TransformTool, name: str) -> bool:
    return bool(transforms.mimetypes_registry.lookup(name))


@pytest.fixture
def transforms(portal: PloneSite) -> TransformTool:
    return portal.portal_transforms


@pytest.fixture
def setup_tool(portal: PloneSite) -> SetupTool:
    return portal.portal_setup


def test_addon_installed(installer):
    assert installer.is_product_installed(PACKAGE_NAME) is True


def test_latest_version(profile_last_version):
    assert profile_last_version(f"{PACKAGE_NAME}:default") == "1000"


def test_transform_installed(transforms):
    assert TRANSFORM_NAME in transforms.objectIds()
    transform = transforms[TRANSFORM_NAME]
    assert transform.module == "c2.transform.ooxml.transform"
    assert PPSM in transform.inputs
    assert [t.name() for t in transforms._mtmap[PPSM]["text/plain"]] == [TRANSFORM_NAME]


def test_install_restores_a_missing_mimetype(portal, setup_tool):
    mtr = portal.mimetypes_registry
    mtr.manage_delObjects([DOCX])
    assert mtr.lookup(DOCX) == ()
    setup_tool.runAllImportStepsFromProfile(DEFAULT_PROFILE)
    [mimetype] = mtr.lookup(DOCX)
    assert mimetype.name() == "Office Word 2007 XML document"
    assert mimetype.extensions == ("docx",)
    assert mimetype.globs == ("*.docx",)
    assert mimetype.binary


def test_install_twice(transforms, setup_tool, caplog):
    transform = transforms[TRANSFORM_NAME]
    with caplog.at_level(logging.INFO, logger=PACKAGE_NAME):
        setup_tool.runAllImportStepsFromProfile(DEFAULT_PROFILE)
    assert transforms.objectIds().count(TRANSFORM_NAME) == 1
    assert aq_base(transforms[TRANSFORM_NAME]) is aq_base(transform)
    assert (
        PACKAGE_NAME,
        logging.INFO,
        "ooxml_to_text is already registered in portal_transforms; skipped",
    ) in caplog.record_tuples


def test_install_does_not_reindex(portal, setup_tool, monkeypatch):
    calls = []
    catalog = type(aq_base(portal.portal_catalog))
    for name in ("reindexObject", "refreshCatalog", "manage_catalogRebuild"):
        monkeypatch.setattr(
            catalog, name, lambda *a, _name=name, **k: calls.append(_name)
        )
    portal.portal_transforms.manage_delObjects([TRANSFORM_NAME])
    setup_tool.runAllImportStepsFromProfile(DEFAULT_PROFILE)
    assert TRANSFORM_NAME in portal.portal_transforms.objectIds()
    assert calls == []


def test_uninstall_profile_is_hidden(portal):
    hidden = getUtility(INonInstallable, name=PACKAGE_NAME)
    assert hidden.getNonInstallableProfiles() == ["c2.transform.ooxml:uninstall"]


class TestUninstall:
    @pytest.fixture(autouse=True)
    def uninstalled(self, installer: InstallerView) -> None:
        installer.uninstall_product(PACKAGE_NAME)

    def test_addon_uninstalled(self, installer):
        assert installer.is_product_installed(PACKAGE_NAME) is False

    def test_transform_removed(self, transforms):
        assert TRANSFORM_NAME not in transforms.objectIds()

    def test_mimetypes_are_kept(self, portal):
        assert len(portal.mimetypes_registry.lookup(DOCX)) == 1

    def test_uninstall_twice(self, transforms, setup_tool):
        setup_tool.runAllImportStepsFromProfile(UNINSTALL_PROFILE)
        assert TRANSFORM_NAME not in transforms.objectIds()

    def test_missing_mapping_still_removes_the_transform(
        self, installer, transforms, caplog
    ):
        installer.install_product(PACKAGE_NAME)
        del transforms._mtmap[DOCX]["text/plain"]
        with caplog.at_level(logging.WARNING, logger=PACKAGE_NAME):
            installer.uninstall_product(PACKAGE_NAME)
        assert installer.is_product_installed(PACKAGE_NAME) is False
        assert TRANSFORM_NAME not in transforms.objectIds()
        assert [r.getMessage() for r in caplog.records] == [
            "Could not unmap ooxml_to_text in portal_transforms: "
            "KeyError('text/plain'); the transform was removed anyway"
        ]

    def test_missing_mapping_unmaps_every_mimetype(self, installer, transforms):
        from c2.transform.ooxml import config

        def names() -> list[tuple[str, str, str]]:
            return [
                (mt, output, t.name())
                for mt, outputs in transforms._mtmap.items()
                for output, chain in outputs.items()
                for t in chain
            ]

        installer.install_product(PACKAGE_NAME)
        others = [n for n in names() if n[2] != TRANSFORM_NAME]
        del transforms._mtmap[DOCX]["text/plain"]
        installer.uninstall_product(PACKAGE_NAME)
        assert [n for n in names() if n[2] == TRANSFORM_NAME] == []
        # The other transforms keep their mappings, and the MIME types stay.
        assert [n for n in names() if n[2] != TRANSFORM_NAME] == [
            n for n in others if not (n[0] == DOCX and n[1] == "text/plain")
        ]
        for m in config.ooxml_mimetypes:
            assert portal_mimetype(transforms, m["mimetypes"][0])

    def test_install_again(self, installer, transforms):
        installer.install_product(PACKAGE_NAME)
        assert TRANSFORM_NAME in transforms.objectIds()
