from OFS.Application import Application
from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer
from Products.CMFPlone.Portal import PloneSite
from zope.configuration.config import ConfigurationMachine

import c2.transform.ooxml


class Layer(PloneSandboxLayer):
    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(
        self, app: Application, configurationContext: ConfigurationMachine
    ) -> None:
        # z3c.autoinclude is disabled in the Plone fixture base layer.
        self.loadZCML(package=c2.transform.ooxml)

    def setUpPloneSite(self, portal: PloneSite) -> None:
        applyProfile(portal, "c2.transform.ooxml:default")


FIXTURE = Layer()

INTEGRATION_TESTING = IntegrationTesting(
    bases=(FIXTURE,),
    name="C2.Transform.OoxmlLayer:IntegrationTesting",
)

FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(FIXTURE,),
    name="C2.Transform.OoxmlLayer:FunctionalTesting",
)
