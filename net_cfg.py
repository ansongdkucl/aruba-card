import json
import os
import ipaddress

def load_network_config():
    """Loads the network_config.json file."""
    config_path = os.path.join("config", "network_config.json")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r") as f:
        return json.load(f)

def find_site_by_ip(mgmt_ip):
    """
    Identifies the site by checking which subnet the mgmt_ip falls into.
    Returns (site_key, site_info) or (None, None).
    """
    try:
        target_ip = ipaddress.ip_address(mgmt_ip)
        network_data = load_network_config()

        for site_key, site_info in network_data.items():
            # Create a network object from the JSON address and mask
            net_addr = site_info.get("network_address")
            net_mask = site_info.get("subnet_mask")
            
            if net_addr and net_mask:
                network = ipaddress.ip_network(f"{net_addr}/{net_mask}", strict=False)
                if target_ip in network:
                    return site_key, site_info
                    
        return None, None
    except Exception as e:
        print(f"Error in find_site_by_ip: {e}")
        return None, None

def generate_hostname(mgmt_ip, template_name):
    """
    Generates a hostname based on the last three octets of the IP.
    Example: 172.22.18.241 -> sw-22-18-241
    """
    octets = mgmt_ip.split('.')
    suffix = "-".join(octets[1:]) # Uses 22-18-241
    
    if "6300" in template_name:
        prefix = "ae6300"
    elif "4100" in template_name:
        prefix = "ae4100i"
    else:
        prefix = "sw"
        
    return f"{prefix}-{suffix}"

def get_data_vlan(mgmt_ip):
    """Helper to get data vlan details for a specific IP site."""
    _, site_info = find_site_by_ip(mgmt_ip)
    if site_info:
        dv = site_info.get("data_vlan", {})
        return dv.get("id", "1"), dv.get("name", "default")
    return "1", "default"

def get_voice_vlan(mgmt_ip):
    """Helper to get voice vlan details for a specific IP site."""
    _, site_info = find_site_by_ip(mgmt_ip)
    if site_info:
        vv = site_info.get("voice_vlan", {})
        return vv.get("id", ""), vv.get("name", "")
    return "", ""

def get_gateway(mgmt_ip):
    """Retrieves the gateway for the site associated with the IP."""
    _, site_info = find_site_by_ip(mgmt_ip)
    return site_info.get("gateway", "") if site_info else ""