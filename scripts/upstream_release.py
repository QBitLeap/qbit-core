"""Prepare stable upstream Core locks only after pinned three-signer verification.
No node operation, wallet, installed data or automatic installation access.
"""
import argparse,base64,hashlib,json,os,re,subprocess,tarfile,tempfile
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
API='https://api.github.com/repos/Qbit-Org/qbit'
TRUST_COMMIT='7ebcddb622d6e639041f005a189b048ec2a221fe'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def fetch(url,budget=4*1024**2):
 if not url.startswith(('https://api.github.com/repos/Qbit-Org/qbit/','https://raw.githubusercontent.com/Qbit-Org/qbit/','https://github.com/Qbit-Org/qbit/releases/download/')):raise ValueError('Official upstream URL required')
 with urlopen(Request(url,headers={'User-Agent':'QBitLeap-Core-release-monitor','Accept':'application/vnd.github+json'}),timeout=120)as response:
  raw=response.read(budget+1)
 if len(raw)>budget:raise ValueError('Upstream response budget exceeded')
 return raw
def stable(value):
 if not isinstance(value,str)or not re.fullmatch(r'v1\.\d+\.\d+',value):raise ValueError('Stable supported 1.x Core release required; major changes need review')
 return tuple(map(int,value[1:].split('.')))
def checksum(raw,name):
 rows=[]
 for line in raw.decode('ascii').splitlines():
  match=re.fullmatch(r'([0-9a-f]{64}) [ *](\S+)',line)
  if not match:raise ValueError('Malformed signed checksum file')
  if match[2]==name:rows.append(match[1])
 if len(rows)!=1:raise ValueError('Exactly one signed artifact checksum required')
 return rows[0]
def signer(status,expected):
 # Parse only LF-delimited GnuPG status records; reject ambiguous/error output.
 if not status.endswith(b'\n')or any(x in status for x in(b'\r',b'\xc2\x85',b'\xe2\x80\xa8',b'\xe2\x80\xa9')):raise ValueError('Ambiguous GPG status')
 rows=status.decode('utf-8').splitlines();valid=[];good=[]
 for row in rows:
  if not row.startswith('[GNUPG:] '):raise ValueError('Unexpected GPG status record')
  fields=row[9:].split();kind=fields[0]
  if kind in('BADSIG','ERRSIG','EXPKEYSIG','EXPSIG','REVKEYSIG','KEYREVOKED','KEYEXPIRED','SIGEXPIRED','FAILURE','ERROR','NODATA','NO_PUBKEY'):raise ValueError('Upstream signature refused')
  if kind=='VALIDSIG':valid.append(fields)
  if kind=='GOODSIG':good.append(fields)
 if len(valid)!=1 or len(good)!=1:raise ValueError('One unambiguous valid signature required')
 fingerprint=valid[0][1];primary=valid[0][10]if len(valid[0])>10 else fingerprint
 if expected not in(fingerprint,primary)or not fingerprint.endswith(good[0][1]):raise ValueError('Signature identity differs from pinned policy')
 return primary

def prepare(tag=None):
 if tag is not None:stable(tag)
 lock=json.loads((ROOT/'runtime.lock.json').read_bytes());release=json.loads(fetch(API+('/releases/tags/'+tag if tag else'/releases/latest')));tag=release['tag_name']
 if release.get('draft')or release.get('prerelease'):raise ValueError('Stable published release required')
 version=stable(tag);current=tuple(map(int,lock['artifact']['version'].split('.')))
 receipt=ROOT/'releases/upstream/latest.json'
 if version<current:raise ValueError('Upstream downgrade refused')
 if version==current and receipt.is_file()and json.loads(receipt.read_bytes()).get('upstreamTag')==tag:return None
 policy_raw=(ROOT/'upstream-trust/keys.json').read_bytes();policy=json.loads(policy_raw)
 remote=fetch('https://raw.githubusercontent.com/Qbit-Org/qbit/'+tag+'/contrib/keys/operator-keys/keys.json')
 if sha(remote)!=sha(policy_raw):raise ValueError('Release key policy changed; explicit trust rotation review required')
 assets={a['name']:a for a in release['assets']};version_text=tag[1:];name='qbit-'+version_text+'-x86_64-linux-gnu.tar.gz';base='https://github.com/Qbit-Org/qbit/releases/download/'+tag+'/'
 sums=fetch(base+'SHA256SUMS');digest=checksum(sums,name);identities=set()
 with tempfile.TemporaryDirectory(prefix='.qbit-release-verify-',dir=ROOT.parent)as temporary:
  home=Path(temporary);home.chmod(0o700);sumfile=home/'SHA256SUMS';sumfile.write_bytes(sums)
  for entry in policy['signers']:
   if entry['status']!='active'or'mainnet'not in entry['release_lines']or'release-signing'not in entry['capabilities']:continue
   signature_name='SHA256SUMS.'+entry['alias']+'.asc'
   if signature_name not in assets:continue
   key=ROOT/'upstream-trust'/entry['public_key_file'];armor=key.read_text().splitlines();start=armor.index('-----BEGIN PGP PUBLIC KEY BLOCK-----');end=armor.index('-----END PGP PUBLIC KEY BLOCK-----');body=[line for line in armor[start+1:end]if line and ':'not in line and not line.startswith('=')];keyring=home/'public.gpg';keyring.write_bytes(base64.b64decode(''.join(body),validate=True))
   signature=home/signature_name;signature.write_bytes(fetch(base+signature_name));result=subprocess.run(['gpgv','--homedir',str(home),'--keyring',str(keyring),'--status-fd','1',str(signature),str(sumfile)],capture_output=True)
   if result.returncode:raise ValueError('Upstream signature verification failed')
   identities.add(signer(result.stdout,entry['signing_fingerprint']))
  quorum=policy['release_lines']['mainnet']['release_signature_quorum']
  if quorum<3 or len(identities)<quorum:raise ValueError('Pinned distinct-signer quorum not met')
  artifact=fetch(base+name,256*1024**2)
  if sha(artifact)!=digest or assets[name].get('digest')not in(None,'sha256:'+digest):raise ValueError('Signed upstream artifact checksum mismatch')
  archive=home/name;archive.write_bytes(artifact);binaries={}
  with tarfile.open(archive,'r:gz')as tar:
   for binary in('qbitd','qbit-cli'):
    wanted='qbit-'+version_text+'/bin/'+binary;members=[m for m in tar.getmembers()if m.name==wanted]
    if len(members)!=1 or not members[0].isfile()or members[0].size>256*1024**2:raise ValueError('Regular bounded upstream binary required')
    binaries[binary]=sha(tar.extractfile(members[0]).read())
 license_raw=fetch('https://raw.githubusercontent.com/Qbit-Org/qbit/'+tag+'/COPYING')
 if sha(license_raw)!=lock['license']['sha256']:raise ValueError('Upstream license changed; review notices first')
 updated=json.loads(json.dumps(lock));updated['artifact'].update(name=name,version=version_text,url=base+name,sha256=digest);updated['binaries']=binaries;updated['license']['url']='https://raw.githubusercontent.com/Qbit-Org/qbit/'+tag+'/COPYING'
 replacements={lock['artifact']['version']:version_text,lock['artifact']['sha256']:digest,**{lock['binaries'][n]:binaries[n]for n in binaries}}
 # Only the reviewed binary recipe and matching context commitments change.
 for filename in('Dockerfile','scripts/prepare_core_context.py'):
  path=ROOT/filename;text=path.read_text()
  for before,after in replacements.items():text=text.replace(before,after)
  path.write_text(text)
 (ROOT/'runtime.lock.json').write_text(json.dumps(updated,indent=2)+'\n')
 evidence={'format':'qbit-core-upstream-verification-v1','upstreamTag':tag,'upstreamRelease':release['html_url'],'upstreamPublishedAt':release['published_at'],'artifactSha256':digest,'binaries':binaries,'keyPolicySha256':sha(policy_raw),'trustBootstrapCommit':TRUST_COMMIT,'verifiedPrimarySigners':sorted(identities),'signatureQuorum':quorum,'installationPerformed':False}
 out=ROOT/'releases/upstream';out.mkdir(parents=True,exist_ok=True);(out/'verification.json').write_text(json.dumps(evidence,indent=2)+'\n');return evidence
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--tag');a=p.parse_args();result=prepare(a.tag)
 if os.environ.get('GITHUB_OUTPUT'):
  with open(os.environ['GITHUB_OUTPUT'],'a')as f:f.write('changed='+str(result is not None).lower()+'\n'+('version='+result['upstreamTag'][1:]+'\n'if result else''))
 print(json.dumps(result or{'changed':False}))
