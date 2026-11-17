"""Future package releases must retain upgrade storage/settings/operator hooks."""
import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('upgrade_package',ROOT/'scripts/prepare_app_package.py');package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
class UpgradeContract(unittest.TestCase):
 def test_upgrade_changes_images_without_relocating_data_or_resetting_settings(self):
  with tempfile.TemporaryDirectory()as temporary:
   root=Path(temporary);old=root/'old';new=root/'new'
   package.prepare(old,'qbitleap-core-main','main',5100,'example/core@sha256:'+'a'*64,'example/services@sha256:'+'b'*64,package_version='0.1.7')
   package.prepare(new,'qbitleap-core-main','main',5100,'example/core@sha256:'+'c'*64,'example/services@sha256:'+'d'*64,package_version='1.0.1')
   a=json.loads((old/'docker-compose.yml').read_bytes());b=json.loads((new/'docker-compose.yml').read_bytes())
   for role in('core','broker','ui'):b['services'][role]['image']=a['services'][role]['image']
   self.assertEqual(a,b)
   manifests=[json.loads((p/'umbrel-app.yml').read_bytes())for p in(old,new)]
   for field in('id','storage','environment','dependencies'):self.assertEqual(manifests[0][field],manifests[1][field])
   self.assertEqual((old/'exports.sh').read_bytes(),(new/'exports.sh').read_bytes())
   self.assertEqual(hashlib.sha256((new/'exports.sh').read_bytes()).hexdigest(),'639fdd630ab39670422f1cf9b3e87ae752a229b6d2dfbaa2de83a552c705c9b1')
   self.assertEqual(manifests[1]['storage'],{'dataRoot':'data'})
   self.assertEqual({e['name']:e['default']for e in manifests[1]['environment']},{'QBIT_NETWORK_ACTIVE':'1','QBIT_WALLET_ENABLED':'1'})
   self.assertEqual(a['services']['core']['volumes'],['${APP_DATA_DIR}/data/core:/data','${APP_DATA_DIR}/data/auth:/auth','control:/settings'])
   self.assertEqual(a['volumes'],{'control':{}})
   for p in(old,new):
    self.assertFalse((p/'hooks').exists(),'Incoming hooks could overwrite an existing operator hook')
    self.assertFalse((p/'settings.yml').exists(),'Never ship replacement owner settings')
    self.assertFalse(list(p.glob('*.template')),'Templates need separate settings preservation review')
    self.assertEqual({f.relative_to(p/'data').as_posix()for f in(p/'data').rglob('*')if f.is_file()},{'core/.gitkeep','auth/.gitkeep'})
if __name__=='__main__':unittest.main()
