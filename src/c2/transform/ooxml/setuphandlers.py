from c2.transform.ooxml import config
from c2.transform.ooxml import logger
from plone.base.interfaces import INonInstallable
from Products.CMFCore.utils import getToolByName
from Products.GenericSetup.tool import SetupTool
from Products.PortalTransforms.TransformEngine import TransformTool
from zope.interface import implementer


TRANSFORM_MODULE = "c2.transform.ooxml.transform"


@implementer(INonInstallable)
class HiddenProfiles:
    def getNonInstallableProfiles(self) -> list[str]:
        """Hide the uninstall profile from site creation and the add-ons list."""
        return ["c2.transform.ooxml:uninstall"]


def post_install(context: SetupTool) -> None:
    """Register the Office Open XML MIME types and the transform.

    ``context`` is the setup tool. Running it again changes nothing.
    """
    mtr = getToolByName(context, "mimetypes_registry")
    for mt_dict in config.ooxml_mimetypes:
        main_mt = mt_dict["mimetypes"][0]
        mt_name = mt_dict["name"]
        if mtr.lookup(main_mt):
            logger.info("%s (%s) MIME type already registered", main_mt, mt_name)
            continue
        mtr.manage_addMimeType(
            mt_name,
            mt_dict["mimetypes"],
            mt_dict["extensions"],
            mt_dict["icon_path"],
            binary=True,
            globs=mt_dict["globs"],
        )
        logger.info("%s (%s) MIME type registered", main_mt, mt_name)

    transforms = getToolByName(context, "portal_transforms")
    if config.TRANSFORM_NAME in transforms.objectIds():
        logger.info(
            "%s is already registered in portal_transforms; skipped",
            config.TRANSFORM_NAME,
        )
        return
    transforms.manage_addTransform(config.TRANSFORM_NAME, TRANSFORM_MODULE)


def _unmap_everywhere(transforms: TransformTool, name: str) -> None:
    """Remove the transform ``name`` from every mapping of portal_transforms.

    The chains are changed in place: they are persistent lists, which
    portal_transforms changes in place later (a plain list there would not
    be saved). Other transforms keep their places.
    """
    for outputs in transforms._mtmap.values():
        for chain in outputs.values():
            for index in reversed(range(len(chain))):
                if chain[index].name() == name:
                    del chain[index]


def uninstall(context: SetupTool) -> None:
    """Remove the transform. The MIME types stay; others may use them."""
    transforms = getToolByName(context, "portal_transforms")
    if config.TRANSFORM_NAME not in transforms.objectIds():
        return
    try:
        transforms.unregisterTransform(config.TRANSFORM_NAME)
    except KeyError as error:
        # unregisterTransform unmaps first and raises KeyError when a MIME
        # type was never mapped to this transform; it stops there, so the
        # other MIME types are still mapped, and the transform is not
        # deleted yet. Unmap it from every MIME type, then delete it, so
        # that installing again adds it anew. Without events, because
        # Transform.manage_beforeDelete unmaps again and OFS re-raises that
        # KeyError in debug mode for non-Managers.
        _unmap_everywhere(transforms, config.TRANSFORM_NAME)
        transforms._delObject(config.TRANSFORM_NAME, suppress_events=True)
        logger.warning(
            "Could not unmap %s in portal_transforms: %r; "
            "the transform was removed anyway",
            config.TRANSFORM_NAME,
            error,
        )
