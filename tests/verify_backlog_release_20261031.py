from pathlib import Path
import zipfile
root=Path(r"C:\DominiumRuntime\BacklogDominiumDeployLab-20261031")
z=zipfile.ZipFile(root/"output"/"hostinger-node-release.zip")
names=z.namelist()
for suffix in ("app.js","backlog-analysis.js","backlog-analysis.css","backlog-proxy.js","server.js","index.html"):
    matching=[name for name in names if name.endswith("/"+suffix) or name==suffix]
    print("ZIP_MEMBER",suffix,len(matching),matching[:1])
    assert len(matching)==1
assert len(z.read(next(x for x in names if x.endswith("/backlog-analysis.js"))))>9000
print("BACKLOG_RELEASE_PACKAGE_OK=True")
