"""虚拟机检测监视器
实现一个类 VMMonitor，仿函数接口：__call__() -> list[dict]
"""
from typing import List, Dict
import platform

try:
    import wmi
except Exception:
    wmi = None


class VMMonitor:
    """Windows-only VM detection monitor using python-wmi.

    简化实现：使用 WMI 查询 Manufacturer / Model，并检测常见虚拟化关键字；
    也进行网络接口 MAC OUI 检查。
    """
    def __init__(self):
        if platform.system().lower() != 'windows':
            raise RuntimeError('VMMonitor is Windows-only')
        # 预置一些可疑的系统产品名或制造商关键字
        self.suspect_keywords = [
            'virtual', 'vmware', 'vbox', 'virtualbox', 'kvm', 'microsoft corporation', 'qemu', 'xen'
        ]

    def _check_wmi_system(self) -> List[Dict]:
        alerts = []
        if not wmi:
            return alerts
        try:
            c = wmi.WMI()
            for sys in c.Win32_ComputerSystem():
                manufacturer = (sys.Manufacturer or '').lower()
                model = (sys.Model or '').lower()
                text = f"{manufacturer} {model}"
                for kw in self.suspect_keywords:
                    if kw in text:
                        alerts.append({'id': f'vm-dmi-{kw}', 'text': f"Detected virtualization keyword in WMI: {kw}", 'meta': {'matched': kw, 'manufacturer': manufacturer, 'model': model}})
        except Exception:
            pass
        return alerts

    def _check_mac_oui(self) -> List[Dict]:
        alerts = []
        try:
            # Use WMI to enumerate NICs
            if not wmi:
                return alerts
            c = wmi.WMI()
            macs = []
            for nic in c.Win32_NetworkAdapter(ConfigurationManagerErrorCode=0):
                mac = (getattr(nic, 'MACAddress', None) or '')
                if mac:
                    macs.append(mac)

            vm_ouis = ['00:05:69', '00:0c:29', '00:1c:14', '00:50:56', '08:00:27']
            for mac in macs:
                prefix = mac.replace('-', ':').lower()[0:8]
                if prefix in vm_ouis:
                    alerts.append({'id': f'vm-mac-{prefix}', 'text': f'Network MAC OUI suggests virtual NIC: {mac}', 'meta': {'mac': mac}})
        except Exception:
            pass
        return alerts

    def __call__(self) -> List[Dict]:
        alerts: List[Dict] = []
        alerts.extend(self._check_wmi_system())
        alerts.extend(self._check_mac_oui())
        return alerts

