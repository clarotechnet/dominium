"""Read-only sector scope regression for BotDMV DESC -> DataSnap executor."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import disconnect_local_runner as runner
from disconnect_contracts import DisconnectBlocked

NATAL='120363028547806621@g.us'
RECIFE='120363425385335332@g.us'
def job(chat=NATAL,profile='natal',city='NATAL',sender='known-desc@lid',service='43 - ADESAO - INSTALAR PONTO VIRTUA'):
    return SimpleNamespace(chat_id=chat,profile_key=profile,city=city,
        sender_id=sender,toa_snapshot=SimpleNamespace(
        activity_type=service,source_reference='toa-extension-direct|bucket=NTL-DMV_ADM'))

class SectorScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file=Path(self.temp.name)/'whatsapp_technicians.json'
        self.mapping={'technicians':[
            {'name':'TECNICO DESC','installer_id':54321,'profiles':['natal'],
             'whatsapp_ids':['known-desc@lid']},
            {'name':'TECNICO ADESAO','installer_id':54322,'profiles':['natal'],
             'whatsapp_ids':['known-adh@lid']},
            {'name':'TECNICO SEM SUFIXO','sector':'DESC','installer_id':54323,
             'profiles':['natal'],'whatsapp_ids':['explicit-sector@lid']},
        ]}
        self.file.write_text(json.dumps(self.mapping),encoding='utf8')
        self.path=patch.object(runner,'WHATSAPP_TECHNICIAN_MAP_PATH',self.file)
        self.path.start()
        self.addCleanup(self.path.stop)
    def test_desc_sender_can_handle_any_os_service_name(self):
        for service in ('RETIRADA FORA TOA','DESCONEXAO',
                        '43 - ADESAO - INSTALAR PONTO VIRTUA',
                        'INSTALACAO WIFI'):
            with self.subTest(service=service):
                value=job(service=service)
                runner._assert_desc_group_scope(value)
                runner._assert_desc_technician_sector(value)
    def test_wrong_bucket_blocks_even_desc_technician_and_409(self):
        x=job(service='ENTREGA STREAMING',sender='known-desc@lid')
        x.toa_snapshot.source_reference='toa-extension-direct|bucket=NTL-DMV'
        with self.assertRaises(DisconnectBlocked) as captured:
            runner._assert_desc_technician_sector(x)
        self.assertIn('toa_bucket_not_confirmed_as_desc',captured.exception.blockers)

    def test_bucket_missing_blocks_even_desc_technician(self):
        x=job(sender='known-desc@lid')
        x.toa_snapshot.source_reference='toa-extension-direct'
        with self.assertRaises(DisconnectBlocked) as captured:
            runner._assert_desc_technician_sector(x)
        self.assertIn('toa_bucket_not_confirmed_as_desc',captured.exception.blockers)

    def test_non_desc_adherence_not_approved_even_in_desc_group(self):
        with self.assertRaises(DisconnectBlocked) as ctx:
            runner._assert_desc_technician_sector(job(sender='known-adh@lid'))
        self.assertIn('desc_sector_technician_not_verified',ctx.exception.blockers)
    def test_unregistered_sender_is_not_authorized(self):
        with self.assertRaises(DisconnectBlocked) as ctx:
            runner._assert_desc_technician_sector(job(sender='unknown@lid'))
        self.assertIn('desc_sector_technician_not_verified',ctx.exception.blockers)
    def test_explicit_desc_sector_flag_is_supported(self):
        runner._assert_desc_technician_sector(job(sender='explicit-sector@lid'))
    def test_wrong_group_and_city_is_rejected(self):
        for value in (job(chat=RECIFE),job(city='FORTALEZA')):
            with self.assertRaises(DisconnectBlocked):
                runner._assert_desc_group_scope(value)

if __name__=='__main__':
    unittest.main()
