def test_version():
    import c2.transform.ooxml

    assert c2.transform.ooxml.__version__ == "1.0.0b1.dev0"


def test_version_is_the_one_of_the_distribution():
    from c2.transform.ooxml import __version__
    from importlib.metadata import version

    assert __version__ == version("c2.transform.ooxml")


def test_c2_is_a_pep420_namespace():
    import c2
    import c2.transform

    assert getattr(c2, "__file__", None) is None
    assert getattr(c2.transform, "__file__", None) is None
