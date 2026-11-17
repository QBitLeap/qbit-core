import sys,copy,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from platform_receipt import checked
from upstream_release import PLATFORMS
class Platforms(unittest.TestCase):
 def test_complete_set_bound_to_signed_tag_and_artifact_hashes(self):
  evidence={'upstreamTag':'v1.0.1','platformArtifacts':{t:{'sha256':'a'*64}for t in PLATFORMS}};rows={t:{'target':t,'passed':True,'nodeStarted':False,'installedDataAccessed':False,'upstreamTag':'v1.0.1','archiveSha256':'a'*64}for t in PLATFORMS};self.assertEqual(checked(evidence,rows),rows)
  for key,value in [('passed',False),('upstreamTag','v1.0.0'),('archiveSha256','b'*64),('target','other'),('nodeStarted',True),('installedDataAccessed',True)]:
   modified=copy.deepcopy(rows);modified['windows-x64'][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):checked(evidence,modified)
  with self.assertRaises(ValueError):checked(evidence,{t:v for t,v in rows.items()if t!='windows-x64'})
if __name__=='__main__':unittest.main()
