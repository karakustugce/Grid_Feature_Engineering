"""Assemble workflows/02_multisource_normalize.json from the readable JS in 02_code/.

Edit the .js files (they are what git diffs show), then:  python workflows/build_02.py
"""
import json
import uuid
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).parent
CODE = HERE / "02_code"
SHARED = (CODE / "_shared.js").read_text()
SEC_UA = "Grid Feature Engineering research YOUR_NAME your_email@example.com"  # SEC requires a real contact

gdelt_q = '("Apple Inc" OR AAPL OR "Tim Cook" OR iPhone OR "App Store" OR "Apple Intelligence") sourcelang:english'
GDELT_URL = ("https://api.gdeltproject.org/api/v2/doc/doc?query=" + quote(gdelt_q)
             + "&mode=artlist&format=json&timespan=3d&maxrecords=250&sort=datedesc")
GNEWS_URL = ("https://news.google.com/rss/search?q=" + quote('Apple (AAPL OR iPhone OR "Tim Cook") when:3d')
             + "&hl=en-US&gl=US&ceid=US:en")


_counter = iter(range(1000))


def nid():
    """Deterministic node ids so rebuilding does not create noisy diffs."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"gfe-02-{next(_counter)}"))


def code(name, file, pos, shared=True, always=False):
    js = (CODE / file).read_text()
    node = {"parameters": {"jsCode": (SHARED + "\n// ---- node code ----\n" + js) if shared else js},
            "id": nid(), "name": name, "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos}
    if always:
        node["alwaysOutputData"] = True
    return node


def http(name, url, pos, headers=None):
    p = {"url": url, "options": {"timeout": 30000}}
    if headers:
        p["sendHeaders"] = True
        p["headerParameters"] = {"parameters": [{"name": k, "value": v} for k, v in headers.items()]}
    return {"parameters": p, "id": nid(), "name": name, "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2, "position": pos, "onError": "continueRegularOutput",
            "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000}


def rss(name, url, pos):
    return {"parameters": {"url": url, "options": {}}, "id": nid(), "name": name,
            "type": "n8n-nodes-base.rssFeedRead", "typeVersion": 1.2, "position": pos,
            "onError": "continueRegularOutput", "retryOnFail": True, "maxTries": 3, "waitBetweenTries": 2000}


nodes = [
    {"parameters": {}, "id": nid(), "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger",
     "typeVersion": 1, "position": [0, 400]},
    code("Run Config", "run_config.js", [220, 400], shared=False),
    http("GDELT DOC (JSON)", GDELT_URL, [480, 100]),
    rss("Google News RSS", GNEWS_URL, [480, 300]),
    rss("Apple Newsroom RSS", "https://www.apple.com/newsroom/rss-feed.rss", [480, 500]),
    http("SEC EDGAR Submissions", "https://data.sec.gov/submissions/CIK0000320193.json", [480, 700],
         headers={"User-Agent": SEC_UA, "Accept": "application/json"}),
    code("Normalize GDELT", "normalize_gdelt.js", [740, 100], always=True),
    code("Normalize Google News", "normalize_google_news.js", [740, 300], always=True),
    code("Normalize Apple Newsroom", "normalize_apple_newsroom.js", [740, 500], always=True),
    code("Normalize SEC", "normalize_sec.js", [740, 700], always=True),
    {"parameters": {"numberInputs": 4}, "id": nid(), "name": "Merge Sources", "type": "n8n-nodes-base.merge",
     "typeVersion": 3, "position": [1000, 400]},
    code("Audit + Dedupe", "audit_dedupe.js", [1240, 400], shared=False),
    code("Run Report", "run_report.js", [1480, 560], shared=False),
]


def link(a, b, idx=0):
    return {"node": b, "type": "main", "index": idx}


connections = {
    "Manual Trigger": {"main": [[link("Manual Trigger", "Run Config")]]},
    "Run Config": {"main": [[link("", "GDELT DOC (JSON)"), link("", "Google News RSS"),
                             link("", "Apple Newsroom RSS"), link("", "SEC EDGAR Submissions")]]},
    "GDELT DOC (JSON)": {"main": [[link("", "Normalize GDELT")]]},
    "Google News RSS": {"main": [[link("", "Normalize Google News")]]},
    "Apple Newsroom RSS": {"main": [[link("", "Normalize Apple Newsroom")]]},
    "SEC EDGAR Submissions": {"main": [[link("", "Normalize SEC")]]},
    "Normalize GDELT": {"main": [[link("", "Merge Sources", 0)]]},
    "Normalize Google News": {"main": [[link("", "Merge Sources", 1)]]},
    "Normalize Apple Newsroom": {"main": [[link("", "Merge Sources", 2)]]},
    "Normalize SEC": {"main": [[link("", "Merge Sources", 3)]]},
    "Merge Sources": {"main": [[link("", "Audit + Dedupe")]]},
    "Audit + Dedupe": {"main": [[link("", "Run Report")]]},
}

wf = {"name": "AAPL news 02 - multi-source normalize + audit", "nodes": nodes, "connections": connections,
      "active": False, "settings": {"executionOrder": "v1", "timezone": "America/New_York"},
      "meta": {"templateCredsSetupCompleted": True}}
(HERE / "02_multisource_normalize.json").write_text(json.dumps(wf, indent=2))
print("wrote", HERE / "02_multisource_normalize.json", len(nodes), "nodes")
