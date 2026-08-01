import pytest
from app.engines.ioc_engine import IoCEngine
from app.sources import ALL_SOURCES

@pytest.mark.asyncio
async def test_ioc_engine_instantiation():
    engine = IoCEngine()
    assert engine is not None
    assert len(engine.sources) > 0

@pytest.mark.asyncio
async def test_ioc_engine_routes_by_type():
    engine = IoCEngine()
    result = await engine.analyze("ip", "8.8.8.8")
    assert result.ioc_type == "ip"
    assert result.ioc_value == "8.8.8.8"
    assert result.sources is not None
    # NVD and PhishTank should say they don't support IP type
    nvd = [s for s in result.sources if s.source == "nvd"]
    pt = [s for s in result.sources if s.source == "phishtank"]
    assert len(nvd) == 1
    assert len(pt) == 1

def test_all_sources_declare_types():
    for source in ALL_SOURCES:
        assert source.name
        assert isinstance(source.supported_types, list), f"{source.name} missing supported_types"
        assert len(source.supported_types) > 0, f"{source.name} has empty supported_types"

def test_can_handle():
    from app.sources.nvd import NVDSource
    nvd = NVDSource()
    assert nvd.can_handle("cve")
    assert not nvd.can_handle("ip")

@pytest.mark.asyncio
async def test_source_supports_type_agreement():
    """Each source should support at least the types it implements query for."""
    for source in ALL_SOURCES:
        for ioc_type in source.supported_types:
            result = await source.query(ioc_type, "test")
            # Should not crash - might return error for invalid value but that's OK
            assert isinstance(result, dict)
