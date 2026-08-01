TECHNIQUES = [
    {
        "id": "T1190",
        "name": "Exploit Public-Facing Application",
        "tactics": ["Initial Access"],
        "description": "攻击者利用面向公众的应用程序中的漏洞进行初始访问。",
        "detection": "监控WAF/IPS告警、异常HTTP请求、未知User-Agent。",
        "mitigation": "定期更新补丁、部署WAF、最小化攻击面。",
    },
    {
        "id": "T1059.007",
        "name": "Command and Scripting Interpreter: JavaScript",
        "tactics": ["Execution"],
        "description": "攻击者使用JavaScript执行恶意代码，常用于XSS攻击。",
        "detection": "监控异常脚本加载、CSP违规告警、DOM异常操作。",
        "mitigation": "实施CSP策略、输入输出编码、使用防XSS库。",
    },
    {
        "id": "T1203",
        "name": "Exploitation for Client Execution",
        "tactics": ["Execution"],
        "description": "攻击者利用客户端应用程序漏洞执行任意代码。",
        "detection": "监控异常进程创建、Office文档宏行为、浏览器崩溃日志。",
        "mitigation": "禁用不必要的宏、使用应用白名单、及时更新客户端软件。",
    },
    {
        "id": "T1046",
        "name": "Network Service Scanning",
        "tactics": ["Discovery"],
        "description": "攻击者扫描目标网络以发现开放端口和服务。",
        "detection": "监控异常端口扫描流量、IDS/IPS扫描告警、DNS异常查询。",
        "mitigation": "限制入站流量、部署防火墙规则、隐藏非必要端口。",
    },
    {
        "id": "T1110",
        "name": "Brute Force",
        "tactics": ["Credential Access"],
        "description": "攻击者通过暴力破解获取账号密码凭证。",
        "detection": "监控登录失败次数、异常时间登录、异地登录告警。",
        "mitigation": "启用多因素认证、账户锁定策略、复杂密码策略。",
    },
    {
        "id": "T1505.003",
        "name": "Server Software Component: Web Shell",
        "tactics": ["Persistence"],
        "description": "攻击者在Web服务器上部署Webshell以维持持久化访问。",
        "detection": "监控文件完整性、异常文件创建、Webshell特征检测。",
        "mitigation": "限制上传功能、执行严格权限控制、定期文件审计。",
    },
    {
        "id": "T1566",
        "name": "Phishing",
        "tactics": ["Initial Access"],
        "description": "攻击者通过钓鱼邮件诱导用户点击恶意链接或打开附件。",
        "detection": "邮件网关过滤、URL信誉检测、沙箱分析附件。",
        "mitigation": "员工安全意识培训、部署DMARC/DKIM/SPF、邮件沙箱检测。",
    },
    {
        "id": "T1055",
        "name": "Process Injection",
        "tactics": ["Defense Evasion", "Privilege Escalation"],
        "description": "攻击者将恶意代码注入到合法进程中以逃避检测。",
        "detection": "监控异常API调用、进程内存访问、CreateRemoteThread行为。",
        "mitigation": "启用Windows Defender Credential Guard、监控敏感API。",
    },
    {
        "id": "T1486",
        "name": "Data Encrypted for Impact",
        "tactics": ["Impact"],
        "description": "攻击者加密目标数据以索要赎金（勒索软件攻击）。",
        "detection": "监控大量文件重命名/加密操作、异常SMB流量、高I/O写入。",
        "mitigation": "定期离线备份、隔离关键系统、限制管理员权限。",
    },
    {
        "id": "T1071",
        "name": "Application Layer Protocol",
        "tactics": ["Command and Control"],
        "description": "攻击者使用标准应用层协议（HTTP/DNS）进行C2通信。",
        "detection": "监控异常外连IP、DNS TXT查询异常、HTTPS流量指纹分析。",
        "mitigation": "网络分段、出口过滤、DNS隧道检测。",
    },
]

def get_all_techniques():
    return {"count": len(TECHNIQUES), "techniques": TECHNIQUES}

def get_technique(technique_id: str):
    for t in TECHNIQUES:
        if t["id"] == technique_id.upper():
            return t
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail=f"Technique {technique_id} not found")
