#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🔥 SHADOW OSINT v6.0 - ULTIMATE 🔥                       ║
║            أقوى موقع استخبارات وفحص شامل في العالم العربي                     ║
║                المستخدم يتحمل المسؤولية القانونية كاملة                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os, re, json, time, socket, ssl, base64, hashlib, secrets, sqlite3, random
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote
from flask import Flask, render_template_string, request, jsonify
from concurrent.futures import ThreadPoolExecutor

# ==================== Flask ====================
web_app = Flask(__name__)
web_app.secret_key = secrets.token_hex(32)
PORT = int(os.environ.get("PORT", 8080))
executor = ThreadPoolExecutor(max_workers=10)

# ==================== API Keys ====================
NUMVERIFY_KEY = os.environ.get("NUMVERIFY_KEY", "")
VIRUSTOTAL_KEY = os.environ.get("VIRUSTOTAL_KEY", "")
SHODAN_KEY = os.environ.get("SHODAN_KEY", "")
IPINFO_TOKEN = os.environ.get("IPINFO_TOKEN", "")
ABSTRACT_API_KEY = os.environ.get("ABSTRACT_API_KEY", "")

# ==================== Database ====================
DB = "shadow.db"

def init_db():
    with sqlite3.connect(DB) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT, type TEXT, data TEXT,
                ip TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE, password TEXT,
                is_admin INTEGER DEFAULT 0
            );
        """)
        conn.commit()

def db(query, params=(), fetch=False):
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query, params)
        conn.commit()
        return [dict(r) for r in cur.fetchall()] if fetch else cur

# ==================== الفحص الشامل ====================
class UltimateScanner:
    def __init__(self):
        self.ua_list = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
            "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15"
        ]
    
    def ua(self):
        return random.choice(self.ua_list)
    
    def http(self, url, method='get', **kwargs):
        try:
            import httpx
            headers = {"User-Agent": self.ua()}
            headers.update(kwargs.pop('headers', {}))
            timeout = kwargs.pop('timeout', 10)
            if method == 'post':
                return httpx.post(url, headers=headers, timeout=timeout, **kwargs)
            return httpx.get(url, headers=headers, timeout=timeout, **kwargs)
        except:
            return None
    
    # ==================== فحص الهاتف ====================
    def scan_phone(self, phone):
        results = {"phone": phone, "timestamp": datetime.now().isoformat()}
        
        # WhatsApp
        clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        try:
            r = self.http(f"https://wa.me/{clean}", follow_redirects=True)
            results["whatsapp"] = "Continue to Chat" in r.text if r else None
        except:
            results["whatsapp"] = None
        
        # Viber
        try:
            r = self.http("https://api.viber.com/api/v2/check", method='post', json={"phone": phone})
            results["viber"] = r.json().get("exists", False) if r else None
        except:
            results["viber"] = None
        
        # Signal
        try:
            r = self.http(f"https://api.signal.org/v1/accounts/{phone}")
            results["signal"] = r.status_code == 200 if r else None
        except:
            results["signal"] = None
        
        # Telegram
        try:
            r = self.http("https://my.telegram.org/auth/send_password", method='post', data={"phone": phone})
            results["telegram"] = "code" in r.text.lower() if r else None
        except:
            results["telegram"] = None
        
        # Truecaller
        try:
            r = self.http(f"https://www.truecaller.com/search/eg/{clean}")
            if r:
                import bs4
                soup = bs4.BeautifulSoup(r.text, 'html.parser')
                scripts = soup.find_all("script", type="application/ld+json")
                for s in scripts:
                    if s.string and "name" in s.string:
                        data = json.loads(s.string)
                        if data.get("name"):
                            results["truecaller"] = {"name": data["name"]}
                            break
                else:
                    results["truecaller"] = {"found": False}
        except:
            results["truecaller"] = None
        
        # Carrier
        try:
            import phonenumbers
            from phonenumbers import carrier, geocoder
            p = phonenumbers.parse(phone)
            results["carrier"] = {
                "valid": phonenumbers.is_valid_number(p),
                "country": geocoder.description_for_number(p, "en"),
                "carrier": carrier.name_for_number(p, "en"),
                "type": str(phonenumbers.number_type(p)),
                "national": phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.NATIONAL),
                "international": phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            }
        except:
            results["carrier"] = {"error": "Invalid"}
        
        # NumVerify
        if NUMVERIFY_KEY:
            try:
                r = self.http("http://apilayer.net/api/validate", params={"access_key": NUMVERIFY_KEY, "number": phone, "format": 1})
                if r:
                    d = r.json()
                    results["numverify"] = {
                        "valid": d.get("valid"),
                        "country": d.get("country_name"),
                        "carrier": d.get("carrier"),
                        "line_type": d.get("line_type"),
                        "location": d.get("location")
                    }
            except:
                pass
        
        # Facebook
        try:
            r = self.http("https://www.facebook.com/login/identify", params={"ctx": "recover"})
            results["facebook"] = r.status_code == 200 if r else None
        except:
            results["facebook"] = None
        
        # Instagram
        try:
            r = self.http("https://www.instagram.com/api/v1/accounts/send_signup_sms/", method='post', data={"phone_number": phone, "device_id": hashlib.md5(phone.encode()).hexdigest()})
            results["instagram"] = r.status_code == 200 if r else None
        except:
            results["instagram"] = None
        
        # Snapchat
        try:
            r = self.http("https://accounts.snapchat.com/accounts/phone_verify", method='post', json={"phone": phone})
            results["snapchat"] = r.status_code == 200 if r else None
        except:
            results["snapchat"] = None
        
        # Twitter/X
        try:
            r = self.http("https://api.twitter.com/1.1/account/send_verification", method='post', data={"phone_number": phone})
            results["twitter"] = r.status_code == 200 if r else None
        except:
            results["twitter"] = None
        
        # Breaches
        try:
            r = self.http(f"https://haveibeenpwned.com/api/v3/pasteaccount/{phone}")
            results["breaches"] = len(r.json()) if r and r.status_code == 200 else 0
        except:
            results["breaches"] = 0
        
        return results
    
    # ==================== فحص IP ====================
    def scan_ip(self, ip):
        results = {"ip": ip, "timestamp": datetime.now().isoformat()}
        
        # IPInfo
        try:
            url = f"https://ipinfo.io/{ip}/json"
            if IPINFO_TOKEN:
                url += f"?token={IPINFO_TOKEN}"
            r = self.http(url)
            if r and r.status_code == 200:
                results["ipinfo"] = r.json()
        except:
            pass
        
        # GeoIP
        try:
            r = self.http(f"http://ip-api.com/json/{ip}?fields=66846719")
            if r and r.status_code == 200:
                results["geoip"] = r.json()
        except:
            pass
        
        # AbuseIPDB
        try:
            key = os.environ.get("ABUSEIPDB_KEY", "")
            if key:
                r = self.http("https://api.abuseipdb.com/api/v2/check", params={"ipAddress": ip, "maxAgeInDays": 90}, headers={"Key": key, "Accept": "application/json"})
                if r and r.status_code == 200:
                    d = r.json().get("data", {})
                    results["abuse"] = {
                        "score": d.get("abuseConfidenceScore", 0),
                        "reports": d.get("totalReports", 0),
                        "isp": d.get("isp", ""),
                        "usage": d.get("usageType", "")
                    }
        except:
            pass
        
        # Shodan
        if SHODAN_KEY:
            try:
                r = self.http(f"https://api.shodan.io/shodan/host/{ip}", params={"key": SHODAN_KEY})
                if r and r.status_code == 200:
                    d = r.json()
                    results["shodan"] = {
                        "ports": d.get("ports", []),
                        "org": d.get("org", ""),
                        "os": d.get("os", ""),
                        "vulns": list(d.get("vulns", {}).keys())[:5]
                    }
            except:
                pass
        
        # Port Scan
        ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1433, 3306, 3389, 5900, 6379, 8080, 8443, 27017]
        open_ports = []
        for port in ports:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.3)
                if s.connect_ex((ip, port)) == 0:
                    service = {21:"FTP",22:"SSH",23:"Telnet",25:"SMTP",53:"DNS",80:"HTTP",110:"POP3",135:"RPC",139:"NetBIOS",143:"IMAP",443:"HTTPS",445:"SMB",993:"IMAPS",995:"POP3S",1433:"MSSQL",3306:"MySQL",3389:"RDP",5900:"VNC",6379:"Redis",8080:"HTTP-Alt",8443:"HTTPS-Alt",27017:"MongoDB"}
                    open_ports.append({"port": port, "service": service.get(port, "?")})
                s.close()
            except:
                pass
        results["ports"] = {"open": open_ports, "scanned": len(ports)}
        
        # Reverse DNS
        try:
            results["dns"] = socket.gethostbyaddr(ip)[0]
        except:
            results["dns"] = None
        
        return results
    
    # ==================== فحص URL ====================
    def scan_url(self, url):
        results = {"url": url, "timestamp": datetime.now().isoformat()}
        
        # SSL
        try:
            hostname = urlparse(url).hostname or url
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    results["ssl"] = {
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                        "valid_from": cert.get("notBefore"),
                        "valid_to": cert.get("notAfter"),
                        "days_left": (datetime.strptime(cert.get("notAfter"), "%b %d %H:%M:%S %Y %Z") - datetime.now()).days if cert.get("notAfter") else None
                    }
        except Exception as e:
            results["ssl"] = {"error": str(e)}
        
        # Headers
        try:
            r = self.http(url, follow_redirects=True)
            if r:
                sec = {
                    "Strict-Transport-Security": r.headers.get("Strict-Transport-Security", ""),
                    "Content-Security-Policy": r.headers.get("Content-Security-Policy", ""),
                    "X-Frame-Options": r.headers.get("X-Frame-Options", ""),
                    "X-Content-Type-Options": r.headers.get("X-Content-Type-Options", ""),
                    "X-XSS-Protection": r.headers.get("X-XSS-Protection", "")
                }
                missing = [k for k, v in sec.items() if not v]
                results["headers"] = {
                    "security_headers": sec,
                    "missing": missing,
                    "score": len([v for v in sec.values() if v]) * 100 // len(sec),
                    "server": r.headers.get("Server", "?"),
                    "status": r.status_code
                }
        except:
            pass
        
        # VirusTotal
        if VIRUSTOTAL_KEY:
            try:
                url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
                r = self.http(f"https://www.virustotal.com/api/v3/urls/{url_id}", headers={"x-apikey": VIRUSTOTAL_KEY})
                if r and r.status_code == 200:
                    stats = r.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    results["virustotal"] = stats
            except:
                pass
        
        # Technology
        try:
            r = self.http(url)
            if r:
                import bs4
                soup = bs4.BeautifulSoup(r.text, 'html.parser')
                tech = []
                if soup.find("meta", {"name": "generator"}):
                    tech.append(soup.find("meta", {"name": "generator"})["content"])
                scripts = [s.get("src", "") for s in soup.find_all("script", src=True)]
                for src in scripts:
                    if "jquery" in src.lower(): tech.append("jQuery")
                    if "react" in src.lower(): tech.append("React")
                    if "vue" in src.lower(): tech.append("Vue.js")
                    if "angular" in src.lower(): tech.append("Angular")
                    if "bootstrap" in src.lower(): tech.append("Bootstrap")
                results["technology"] = list(set(tech))
        except:
            pass
        
        # Redirects
        try:
            r = self.http(url, follow_redirects=False)
            if r and r.status_code in (301, 302, 307, 308):
                results["redirect"] = {"status": r.status_code, "to": r.headers.get("Location", "")}
        except:
            pass
        
        # Content
        try:
            r = self.http(url, follow_redirects=True)
            if r:
                import bs4
                soup = bs4.BeautifulSoup(r.text, 'html.parser')
                results["content"] = {
                    "title": soup.title.string if soup.title else "",
                    "forms": len(soup.find_all("form")),
                    "links": len(soup.find_all("a")),
                    "images": len(soup.find_all("img")),
                    "scripts": len(soup.find_all("script")),
                    "has_login": bool(soup.find("input", {"type": "password"}))
                }
        except:
            pass
        
        return results
    
    # ==================== فحص Email ====================
    def scan_email(self, email):
        results = {"email": email, "timestamp": datetime.now().isoformat()}
        
        domain = email.split("@")[-1] if "@" in email else ""
        
        # Format check
        results["valid_format"] = bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))
        
        # Disposable
        disposable = ['tempmail.com','10minutemail.com','guerrillamail.com','mailinator.com','yopmail.com','throwaway.email','sharklasers.com','trashmail.com','temp-mail.org','fakeinbox.com','emailondeck.com','spamgourmet.com','maildrop.cc','getnada.com','dispostable.com']
        results["disposable"] = domain in disposable
        
        # MX Check
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'MX')
            results["mx_valid"] = bool(answers)
        except:
            results["mx_valid"] = False
        
        # Breaches
        try:
            r = self.http(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}")
            if r and r.status_code == 200:
                results["breaches"] = [b["Name"] for b in r.json()]
            elif r and r.status_code == 404:
                results["breaches"] = []
        except:
            results["breaches"] = None
        
        # Gravatar
        try:
            hash_email = hashlib.md5(email.lower().strip().encode()).hexdigest()
            r = self.http(f"https://www.gravatar.com/{hash_email}.json")
            if r and r.status_code == 200:
                results["gravatar"] = r.json()
        except:
            pass
        
        return results
    
    # ==================== فحص Username ====================
    def scan_username(self, username):
        results = {"username": username, "timestamp": datetime.now().isoformat(), "platforms": {}}
        
        platforms = {
            "GitHub": f"https://github.com/{username}",
            "Twitter": f"https://twitter.com/{username}",
            "Instagram": f"https://www.instagram.com/{username}/",
            "Reddit": f"https://www.reddit.com/user/{username}",
            "TikTok": f"https://www.tiktok.com/@{username}",
            "Snapchat": f"https://www.snapchat.com/add/{username}",
            "Telegram": f"https://t.me/{username}",
            "YouTube": f"https://www.youtube.com/@{username}",
            "Twitch": f"https://www.twitch.tv/{username}",
            "Pinterest": f"https://www.pinterest.com/{username}/",
            "Spotify": f"https://open.spotify.com/user/{username}",
            "Steam": f"https://steamcommunity.com/id/{username}",
            "Roblox": f"https://www.roblox.com/user.aspx?username={username}",
            "DeviantArt": f"https://www.deviantart.com/{username}",
            "Patreon": f"https://www.patreon.com/{username}",
            "Medium": f"https://medium.com/@{username}",
            "Quora": f"https://www.quora.com/profile/{username}",
            "VK": f"https://vk.com/{username}",
            "Flickr": f"https://www.flickr.com/people/{username}",
            "Behance": f"https://www.behance.net/{username}",
            "Dribbble": f"https://dribbble.com/{username}",
            "Keybase": f"https://keybase.io/{username}",
            "Pastebin": f"https://pastebin.com/u/{username}",
            "SoundCloud": f"https://soundcloud.com/{username}",
            "LinkedIn": f"https://www.linkedin.com/in/{username}",
            "Facebook": f"https://www.facebook.com/{username}",
            "OnlyFans": f"https://onlyfans.com/{username}",
        }
        
        for name, url in platforms.items():
            try:
                r = self.http(url, follow_redirects=True)
                if r and r.status_code == 200 and username.lower() in r.text.lower():
                    results["platforms"][name] = True
                else:
                    results["platforms"][name] = False
            except:
                results["platforms"][name] = None
        
        results["found_count"] = sum(1 for v in results["platforms"].values() if v)
        results["total_checked"] = len(platforms)
        
        return results

scanner = UltimateScanner()

# ==================== HTML ====================
HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="SHADOW OSINT - أقوى أداة استخبارات وفحص شامل">
    <title>🔥 SHADOW OSINT v6.0</title>
    <style>
        :root {
            --bg: #0a0a0f;
            --surface: #12121a;
            --surface2: #1a1a25;
            --primary: #e94560;
            --primary2: #ff6b81;
            --text: #e4e4e4;
            --muted: #888;
            --border: #252530;
            --green: #00c853;
            --red: #ff1744;
            --yellow: #ffab00;
            --blue: #448aff;
            --purple: #e040fb;
        }
        *{margin:0;padding:0;box-sizing:border-box}
        body{
            font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;
            background:var(--bg);
            color:var(--text);
            min-height:100vh;
            line-height:1.7;
        }
        
        /* Animated BG */
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: 
                radial-gradient(circle at 20% 50%, rgba(233,69,96,0.05) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(68,138,255,0.05) 0%, transparent 50%),
                radial-gradient(circle at 50% 80%, rgba(224,64,251,0.03) 0%, transparent 50%);
            z-index: 0;
            pointer-events: none;
        }
        
        .container {max-width:1100px;margin:0 auto;padding:20px;position:relative;z-index:1}
        
        /* Header */
        .header {
            text-align:center;
            padding:40px 20px;
            background:linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            border-bottom:3px solid var(--primary);
            position:relative;
            overflow:hidden;
        }
        .header::after {
            content:'';
            position:absolute;
            top:0;left:0;right:0;bottom:0;
            background:repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(255,255,255,0.01) 3px, rgba(255,255,255,0.01) 6px);
            pointer-events:none;
        }
        .header h1 {
            font-size:3em;
            color:var(--primary);
            text-shadow:0 0 30px rgba(233,69,96,0.6), 0 0 60px rgba(233,69,96,0.3);
            position:relative;z-index:1;
        }
        .header .subtitle {
            color:var(--muted);
            margin-top:10px;
            font-size:16px;
            position:relative;z-index:1;
        }
        .header .version {
            display:inline-block;
            background:var(--primary);
            color:#fff;
            padding:4px 12px;
            border-radius:20px;
            font-size:12px;
            margin-top:10px;
            position:relative;z-index:1;
        }
        
        /* Nav */
        .nav {
            display:flex;
            justify-content:center;
            gap:5px;
            padding:15px;
            flex-wrap:wrap;
            background:var(--surface);
            position:sticky;
            top:0;
            z-index:1000;
            border-bottom:1px solid var(--border);
            box-shadow:0 4px 20px rgba(0,0,0,0.3);
        }
        .nav a {
            padding:10px 20px;
            background:var(--surface2);
            color:var(--text);
            text-decoration:none;
            border-radius:8px;
            border:1px solid var(--border);
            font-size:14px;
            font-weight:500;
            transition:all 0.3s;
            white-space:nowrap;
        }
        .nav a:hover {
            background:var(--primary);
            color:#fff;
            border-color:var(--primary);
            transform:translateY(-2px);
            box-shadow:0 8px 25px rgba(233,69,96,0.3);
        }
        .nav a.active {
            background:var(--primary);
            color:#fff;
            border-color:var(--primary);
        }
        
        /* Cards */
        .card {
            background:var(--surface);
            border:1px solid var(--border);
            border-radius:16px;
            padding:30px;
            margin:25px 0;
            box-shadow:0 8px 30px rgba(0,0,0,0.4);
            transition:all 0.3s;
        }
        .card:hover {
            border-color:var(--primary);
            box-shadow:0 12px 40px rgba(233,69,96,0.1);
        }
        .card h2 {
            color:var(--primary);
            margin-bottom:20px;
            font-size:1.5em;
            display:flex;
            align-items:center;
            gap:10px;
        }
        .card h3 {
            color:var(--text);
            margin:15px 0 10px;
            font-size:1.1em;
        }
        .card p {color:var(--muted);margin-bottom:15px}
        
        /* Inputs */
        .input-row {
            display:flex;
            gap:10px;
            margin-bottom:15px;
        }
        input, textarea, select {
            flex:1;
            padding:14px 18px;
            background:var(--bg);
            border:2px solid var(--border);
            border-radius:10px;
            color:var(--text);
            font-size:15px;
            font-family:inherit;
            transition:all 0.3s;
        }
        input:focus, textarea:focus, select:focus {
            outline:none;
            border-color:var(--primary);
            box-shadow:0 0 0 4px rgba(233,69,96,0.1);
        }
        input::placeholder {color:#555}
        
        /* Buttons */
        .btn {
            padding:14px 35px;
            background:var(--primary);
            color:#fff;
            border:none;
            border-radius:10px;
            cursor:pointer;
            font-size:15px;
            font-weight:600;
            transition:all 0.3s;
            white-space:nowrap;
            letter-spacing:0.5px;
        }
        .btn:hover {
            background:var(--primary2);
            transform:translateY(-2px);
            box-shadow:0 10px 30px rgba(233,69,96,0.4);
        }
        .btn:active {transform:translateY(0)}
        .btn:disabled {opacity:0.5;cursor:not-allowed;transform:none}
        .btn-outline {
            background:transparent;
            border:2px solid var(--primary);
            color:var(--primary);
        }
        .btn-outline:hover {background:var(--primary);color:#fff}
        .btn-sm {padding:8px 18px;font-size:13px}
        
        /* Results */
        .result-box {
            background:var(--bg);
            border:2px solid var(--border);
            border-radius:12px;
            padding:20px;
            margin-top:20px;
            display:none;
            font-family:'Fira Code','Courier New',monospace;
            font-size:13px;
            white-space:pre-wrap;
            word-wrap:break-word;
            max-height:600px;
            overflow-y:auto;
            line-height:1.5;
        }
        .result-box.show {display:block}
        .result-box.success {border-color:var(--green)}
        .result-box.error {border-color:var(--red)}
        
        /* Loading */
        .loading {
            text-align:center;
            padding:20px;
            display:none;
        }
        .loading.show {display:block}
        .spinner {
            width:50px;
            height:50px;
            border:3px solid var(--border);
            border-top:3px solid var(--primary);
            border-radius:50%;
            animation:spin 0.8s linear infinite;
            margin:0 auto 15px;
        }
        @keyframes spin {0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
        
        /* Badges */
        .badge {
            display:inline-block;
            padding:5px 12px;
            border-radius:6px;
            font-weight:600;
            font-size:12px;
            margin:3px;
        }
        .badge-success {background:var(--green);color:#000}
        .badge-danger {background:var(--red);color:#fff}
        .badge-warning {background:var(--yellow);color:#000}
        .badge-info {background:var(--blue);color:#fff}
        .badge-purple {background:var(--purple);color:#fff}
        
        /* Tables */
        table {
            width:100%;
            border-collapse:collapse;
            margin:15px 0;
        }
        th, td {
            padding:12px 15px;
            border:1px solid var(--border);
            text-align:right;
            font-size:13px;
        }
        th {
            background:var(--surface2);
            color:var(--primary);
            font-weight:600;
            text-transform:uppercase;
            letter-spacing:0.5px;
        }
        td {background:var(--bg)}
        tr:hover td {background:#1a1a25}
        
        /* Stats Grid */
        .stats-grid {
            display:grid;
            grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));
            gap:15px;
            margin:20px 0;
        }
        .stat-card {
            background:var(--surface2);
            border:1px solid var(--border);
            border-radius:12px;
            padding:25px;
            text-align:center;
            transition:all 0.3s;
        }
        .stat-card:hover {
            border-color:var(--primary);
            transform:translateY(-3px);
        }
        .stat-card .icon {font-size:2em;margin-bottom:10px}
        .stat-card .value {
            font-size:2.5em;
            font-weight:bold;
            color:var(--primary);
        }
        .stat-card .label {
            color:var(--muted);
            font-size:0.85em;
            text-transform:uppercase;
            letter-spacing:1px;
        }
        
        /* Code */
        code {
            background:#1a1a1a;
            padding:2px 8px;
            border-radius:4px;
            color:var(--primary);
            font-family:'Fira Code',monospace;
            font-size:13px;
        }
        pre {
            background:var(--bg);
            padding:15px;
            border-radius:10px;
            overflow-x:auto;
            border:1px solid var(--border);
        }
        
        /* Footer */
        .footer {
            text-align:center;
            padding:25px;
            color:var(--muted);
            border-top:1px solid var(--border);
            margin-top:40px;
            font-size:13px;
        }
        .footer a {color:var(--primary);text-decoration:none}
        
        /* Scrollbar */
        ::-webkit-scrollbar {width:6px}
        ::-webkit-scrollbar-track {background:var(--bg)}
        ::-webkit-scrollbar-thumb {background:var(--border);border-radius:3px}
        ::-webkit-scrollbar-thumb:hover {background:var(--primary)}
        
        /* Animations */
        @keyframes fadeIn {from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
        .card {animation:fadeIn 0.5s ease}
        
        /* Responsive */
        @media(max-width:768px){
            .header h1{font-size:2em}
            .input-row{flex-direction:column}
            .nav{flex-direction:column}
            .nav a{text-align:center}
            .stats-grid{grid-template-columns:1fr 1fr}
        }
        @media(max-width:480px){
            .header h1{font-size:1.5em}
            .stats-grid{grid-template-columns:1fr}
            .card{padding:15px}
            .btn{width:100%}
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔥 SHADOW OSINT</h1>
        <p class="subtitle">أقوى منصة استخبارات مفتوحة المصدر - فحص شامل للأرقام والبريد و IP والروابط والمستخدمين</p>
        <span class="version">v6.0 ULTIMATE</span>
    </div>
    
    <div class="nav">
        <a href="/" class="{{active_phone}}">📱 هاتف</a>
        <a href="/email" class="{{active_email}}">📧 بريد</a>
        <a href="/ip" class="{{active_ip}}">🌐 IP</a>
        <a href="/url" class="{{active_url}}">🔗 رابط</a>
        <a href="/username" class="{{active_user}}">👤 يوزر</a>
        <a href="/api" class="{{active_api}}">⚡ API</a>
        <a href="/stats" class="{{active_stats}}">📊 إحصائيات</a>
    </div>
    
    <div class="container">{{content|safe}}</div>
    
    <div class="footer">
        <p>⚠️ <strong>تنبيه هام:</strong> هذه المنصة للأغراض التعليمية والبحثية فقط. المستخدم يتحمل المسؤولية القانونية الكاملة عن أي استخدام غير أخلاقي.</p>
        <p>SHADOW OSINT v6.0 | <a href="/api">API</a> | جميع الحقوق محفوظة © 2024</p>
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
            
            const value = input.value.trim();
            
            loading.classList.add('show');
            result.classList.remove('show', 'success', 'error');
            result.innerHTML = '';
            
            try {
                const body = {};
                body[type] = value;
                
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
                    result.innerHTML = '<div style="color:#ff1744;padding:20px;">❌ ' + (data.error || 'خطأ غير معروف') + '</div>';
                    result.classList.add('error');
                }
                result.classList.add('show');
                result.scrollIntoView({behavior:'smooth',block:'nearest'});
            } catch(e) {
                result.innerHTML = '<div style="color:#ff1744;padding:20px;">❌ خطأ في الاتصال: ' + e.message + '</div>';
                result.classList.add('error', 'show');
            } finally {
                loading.classList.remove('show');
            }
        }
        
        function getLabel(type) {
            const labels = {phone:'رقم الهاتف',email:'البريد الإلكتروني',ip:'عنوان IP',url:'الرابط',username:'اسم المستخدم'};
            return labels[type] || '';
        }
        
        function badge(val, trueText, falseText) {
            if (val === true) return '<span class="badge badge-success">✅ ' + trueText + '</span>';
            if (val === false) return '<span class="badge badge-danger">❌ ' + falseText + '</span>';
            return '<span class="badge badge-warning">⚠️ غير معروف</span>';
        }
        
        function formatResult(type, data) {
            let h = '';
            
            if (type === 'phone') {
                h += '<h3 style="color:#e94560;margin-bottom:15px;">📱 ' + data.phone + '</h3>';
                h += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px;">';
                h += '<div style="background:#1a1a25;padding:10px;border-radius:8px;">💬 واتساب: ' + badge(data.whatsapp,'موجود','غير مسجل') + '</div>';
                h += '<div style="background:#1a1a25;padding:10px;border-radius:8px;">📞 Viber: ' + badge(data.viber,'موجود','غير مسجل') + '</div>';
                h += '<div style="background:#1a1a25;padding:10px;border-radius:8px;">🔒 Signal: ' + badge(data.signal,'موجود','غير مسجل') + '</div>';
                h += '<div style="background:#1a1a25;padding:10px;border-radius:8px;">📡 تيليجرام: ' + badge(data.telegram,'موجود','غير مسجل') + '</div>';
                h += '<div style="background:#1a1a25;padding:10px;border-radius:8px;">📘 فيسبوك: ' + badge(data.facebook,'مرتبط','غير مرتبط') + '</div>';
                h += '<div style="background:#1a1a25;padding:10px;border-radius:8px;">📸 انستجرام: ' + badge(data.instagram,'مرتبط','غير مرتبط') + '</div>';
                h += '<div style="background:#1a1a25;padding:10px;border-radius:8px;">👻 سناب شات: ' + badge(data.snapchat,'مرتبط','غير مرتبط') + '</div>';
                h += '<div style="background:#1a1a25;padding:10px;border-radius:8px;">🐦 تويتر: ' + badge(data.twitter,'مرتبط','غير مرتبط') + '</div>';
                h += '</div>';
                
                const tc = data.truecaller || {};
                if (tc.name) {
                    h += '<br><strong>👤 Truecaller:</strong> <span style="color:#e040fb;font-size:16px;">' + tc.name + '</span>';
                }
                
                const cr = data.carrier || {};
                if (!cr.error) {
                    h += '<br><br><strong>📶 الشبكة:</strong><br>';
                    h += '<table><tr><th>الخاصية</th><th>القيمة</th></tr>';
                    h += '<tr><td>المزود</td><td>' + (cr.carrier||'?') + '</td></tr>';
                    h += '<tr><td>الدولة</td><td>' + (cr.country||'?') + '</td></tr>';
                    h += '<tr><td>النوع</td><td>' + (cr.type||'?') + '</td></tr>';
                    h += '<tr><td>الصيغة</td><td>' + (cr.international||'?') + '</td></tr>';
                    h += '<tr><td>صالح</td><td>' + badge(cr.valid,'نعم','لا') + '</td></tr>';
                    h += '</table>';
                }
                
                const nv = data.numverify || {};
                if (nv.valid !== undefined) {
                    h += '<br><strong>🔍 NumVerify:</strong> ' + (nv.carrier||'?') + ' - ' + (nv.country||'?') + ' - ' + (nv.line_type||'?');
                }
                
                if (data.breaches > 0) {
                    h += '<br><br><strong>⚠️ التسريبات:</strong> <span class="badge badge-danger">تم العثور على ' + data.breaches + ' تسريب</span>';
                }
            }
            
            else if (type === 'email') {
                h += '<h3 style="color:#e94560;margin-bottom:15px;">📧 ' + data.email + '</h3>';
                h += '<strong>الصيغة:</strong> ' + badge(data.valid_format,'صحيحة','غير صحيحة') + '<br>';
                h += '<strong>بريد مؤقت:</strong> ' + badge(data.disposable,'نعم','لا') + '<br>';
                h += '<strong>MX صالح:</strong> ' + badge(data.mx_valid,'نعم','لا') + '<br>';
                
                if (data.breaches && data.breaches.length > 0) {
                    h += '<br><strong>⚠️ التسريبات (' + data.breaches.length + '):</strong><br>';
                    data.breaches.forEach(function(b) {
                        h += '<span class="badge badge-danger">' + b + '</span> ';
                    });
                } else if (data.breaches) {
                    h += '<br><strong>✅ لا توجد تسريبات</strong>';
                }
                
                if (data.gravatar) {
                    h += '<br><br><strong>Gravatar:</strong> موجود';
                }
            }
            
            else if (type === 'ip') {
                h += '<h3 style="color:#e94560;margin-bottom:15px;">🌐 ' + data.ip + '</h3>';
                
                const geo = data.geoip || {};
                if (geo.country) {
                    h += '<strong>📍 الموقع:</strong> ' + (geo.city||'') + ', ' + (geo.regionName||'') + ', ' + geo.country + '<br>';
                    h += '<strong>ISP:</strong> ' + (geo.isp||'?') + '<br>';
                    h += '<strong>ORG:</strong> ' + (geo.org||'?') + '<br><br>';
                }
                
                const abuse = data.abuse || {};
                if (abuse.score !== undefined) {
                    h += '<strong>⚠️ AbuseIPDB:</strong> <span class="badge ' + (abuse.score > 50 ? 'badge-danger' : 'badge-success') + '">' + abuse.score + '%</span><br>';
                    h += 'بلاغات: ' + abuse.reports + ' | ISP: ' + abuse.isp + '<br><br>';
                }
                
                const ports = data.ports || {};
                if (ports.open && ports.open.length > 0) {
                    h += '<strong>🔓 منافذ مفتوحة:</strong> ';
                    ports.open.forEach(function(p) {
                        h += '<span class="badge badge-warning">' + p.port + ' (' + p.service + ')</span> ';
                    });
                } else {
                    h += '<strong>🔒 لا توجد منافذ مفتوحة</strong>';
                }
                
                if (data.dns) {
                    h += '<br><br><strong>🔍 DNS:</strong> ' + data.dns;
                }
            }
            
            else if (type === 'url') {
                h += '<h3 style="color:#e94560;margin-bottom:15px;">🔗 ' + data.url + '</h3>';
                
                const ssl = data.ssl || {};
                if (!ssl.error) {
                    h += '<strong>🔒 SSL:</strong> صالح حتى ' + (ssl.valid_to||'?');
                    if (ssl.days_left !== undefined) {
                        h += ' <span class="badge ' + (ssl.days_left > 30 ? 'badge-success' : ssl.days_left > 7 ? 'badge-warning' : 'badge-danger') + '">' + ssl.days_left + ' يوم</span>';
                    }
                    h += '<br>';
                }
                
                const headers = data.headers || {};
                if (headers.score !== undefined) {
                    h += '<strong>🛡️ الأمان:</strong> <span class="badge ' + (headers.score >= 70 ? 'badge-success' : 'badge-warning') + '">' + headers.score + '%</span><br>';
                    h += 'السيرفر: ' + headers.server + ' | الحالة: ' + headers.status + '<br>';
                    if (headers.missing && headers.missing.length > 0) {
                        h += 'الرؤوس المفقودة: ' + headers.missing.join(', ') + '<br>';
                    }
                }
                
                const vt = data.virustotal || {};
                if (vt.malicious !== undefined) {
                    h += '<br><strong>🦠 VirusTotal:</strong> ضار:' + vt.malicious + ' | مشبوه:' + vt.suspicious + ' | آمن:' + vt.harmless + '<br>';
                }
                
                if (data.technology && data.technology.length > 0) {
                    h += '<br><strong>🔧 التقنيات:</strong> ';
                    data.technology.forEach(function(t) {
                        h += '<span class="badge badge-info">' + t + '</span> ';
                    });
                }
                
                const content = data.content || {};
                if (content.title) {
                    h += '<br><br><strong>📄 المحتوى:</strong><br>';
                    h += 'العنوان: ' + content.title + '<br>';
                    h += 'روابط: ' + content.links + ' | صور: ' + content.images + ' | نماذج: ' + content.forms + '<br>';
                    h += 'تسجيل دخول: ' + (content.has_login ? '<span class="badge badge-warning">نعم</span>' : '<span class="badge badge-success">لا</span>');
                }
            }
            
            else if (type === 'username') {
                h += '<h3 style="color:#e94560;margin-bottom:15px;">👤 @' + data.username + '</h3>';
                h += '<strong>تم العثور على ' + data.found_count + ' من أصل ' + data.total_checked + ' منصة</strong><br><br>';
                
                const platforms = data.platforms || {};
                for (const [name, found] of Object.entries(platforms)) {
                    h += '<div style="display:inline-block;margin:3px;">';
                    h += badge(found, name, name);
                    h += '</div>';
                }
            }
            
            return h;
        }
        
        // Enter key
        document.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const active = document.activeElement;
                if (active && active.id && active.id.endsWith('-input')) {
                    const type = active.id.replace('-input', '');
                    scan(type);
                }
            }
        });
    </script>
</body>
</html>"""

# ==================== Pages ====================
PHONE_PAGE = """
<div class="card">
    <h2>📱 فحص رقم الهاتف</h2>
    <p>أدخل رقم الهاتف بصيغة دولية للفحص الشامل - واتساب، تيليجرام، فيسبوك، انستجرام، سناب شات، تروكولر، الشبكة، التسريبات والمزيد...</p>
    <div class="input-row">
        <input id="phone-input" placeholder="+201234567890" value="+20" autofocus>
        <button class="btn" onclick="scan('phone')">🔍 فحص شامل</button>
    </div>
    <div class="loading" id="phone-loading"><div class="spinner"></div><p>جاري الفحص الشامل... قد يستغرق 30-60 ثانية</p></div>
    <div class="result-box" id="phone-result"></div>
</div>
"""

EMAIL_PAGE = """
<div class="card">
    <h2>📧 فحص البريد الإلكتروني</h2>
    <p>تحقق من صحة البريد، التسريبات، البريد المؤقت، Gravatar والمزيد...</p>
    <div class="input-row">
        <input id="email-input" placeholder="user@example.com" autofocus>
        <button class="btn" onclick="scan('email')">🔍 فحص</button>
    </div>
    <div class="loading" id="email-loading"><div class="spinner"></div><p>جاري الفحص...</p></div>
    <div class="result-box" id="email-result"></div>
</div>
"""

IP_PAGE = """
<div class="card">
    <h2>🌐 فحص عنوان IP</h2>
    <p>فحص شامل: الموقع الجغرافي، ISP، السمعة، المنافذ المفتوحة، DNS، Shodan، AbuseIPDB...</p>
    <div class="input-row">
        <input id="ip-input" placeholder="8.8.8.8" autofocus>
        <button class="btn" onclick="scan('ip')">🔍 فحص شامل</button>
    </div>
    <div class="loading" id="ip-loading"><div class="spinner"></div><p>جاري الفحص...</p></div>
    <div class="result-box" id="ip-result"></div>
</div>
"""

URL_PAGE = """
<div class="card">
    <h2>🔗 فحص رابط</h2>
    <p>تحليل شامل: SSL، رؤوس الأمان، VirusTotal، التقنيات المستخدمة، المحتوى، التوجيه...</p>
    <div class="input-row">
        <input id="url-input" placeholder="https://example.com" autofocus>
        <button class="btn" onclick="scan('url')">🔍 فحص شامل</button>
    </div>
    <div class="loading" id="url-loading"><div class="spinner"></div><p>جاري الفحص...</p></div>
    <div class="result-box" id="url-result"></div>
</div>
"""

USERNAME_PAGE = """
<div class="card">
    <h2>👤 فحص اسم المستخدم</h2>
    <p>البحث عن اسم المستخدم في 27 منصة اجتماعية مختلفة...</p>
    <div class="input-row">
        <input id="username-input" placeholder="username" autofocus>
        <button class="btn" onclick="scan('username')">🔍 بحث</button>
    </div>
    <div class="loading" id="username-loading"><div class="spinner"></div><p>جاري البحث في المنصات...</p></div>
    <div class="result-box" id="username-result"></div>
</div>
"""

API_PAGE = """
<div class="card">
    <h2>⚡ API Documentation</h2>
    <p>API بسيط وقوي لدمج خدماتنا في تطبيقاتك</p>
    
    <h3>📱 فحص هاتف</h3>
    <pre><code>POST /api/scan/phone
Content-Type: application/json
{"phone": "+201234567890"}</code></pre>
    
    <h3>📧 فحص بريد</h3>
    <pre><code>POST /api/scan/email
{"email": "user@example.com"}</code></pre>
    
    <h3>🌐 فحص IP</h3>
    <pre><code>POST /api/scan/ip
{"ip": "8.8.8.8"}</code></pre>
    
    <h3>🔗 فحص رابط</h3>
    <pre><code>POST /api/scan/url
{"url": "https://example.com"}</code></pre>
    
    <h3>👤 فحص يوزر</h3>
    <pre><code>POST /api/scan/username
{"username": "elonmusk"}</code></pre>
    
    <h3>📊 إحصائيات</h3>
    <pre><code>GET /api/stats</code></pre>
</div>
"""

STATS_PAGE = """
<div class="card">
    <h2>📊 إحصائيات المنصة</h2>
    <div class="stats-grid">
        <div class="stat-card">
            <div class="icon">🔍</div>
            <div class="value">{{total}}</div>
            <div class="label">إجمالي الفحوصات</div>
        </div>
        <div class="stat-card">
            <div class="icon">📱</div>
            <div class="value">{{phone}}</div>
            <div class="label">فحص هواتف</div>
        </div>
        <div class="stat-card">
            <div class="icon">🌐</div>
            <div class="value">{{ip}}</div>
            <div class="label">فحص IP</div>
        </div>
        <div class="stat-card">
            <div class="icon">🔗</div>
            <div class="value">{{url}}</div>
            <div class="label">فحص روابط</div>
        </div>
        <div class="stat-card">
            <div class="icon">📧</div>
            <div class="value">{{email}}</div>
            <div class="label">فحص بريد</div>
        </div>
        <div class="stat-card">
            <div class="icon">👤</div>
            <div class="value">{{username}}</div>
            <div class="label">فحص يوزر</div>
        </div>
    </div>
</div>
"""

# ==================== Routes ====================
@web_app.route('/')
def home():
    return HTML.replace("{{active_phone}}", "active").replace("{{active_email}}", "").replace("{{active_ip}}", "").replace("{{active_url}}", "").replace("{{active_user}}", "").replace("{{active_api}}", "").replace("{{active_stats}}", "").replace("{{content|safe}}", PHONE_PAGE)

@web_app.route('/email')
def email_page():
    return HTML.replace("{{active_phone}}", "").replace("{{active_email}}", "active").replace("{{active_ip}}", "").replace("{{active_url}}", "").replace("{{active_user}}", "").replace("{{active_api}}", "").replace("{{active_stats}}", "").replace("{{content|safe}}", EMAIL_PAGE)

@web_app.route('/ip')
def ip_page():
    return HTML.replace("{{active_phone}}", "").replace("{{active_email}}", "").replace("{{active_ip}}", "active").replace("{{active_url}}", "").replace("{{active_user}}", "").replace("{{active_api}}", "").replace("{{active_stats}}", "").replace("{{content|safe}}", IP_PAGE)

@web_app.route('/url')
def url_page():
    return HTML.replace("{{active_phone}}", "").replace("{{active_email}}", "").replace("{{active_ip}}", "").replace("{{active_url}}", "active").replace("{{active_user}}", "").replace("{{active_api}}", "").replace("{{active_stats}}", "").replace("{{content|safe}}", URL_PAGE)

@web_app.route('/username')
def username_page():
    return HTML.replace("{{active_phone}}", "").replace("{{active_email}}", "").replace("{{active_ip}}", "").replace("{{active_url}}", "").replace("{{active_user}}", "active").replace("{{active_api}}", "").replace("{{active_stats}}", "").replace("{{content|safe}}", USERNAME_PAGE)

@web_app.route('/api')
def api_page():
    return HTML.replace("{{active_phone}}", "").replace("{{active_email}}", "").replace("{{active_ip}}", "").replace("{{active_url}}", "").replace("{{active_user}}", "").replace("{{active_api}}", "active").replace("{{active_stats}}", "").replace("{{content|safe}}", API_PAGE)

@web_app.route('/stats')
def stats_page():
    total = db("SELECT COUNT(*) as c FROM scans", fetch=True)[0]['c']
    phone = db("SELECT COUNT(*) as c FROM scans WHERE type='phone'", fetch=True)[0]['c']
    ip = db("SELECT COUNT(*) as c FROM scans WHERE type='ip'", fetch=True)[0]['c']
    url = db("SELECT COUNT(*) as c FROM scans WHERE type='url'", fetch=True)[0]['c']
    email = db("SELECT COUNT(*) as c FROM scans WHERE type='email'", fetch=True)[0]['c']
    username = db("SELECT COUNT(*) as c FROM scans WHERE type='username'", fetch=True)[0]['c']
    
    content = STATS_PAGE.replace("{{total}}", str(total)).replace("{{phone}}", str(phone)).replace("{{ip}}", str(ip)).replace("{{url}}", str(url)).replace("{{email}}", str(email)).replace("{{username}}", str(username))
    return HTML.replace("{{active_phone}}", "").replace("{{active_email}}", "").replace("{{active_ip}}", "").replace("{{active_url}}", "").replace("{{active_user}}", "").replace("{{active_api}}", "").replace("{{active_stats}}", "active").replace("{{content|safe}}", content)

# ==================== API ====================
@web_app.route('/api/scan/<scan_type>', methods=['POST'])
def api_scan(scan_type):
    try:
        data = request.get_json() or {}
        target = data.get(scan_type, '')
        
        if not target:
            return jsonify({"error": f"الرجاء إدخال {scan_type}"}), 400
        
        if scan_type == 'phone':
            result = scanner.scan_phone(target)
        elif scan_type == 'ip':
            result = scanner.scan_ip(target)
        elif scan_type == 'url':
            result = scanner.scan_url(target)
        elif scan_type == 'email':
            result = scanner.scan_email(target)
        elif scan_type == 'username':
            result = scanner.scan_username(target)
        else:
            return jsonify({"error": "نوع فحص غير معروف"}), 400
        
        db("INSERT INTO scans (target, type, data, ip) VALUES (?, ?, ?, ?)",
           (target, scan_type, json.dumps(result, ensure_ascii=False), request.remote_addr or ''))
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/stats')
def api_stats():
    total = db("SELECT COUNT(*) as c FROM scans", fetch=True)[0]['c']
    return jsonify({"total_scans": total, "version": "6.0.0", "status": "operational"})

@web_app.route('/health')
def health():
    return jsonify({"status": "healthy"})

# ==================== Run ====================
if __name__ == '__main__':
    init_db()
    print("""
╔══════════════════════════════════════════════════════════════════╗
║            🔥 SHADOW OSINT v6.0 - ULTIMATE 🔥                   ║
║        فحص: هواتف | بريد | IP | روابط | يوزرات                 ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    print(f"🚀 http://0.0.0.0:{PORT}")
    web_app.run(host='0.0.0.0', port=PORT, debug=False)
