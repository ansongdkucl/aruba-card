from pathlib import Path
from services.network_config import NetworkConfig
from services.templates import TemplateManager






BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
TEMPLATE_DIR = BASE_DIR / "templates"

net_cfg = NetworkConfig(CONFIG_DIR / "network_config.json")
tmpl_mgr = TemplateManager(TEMPLATE_DIR)

# ---- fake user input (what Teams will eventually send) ----
payload = {
    "mgmt_ip": "172.22.18.241",
    "template": "6300m - Audio Visual",
    "location": "Anatomy HO Schild",
    "serial": "TW52KYL01X",
    "mac": "7c:a8:ec:55:20:c0"
}

# ---- derive values ----
hostname = net_cfg.generate_hostname(payload["mgmt_ip"], payload["template"])
data_vlan_id, data_vlan_name = net_cfg.get_data_vlan(payload["mgmt_ip"])
voice_id, voice_name = net_cfg.get_voice_vlan(payload["mgmt_ip"])
gateway = net_cfg.get_gateway(payload["mgmt_ip"])
profile = net_cfg.detect_profile(payload["template"])
trunk = net_cfg.build_trunk_list(payload["mgmt_ip"], data_vlan_id, profile)

template_text = tmpl_mgr.load_template("6300m_standard.txt")

config = template_text
replacements = {
    "{{hostname}}": hostname,
    "{{access_vlan}}": data_vlan_id,
    "{{voice_vlan}}": voice_id,
    "{{gateway}}": gateway,
    "{{location}}": payload["location"],
}

for k, v in replacements.items():
    config = config.replace(k, str(v))

print("===== GENERATED CONFIG =====\n")
print(config)
