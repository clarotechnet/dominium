import unittest
from adm_allocation import single_os_allocation,AllocationBlocked
from toa_adm_task_splitter import ADMTaskEvidence

def task(i,code='430',inst=(),removed=()):
    return ADMTaskEvidence(index=i,os_number=str(2663000000+i),
                           close_code=code,service='RETIRADA FORA TOA',point='',
                           installed_serials=tuple(inst),removed_serials=tuple(removed),
                           source_file='NTL-DMV_ADM.csv')

class TestSingleEquipmentOwner(unittest.TestCase):
    def test_ten_os_ten_removed_all_in_first_one(self):
        tasks=[task(i,removed=(f'SERIAL{i:06d}',)) for i in range(1,11)]
        result=single_os_allocation(tasks,'430')
        self.assertEqual(result.target_os,'2663000001')
        self.assertEqual(len(result.removed_serials),10)
        self.assertEqual(len(set(result.removed_serials)),10)
        self.assertEqual(result.other_os[0],'2663000002')
        self.assertEqual(len(result.other_os),9)

    def test_409_incoming_and_outgoing_group_into_single_os(self):
        tasks=[task(1,'409',inst=('IN00001',),removed=('OUT0001',)),
               task(2,'409',inst=('IN00002',),removed=('OUT0002',))]
        result=single_os_allocation(tasks,'409')
        self.assertEqual(result.installed_serials,('IN00001','IN00002'))
        self.assertEqual(result.removed_serials,('OUT0001','OUT0002'))
        self.assertEqual(result.target_os,'2663000001')

    def test_live_extra_serials_same_code_included_once(self):
        result=single_os_allocation([task(1,removed=('A111111',)),task(2,removed=('A222222',))],
             '430',toa_removed=['A222222','A333333'])
        self.assertEqual(result.removed_serials,('A111111','A222222','A333333'))

    def test_different_codes_keep_equipment_in_their_own_group(self):
        result=single_os_allocation([task(1,code='409',inst=('IN11111',)),
              task(2,code='430',removed=('OUT2222',))],'409',
              toa_installed=['IN11111'],toa_removed=['OUT2222'])
        self.assertEqual(result.installed_serials,('IN11111',))
        self.assertEqual(result.removed_serials,())

    def test_unmapped_aggregate_serial_blocks_mixed_codes(self):
        with self.assertRaisesRegex(AllocationBlocked,'mixed_code_equipment_mapping_incomplete'):
            single_os_allocation([task(1,code='409',inst=('IN11111',)),
              task(2,code='430',removed=('OUT2222',))],'409',
              toa_installed=['IN11111'],toa_removed=['OUT2222','UNKNOWN'])

    def test_same_serial_cannot_belong_to_different_close_codes(self):
        with self.assertRaisesRegex(AllocationBlocked,'equipment_code_conflict'):
            single_os_allocation([task(1,code='409',inst=('SHARED1',)),
                                 task(2,code='430',removed=('SHARED1',))],'409')

    def test_same_serial_entering_and_leaving_blocks(self):
        with self.assertRaisesRegex(AllocationBlocked,'equipment_direction_conflict'):
            single_os_allocation([task(1,inst=('ABC1234',),removed=('ABC1234',))],'430')

if __name__=='__main__':unittest.main()
