from app.kb.attack_techniques import get_all_techniques, get_technique
from app.kb.ir_playbooks import get_all_playbooks, get_playbook
from . import api_router

@api_router.get("/kb/techniques")
async def list_techniques():
    return get_all_techniques()

@api_router.get("/kb/techniques/{technique_id}")
async def technique_detail(technique_id: str):
    return get_technique(technique_id)

@api_router.get("/kb/playbooks")
async def list_playbooks():
    return get_all_playbooks()

@api_router.get("/kb/playbooks/{playbook_id}")
async def playbook_detail(playbook_id: str):
    return get_playbook(playbook_id)
