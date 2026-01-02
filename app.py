from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json
import ipaddress
from typing import Optional

from services.network_config import NetworkConfig
from services.templates import TemplateManager



# --------------------------------------------------
# App setup
# --------------------------------------------------

app = FastAPI(
    title="UCL Switch Config Generator",
    version="1.0.0"
)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
TEMPLATE_DIR = BASE_DIR / "templates"

net_cfg = NetworkConfig(CONFIG_DIR / "network_config.json")
template_mgr = TemplateManager(TEMPLATE_DIR)

# --------------------------------------------------
# Input model (Adaptive Card → Power Automate → API)
# --------------------------------------------------

class SwitchRequest(BaseModel):
    mgmt_ip: str
    hostname: Optional[str] = None
    serial: str
    mac: str
    location: str
    template: str
    send_to_central: bool = False

# --------------------------------------------------
# Health check (Azure likes this)
# --------------------------------------------------

@app.get("/")
def health():
    return {"status": "ok", "service": "config-generator"}

# --------------------------------------------------
# Main generator endpoint
# --------------------------------------------------

@app.post("/generate")
def generate_config(req: SwitchRequest):
    # ---- validate IP ----
    try:
        ipaddress.IPv4Address(req.mgmt_ip)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid management IP")

    # ---- load template ----
    try:
        template_text = template_mgr.load_template(req.template)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ---- auto hostname if blank ----
    hostname = req.hostname
    if not hostname:
        hostname = net_cfg.generate_hostname(req.mgmt_ip, req.template)

    # ---- network derived values ----
    data_vlan_id, data_vlan_name = net_cfg.get_data_vlan(req.mgmt_ip)
    voice_id, voice_name = net_cfg.get_voice_vlan(req.mgmt_ip)
    gateway = net_cfg.get_gateway(req.mgmt_ip)

    profile_type = net_cfg.detect_profile(req.template)
    profile_vlans = net_cfg.get_profile_vlans(req.mgmt_ip, profile_type)
    trunk_allowed = net_cfg.build_trunk_list(
        req.mgmt_ip, data_vlan_id, profile_type
    )

    # ---- build profile VLAN block ----
    profile_block = ""
    for vid, vname in profile_vlans.items():
        profile_block += f"vlan {vid}\n name {vname}\n!\n"

    # ---- replace template tokens ----
    cfg = template_text
    replacements = {
        "{{hostname}}": hostname,
        "{{access_vlan}}": data_vlan_id,
        "{{voice_vlan}}": voice_id,
        "{{gateway}}": gateway,
        "{{location}}": req.location,
        "{{trunk_allowed_vlans}}": trunk_allowed,
    }

    for k, v in replacements.items():
        cfg = cfg.replace(k, str(v))

    # optional blocks
    cfg = cfg.replace("{{profile_vlans}}", profile_block)

    # ---- Aruba Central JSON ----
    central_vars = {
        "_sys_hostname": hostname,
        "_sys_mgnt_ip": req.mgmt_ip,
        "_sys_serial": req.serial,
        "_sys_lan_mac": req.mac,
        "_sys_location": req.location,
        "_sys_data_vlan_id": data_vlan_id,
        "_sys_data_vlan_name": data_vlan_name,
        "_sys_voice_vlan_id": voice_id,
        "_sys_voice_vlan_name": voice_name,
        "_sys_gateway": gateway,
    }

    for vid, vname in profile_vlans.items():
        central_vars[f"_sys_{vid}_vlan_name"] = vname

    central_payload = {
        "total": len(central_vars),
        "variables": central_vars
    }

    # ---- final response ----
    return {
        "success": True,
        "hostname": hostname,
        "config": cfg,
        "central_json": central_payload,
        "send_to_central": req.send_to_central
    }
