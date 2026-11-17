"""Check official signed-checksum-bound Core binaries on native OS runners.
No node, wallets, networking or installed data is started; version commands only.
"""
import argparse,hashlib,json,os,platform,re,shutil,subprocess,tempfile
from pathlib import Path
from urllib.request import urlopen
TARGETS={'macos-arm64':('Darwin','arm64'),'macos-x64':('Darwin','x86_64'),'windows-x64':('Windows','AMD64'),'linux-x64':('Linux','x86_64'),'linux-arm64':('Linux','aarch64')}
def check(target,evidence):
 expected_os,expected_cpu=TARGETS[target]
 if platform.system()!=expected_os or platform.machine().lower()!=expected_cpu.lower():raise ValueError('Native target runner required')
 tag=evidence['upstreamTag']
 if re.fullmatch(r'v1\.\d+\.\d+',tag)is None or evidence.get('signatureQuorum',0)<3 or len(set(evidence.get('verifiedPrimarySigners',[])))<evidence['signatureQuorum']:raise ValueError('Verified stable release context required')
 item=evidence['platformArtifacts'][target]
 if 'error'in item:raise ValueError('This platform artifact is unavailable; other platforms are independent')
 url=item['url'];name=item['name'];digest=item['sha256']
 if name!=Path(name).name or not url.startswith('https://github.com/Qbit-Org/qbit/releases/download/'+tag+'/')or url.rsplit('/',1)[1]!=name or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Exact official artifact identity required')
 # Runner temporary storage has room for archives; do not use Cosmic's small /tmp.
 with tempfile.TemporaryDirectory(prefix='core-platform-',dir=os.environ.get('RUNNER_TEMP',str(Path.cwd().parent)))as tmp:
  tmp=Path(tmp);archive=tmp/name;value=hashlib.sha256();total=0
  with urlopen(url,timeout=120)as response,archive.open('xb')as stream:
   for blob in iter(lambda:response.read(1024**2),b''):
    total+=len(blob)
    if total>512*1024**2:raise ValueError('Platform archive size budget')
    value.update(blob);stream.write(blob)
  if value.hexdigest()!=digest:raise ValueError('Platform checksum differs from verified signed manifest')
  dest=tmp/'extracted'
  if name.endswith('.tar.gz'):shutil.unpack_archive(archive,dest,filter='data')
  else:shutil.unpack_archive(archive,dest)
  for binary in('qbitd','qbit-cli'):
   candidates=list(dest.rglob(binary+('.exe'if expected_os=='Windows'else'')))
   if len(candidates)!=1 or not candidates[0].is_file()or candidates[0].is_symlink():raise ValueError('One regular native binary required')
   executable=candidates[0]
   if expected_os=='Darwin':subprocess.run(['codesign','--force','--sign','-',str(executable)],check=True,capture_output=True,timeout=30)
   result=subprocess.run([str(executable),'--version'],check=True,capture_output=True,text=True,timeout=30)
   if tag[1:]not in result.stdout:raise ValueError('Native binary reported wrong version')
 return {'target':target,'upstreamTag':tag,'archiveSha256':digest,'passed':True,'nodeStarted':False,'installedDataAccessed':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('target',choices=TARGETS);p.add_argument('--evidence',type=Path,default=Path('releases/upstream/verification.json'));p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=check(a.target,json.loads(a.evidence.read_bytes()));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
