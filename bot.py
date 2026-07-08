#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════╗
║                      🔥 SHADOW OSINT v5.0 - FINAL 🔥                    ║
║                  أقوى أداة استخبارات مفتوحة المصدر                        ║
║               المستخدم يتحمل المسؤولية القانونية كاملة                     ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import os, re, json, time, socket, ssl, base64, hashlib, secrets, asyncio, logging, threading, sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse, quote, urlencode
from functools import wraps
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import phonenumbers
from phonenumbers import carrier, geocoder, timezone as ph_timezone
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for

# ==================== التهيئة ====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SHADOW_OSINT")

web_app = Flask(__name__)
web_app.secret_key = secrets.token_hex(32)

PORT = int(os.environ.get("PORT", 8080))
NUMVERIFY_KEY = os.environ.get("NUMVERIFY_KEY", "")
ABSTRACT_API_KEY = os.environ.get("ABSTRACT_API_KEY", "")
VIRUSTOTAL_KEY = os.environ.get("VIRUSTOTAL_KEY", "")
SHODAN_KEY = os.environ.get("SHODAN_KEY", "")
IPINFO_TOKEN = os.environ.get("IPINFO_TOKEN", "")
ABUSEIPDB_KEY = os.environ.get("ABUSEIPDB_KEY", "")
DB_PATH = "shadow_osint.db"
executor = ThreadPoolExecutor(max_workers=10)
ua = UserAgent()

# ==================== قاعدة البيانات ====================
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT, scan_type TEXT, result TEXT,
                ip_address TEXT, user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE, password_hash TEXT,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS api_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT, request_data TEXT,
                ip_address TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

def db_execute(query, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(query, params)
        conn.commit()
        return cursor

def db_fetchone(query, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(query, params).fetchone()

def db_fetchall(query, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(query, params).fetchall()

# ==================== محرك الفحص المتكامل ====================
class ShadowEngine:
    def __init__(self):
        self.ua = UserAgent()
        self.session = httpx.Client(timeout=httpx.Timeout(15.0), follow_redirects=True)
    
    def _headers(self, extra=None):
        h = {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        if extra:
            h.update(extra)
        return h
    
    # ==================== فحص الهاتف ====================
    def scan_phone(self, phone: str) -> Dict:
        results = {
            "phone": phone,
            "timestamp": datetime.now().isoformat(),
            "whatsapp": self._check_whatsapp(phone),
            "viber": self._check_viber(phone),
            "signal": self._check_signal(phone),
            "telegram_hint": self._check_telegram_hint(phone),
            "truecaller": self._check_truecaller(phone),
            "carrier_info": self._check_carrier(phone),
            "numverify": self._check_numverify(phone),
            "facebook": self._check_facebook(phone),
            "instagram": self._check_instagram(phone),
            "snapchat": self._check_snapchat(phone),
            "linkedin": self._check_linkedin_phone(phone),
            "email_leaks": self._check_email_leaks(phone)
        }
        return results
    
    def _check_whatsapp(self, phone):
        clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        methods = {}
        try:
            r = httpx.get(f"https://wa.me/{clean}", headers=self._headers(), timeout=10, follow_redirects=True)
            methods["wa_me"] = "Continue to Chat" in r.text or "متابعة إلى الدردشة" in r.text
        except:
            methods["wa_me"] = None
        try:
            r = httpx.post("https://v.whatsapp.com/v2/exist", 
                          json={"cc": phone[:3] if phone.startswith("+") else "", 
                                "in": phone[3:] if phone.startswith("+") else phone, "to": phone},
                          headers={"User-Agent": "WhatsApp/2.24.2.17 Android"}, timeout=10)
            methods["api"] = r.status_code == 200
        except:
            methods["api"] = None
        return {"exists": methods.get("wa_me") or methods.get("api"), "methods": methods}
    
    def _check_viber(self, phone):
        try:
            r = httpx.post("https://api.viber.com/api/v2/check", json={"phone": phone}, 
                          headers=self._headers(), timeout=10)
            return {"exists": r.json().get("exists", False)} if r.status_code == 200 else {"exists": None}
        except:
            return {"exists": None}
    
    def _check_signal(self, phone):
        try:
            r = httpx.get(f"https://api.signal.org/v1/accounts/{phone}", 
                         headers={"User-Agent": "Signal-Android/6.0"}, timeout=10)
            return {"exists": r.status_code == 200}
        except:
            return {"exists": None}
    
    def _check_telegram_hint(self, phone):
        try:
            r = httpx.post("https://my.telegram.org/auth/send_password", 
                          data={"phone": phone}, headers=self._headers(), timeout=10)
            return {"account_exists": "code" in r.text.lower() or "password" in r.text.lower()}
        except:
            return {"account_exists": None}
    
    def _check_truecaller(self, phone):
        clean = phone.replace("+", "")
        try:
            r = httpx.get(f"https://www.truecaller.com/search/eg/{clean}", 
                         headers={**self._headers(), "Accept-Language": "ar,en;q=0.9"}, timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'lxml')
                for script in soup.find_all("script", type="application/ld+json"):
                    if script.string:
                        try:
                            data = json.loads(script.string)
                            name = data.get("name", "")
                            if name:
                                return {"found": True, "name": name, "spam_score": data.get("spamScore", 0)}
                        except:
                            pass
                return {"found": False}
        except:
            return {"error": "تعذر الفحص"}
    
    def _check_carrier(self, phone):
        try:
            parsed = phonenumbers.parse(phone)
            return {
                "valid": phonenumbers.is_valid_number(parsed),
                "possible": phonenumbers.is_possible_number(parsed),
                "country": geocoder.description_for_number(parsed, "en"),
                "carrier": carrier.name_for_number(parsed, "en"),
                "timezone": list(ph_timezone.time_zones_for_number(parsed)),
                "national_format": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
                "international_format": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
                "country_code": parsed.country_code,
                "national_number": parsed.national_number,
                "number_type": str(phonenumbers.number_type(parsed))
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _check_numverify(self, phone):
        if not NUMVERIFY_KEY:
            return {"status": "no_api_key"}
        try:
            r = httpx.get("http://apilayer.net/api/validate", params={
                "access_key": NUMVERIFY_KEY, "number": phone, "format": 1
            }, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return {
                    "valid": data.get("valid"),
                    "country": data.get("country_name"),
                    "location": data.get("location"),
                    "carrier": data.get("carrier"),
                    "line_type": data.get("line_type")
                }
        except:
            pass
        return {"status": "failed"}
    
    def _check_facebook(self, phone):
        try:
            r = httpx.get("https://www.facebook.com/login/identify",
                         params={"ctx": "recover"}, headers=self._headers(), timeout=10)
            return {"possibly_linked": r.status_code == 200}
        except:
            return {"possibly_linked": None}
    
    def _check_instagram(self, phone):
        try:
            r = httpx.get(f"https://www.instagram.com/accounts/account_recovery/",
                         headers=self._headers(), timeout=10)
            soup = BeautifulSoup(r.text, 'lxml')
            csrf = soup.find("input", {"name": "csrfmiddlewaretoken"})
            if csrf:
                r2 = httpx.post("https://www.instagram.com/api/v1/accounts/send_signup_sms/",
                               data={"phone_number": phone, "device_id": hashlib.md5(phone.encode()).hexdigest()},
                               headers={**self._headers(), "X-CSRFToken": csrf.get("value", "")}, timeout=10)
                return {"possibly_linked": r2.status_code == 200}
        except:
            return {"possibly_linked": None}
    
    def _check_snapchat(self, phone):
        try:
            r = httpx.post("https://accounts.snapchat.com/accounts/phone_verify",
                          json={"phone": phone}, headers=self._headers(), timeout=10)
            return {"possibly_linked": r.status_code == 200}
        except:
            return {"possibly_linked": None}
    
    def _check_linkedin_phone(self, phone):
        try:
            r = httpx.get("https://www.linkedin.com/uas/request-password-reset",
                         headers=self._headers(), timeout=10)
            return {"checked": True}
        except:
            return {"checked": False}
    
    def _check_email_leaks(self, phone):
        """فحص إذا كان الرقم مرتبط ببريد مسرب"""
        try:
            # بحث في Have I Been Pwned بالرقم
            r = httpx.get(f"https://haveibeenpwned.com/api/v3/pasteaccount/{phone}",
                         headers={**self._headers(), "hibp-api-key": os.environ.get("HIBP_KEY", "")}, timeout=10)
            if r.status_code == 200:
                return {"leaks_found": len(r.json())}
            return {"leaks_found": 0}
        except:
            return {"error": "API not available"}
    
    # ==================== فحص IP ====================
    def scan_ip(self, ip: str) -> Dict:
        results = {"ip": ip, "timestamp": datetime.now().isoformat()}
        
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                "ipinfo": pool.submit(self._ipinfo, ip),
                "geoip": pool.submit(self._geoip, ip),
                "abuseipdb": pool.submit(self._abuseipdb, ip),
                "shodan": pool.submit(self._shodan, ip),
                "ports": pool.submit(self._port_scan, ip),
                "dns": pool.submit(self._reverse_dns, ip),
                "isp": pool.submit(self._isp_info, ip)
            }
            
            for key, future in futures.items():
                try:
                    result = future.result(timeout=10)
                    if result:
                        results[key] = result
                except:
                    pass
        
        return results
    
    def _ipinfo(self, ip):
        try:
            url = f"https://ipinfo.io/{ip}/json"
            if IPINFO_TOKEN:
                url += f"?token={IPINFO_TOKEN}"
            r = httpx.get(url, timeout=10)
            return r.json() if r.status_code == 200 else None
        except:
            return None
    
    def _geoip(self, ip):
        try:
            r = httpx.get(f"http://ip-api.com/json/{ip}?fields=66846719", timeout=10)
            return r.json() if r.status_code == 200 else None
        except:
            return None
    
    def _abuseipdb(self, ip):
        if not ABUSEIPDB_KEY:
            return None
        try:
            r = httpx.get("https://api.abuseipdb.com/api/v2/check",
                         params={"ipAddress": ip, "maxAgeInDays": 90, "verbose": ""},
                         headers={"Key": ABUSEIPDB_KEY, "Accept": "application/json"}, timeout=10)
            return r.json() if r.status_code == 200 else None
        except:
            return None
    
    def _shodan(self, ip):
        if not SHODAN_KEY:
            return None
        try:
            r = httpx.get(f"https://api.shodan.io/shodan/host/{ip}",
                         params={"key": SHODAN_KEY, "minify": "true"}, timeout=10)
            return r.json() if r.status_code == 200 else None
        except:
            return None
    
    def _port_scan(self, ip):
        ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1433, 3306, 3389, 5900, 8080, 8443]
        open_ports = []
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                if sock.connect_ex((ip, port)) == 0:
                    service = {21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP", 
                              110: "POP3", 135: "RPC", 139: "NetBIOS", 143: "IMAP", 443: "HTTPS",
                              445: "SMB", 993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 3306: "MySQL",
                              3389: "RDP", 5900: "VNC", 8080: "HTTP-Alt", 8443: "HTTPS-Alt"}
                    open_ports.append({"port": port, "service": service.get(port, "Unknown")})
                sock.close()
            except:
                pass
        return {"open_ports": open_ports, "total_scanned": len(ports)}
    
    def _reverse_dns(self, ip):
        try:
            return socket.gethostbyaddr(ip)[0]
        except:
            return None
    
    def _isp_info(self, ip):
        try:
            r = httpx.get(f"https://api.ipapi.is/?q={ip}", timeout=10)
            return r.json() if r.status_code == 200 else None
        except:
            return None
    
    # ==================== فحص URL ====================
    def scan_url(self, url: str) -> Dict:
        results = {"url": url, "timestamp": datetime.now().isoformat()}
        
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                "ssl": pool.submit(self._ssl_check, url),
                "headers": pool.submit(self._headers_check, url),
                "virustotal": pool.submit(self._virustotal, url),
                "technology": pool.submit(self._tech_detect, url),
                "whois": pool.submit(self._whois_lookup, url),
                "redirects": pool.submit(self._redirect_chain, url),
                "content": pool.submit(self._content_analysis, url)
            }
            
            for key, future in futures.items():
                try:
                    result = future.result(timeout=15)
                    if result:
                        results[key] = result
                except:
                    pass
        
        return results
    
    def _ssl_check(self, url):
        try:
            hostname = urlparse(url).hostname or url
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    return {
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                        "subject": dict(x[0] for x in cert.get("subject", [])),
                        "valid_from": cert.get("notBefore"),
                        "valid_to": cert.get("notAfter"),
                        "serial": cert.get("serialNumber"),
                        "san": cert.get("subjectAltName", []),
                        "version": cert.get("version"),
                        "days_remaining": (datetime.strptime(cert.get("notAfter"), "%b %d %H:%M:%S %Y %Z") - datetime.now()).days if cert.get("notAfter") else None
                    }
        except Exception as e:
            return {"error": str(e)}
    
    def _headers_check(self, url):
        try:
            r = httpx.get(url, headers=self._headers(), timeout=10, follow_redirects=True)
            security = {
                "Strict-Transport-Security": r.headers.get("Strict-Transport-Security", ""),
                "Content-Security-Policy": r.headers.get("Content-Security-Policy", ""),
                "X-Frame-Options": r.headers.get("X-Frame-Options", ""),
                "X-Content-Type-Options": r.headers.get("X-Content-Type-Options", ""),
                "X-XSS-Protection": r.headers.get("X-XSS-Protection", ""),
                "Referrer-Policy": r.headers.get("Referrer-Policy", ""),
                "Permissions-Policy": r.headers.get("Permissions-Policy", ""),
                "Cache-Control": r.headers.get("Cache-Control", ""),
            }
            missing = [k for k, v in security.items() if not v]
            return {
                "security_headers": security,
                "missing_headers": missing,
                "security_score": len([v for v in security.values() if v]) * 100 // len(security),
                "server": r.headers.get("Server", "Unknown"),
                "powered_by": r.headers.get("X-Powered-By", "Unknown"),
                "status_code": r.status_code,
                "content_type": r.headers.get("Content-Type", ""),
                "cookies": len(r.cookies)
            }
        except:
            return None
    
    def _virustotal(self, url):
        if not VIRUSTOTAL_KEY:
            return None
        try:
            url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
            r = httpx.get(f"https://www.virustotal.com/api/v3/urls/{url_id}",
                         headers={"x-apikey": VIRUSTOTAL_KEY}, timeout=15)
            if r.status_code == 200:
                stats = r.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                return {
                    "malicious": stats.get("malicious", 0),
                    "suspicious": stats.get("suspicious", 0),
                    "harmless": stats.get("harmless", 0),
                    "undetected": stats.get("undetected", 0),
                    "timeout": stats.get("timeout", 0)
                }
        except:
            pass
        return None
    
    def _tech_detect(self, url):
        try:
            r = httpx.get(url, headers=self._headers(), timeout=10)
            soup = BeautifulSoup(r.text, 'lxml')
            tech = []
            
            # Framework detection
            if soup.find("meta", {"name": "generator"}):
                tech.append({"type": "CMS", "name": soup.find("meta", {"name": "generator"}).get("content", "")})
            
            # JavaScript frameworks
            scripts = soup.find_all("script", src=True)
            for script in scripts:
                src = script.get("src", "")
                if "jquery" in src.lower():
                    tech.append({"type": "JS Library", "name": "jQuery"})
                if "react" in src.lower():
                    tech.append({"type": "JS Framework", "name": "React"})
                if "vue" in src.lower():
                    tech.append({"type": "JS Framework", "name": "Vue.js"})
                if "angular" in src.lower():
                    tech.append({"type": "JS Framework", "name": "Angular"})
                if "bootstrap" in src.lower():
                    tech.append({"type": "CSS Framework", "name": "Bootstrap"})
            
            # Analytics
            if "googletagmanager" in r.text.lower() or "gtag" in r.text.lower():
                tech.append({"type": "Analytics", "name": "Google Analytics"})
            if "facebook.com/tr" in r.text.lower():
                tech.append({"type": "Analytics", "name": "Facebook Pixel"})
            
            return {"detected": tech, "count": len(tech)}
        except:
            return None
    
    def _whois_lookup(self, url):
        try:
            hostname = urlparse(url).hostname or url
            r = httpx.get(f"https://whois.freeaiapi.xyz/?domain={hostname}&format=json", timeout=10)
            return r.json() if r.status_code == 200 else None
        except:
            return None
    
    def _redirect_chain(self, url):
        try:
            chain = []
            current = url
            for i in range(5):
                r = httpx.get(current, headers=self._headers(), timeout=5, follow_redirects=False)
                chain.append({"url": current, "status": r.status_code})
                if r.status_code in (301, 302, 307, 308):
                    current = r.headers.get("Location", "")
                    if not current:
                        break
                else:
                    break
            return {"chain": chain, "hops": len(chain)}
        except:
            return None
    
    def _content_analysis(self, url):
        try:
            r = httpx.get(url, headers=self._headers(), timeout=10, follow_redirects=True)
            soup = BeautifulSoup(r.text, 'lxml')
            return {
                "title": soup.title.string if soup.title else "No title",
                "meta_description": soup.find("meta", {"name": "description"}).get("content", "") if soup.find("meta", {"name": "description"}) else "",
                "forms_count": len(soup.find_all("form")),
                "links_count": len(soup.find_all("a")),
                "images_count": len(soup.find_all("img")),
                "scripts_count": len(soup.find_all("script")),
                "has_login_form": bool(soup.find("input", {"type": "password"})),
                "has_search": bool(soup.find("input", {"type": "search"})),
                "language": soup.find("html").get("lang", "Unknown") if soup.find("html") else "Unknown"
            }
        except:
            return None

engine = ShadowEngine()

# ==================== HTML Template ====================
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="SHADOW OSINT - أقوى أداة استخبارات مفتوحة المصدر">
    <title>SHADOW OSINT v5.0 - أداة الاستخبارات المفتوحة</title>
    <style>
        :root {
            --bg: #0a0a0a;
            --surface: #141414;
            --primary: #e94560;
            --primary-dark: #c73e54;
            --text: #e0e0e0;
            --text-secondary: #888;
            --border: #2a2a2a;
            --success: #4caf50;
            --warning: #ff9800;
            --danger: #f44336;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Tahoma, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            line-height: 1.6;
        }
        
        /* Header */
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            padding: 25px 20px;
            text-align: center;
            border-bottom: 2px solid var(--primary);
            position: relative;
            overflow: hidden;
        }
        .header::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(233,69,96,0.03) 2px, rgba(233,69,96,0.03) 4px);
        }
        .header h1 {
            font-size: 2.8em;
            color: var(--primary);
            text-shadow: 0 0 20px rgba(233,69,96,0.5), 0 0 40px rgba(233,69,96,0.3);
            letter-spacing: 2px;
            position: relative;
            z-index: 1;
        }
        .header p {
            color: var(--text-secondary);
            margin-top: 8px;
            font-size: 14px;
            position: relative;
            z-index: 1;
        }
        
        /* Container */
        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 20px 15px;
        }
        
        /* Navigation */
        .nav {
            display: flex;
            justify-content: center;
            gap: 5px;
            padding: 15px;
            flex-wrap: wrap;
            position: sticky;
            top: 0;
            background: var(--bg);
            z-index: 100;
            border-bottom: 1px solid var(--border);
        }
        .nav a {
            padding: 10px 22px;
            background: var(--surface);
            color: var(--text);
            text-decoration: none;
            border-radius: 6px;
            border: 1px solid var(--border);
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        .nav a:hover {
            background: var(--primary-dark);
            border-color: var(--primary);
            color: white;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(233,69,96,0.3);
        }
        .nav a.active {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
            box-shadow: 0 0 15px rgba(233,69,96,0.4);
        }
        
        /* Cards */
        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 25px;
            margin: 20px 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .card h2 {
            color: var(--primary);
            margin-bottom: 20px;
            font-size: 1.4em;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .card h3 {
            color: var(--text);
            margin: 15px 0 10px;
            font-size: 1.1em;
        }
        
        /* Inputs */
        .input-group {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }
        input, textarea, select {
            flex: 1;
            padding: 12px 16px;
            background: var(--bg);
            border: 2px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 15px;
            font-family: inherit;
            transition: all 0.3s ease;
        }
        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(233,69,96,0.1);
        }
        
        /* Buttons */
        .btn {
            padding: 12px 30px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 15px;
            font-weight: 600;
            transition: all 0.3s ease;
            white-space: nowrap;
        }
        .btn:hover {
            background: var(--primary-dark);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(233,69,96,0.4);
        }
        .btn:active { transform: translateY(0); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .btn-outline {
            background: transparent;
            border: 2px solid var(--primary);
            color: var(--primary);
        }
        .btn-outline:hover { background: var(--primary); color: white; }
        
        /* Results */
        .result-box {
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            margin-top: 20px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-height: 500px;
            overflow-y: auto;
            display: none;
            line-height: 1.4;
        }
        .result-box.show { display: block; }
        .result-box.success { border-color: var(--success); }
        .result-box.error { border-color: var(--danger); }
        
        /* Loading */
        .loading {
            text-align: center;
            padding: 20px;
            display: none;
        }
        .loading.show { display: block; }
        .spinner {
            border: 3px solid var(--border);
            border-top: 3px solid var(--primary);
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        /* Badges */
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
            margin: 2px;
        }
        .badge-success { background: var(--success); color: white; }
        .badge-danger { background: var(--danger); color: white; }
        .badge-warning { background: var(--warning); color: black; }
        .badge-info { background: #2196f3; color: white; }
        
        /* Tables */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }
        th, td {
            padding: 12px;
            border: 1px solid var(--border);
            text-align: right;
            font-size: 13px;
        }
        th {
            background: var(--surface);
            color: var(--primary);
            font-weight: 600;
        }
        td { background: var(--bg); }
        tr:hover td { background: #1a1a1a; }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .stat-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            transition: all 0.3s ease;
        }
        .stat-card:hover {
            border-color: var(--primary);
            transform: translateY(-2px);
        }
        .stat-card h3 {
            color: var(--text-secondary);
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .stat-card .value {
            color: var(--primary);
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }
        
        /* Footer */
        .footer {
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            border-top: 1px solid var(--border);
            margin-top: 40px;
            font-size: 12px;
        }
        .footer a { color: var(--primary); text-decoration: none; }
        
        /* Responsive */
        @media (max-width: 768px) {
            .header h1 { font-size: 2em; }
            .input-group { flex-direction: column; }
            .nav { flex-direction: column; }
            .nav a { text-align: center; }
            .stats-grid { grid-template-columns: 1fr 1fr; }
        }
        @media (max-width: 480px) {
            .header h1 { font-size: 1.6em; }
            .stats-grid { grid-template-columns: 1fr; }
            .card { padding: 15px; }
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg); }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--primary); }
        
        /* Code blocks */
        code {
            background: #1a1a1a;
            padding: 2px 6px;
            border-radius: 3px;
            color: var(--primary);
            font-family: 'Courier New', monospace;
        }
        pre {
            background: var(--bg);
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
            border: 1px solid var(--border);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔥 SHADOW OSINT</h1>
        <p>أداة الاستخبارات المفتوحة | فحص الأرقام - IP - الروابط - الإيميلات</p>
    </div>
    
    <div class="nav">
        <a href="/" class="{{ 'active' if page == 'phone' else '' }}">📱 فحص رقم</a>
        <a href="/ip" class="{{ 'active' if page == 'ip' else '' }}">🌐 فحص IP</a>
        <a href="/url" class="{{ 'active' if page == 'url' else '' }}">🔗 فحص رابط</a>
        <a href="/email" class="{{ 'active' if page == 'email' else '' }}">📧 فحص بريد</a>
        <a href="/api" class="{{ 'active' if page == 'api' else '' }}">⚡ API</a>
        <a href="/stats" class="{{ 'active' if page == 'stats' else '' }}">📊 إحصائيات</a>
    </div>
    
    <div class="container">
        {{ content|safe }}
    </div>
    
    <div class="footer">
        <p>⚠️ <strong>تنبيه:</strong> هذه الأداة للأغراض التعليمية والبحثية فقط. المستخدم يتحمل المسؤولية القانونية الكاملة عن استخدامه.</p>
        <p>SHADOW OSINT v5.0 | <a href="/api">API Docs</a> | <a href="/stats">Stats</a></p>
    </div>
    
    <script>
        const API = {
            phone: '/api/scan/phone',
            ip: '/api/scan/ip',
            url: '/api/scan/url',
            email: '/api/scan/email'
        };
        
        async function scan(type) {
            const inputId = type + '-input';
            const loadingId = type + '-loading';
            const resultId = type + '-result';
            
            const input = document.getElementById(inputId);
            if (!input || !input.value.trim()) {
                alert('الرجاء إدخال ' + (type === 'phone' ? 'رقم الهاتف' : type.toUpperCase()));
                return;
            }
            
            const value = input.value.trim();
            const loading = document.getElementById(loadingId);
            const result = document.getElementById(resultId);
            
            loading.classList.add('show');
            result.classList.remove('show', 'success', 'error');
            result.innerHTML = '';
            
            try {
                const body = {};
                body[type] = value;
                
                const resp = await fetch(API[type], {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });
                
                const data = await resp.json();
                
                if (resp.ok) {
                    result.innerHTML = type === 'phone' ? formatPhoneResult(data) : 
                                      type === 'ip' ? formatIPResult(data) :
                                      type === 'url' ? formatURLResult(data) :
                                      JSON.stringify(data, null, 2);
                    result.classList.add('success');
                } else {
                    result.innerHTML = '<span style="color:#f44336">❌ ' + (data.error || 'خطأ غير معروف') + '</span>';
                    result.classList.add('error');
                }
                result.classList.add('show');
            } catch(e) {
                result.innerHTML = '<span style="color:#f44336">❌ خطأ في الاتصال: ' + e.message + '</span>';
                result.classList.add('error', 'show');
            } finally {
                loading.classList.remove('show');
            }
        }
        
        function formatPhoneResult(d) {
            let h = '<h3 style="color:#e94560;margin-bottom:15px;">📱 نتيجة فحص: ' + d.phone + '</h3>';
            
            // WhatsApp
            const wa = d.whatsapp || {};
            h += '<div style="margin:10px 0;"><strong>💬 واتساب:</strong> ';
            h += wa.exists === true ? '<span class="badge badge-success">✅ موجود</span>' :
                 wa.exists === false ? '<span class="badge badge-danger">❌ غير مسجل</span>' :
                 '<span class="badge badge-warning">⚠️ غير معروف</span>';
            h += '</div>';
            
            // Viber
            const vb = d.viber || {};
            h += '<div style="margin:10px 0;"><strong>📞 Viber:</strong> ';
            h += vb.exists === true ? '<span class="badge badge-success">✅ موجود</span>' :
                 vb.exists === false ? '<span class="badge badge-danger">❌ غير مسجل</span>' :
                 '<span class="badge badge-warning">⚠️ غير معروف</span>';
            h += '</div>';
            
            // Signal
            const sg = d.signal || {};
            h += '<div style="margin:10px 0;"><strong>🔒 Signal:</strong> ';
            h += sg.exists === true ? '<span class="badge badge-success">✅ موجود</span>' :
                 sg.exists === false ? '<span class="badge badge-danger">❌ غير مسجل</span>' :
                 '<span class="badge badge-warning">⚠️ غير معروف</span>';
            h += '</div>';
            
            // Telegram
            const tg = d.telegram_hint || {};
            h += '<div style="margin:10px 0;"><strong>📡 تيليجرام:</strong> ';
            h += tg.account_exists === true ? '<span class="badge badge-success">✅ محتمل</span>' :
                 tg.account_exists === false ? '<span class="badge badge-danger">❌ غير موجود</span>' :
                 '<span class="badge badge-warning">⚠️ غير معروف</span>';
            h += '</div>';
            
            // Truecaller
            const tc = d.truecaller || {};
            h += '<div style="margin:10px 0;"><strong>👤 Truecaller:</strong> ';
            h += tc.found ? tc.name : '<span class="badge badge-warning">غير موجود</span>';
            h += '</div>';
            
            // Carrier
            const cr = d.carrier_info || {};
            if (!cr.error) {
                h += '<br><strong>📶 معلومات الشبكة:</strong><br>';
                h += '<table><tr><th>الخاصية</th><th>القيمة</th></tr>';
                h += '<tr><td>الشبكة</td><td>' + (cr.carrier || 'غير معروف') + '</td></tr>';
                h += '<tr><td>الدولة</td><td>' + (cr.country || 'غير معروف') + '</td></tr>';
                h += '<tr><td>النوع</td><td>' + (cr.number_type || 'غير معروف') + '</td></tr>';
                h += '<tr><td>صالح</td><td>' + (cr.valid ? '<span class="badge badge-success">نعم</span>' : '<span class="badge badge-danger">لا</span>') + '</td></tr>';
                h += '<tr><td>الصيغة الدولية</td><td>' + (cr.international_format || '') + '</td></tr>';
                h += '</table>';
            }
            
            // NumVerify
            const nv = d.numverify || {};
            if (nv.valid !== undefined) {
                h += '<br><strong>🔍 NumVerify:</strong><br>';
                h += '<table><tr><th>الخاصية</th><th>القيمة</th></tr>';
                h += '<tr><td>الدولة</td><td>' + (nv.country || '-') + '</td></tr>';
                h += '<tr><td>المزود</td><td>' + (nv.carrier || '-') + '</td></tr>';
                h += '<tr><td>النوع</td><td>' + (nv.line_type || '-') + '</td></tr>';
                h += '<tr><td>الموقع</td><td>' + (nv.location || '-') + '</td></tr>';
                h += '</table>';
            }
            
            // Social
            h += '<br><strong>📱 وسائل التواصل:</strong><br>';
            const fb = d.facebook || {};
            const ig = d.instagram || {};
            const sc = d.snapchat || {};
            h += 'فيسبوك: ' + (fb.possibly_linked ? '<span class="badge badge-success">✅ محتمل</span>' : '<span class="badge badge-warning">⚠️ غير معروف</span>') + ' | ';
            h += 'انستجرام: ' + (ig.possibly_linked ? '<span class="badge badge-success">✅ محتمل</span>' : '<span class="badge badge-warning">⚠️ غير معروف</span>') + ' | ';
            h += 'سناب شات: ' + (sc.possibly_linked ? '<span class="badge badge-success">✅ محتمل</span>' : '<span class="badge badge-warning">⚠️ غير معروف</span>');
            
            return h;
        }
        
        function formatIPResult(d) {
            let h = '<h3 style="color:#e94560;margin-bottom:15px;">🌐 نتيجة فحص: ' + d.ip + '</h3>';
            
            // IPInfo
            const ipi = d.ipinfo || {};
            if (ipi.city) {
                h += '<strong>📍 الموقع (IPInfo):</strong><br>';
                h += 'المدينة: ' + (ipi.city || '-') + ' | المنطقة: ' + (ipi.region || '-') + ' | الدولة: ' + (ipi.country || '-') + '<br>';
                h += 'المنظمة: ' + (ipi.org || '-') + ' | الرمز البريدي: ' + (ipi.postal || '-') + '<br>';
                h += 'الإحداثيات: ' + (ipi.loc || '-') + '<br><br>';
            }
            
            // AbuseIPDB
            const ab = d.abuseipdb || {};
            if (ab.data) {
                const ad = ab.data;
                h += '<strong>⚠️ AbuseIPDB:</strong><br>';
                h += 'نسبة الإساءة: <span class="badge ' + (ad.abuseConfidenceScore > 50 ? 'badge-danger' : 'badge-success') + '">' + (ad.abuseConfidenceScore || 0) + '%</span><br>';
                h += 'عدد البلاغات: ' + (ad.totalReports || 0) + '<br>';
                h += 'النطاق: ' + (ad.usageType || '-') + '<br>';
                h += 'ISP: ' + (ad.isp || '-') + '<br><br>';
            }
            
            // Ports
            const ports = d.ports || {};
            if (ports.open_ports && ports.open_ports.length > 0) {
                h += '<strong>🔓 المنافذ المفتوحة (' + ports.open_ports.length + '/' + ports.total_scanned + '):</strong><br>';
                ports.open_ports.forEach(p => {
                    h += '<span class="badge badge-warning">' + p.port + ' (' + p.service + ')</span> ';
                });
                h += '<br><br>';
            } else {
                h += '<strong>🔒 المنافذ:</strong> لا توجد منافذ مفتوحة (' + (ports.total_scanned || 0) + ' تم فحصها)<br><br>';
            }
            
            // DNS
            if (d.dns) {
                h += '<strong>🔍 Reverse DNS:</strong> ' + d.dns + '<br><br>';
            }
            
            return h;
        }
        
        function formatURLResult(d) {
            let h = '<h3 style="color:#e94560;margin-bottom:15px;">🔗 نتيجة فحص: ' + d.url + '</h3>';
            
            // SSL
            const ssl = d.ssl || {};
            if (!ssl.error) {
                h += '<strong>🔒 SSL Certificate:</strong><br>';
                h += 'المصدر: ' + (ssl.issuer?.organizationName || ssl.issuer?.commonName || 'غير معروف') + '<br>';
                h += 'صالح من: ' + (ssl.valid_from || '-') + '<br>';
                h += 'صالح حتى: ' + (ssl.valid_to || '-') + '<br>';
                if (ssl.days_remaining !== undefined) {
                    h += 'الأيام المتبقية: <span class="badge ' + (ssl.days_remaining > 30 ? 'badge-success' : ssl.days_remaining > 7 ? 'badge-warning' : 'badge-danger') + '">' + ssl.days_remaining + ' يوم</span><br>';
                }
                h += '<br>';
            }
            
            // Headers
            const headers = d.headers || {};
            if (headers.security_score !== undefined) {
                h += '<strong>🛡️ أمان الرؤوس: <span class="badge ' + (headers.security_score >= 70 ? 'badge-success' : headers.security_score >= 40 ? 'badge-warning' : 'badge-danger') + '">' + headers.security_score + '%</span></strong><br>';
                h += 'السيرفر: ' + (headers.server || 'غير معروف') + '<br>';
                h += 'الحالة: ' + (headers.status_code || '-') + '<br>';
                if (headers.missing_headers && headers.missing_headers.length > 0) {
                    h += 'الرؤوس المفقودة: ' + headers.missing_headers.join(', ') + '<br>';
                }
                h += '<br>';
            }
            
            // VirusTotal
            const vt = d.virustotal || {};
            if (vt.malicious !== undefined) {
                h += '<strong>🦠 VirusTotal:</strong><br>';
                h += 'ضار: <span class="badge ' + (vt.malicious > 0 ? 'badge-danger' : 'badge-success') + '">' + vt.malicious + '</span> | ';
                h += 'مشبوه: <span class="badge badge-warning">' + vt.suspicious + '</span> | ';
                h += 'آمن: <span class="badge badge-success">' + vt.harmless + '</span><br><br>';
            }
            
            // Technology
            const tech = d.technology || {};
            if (tech.detected && tech.detected.length > 0) {
                h += '<strong>🔧 التقنيات المكتشفة:</strong><br>';
                tech.detected.forEach(t => {
                    h += '<span class="badge badge-info">' + t.type + ': ' + t.name + '</span> ';
                });
                h += '<br><br>';
            }
            
            // Content
            const content = d.content || {};
            if (content.title) {
                h += '<strong>📄 محتوى الصفحة:</strong><br>';
                h += 'العنوان: ' + content.title + '<br>';
                h += 'النماذج: ' + content.forms_count + ' | الروابط: ' + content.links_count + ' | الصور: ' + content.images_count + '<br>';
                h += 'يحتوي نموذج تسجيل: ' + (content.has_login_form ? '<span class="badge badge-warning">نعم</span>' : '<span class="badge badge-success">لا</span>') + '<br>';
                h += 'اللغة: ' + (content.language || 'غير معروف') + '<br>';
            }
            
            return h;
        }
        
        // Enter key to scan
        document.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const activeInput = document.activeElement;
                if (activeInput && activeInput.id) {
                    const type = activeInput.id.replace('-input', '');
                    if (['phone', 'ip', 'url', 'email'].includes(type)) {
                        scan(type);
                    }
                }
            }
        });
    </script>
</body>
</html>"""

# ==================== الصفحات ====================
PHONE_CONTENT = """
<div class="card">
    <h2>📱 فحص رقم الهاتف</h2>
    <p style="color:#888;margin-bottom:15px;">أدخل رقم الهاتف بصيغة دولية للفحص الشامل</p>
    <div class="input-group">
        <input type="tel" id="phone-input" placeholder="+201234567890" value="+20" autofocus>
        <button class="btn" onclick="scan('phone')">🔍 فحص شامل</button>
    </div>
    <div class="loading" id="phone-loading"><div class="spinner"></div><p>جاري الفحص الشامل... قد يستغرق 30-60 ثانية</p></div>
    <div class="result-box" id="phone-result"></div>
</div>
<div class="card">
    <h2>📊 آخر {{ scans|length }} فحص</h2>
    <div style="overflow-x:auto;">
        <table>
            <tr><th>الهدف</th><th>النوع</th><th>التاريخ</th></tr>
            {% for scan in scans %}
            <tr><td><code>{{ scan[0] }}</code></td><td>{{ scan[1] }}</td><td>{{ scan[2] }}</td></tr>
            {% endfor %}
        </table>
    </div>
</div>
"""

IP_CONTENT = """
<div class="card">
    <h2>🌐 فحص عنوان IP</h2>
    <p style="color:#888;margin-bottom:15px;">أدخل عنوان IP للفحص الأمني الشامل</p>
    <div class="input-group">
        <input type="text" id="ip-input" placeholder="8.8.8.8" autofocus>
        <button class="btn" onclick="scan('ip')">🔍 فحص شامل</button>
    </div>
    <div class="loading" id="ip-loading"><div class="spinner"></div><p>جاري فحص IP...</p></div>
    <div class="result-box" id="ip-result"></div>
</div>
"""

URL_CONTENT = """
<div class="card">
    <h2>🔗 فحص رابط</h2>
    <p style="color:#888;margin-bottom:15px;">أدخل رابط URL للفحص الأمني وتحليل الموقع</p>
    <div class="input-group">
        <input type="url" id="url-input" placeholder="https://example.com" autofocus>
        <button class="btn" onclick="scan('url')">🔍 فحص شامل</button>
    </div>
    <div class="loading" id="url-loading"><div class="spinner"></div><p>جاري فحص الرابط...</p></div>
    <div class="result-box" id="url-result"></div>
</div>
"""

EMAIL_CONTENT = """
<div class="card">
    <h2>📧 فحص البريد الإلكتروني</h2>
    <p style="color:#888;margin-bottom:15px;">أدخل البريد الإلكتروني للفحص</p>
    <div class="input-group">
        <input type="email" id="email-input" placeholder="user@example.com" autofocus>
        <button class="btn" onclick="scan('email')">🔍 فحص</button>
    </div>
    <div class="loading" id="email-loading"><div class="spinner"></div><p>جاري الفحص...</p></div>
    <div class="result-box" id="email-result"></div>
</div>
"""

API_CONTENT = """
<div class="card">
    <h2>⚡ API Documentation</h2>
    <p style="color:#888;margin-bottom:20px;">API بسيط وقوي لدمج أدواتنا في تطبيقاتك</p>
    
    <h3>📱 فحص رقم الهاتف</h3>
    <pre><code>POST /api/scan/phone
Content-Type: application/json

{"phone": "+201234567890"}</code></pre>
    <br>
    
    <h3>🌐 فحص IP</h3>
    <pre><code>POST /api/scan/ip
Content-Type: application/json

{"ip": "8.8.8.8"}</code></pre>
    <br>
    
    <h3>🔗 فحص رابط</h3>
    <pre><code>POST /api/scan/url
Content-Type: application/json

{"url": "https://example.com"}</code></pre>
    <br>
    
    <h3>📊 الإحصائيات</h3>
    <pre><code>GET /api/stats</code></pre>
</div>
"""

STATS_CONTENT = """
<div class="card">
    <h2>📊 إحصائيات المنصة</h2>
    <div class="stats-grid">
        <div class="stat-card">
            <h3>إجمالي الفحوصات</h3>
            <div class="value">{{ total_scans }}</div>
        </div>
        <div class="stat-card">
            <h3>فحص هواتف</h3>
            <div class="value">{{ phone_scans }}</div>
        </div>
        <div class="stat-card">
            <h3>فحص IP</h3>
            <div class="value">{{ ip_scans }}</div>
        </div>
        <div class="stat-card">
            <h3>فحص روابط</h3>
            <div class="value">{{ url_scans }}</div>
        </div>
    </div>
</div>
<div class="card">
    <h2>📋 آخر الفحوصات</h2>
    <div style="overflow-x:auto;">
        <table>
            <tr><th>الهدف</th><th>النوع</th><th>IP</th><th>التاريخ</th></tr>
            {% for scan in recent_scans %}
            <tr>
                <td><code>{{ scan[0] }}</code></td>
                <td><span class="badge badge-info">{{ scan[1] }}</span></td>
                <td>{{ scan[2] or '-' }}</td>
                <td>{{ scan[3] }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
</div>
"""

# ==================== Routes ====================
@web_app.route('/')
def home():
    scans = db_fetchall("SELECT target, scan_type, created_at FROM scans ORDER BY created_at DESC LIMIT 20")
    table_rows = ""
    for scan in scans:
        table_rows += f"<tr><td><code>{scan[0]}</code></td><td>{scan[1]}</td><td>{scan[2]}</td></tr>"
    content = PHONE_CONTENT.replace("{{ scans|length }}", str(len(scans)))
    content = content.replace("{% for scan in scans %}<tr><td><code>{{ scan[0] }}</code></td><td>{{ scan[1] }}</td><td>{{ scan[2] }}</td></tr>{% endfor %}", table_rows)
    html = HTML_TEMPLATE.replace("{{ page == 'phone' }}", "True").replace("{{ content|safe }}", content)
    for p in ['ip', 'url', 'email', 'api', 'stats']:
        html = html.replace(f"{{{{ page == '{p}' }}}}", "False")
    return html

@web_app.route('/ip')
def ip_page():
    html = HTML_TEMPLATE.replace("{{ page == 'ip' }}", "True").replace("{{ content|safe }}", IP_CONTENT)
    for p in ['phone', 'url', 'email', 'api', 'stats']:
        html = html.replace(f"{{{{ page == '{p}' }}}}", "False")
    return html

@web_app.route('/url')
def url_page():
    html = HTML_TEMPLATE.replace("{{ page == 'url' }}", "True").replace("{{ content|safe }}", URL_CONTENT)
    for p in ['phone', 'ip', 'email', 'api', 'stats']:
        html = html.replace(f"{{{{ page == '{p}' }}}}", "False")
    return html

@web_app.route('/email')
def email_page():
    html = HTML_TEMPLATE.replace("{{ page == 'email' }}", "True").replace("{{ content|safe }}", EMAIL_CONTENT)
    for p in ['phone', 'ip', 'url', 'api', 'stats']:
        html = html.replace(f"{{{{ page == '{p}' }}}}", "False")
    return html

@web_app.route('/api')
def api_page():
    html = HTML_TEMPLATE.replace("{{ page == 'api' }}", "True").replace("{{ content|safe }}", API_CONTENT)
    for p in ['phone', 'ip', 'url', 'email', 'stats']:
        html = html.replace(f"{{{{ page == '{p}' }}}}", "False")
    return html

@web_app.route('/stats')
def stats_page():
    total = db_fetchone("SELECT COUNT(*) FROM scans")[0]
    phone_scans = db_fetchone("SELECT COUNT(*) FROM scans WHERE scan_type='phone'")[0]
    ip_scans = db_fetchone("SELECT COUNT(*) FROM scans WHERE scan_type='ip'")[0]
    url_scans = db_fetchone("SELECT COUNT(*) FROM scans WHERE scan_type='url'")[0]
    
    recent = db_fetchall("SELECT target, scan_type, ip_address, created_at FROM scans ORDER BY created_at DESC LIMIT 20")
    table_rows = ""
    for scan in recent:
        table_rows += f"<tr><td><code>{scan[0]}</code></td><td><span class='badge badge-info'>{scan[1]}</span></td><td>{scan[2] or '-'}</td><td>{scan[3]}</td></tr>"
    
    content = STATS_CONTENT.replace("{{ total_scans }}", str(total))
    content = content.replace("{{ phone_scans }}", str(phone_scans))
    content = content.replace("{{ ip_scans }}", str(ip_scans))
    content = content.replace("{{ url_scans }}", str(url_scans))
    content = content.replace("{% for scan in recent_scans %}<tr><td><code>{{ scan[0] }}</code></td><td><span class='badge badge-info'>{{ scan[1] }}</span></td><td>{{ scan[2] or '-' }}</td><td>{{ scan[3] }}</td></tr>{% endfor %}", table_rows)
    
    html = HTML_TEMPLATE.replace("{{ page == 'stats' }}", "True").replace("{{ content|safe }}", content)
    for p in ['phone', 'ip', 'url', 'email', 'api']:
        html = html.replace(f"{{{{ page == '{p}' }}}}", "False")
    return html

# ==================== API Routes ====================
@web_app.route('/api/scan/phone', methods=['POST'])
def api_scan_phone():
    data = request.get_json() or {}
    phone = data.get('phone', '')
    if not phone:
        return jsonify({"error": "الرجاء إدخال رقم الهاتف"}), 400
    try:
        results = engine.scan_phone(phone)
        db_execute("INSERT INTO scans (target, scan_type, result, ip_address) VALUES (?, ?, ?, ?)",
                   (phone, 'phone', json.dumps(results, ensure_ascii=False), request.remote_addr or ''))
        return jsonify(results)
    except Exception as e:
        logger.error(f"Phone scan error: {e}")
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/scan/ip', methods=['POST'])
def api_scan_ip():
    data = request.get_json() or {}
    ip = data.get('ip', '')
    if not ip:
        return jsonify({"error": "الرجاء إدخال IP"}), 400
    try:
        results = engine.scan_ip(ip)
        db_execute("INSERT INTO scans (target, scan_type, result, ip_address) VALUES (?, ?, ?, ?)",
                   (ip, 'ip', json.dumps(results, ensure_ascii=False), request.remote_addr or ''))
        return jsonify(results)
    except Exception as e:
        logger.error(f"IP scan error: {e}")
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/scan/url', methods=['POST'])
def api_scan_url():
    data = request.get_json() or {}
    url = data.get('url', '')
    if not url:
        return jsonify({"error": "الرجاء إدخال رابط"}), 400
    try:
        results = engine.scan_url(url)
        db_execute("INSERT INTO scans (target, scan_type, result, ip_address) VALUES (?, ?, ?, ?)",
                   (url, 'url', json.dumps(results, ensure_ascii=False), request.remote_addr or ''))
        return jsonify(results)
    except Exception as e:
        logger.error(f"URL scan error: {e}")
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/scan/email', methods=['POST'])
def api_scan_email():
    data = request.get_json() or {}
    email = data.get('email', '')
    if not email:
        return jsonify({"error": "الرجاء إدخال بريد إلكتروني"}), 400
    try:
        # فحص أساسي للبريد
        domain = email.split('@')[-1] if '@' in email else ''
        results = {
            "email": email,
            "timestamp": datetime.now().isoformat(),
            "valid_format": bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email)),
            "domain": domain,
            "disposable": domain in ['tempmail.com', '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'yopmail.com', 'throwaway.email'],
            "mx_check": None
        }
        # فحص MX
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'MX')
            results["mx_check"] = bool(answers)
        except:
            results["mx_check"] = False
        
        db_execute("INSERT INTO scans (target, scan_type, result, ip_address) VALUES (?, ?, ?, ?)",
                   (email, 'email', json.dumps(results, ensure_ascii=False), request.remote_addr or ''))
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/stats')
def api_stats():
    total = db_fetchone("SELECT COUNT(*) FROM scans")[0]
    phone = db_fetchone("SELECT COUNT(*) FROM scans WHERE scan_type='phone'")[0]
    ip = db_fetchone("SELECT COUNT(*) FROM scans WHERE scan_type='ip'")[0]
    url = db_fetchone("SELECT COUNT(*) FROM scans WHERE scan_type='url'")[0]
    return jsonify({
        "total_scans": total,
        "phone_scans": phone,
        "ip_scans": ip,
        "url_scans": url,
        "version": "5.0.0",
        "status": "operational"
    })

@web_app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@web_app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@web_app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500

# ==================== التشغيل ====================
def main():
    init_db()
    
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║                   🔥 SHADOW OSINT v5.0 - FINAL 🔥                       ║
║               أقوى أداة استخبارات مفتوحة المصدر                           ║
║            المستخدم يتحمل المسؤولية القانونية كاملة                        ║
╚══════════════════════════════════════════════════════════════════════════╝
    """)
    print(f"🌐 الموقع: http://0.0.0.0:{PORT}")
    print(f"📱 NumVerify: {'✅' if NUMVERIFY_KEY else '❌'}")
    print(f"🛡️ VirusTotal: {'✅' if VIRUSTOTAL_KEY else '❌'}")
    print(f"🔍 Shodan: {'✅' if SHODAN_KEY else '❌'}")
    print(f"⚠️ AbuseIPDB: {'✅' if ABUSEIPDB_KEY else '❌'}")
    print("═" * 70)
    print("⚡ جاهز للانطلاق...")
    
    web_app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)

if __name__ == "__main__":
    main()
