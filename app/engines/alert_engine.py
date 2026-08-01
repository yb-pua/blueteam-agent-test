import re
from typing import Optional
from app.models.schemas import AlertParseResponse, AlertMatchItem

# ============================================================
# 日志格式自动检测
# ============================================================

def detect_format(raw_text: str) -> str:
    """根据前 5~10 行特征判断日志格式"""
    lines = raw_text.strip().split("\n")
    head = lines[:10]
    sample = "\n".join(head)

    # Suricata EVE JSON
    if re.search(r'"event_type"\s*:', sample) and re.search(r'"src_ip"\s*:', sample):
        return "suricata_eve"

    # Nginx combined / common log format
    nginx_pat = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\s+-\s+\S+\s+\[.*?\]\s+"(?:GET|POST|PUT|DELETE|HEAD|OPTIONS|PATCH|CONNECT)'
    if re.search(nginx_pat, sample):
        return "nginx_combined"

    # Linux auth log
    if re.search(r'sshd\[\d+\]', sample):
        return "linux_auth"
    if re.search(r'pam_unix\(sshd:', sample):
        return "linux_auth"
    if re.search(r'(Failed password|Invalid user|Accepted password)', sample):
        return "linux_auth"

    # Windows Event (XML or CSV style)
    if re.search(r'(<EventID>|EventID:\s*\d+|EventCode:\s*\d+)', sample):
        return "windows_event"

    # Generic syslog
    syslog_pat = r'^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\S+\s+\w+'
    if re.search(syslog_pat, sample, re.MULTILINE):
        return "generic_syslog"

    # Generic web access log (HTTP requests)
    if re.search(r'(GET|POST|PUT|DELETE|HEAD)\s+/\S*\s+HTTP/', sample):
        return "generic_web"

    return "unknown"


# ============================================================
# 告警规则库（20+ 种）
# ============================================================

# 每种规则包含：
#   name        - 攻击类型名称
#   log_types   - 可匹配的日志格式列表（空列表 = 全部匹配）
#   patterns    - 正则表达式列表（任一命中即计分）
#   mitre_id    - MITRE ATT&CK ID
#   mitre_name  - 技术名称
#   risk        - 风险等级（critical / high / medium / low）
#   description - 描述模板

RULES = [
    # ==================== Web 攻击 ====================
    {
        "name": "SQL Injection",
        "log_types": ["nginx_combined", "generic_web", "suricata_eve"],
        "patterns": [
            r"(?i)(union\s+select|select\s+.*\s+from\s+.*\s+where)",
            r"(?i)('\s*or\s*'1'\s*=\s*'1|'\s*or\s*'1'\s*=')",
            r"(?i)(sleep\(\d+\)|waitfor\s+delay|benchmark\s*\()",
            r"(?i)(exec\s*\(|xp_cmdshell|sp_executesql)",
            r"(?i)(information_schema|sys\.objects|sys\.columns)",
            r"(?i)(0x[\da-f]{16,})",
            r"(?i)(order\s+by\s+\d+|--\s*$|--\s+-)",
            r"(?i)(;drop\s+table|;truncate\s+|into\s+outfile|into\s+dumpfile)",
            r"(?i)(%27|%22|%3B|%2D%2D)",
        ],
        "mitre_id": "T1190",
        "mitre_name": "Exploit Public-Facing Application",
        "risk": "high",
        "description": "检测到 SQL 注入攻击特征：{preview}",
    },
    {
        "name": "Cross-Site Scripting (XSS)",
        "log_types": ["nginx_combined", "generic_web", "suricata_eve"],
        "patterns": [
            r"(?i)(<script[\s>])",
            r"(?i)(javascript:\s*|vbscript:\s*)",
            r"(?i)(onerror\s*=|onload\s*=|onclick\s*=|onfocus\s*=|onmouseover\s*=)",
            r"(?i)(alert\s*\(|prompt\s*\(|confirm\s*\()",
            r"(?i)(<img\s+src\s*=.*onerror|<svg\s+onload)",
            r"(?i)(%3Cscript%3E|%3Csvg%20onload|%3Cimg%20src)",
            r"(?i)(eval\s*\(.*document\.|String\.fromCharCode)",
        ],
        "mitre_id": "T1059.007",
        "mitre_name": "Command and Scripting Interpreter: JavaScript",
        "risk": "medium",
        "description": "检测到跨站脚本攻击（XSS）特征：{preview}",
    },
    {
        "name": "Remote Code Execution",
        "log_types": ["nginx_combined", "generic_web", "suricata_eve"],
        "patterns": [
            r"(?i)(system\s*\(|exec\s*\(|passthru\s*\(|shell_exec)",
            r"(?i)(cmd\.exe|powershell\s+-\w+\s+)",
            r"(?i)(/bin/bash|/bin/sh|/bin/dash)",
            r"(?i)(\$\{IFS\}|\$\{7\}|\$\(whoami\))",
            r"(?i)(wget\s+http|curl\s+http|nc\s+\d+\.\d+\.\d+\.\d+)",
        ],
        "mitre_id": "T1203",
        "mitre_name": "Exploitation for Client Execution",
        "risk": "critical",
        "description": "检测到远程命令执行攻击特征：{preview}",
    },
    {
        "name": "Path Traversal",
        "log_types": ["nginx_combined", "generic_web"],
        "patterns": [
            r"(?i)(\.\.\/|\.\.\\)",
            r"(?i)(%2e%2e%2f|%2e%2e%5c|%c0%ae%c0%ae/)",
            r"(?i)(etc/passwd|etc/shadow|boot\.ini|windows/win\.ini)",
            r"(?i)(proc/self/environ|proc/self/cmdline)",
            r"(?i)(\.\./\.\./\.\./|\.\.\\\.\.\\\.\.\\)",
        ],
        "mitre_id": "T1190",
        "mitre_name": "Exploit Public-Facing Application",
        "risk": "high",
        "description": "检测到路径遍历攻击特征：{preview}",
    },
    {
        "name": "SSRF (Server-Side Request Forgery)",
        "log_types": ["nginx_combined", "generic_web"],
        "patterns": [
            r"(?i)(file://|gopher://|dict://|ftp://)",
            r"(169\.254\.169\.254|metadata\.google\.internal|metadata\.amazonaws\.com)",
            r"(?i)(url=|redirect=|return=|dest=|target=|host=)\s*(?:https?://)?(?:127\.0\.0\.1|localhost|0\.0\.0\.0)",
            r"(?i)(url=|redirect=|return=|dest=|target=|host=)\s*(?:https?://)?(?:10\.|172\.(?:1[6-9]|2[0-9]|3[01])\.|192\.168\.)",
        ],
        "mitre_id": "T1190",
        "mitre_name": "Exploit Public-Facing Application",
        "risk": "high",
        "description": "检测到服务端请求伪造（SSRF）特征：{preview}",
    },
    {
        "name": "Local File Inclusion (LFI)",
        "log_types": ["nginx_combined", "generic_web"],
        "patterns": [
            r"(?i)(include\s*\(.*\.\.|require\s*\(.*\.\.)",
            r"(?i)(php://input|php://filter|data://|expect://)",
            r"(?i)(include_once|require_once).*\.\.",
        ],
        "mitre_id": "T1190",
        "mitre_name": "Exploit Public-Facing Application",
        "risk": "high",
        "description": "检测到本地文件包含（LFI）攻击特征：{preview}",
    },
    {
        "name": "WebShell Access",
        "log_types": ["nginx_combined", "generic_web"],
        "patterns": [
            r"(?i)(webshell|一句话木马|大马|小马)",
            r"(?i)(eval\s*\(.*\$_|assert\s*\(.*\$)",
            r"(?i)(base64_decode\s*\(.*\$_|base64_decode\s*\(.*\$POST)",
            r"(?i)(c99|r57|b374k|shell\.php|cmd\.php)",
        ],
        "mitre_id": "T1505.003",
        "mitre_name": "Server Software Component: Web Shell",
        "risk": "critical",
        "description": "检测到 Webshell 访问特征：{preview}",
    },
    {
        "name": "Malicious File Upload",
        "log_types": ["nginx_combined", "generic_web"],
        "patterns": [
            r"(?i)(Content-Disposition:.*\.php|Content-Disposition:.*\.jsp)",
            r"(?i)(\.php\s*$|\.jsp\s*$|\.war\s*$|\.aspx\s*$|\.ashx\s*$)",
            r"(?i)(Content-Disposition:.*filename=.*\.(?:php[0-9]?|phtml|shtml|jsp|jspx|war|asp|aspx|ashx|cgi|pl|py|rb))",
        ],
        "mitre_id": "T1190",
        "mitre_name": "Exploit Public-Facing Application",
        "risk": "high",
        "description": "检测到恶意文件上传特征：{preview}",
    },
    {
        "name": "Suspicious User-Agent (Scanning)",
        "log_types": ["nginx_combined", "generic_web"],
        "patterns": [
            r"(?i)(sqlmap|nmap|masscan|nikto|acunetix|nessus|openvas)",
            r"(?i)(python-requests|Go-http-client|curl/\d|wget/\d)",
            r"(?i)(zgrab|massdns|httpx|subfinder)",
        ],
        "mitre_id": "T1046",
        "mitre_name": "Network Service Scanning",
        "risk": "low",
        "description": "检测到可疑 User-Agent（扫描工具特征）：{preview}",
    },
    {
        "name": "Directory Brute Force",
        "log_types": ["nginx_combined", "generic_web"],
        "patterns": [
            r"(?i)(/admin|/wp-admin|/wp-login|/administrator)",
            r"(?i)(/api/v1|/api/v2|/swagger|/docs)",
            r"(?i)(/\.git|/\.env|/\.svn|/config\.php|/db\.php)",
            r"(?i)(/phpmyadmin|/pma|/myadmin)",
        ],
        "mitre_id": "T1190",
        "mitre_name": "Exploit Public-Facing Application",
        "risk": "low",
        "description": "检测到目录扫描/暴力破解特征：{preview}",
    },

    # ==================== 系统攻击 ====================
    {
        "name": "SSH Brute Force",
        "log_types": ["linux_auth", "generic_syslog"],
        "patterns": [
            r"(?i)(Failed password for)",
            r"(?i)(Invalid user)",
            r"(?i)(authentication failure)",
            r"(?i)(Connection closed by.*\[preauth\])",
            r"(?i)(pam_unix\(sshd:auth\):\s+authentication failure)",
        ],
        "mitre_id": "T1110",
        "mitre_name": "Brute Force",
        "risk": "medium",
        "description": "检测到 SSH 暴力破解尝试：{preview}",
    },
    {
        "name": "SSH Login Success",
        "log_types": ["linux_auth", "generic_syslog"],
        "patterns": [
            r"(?i)(Accepted password for)",
            r"(?i)(Accepted publickey for)",
            r"(?i)(session opened for user)",
        ],
        "mitre_id": "T1078",
        "mitre_name": "Valid Accounts",
        "risk": "low",
        "description": "SSH 登录成功记录：{preview}",
    },
    {
        "name": "Sudo Privilege Escalation",
        "log_types": ["linux_auth", "generic_syslog"],
        "patterns": [
            r"(?i)(sudo:.*COMMAND=)",
            r"(?i)(FAILED SU)",
            r"(?i)(Authentication failure.*root)",
            r"(?i)(sudo:.*USER=root)",
        ],
        "mitre_id": "T1548",
        "mitre_name": "Abuse Elevation Control Mechanism",
        "risk": "high",
        "description": "检测到 sudo 提权操作：{preview}",
    },
    {
        "name": "SSH User Enumeration",
        "log_types": ["linux_auth", "generic_syslog"],
        "patterns": [
            r"(?i)(Invalid user \w+\s+from)",
            r"(?i)(Failed password for invalid user)",
        ],
        "mitre_id": "T1110",
        "mitre_name": "Brute Force",
        "risk": "medium",
        "description": "检测到 SSH 用户枚举攻击：{preview}",
    },

    # ==================== 网络/扫描攻击 ====================
    {
        "name": "Port Scan Detection",
        "log_types": ["suricata_eve", "generic_syslog", "generic_web"],
        "patterns": [
            r"(?i)(port\s*scan|nmap|masscan|syn\s*scan|portscan)",
            r"(?i)(conn_state.*S0|conn_state.*REJ)",
            r"(?i)(too many ports|scanning detected)",
        ],
        "mitre_id": "T1046",
        "mitre_name": "Network Service Scanning",
        "risk": "low",
        "description": "检测到端口扫描行为：{preview}",
    },
    {
        "name": "DNS Tunneling",
        "log_types": ["suricata_eve", "generic_syslog"],
        "patterns": [
            r"(?i)(type:\s*TXT|qtype_name:\s*TXT)",
            r"(?i)([a-z0-9]{30,}\.(com|top|xyz|cn|info))",
            r"(?i)(dns\.query.*base64|dns\.query.*hex)",
        ],
        "mitre_id": "T1572",
        "mitre_name": "Protocol Tunneling",
        "risk": "medium",
        "description": "检测到 DNS 隧道通信特征：{preview}",
    },
    {
        "name": "DGA Domain Detection",
        "log_types": ["suricata_eve", "nginx_combined", "generic_web"],
        "patterns": [
            r"(?i)([a-z]{20,}\.(com|top|xyz|club|site|work))",
            r"(?i)([a-z0-9]{15,}\.(com|top|xyz))",
        ],
        "mitre_id": "T1568",
        "mitre_name": "Dynamic Resolution",
        "risk": "medium",
        "description": "检测到疑似 DGA 算法生成的域名：{preview}",
    },
    {
        "name": "C2 Communication",
        "log_types": ["suricata_eve", "nginx_combined", "generic_web"],
        "patterns": [
            r"(?i)(ja3.*(?:[a-f0-9]{32}))",
            r"(?i)(sni.*[a-z0-9]{15,}\.(com|top|xyz))",
            r"(?i)(POST.*/gateway\.php|POST.*/api/.*/heartbeat)",
        ],
        "mitre_id": "T1071",
        "mitre_name": "Application Layer Protocol",
        "risk": "high",
        "description": "检测到可疑 C2 通信特征：{preview}",
    },

    # ==================== 通用检测 ====================
    {
        "name": "DDoS / Flooding",
        "log_types": [],
        "patterns": [
            r"(?i)(too many requests|rate limit|connection refused)",
            r"(?i)(syn flood|syn_flood|udp flood|icmp flood)",
            r"(?i)(connection reset by peer.*too many)",
        ],
        "mitre_id": "T1498",
        "mitre_name": "Network Denial of Service",
        "risk": "high",
        "description": "检测到 DDoS/Flooding 攻击特征：{preview}",
    },
    {
        "name": "Suspicious Base64 Payload",
        "log_types": [],
        "patterns": [
            r"(?i)([A-Za-z0-9+/]{60,}={0,2})",
            r"(?i)(base64_decode|base64_encode)",
        ],
        "mitre_id": "T1027",
        "mitre_name": "Obfuscated Files or Information",
        "risk": "medium",
        "description": "检测到可疑 Base64 编码载荷：{preview}",
    },
    {
        "name": "Information Disclosure",
        "log_types": ["nginx_combined", "generic_web"],
        "patterns": [
            r"(?i)(\.git/config|\.env|\.aws/credentials|credentials\.json)",
            r"(?i)(/server-status|/server-info|/phpinfo\.php)",
            r"(?i)(stack trace:|debug_backtrace|Fatal error:|Parse error:)",
        ],
        "mitre_id": "T1592",
        "mitre_name": "Gather Victim Host Information",
        "risk": "medium",
        "description": "检测到敏感信息泄露特征：{preview}",
    },
    {
        "name": "Brute Force (Generic)",
        "log_types": [],
        "patterns": [
            r"(?i)(brute\s*force|login\s*failure|auth\s*failure|too\s*many\s*login)",
            r"(?i)(invalid\s+credentials|login\s+attempt\s+failed)",
        ],
        "mitre_id": "T1110",
        "mitre_name": "Brute Force",
        "risk": "medium",
        "description": "检测到暴力破解攻击特征：{preview}",
    },
]


# ============================================================
# 引擎核心
# ============================================================

class AlertEngine:
    def parse(self, raw_text: str, source: Optional[str] = None) -> AlertParseResponse:
        lines = raw_text.strip().split("\n")
        line_count = len(lines)

        # 1. 检测日志格式
        fmt = detect_format(raw_text)

        # 2. 筛选该格式可匹配的规则
        applicable = [r for r in RULES if not r["log_types"] or fmt in r["log_types"]]

        # 3. 多规则匹配计分
        matches = []  # [{name, risk, mitre_id, mitre_name, score, detail}]
        for rule in applicable:
            total_score = 0
            matched_lines = 0
            for pat in rule["patterns"]:
                # 逐行匹配避免单行跨度过大
                for line in lines:
                    if re.search(pat, line):
                        total_score += 10
                        matched_lines += 1
            if total_score > 0:
                # 同一规则多行命中额外加分
                if matched_lines > 1:
                    total_score += matched_lines * 5
                confidence = min(100, total_score)
                matches.append({
                    "name": rule["name"],
                    "risk": rule["risk"],
                    "confidence": confidence,
                    "mitre_id": rule["mitre_id"],
                    "mitre_name": rule["mitre_name"],
                    "score": total_score,
                })

        # 4. 按总分排序取 top
        matches.sort(key=lambda m: m["score"], reverse=True)

        if not matches:
            preview = raw_text[:200].replace("\n", " ")
            return AlertParseResponse(
                attack_type="Unknown / Benign",
                mitre_id=None,
                mitre_name=None,
                risk_level="low",
                confidence=20,
                description="未匹配到已知攻击模式，请人工分析确认。",
                recommendation="建议查看原始日志上下文，确认是否为误报。",
                related_techniques=[],
                detected_format=fmt,
                all_matches=[],
                line_count=line_count,
                match_count=0,
            )

        # 5. 构造返回
        best = matches[0]
        all_matches_items = [
            AlertMatchItem(
                attack_type=m["name"],
                risk_level=m["risk"],
                confidence=m["confidence"],
                mitre_id=m["mitre_id"],
                mitre_name=m["mitre_name"],
            )
            for m in matches[:10]  # 最多返回 10 个
        ]
        related = [{"id": m["mitre_id"], "name": m["mitre_name"]} for m in matches[:5]]

        preview = raw_text[:200].replace("\n", " ")
        desc = self._generate_description(best["name"], preview)
        rec = self._generate_recommendation(best["risk"], best["name"])

        return AlertParseResponse(
            attack_type=best["name"],
            mitre_id=best["mitre_id"],
            mitre_name=best["mitre_name"],
            risk_level=best["risk"],
            confidence=best["confidence"],
            description=desc,
            recommendation=rec,
            related_techniques=related,
            detected_format=fmt,
            all_matches=all_matches_items,
            line_count=line_count,
            match_count=len(matches),
        )

    @staticmethod
    def _generate_description(attack_type: str, preview: str) -> str:
        return f"告警疑似为 {attack_type} 攻击。原始内容摘要: {preview}..."

    @staticmethod
    def _generate_recommendation(risk: str, attack_type: str) -> str:
        recs = {
            "critical": (
                f"【紧急处置】确认 {attack_type} 攻击是否成功，立即隔离受影响系统，"
                f"采集内存/日志证据，启动应急响应流程。"
            ),
            "high": (
                f"【优先处理】确认 {attack_type} 攻击请求是否到达目标，"
                f"检查 WAF/IPS 拦截日志，必要时添加临时阻断规则。"
            ),
            "medium": (
                f"【关注】分析 {attack_type} 攻击来源 IP，查询威胁情报，"
                f"评估是否需要提升防护等级。"
            ),
            "low": (
                f"【常规】记录 {attack_type} 告警，定期汇总分析攻击趋势。"
            ),
        }
        return recs.get(risk, "请人工分析确认。")