"""Create a consistent, local portable backup and a static research dashboard."""
import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import tarfile
import tempfile
import time

ROOT=Path(__file__).resolve().parent


def export(destination):
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        bundle=Path(temp)/"hunter"
        bundle.mkdir()
        for name in ("src","rt","docs","experiments"):
            shutil.copytree(ROOT/name,bundle/name,ignore=shutil.ignore_patterns('__pycache__'))
        for name in ("build.sh","README.md","moon.py","research.py","shared_learning.py","calibration.py","fleet_supervisor.py","export_learning.py",
                     "research.html","ui.html","state.tsv","records.txt","FOUND.tsv","VERIFIED.tsv",
                     "gaps.tsv","jobs.tsv","submitted.txt","table.tsv"):
            if (ROOT/name).exists(): shutil.copy2(ROOT/name,bundle/name)
        (bundle/"learning").mkdir()
        source=ROOT/"learning/research.sqlite3"
        if source.exists():
            with sqlite3.connect(f"file:{source}?mode=ro",uri=True) as db:
                with sqlite3.connect(bundle/"learning/research.sqlite3") as target: db.backup(target)
        for name in ("summary.json","calibration.json","found.tsv","shared.json","shared-scale.tsv","known-records.txt","public-bands.json","submissions.json"):
            if (ROOT/"learning"/name).exists(): shutil.copy2(ROOT/"learning"/name,bundle/"learning"/name)
        manifest=dict(created=time.time(),note="SQLite uses online backup. Ordinary log copies may include active work; stop the hunter for a fully quiescent snapshot.")
        (bundle/"backup.json").write_text(json.dumps(manifest,indent=2))
        path=destination/time.strftime("hunter-%Y%m%d-%H%M%S.tar.gz")
        with tarfile.open(path,"w:gz") as archive: archive.add(bundle,arcname="hunter")
    pages=destination/"pages"
    pages.mkdir(exist_ok=True)
    html=(ROOT/"research.html").read_text().replace('<a href="/">← ordinary hunter</a>',
        '<p>saved research snapshot · this page does not run the hunter</p>')
    (pages/"index.html").write_text(html)
    for source,name in (("summary.json","research.json"),("calibration.json","calibration.json"),("shared.json","shared.json")):
        if (ROOT/"learning"/source).exists():
            value=json.loads((ROOT/"learning"/source).read_text())
            if source=="summary.json": value.update(status="saved snapshot — no live worker connection",phase="exported for static hosting")
            (pages/name).write_text(json.dumps(value))
    print(path)
    print(pages)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination",type=Path,nargs="?",default=ROOT/"build/portable")
    export(parser.parse_args().destination)
