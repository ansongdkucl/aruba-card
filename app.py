from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import ipaddress
import os
from typing import Optional
from fastapi.responses import JSONResponse
import traceback

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

# Initialise services
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
# Health check
# --------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "traceback": traceback.format_exc()
        }
    )

@app.get("/")
def health():
    return {"status": "ok", "service": "config-generator"}

# --------------------------------------------------
# Debug endpoints (to prove what Azure deployed)
# --------------------------------------------------

@app.get("/debug/info")
def debug_info():
    return {
        "cwd": os.getcwd(),
        "base_dir": str(BASE_DIR),
        "config_dir": str(CONFIG_DIR),
        "template_dir": str(TEMPLATE_DIR),
        "config_dir_exists": CONFIG_DIR.exists(),
        "template_dir_exists": TEMPLATE_DIR.exists(),
    }

@app.get("/debug/templates")
def debug_templates():
    if not TEMPLATE_DIR.exists():
        return {"template_dir": str(TEMPLATE_DIR), "exists": False, "files": []}

    files = sorted([p.name for p in TEMPLATE_DIR.glob("*.j2")])
    return {"template_dir": str(TEMPLATE_DIR), "exists": True, "files": files}

# --------------------------------------------------
# Main generator endpoint
# --------------------------------------------------

@app.post("/generate")
def generate_config(req: SwitchRequest):
    # ---- 1. Validate Management IP ----
    try:
        target_ip = ipaddress.ip_address(req.mgmt_ip)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid management IP")

    # ---- 2. Identify Site from network_config.json ----
    # This assumes net_cfg has a helper to find the site dict by IP
    site_key, site_info = net_cfg.find_site_by_ip(req.mgmt_ip)
    if not site_info:
        raise HTTPException(status_code=400, detail="IP does not match any known site in network_config.json")

    # ---- 3. Load Template ----
    try:
        template_text = template_mgr.load_template(req.template)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ---- 4. Derived Network Values ----
    hostname = (req.hostname or "").strip() or net_cfg.generate_hostname(req.mgmt_ip, req.template)
    
    # Extract site-specific base values
    data_vlan = site_info.get("data_vlan", {})
    voice_vlan = site_info.get("voice_vlan", {})
    gateway = site_info.get("gateway")
    
    # Determine profile (av vs standard)
    profile_type = "av" if "av" in req.template.lower() else "standard"
    profile_vlans = site_info.get("profiles", {}).get(profile_type, {})

    # ---- 5. Build Aruba Central Variables (_sys_) ----
    central_vars = {
        "_sys_hostname": hostname,
        "_sys_mgnt_ip": req.mgmt_ip,
        "_sys_serial": req.serial,
        "_sys_lan_mac": req.mac,
        "_sys_location": req.location or "default_location",
        "_sys_gateway": gateway,
        "_sys_data_vlan_id": data_vlan.get("id"),
        "_sys_data_vlan_name": data_vlan.get("name"),
    }

    # Add Voice VLAN if present for the site
    if voice_vlan:
        central_vars["_sys_voice_vlan_id"] = voice_vlan.get("id")
        central_vars["_sys_voice_vlan_name"] = voice_vlan.get("name")

    # Add Profile-Specific VLANs from your JSON
    for vid, vname in profile_vlans.items():
        central_vars[f"_sys_{vid}_vlan_name"] = vname

    # ---- 6. Format Payload with Serial Number as Key ----
    # This matches the specific requirement for Aruba Central variable imports
    central_payload = {
        req.serial: central_vars
    }

    # ---- 7. Build CLI Config (Replacement Logic) ----
    profile_block = "".join([f"vlan {vid}\n name {vname}\n!\n" for vid, vname in profile_vlans.items()])
    
    replacements = {
        "{{hostname}}": hostname,
        "{{access_vlan}}": data_vlan.get("id", "1"),
        # Fixed: Use voice_vlan.get("id") instead of voice_id
        "{{voice_vlan}}": voice_vlan.get("id", "") if voice_vlan else "",
        "{{gateway}}": gateway,
        "{{location}}": req.location,
        "{{profile_vlans}}": profile_block
    }

    cfg = template_text
    for k, v in replacements.items():
        cfg = cfg.replace(k, str(v or ""))

    return {
        "success": True,
        "hostname": hostname,
        "config": cfg,
        "payload_json": central_vars,  # Send the variables directly
        "serial": req.serial           # Send the serial separately
    }