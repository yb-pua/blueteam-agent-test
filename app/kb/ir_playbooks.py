PLAYBOOKS = [
    {
        "id": "IR-001",
        "name": "Ransomware 勒索软件应急响应",
        "severity": "critical",
        "steps": [
            "1. 立即隔离受影响系统，断开网络连接",
            "2. 收集勒索信息：赎金金额、联系方式、加密文件样本",
            "3. 保留内存和磁盘取证镜像",
            "4. 确定攻击入口：钓鱼邮件、RDP爆破、漏洞利用",
            "5. 检查横向移动痕迹，排查同网段其他主机",
            "6. 在防火墙和EDR中阻断发现的C2域名/IP",
            "7. 从离线备份恢复数据",
            "8. 修复安全漏洞，重置所有受影响账户密码",
            "9. 撰写事件报告，总结教训改进防护",
        ],
        "tools": ["EDR平台", "Volatility(内存取证)", "Wireshark", "离线备份系统"],
    },
    {
        "id": "IR-002",
        "name": "Webshell 发现应急响应",
        "severity": "high",
        "steps": [
            "1. 确认Webshell文件路径，备份文件样本",
            "2. 检查Web服务器日志，确定首次上传时间和来源IP",
            "3. 搜索同服务器其他Webshell文件",
            "4. 查看Webshell连接记录，分析攻击者操作",
            "5. 检查数据是否被窃取（数据库、配置文件等）",
            "6. 清除Webshell文件，修复文件上传漏洞",
            "7. 重置Web服务相关账户密码",
            "8. 部署WAF规则阻止类似攻击",
        ],
        "tools": ["文件完整性监控(FIM)", "Web日志分析工具", "YARA规则扫描"],
    },
    {
        "id": "IR-003",
        "name": "数据泄露事件应急响应",
        "severity": "critical",
        "steps": [
            "1. 确认泄露数据类型和规模",
            "2. 查找数据出口：数据库导出、邮件外发、FTP传输",
            "3. 检查数据库/DLP日志，定位数据访问记录",
            "4. 封锁泄露渠道，重置相关API密钥",
            "5. 评估影响范围：受影响的用户数、数据类型",
            "6. 通知数据保护官(DPO)和法务部门",
            "7. 按法规要求报告监管机构（如适用）",
            "8. 通知受影响用户，提供补救建议",
        ],
        "tools": ["DLP平台", "数据库审计日志", "邮件安全网关"],
    },
    {
        "id": "IR-004",
        "name": "DDoS 攻击应急响应",
        "severity": "high",
        "steps": [
            "1. 通过流量分析确认DDoS攻击类型（SYN Flood/HTTP Flood/DNS Amplification）",
            "2. 联系ISP/CDN启用流量清洗服务",
            "3. 部署临时WAF规则：限速、IP黑名单、挑战验证",
            "4. 启用云防护（Cloudflare/Akamai）的DDoS防护模式",
            "5. 扩容后端资源应对流量冲击",
            "6. 监控攻击趋势，持续调整防护策略",
            "7. 攻击结束后分析攻击向量，完善防护方案",
        ],
        "tools": ["流量分析(NetFlow/sFlow)", "WAF", "CDN/云防护平台"],
    },
]

def get_all_playbooks():
    return {"count": len(PLAYBOOKS), "playbooks": PLAYBOOKS}

def get_playbook(playbook_id: str):
    for p in PLAYBOOKS:
        if p["id"] == playbook_id.upper():
            return p
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail=f"Playbook {playbook_id} not found")
