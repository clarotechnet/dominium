from pathlib import Path
from html.parser import HTMLParser
import subprocess
import re
root=Path(__file__).resolve().parents[1]
html=(root/'static/index.html').read_text(encoding='utf8')
js=(root/'static/app.js').read_text(encoding='utf8')
client=(root/'static/backlog-analysis.js').read_text(encoding='utf8')
assert html.count('id="backlogWorkspace"')==1
assert '<strong>Query | Atlas</strong>' in html
assert '<h2>Query | Atlas</h2>' in html
assert '<strong>Pendente</strong><small>Atlas × IMPERIUM</small>' not in html
assert '"/api/backlog/year/routes",{source:"toa"}' in client
assert '"/api/backlog/year/status"' in client
assert '/api/backlog/year/toa-import' not in client
assert html.count('id="backlogModule"')==1
assert 'src="/backlog-analysis.js?v=20261103-image-1"' in html
assert 'src="/backlog-report-image.js?v=20261103-image-2"' in html
assert 'src="/backlog-report.js?v=20261103-whatsapp-1"' in html
assert 'href="/backlog-analysis.css?v=20261103-image-1"' in html
assert 'src="/app.js?v=20261103-backlog-todos-1"' in html
for id in ['backlogRun','backlogPilot','backlogPause','backlogProfile',
           'backlogRouteFiles','backlogUpload','backlogCompare','backlogResult',
           'backlogFromTOA','backlogAutoStatus','backlogDailyRefresh',
           'backlogCityScope','backlogScopeLabel','backlogReportSummary',
           'backlogReportDetails','backlogReportStatus','backlogCopySummary',
           'backlogDownloadImage',
           'backlogCopyImproductive','backlogDailyMetrics','backlogDailyResult',
           'backlogOffRouteResult','backlogSentResult']:
    assert html.count('id="'+id+'"')==1,id
for tab in ['entry','result','daily','offroute','sent']:
    assert 'data-backlog-tab="'+tab+'"' in html
    assert 'data-backlog-pane="'+tab+'"' in html
assert 'const call = (path, opts={}) => request(path,' in client
assert 'DominiumBacklogReportImage' in client
assert '.backlog-report-city table{border-collapse:collapse;width:100%;min-width:0;' in (root/'static/backlog-analysis.css').read_text(encoding='utf8')
assert 'request(apiUrl(path)' not in client
assert '$(\"backlogRun\").disabled=true' in client
assert '$(\"backlogRun\").disabled=Boolean(s.running)' not in client
for marker in [
    'function selectedMaterialIssues(',
    'function selectedMaterialAdjustments(',
    'return adjustments.filter((item) => item.posted_quantity > 0)',
    'const blocked = unresolved > 0 || validation.can_close === false',
    'state.materialPasteReconciliation',
]:
    assert marker in js, 'Regression: '+marker
class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.counts={}
        self.stack=[]
        self.errors=[]
        self.in_backlog=False
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if d.get('id')=='backlogWorkspace':self.in_backlog=True
        if self.in_backlog and tag in ('div','section','nav','header','details'):
            self.stack.append(tag)
    def handle_endtag(self,tag):
        if self.in_backlog and tag in ('div','section','nav','header','details'):
            if not self.stack or self.stack[-1]!=tag:self.errors.append((tag,self.stack[-4:]))
            else:self.stack.pop()
            if not self.stack:self.in_backlog=False
parser=Collector()
parser.feed(html)
assert not parser.errors,parser.errors
assert not parser.stack,parser.stack
print('BACKLOG_UI_STRUCTURAL_OK=True')
print('STOCK_RECONCILIATION_MARKERS_PRESERVED=True')
print('5_TABS_TOA_AND_UPLOAD_OK=True')