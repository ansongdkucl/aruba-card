import json
import ipaddress
from pathlib import Path

class NetworkConfig:
    def __init__(self, config_path):
        self.config_path = config_path
        self.data = self._load_config()

    def _load_config(self):
        """Loads the JSON file into the class memory."""
        if not Path(self.config_path).exists():
            print(f"ERROR: Config file not found at {self.config_path}")
            return {}
        with open(self.config_path, "r") as f:
            return json.load(f)

    def find_site_by_ip(self, mgmt_ip):
        """
        Scans all sites in the JSON to find which subnet the IP belongs to.
        This is the method your app.py is currently missing!
        """
        try:
            target_ip = ipaddress.ip_address(mgmt_ip)
            
            for site_key, site_info in self.data.items():
                net_addr = site_info.get("network_address")
                net_mask = site_info.get("subnet_mask")
                
                if net_addr and net_mask:
                    # strict=False allows host IPs to be checked against the network
                    network = ipaddress.ip_network(f"{net_addr}/{net_mask}", strict=False)
                    if target_ip in network:
                        return site_key, site_info
            
            return None, None
        except Exception as e:
            print(f"Subnet lookup error: {e}")
            return None, None

    def generate_hostname(self, mgmt_ip, template_name):
        """Generates a standardized hostname based on IP and hardware."""
        octets = mgmt_ip.split('.')
        # Uses last 3 octets: 172.22.18.241 -> 22-18-241
        suffix = "-".join(octets[1:]) 
        
        t_name = template_name.lower()
        if "6300" in t_name:
            prefix = "ae6300"
        elif "4100" in t_name:
            prefix = "ae4100i"
        else:
            prefix = "sw"
            
        return f"{prefix}-{suffix}"