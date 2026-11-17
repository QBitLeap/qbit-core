"""Require complete exact-platform evidence before image/catalog publication."""
import argparse,json,os,subprocess
from pathlib import Path
from upstream_release import PLATFORMS
ROOT=Path(__file__).resolve().parents[1]
def checked(evidence,rows):
 if set(rows)!=set(PLATFORMS)or set(evidence.get('platformArtifacts',{}))!=set(PLATFORMS):raise ValueError('All supported native platform results required')
 for target,row in rows.items():
  if row.get('target')!=target or row.get('passed')is not True or row.get('nodeStarted')is not False or row.get('installedDataAccessed')is not False or row.get('upstreamTag')!=evidence['upstreamTag']or row.get('archiveSha256')!=evidence['platformArtifacts'][target]['sha256']:raise ValueError('Platform evidence identity or acceptance differs: '+target)
 return rows
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('check','publish'));a=p.parse_args();evidence=json.loads((ROOT/'releases/upstream/verification.json').read_bytes());rows={f.stem:json.loads(f.read_bytes())for f in(ROOT/'.release/platforms').glob('*.json')};checked(evidence,rows)
 if a.mode=='publish':
  version=os.environ['CORE_VERSION']
  if evidence['upstreamTag']!='v'+version:raise ValueError('Publication version differs from verified release')
  if os.environ['IMAGE_CHANGED']=='true':
   build=version+'-upstream.'+os.environ['GITHUB_RUN_ID']+'.'+os.environ['GITHUB_RUN_ATTEMPT'];receipt=json.loads((ROOT/'.release'/build/'published-images.json').read_bytes());receipt['sourceRevision']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
  else:
   receipt=json.loads((ROOT/'releases/upstream/latest.json').read_bytes())
   if receipt['upstreamTag']!=evidence['upstreamTag']:raise ValueError('Refuse platform-only refresh for different image version')
  receipt.update(upstreamTag=evidence['upstreamTag'],upstreamVerification=evidence,platformChecksPassed=True,platformChecks=rows,catalogAcceptanceRequired=True);(ROOT/'releases/upstream/latest.json').write_text(json.dumps(receipt,indent=2)+'\n')
