import importlib.util,json,io,tarfile,tempfile,unittest,shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('upstream',ROOT/'scripts/upstream_release.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Upstream(unittest.TestCase):
 def test_stable_and_checksums(self):
  self.assertEqual(m.stable('v1.0.1'),(1,0,1))
  for v in('latest','v1.0.1-rc1','v2.0.0','v0.9.0','v1.0.1/extra'):
   with self.assertRaises(ValueError):m.stable(v)
  line=('a'*64+'  core.tar.gz\n').encode();self.assertEqual(m.checksum(line,'core.tar.gz'),'a'*64)
  for raw in(line+line,b'bad line\n'):
   with self.assertRaises(ValueError):m.checksum(raw,'core.tar.gz')
 def test_missing_desktop_artifact_is_isolated_to_that_target(self):
  version='1.0.2';sums=''.join('a'*64+'  qbit-'+version+'-'+suffix+'\n'for suffix in m.PLATFORMS.values()).encode();assets={'qbit-'+version+'-'+suffix:{}for target,suffix in m.PLATFORMS.items()if target!='windows-x64'};rows=m.platform_metadata(sums,assets,'v'+version)
  self.assertIn('error',rows['windows-x64']);self.assertEqual(rows['linux-x64']['sha256'],'a'*64);self.assertNotIn('error',rows['macos-arm64'])
 def test_signer_identity_errors_and_ambiguity(self):
  key='A'*40;primary='B'*40;status=('[GNUPG:] NEWSIG\n[GNUPG:] GOODSIG '+key[-16:]+' Fixture\n[GNUPG:] VALIDSIG '+key+' 2026-11-13 1 0 4 0 1 10 00 '+primary+'\n').encode();self.assertEqual(m.signer(status,key),primary)
  for raw,expected in[(status,key[:-1]+'C'),(status+b'[GNUPG:] KEYEXPIRED 1\n',key),(status.replace(b'\n',b'\r\n'),key),(status+status,key),(status.replace(b'GOODSIG',b'IGNORED'),key)]:
   with self.assertRaises(ValueError):m.signer(raw,expected)
 def test_verified_lock_update_without_changing_base(self):
  with tempfile.TemporaryDirectory()as directory:
   root=Path(directory);(root/'scripts').mkdir();shutil.copytree(ROOT/'upstream-trust',root/'upstream-trust');lock=json.loads((ROOT/'runtime.lock.json').read_bytes());v=tuple(map(int,lock['artifact']['version'].split('.')));new=f'{v[0]}.{v[1]}.{v[2]+1}';name=f'qbit-{new}-x86_64-linux-gnu.tar.gz'
   for f in('Dockerfile','runtime.lock.json','scripts/prepare_core_context.py'):shutil.copyfile(ROOT/f,root/f)
   archive=io.BytesIO()
   with tarfile.open(fileobj=archive,mode='w:gz')as tar:
    for binary in('qbitd','qbit-cli'):
     raw=binary.encode();info=tarfile.TarInfo('qbit-'+new+'/bin/'+binary);info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
   blob=archive.getvalue();digest=m.sha(blob);policy=(root/'upstream-trust/keys.json').read_bytes();entries=json.loads(policy)['signers'][:3];release={'tag_name':'v'+new,'draft':False,'prerelease':False,'html_url':'https://github.com/Qbit-Org/qbit/releases/tag/v'+new,'published_at':'2026-11-17T00:00:00Z','assets':[{'name':'qbit-'+new+'-'+suffix,'digest':'sha256:'+digest}for suffix in m.PLATFORMS.values()]+[{'name':'SHA256SUMS.'+s['alias']+'.asc'}for s in entries]}
   def fetch(url,budget=None):
    if '/releases/latest'in url:return json.dumps(release).encode()
    if url.endswith('/keys.json'):return policy
    if url.endswith('/SHA256SUMS'):return ''.join(digest+'  qbit-'+new+'-'+suffix+'\n'for suffix in m.PLATFORMS.values()).encode()
    if url.endswith('.asc'):return b'explicit synthetic signature'
    if url.endswith(name):return blob
    if url.endswith('/COPYING'):return(ROOT/'COPYING.qbit').read_bytes()
    raise AssertionError(url)
   def verify(args,**kw):
    alias=Path(args[-2]).name.split('.')[1];key=next(s for s in entries if s['alias']==alias)['signing_fingerprint'];return SimpleNamespace(returncode=0,stdout=('[GNUPG:] GOODSIG '+key[-16:]+' Fixture\n[GNUPG:] VALIDSIG '+key+' 2026-11-13 1 0 4 0 1 10 00 '+key+'\n').encode())
   with patch.object(m,'ROOT',root),patch.object(m,'fetch',side_effect=fetch),patch.object(m.subprocess,'run',side_effect=verify):result=m.prepare()
   updated=json.loads((root/'runtime.lock.json').read_bytes());self.assertEqual(updated['artifact']['version'],new);self.assertEqual(updated['artifact']['sha256'],digest);self.assertEqual(len(result['verifiedPrimarySigners']),3);self.assertEqual(updated['baseImage'],lock['baseImage'])
if __name__=='__main__':unittest.main()
