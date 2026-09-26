import unittest
from tests import test_server as fixture
from tests.fixtures import sample


class ImportCountTests(unittest.TestCase):
    setUp = fixture.APITests.setUp
    tearDown = fixture.APITests.tearDown
    upload = fixture.APITests.upload
    request = fixture.APITests.request

    def test_overlapping_exports_and_duplicate_zip(self):
        self.upload(sample())
        first = sample(); second = sample(cid='call-b')
        self.upload({name:text+second[name] for name,text in first.items()})
        self.upload(sample())  # Identical ZIP creates no new import.
        data = self.request('GET','/api/imports')[1]
        self.assertEqual(len(data),2)
        self.assertEqual([(r['call_count'],r['new_call_count'],r['existing_call_count']) for r in data],
                         [(2,1,1),(1,1,0)])
        self.assertIn('source_profile',data[0])

    def test_same_call_four_sources_and_empty_import(self):
        for index in range(4):
            f=sample();f['extra.log']=f'Synthetic source {index}\n';self.upload(f)
        self.upload({'empty.log':'No calls in this synthetic file\n'})
        data = self.request('GET','/api/imports')[1]
        self.assertEqual([(r['call_count'],r['new_call_count'],r['existing_call_count']) for r in data],
                         [(0,0,0),(1,0,1),(1,0,1),(1,0,1),(1,1,0)])
