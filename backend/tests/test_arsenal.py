import pytest
from services.turbo_scheduler import get_scheduler
from services.vision_service import get_vision_service

@pytest.mark.asyncio
async def test_scheduler_singleton():
    s1 = get_scheduler()
    s2 = get_scheduler()
    assert s1 is s2
    assert s1.is_active == False

@pytest.mark.asyncio
async def test_vision_service_mock():
    # Ensure it returns mock data when not loaded/no deps
    service = get_vision_service()
    service.unload_model()
    
    # Mock image
    result = service.analyze_image("base64data", task="<OD>")
    assert result['status'] == 'mock_success'
    assert 'objects' in result

def test_arsenal_import():
    # verify we can import the router without errors
    from app.routers import arsenal
    assert arsenal.router is not None
