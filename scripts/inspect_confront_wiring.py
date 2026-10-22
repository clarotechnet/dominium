from pathlib import Path
root=Path(__file__).resolve().parents[1]
items={
"static/app.js":["function updateAddress","function setModule","serialsModule","serialsWorkspace","serialsRun","serialsExport","async function bootstrap","hashchange","authUser","user.role","setModule("],
"deploy/hostinger-web/server.js":["operational-relay","operationalRelay","allowedOperationalRead","authorize","csrf","auth","/api/serials/consult","app.post","/api/"],
"deploy/hostinger-web/operational-relay.js":["allowedOperationalRead","request","fetch","method","profile"],
"integrations/serial_consult/desc_review_relay.py":["/api/serials/consult","serial_service","def do_GET","def do_POST","parse_route"],
}
for fn,patterns in items.items():
    p=root/fn
    lines=p.read_text(encoding="utf-8").splitlines()
    print("\nFILE",fn,"LINES",len(lines))
    total=0
    for n,line in enumerate(lines,1):
        if any(pat in line for pat in patterns):
            print(f"{n}: {line[:185]}")
            total+=1
            if total>65:break
