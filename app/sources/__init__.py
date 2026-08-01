from .base import OSINTSource
from .virustotal import VirusTotalSource
from .abuseipdb import AbuseIPDBSource
from .otx import OTXSource
from .urlscan import URLScanSource
from .shodan import ShodanSource
from .censys import CensysSource
from .nvd import NVDSource
from .phishtank import PhishTankSource
from .threatbook import ThreatBookSource
from .ipinfo import IPInfoSource, IPWhoIsSource
from .feed_sources import FeedThreatSource, FeedVulnSource, FeedStatsSource

ALL_SOURCES: list[OSINTSource] = [
    VirusTotalSource(),
    AbuseIPDBSource(),
    OTXSource(),
    URLScanSource(),
    ShodanSource(),
    CensysSource(),
    NVDSource(),
    PhishTankSource(),
    ThreatBookSource(),
    IPInfoSource(),
    IPWhoIsSource(),
    FeedThreatSource(),
    FeedVulnSource(),
    FeedStatsSource(),
]

def get_configured_sources() -> list[OSINTSource]:
    """Return all sources; engine filters by can_handle() and config per-query."""
    return [s for s in ALL_SOURCES if s.is_configured or not s.requires_key]

def refresh_all():
    """Re-check config on all sources (call after runtime config changes)."""
    changed = []
    for s in ALL_SOURCES:
        if s.reload():
            changed.append(s.name)
    return changed
