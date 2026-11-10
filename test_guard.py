import copy
import json
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest.mock import patch
import zipfile
from pathlib import Path
import guard

XML = ('<w:document xmlns:w="'+guard.W+'"><w:body><w:p><w:r><w:rPr><w:sz w:val="24"/><w:vertAlign w:val="superscript"/></w:rPr><w:t>PRIVATE_SAMPLE_123</w:t></w:r><w:fldSimple w:instr="PAGE"/></w:p></w:body></w:document>').encode()
RELS = ('<Relationships xmlns="'+guard.R+'"><Relationship Id="rId1" Type="'+guard.OFFICE+'" Target="word/document.xml"/></Relationships>').encode()

def package(path, xml=XML, extra=None):
    parts = {'[Content_Types].xml':b'<Types/>','_rels/.rels':RELS,'word/document.xml':xml,'word/media/image.bin':b'IMAGE'}
    parts.update(extra or {})
    with zipfile.ZipFile(path,'w') as z:
        for name, data in parts.items(): z.writestr(name,data)

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.a = Path(self.tmp.name)/'a.docx'; self.b = Path(self.tmp.name)/'b.docx'
        package(self.a); package(self.b)
    def tearDown(self): self.tmp.cleanup()
    def contract(self):
        return {'version':1,'before_sha256':guard.digest(self.a.read_bytes()),'changes':[{'part':'word/document.xml','path':'/0/0/0/0/0/0','attribute':'{'+guard.W+'}val','before':'24','after':'28'}]}
    def test_same(self): self.assertEqual(guard.compare(self.a,self.b)['status'],'pass')
    def test_size_change_requires_contract(self):
        package(self.b,XML.replace(b'24',b'28'))
        self.assertEqual(guard.compare(self.a,self.b)['status'],'fail')
        self.assertEqual(guard.compare(self.a,self.b,self.contract())['status'],'pass')
    def test_wrong_expected_value(self):
        package(self.b,XML.replace(b'24',b'30'))
        self.assertEqual(guard.compare(self.a,self.b,self.contract())['status'],'fail')
    def test_unused_rule(self): self.assertEqual(guard.compare(self.a,self.b,self.contract())['status'],'fail')
    def test_hash_bound(self):
        c=self.contract(); c['before_sha256']='0'*64
        with self.assertRaises(guard.GuardError): guard.compare(self.a,self.b,c)
    def test_text_change(self):
        package(self.b,XML.replace(b'PRIVATE_SAMPLE_123',b'SECRET_REPLACEMENT'))
        r=guard.compare(self.a,self.b)
        self.assertEqual(r['status'],'fail')
        self.assertNotIn('PRIVATE_SAMPLE',json.dumps(r));self.assertNotIn('SECRET_REPLACEMENT',json.dumps(r))
    def test_citation_superscript(self):
        package(self.b,XML.replace(b'<w:vertAlign w:val="superscript"/>',b''))
        self.assertEqual(guard.compare(self.a,self.b)['status'],'fail')
    def test_field_removed(self):
        package(self.b,XML.replace(b'<w:fldSimple w:instr="PAGE"/>',b''))
        self.assertEqual(guard.compare(self.a,self.b)['status'],'fail')
    def test_field_and_allowed_size(self):
        package(self.b,XML.replace(b'24',b'28').replace(b'PAGE',b'DATE'))
        self.assertEqual(guard.compare(self.a,self.b,self.contract())['status'],'fail')
    def test_binary(self):
        package(self.b,extra={'word/media/image.bin':b'CHANGED'})
        self.assertEqual(guard.compare(self.a,self.b)['status'],'fail')
    def test_relationship(self):
        package(self.b,extra={'word/_rels/document.xml.rels':b'<Relationships/>'})
        self.assertEqual(guard.compare(self.a,self.b)['status'],'fail')
    def test_comment(self):
        package(self.b,XML.replace(b'<w:body>',b'<w:body><!--added-->'))
        self.assertEqual(guard.compare(self.a,self.b)['status'],'fail')
    def test_whitespace_conservative(self):
        package(self.b,XML.replace(b'<w:body>',b'<w:body>\n'))
        self.assertEqual(guard.compare(self.a,self.b)['status'],'fail')
    def test_attribute_serialization_order(self):
        rel=RELS.replace(b'Id="rId1" Type="'+guard.OFFICE.encode()+b'"',b'Type="'+guard.OFFICE.encode()+b'" Id="rId1"')
        package(self.b,extra={'_rels/.rels':rel})
        self.assertEqual(guard.compare(self.a,self.b)['status'],'pass')
    def test_namespace_binding(self):
        x=XML.replace(b'<w:body>',b'<w:body xmlns:x="urn:one">')
        package(self.a,x);package(self.b,x.replace(b'urn:one',b'urn:two'))
        self.assertEqual(guard.compare(self.a,self.b)['status'],'fail')
    def test_outer_pi(self):
        package(self.b,b'<?changed hello?>'+XML)
        self.assertEqual(guard.compare(self.a,self.b)['status'],'fail')
    def test_dtd_rejected(self):
        package(self.b,b'<!DOCTYPE a [<!ENTITY x "evil">]>'+XML)
        with self.assertRaises(guard.GuardError): guard.compare(self.a,self.b)
    def test_utf16_rejected(self):
        package(self.b,XML.decode().encode('utf-16'))
        with self.assertRaises(guard.GuardError): guard.compare(self.a,self.b)
    def test_depth_limit(self):
        package(self.b,b'<a>'*130+b'</a>'*130)
        with self.assertRaises(guard.GuardError): guard.compare(self.a,self.b)
    def test_duplicate_zip(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(self.b,'a') as z:z.writestr('word/document.xml',XML)
        with self.assertRaises(guard.GuardError): guard.compare(self.a,self.b)
    def test_traversal(self):
        package(self.b,extra={'../escape':b'no'})
        with self.assertRaises(guard.GuardError): guard.compare(self.a,self.b)
    def test_cli_codes(self):
        script=str(Path(guard.__file__))
        p=subprocess.run([sys.executable,script,str(self.a),str(self.b)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0)
        package(self.b,XML.replace(b'24',b'28'))
        p=subprocess.run([sys.executable,script,str(self.a),str(self.b)],capture_output=True,text=True)
        self.assertEqual(p.returncode,1)
        self.b.write_bytes(b'bad zip PRIVATE_SAMPLE_123')
        p=subprocess.run([sys.executable,script,str(self.a),str(self.b)],capture_output=True,text=True)
        self.assertEqual(p.returncode,2);self.assertNotIn('PRIVATE_SAMPLE',p.stdout+p.stderr)
    def test_truncation_fails_closed(self):
        package(self.b,XML.replace(b'24',b'28').replace(b'PAGE',b'DATE'))
        with patch.object(guard,'MAX_DIFFS',1):
            r=guard.compare(self.a,self.b)
            self.assertTrue(r['truncated']);self.assertEqual(r['status'],'fail')
    def test_comment_node_limit(self):
        with patch.object(guard,'MAX_NODES',4):
            with self.assertRaises(guard.GuardError): guard.parse_xml(b'<a><!--1--><!--2--><!--3--><!--4--></a>')
    def test_pi_node_limit(self):
        with patch.object(guard,'MAX_NODES',4):
            with self.assertRaises(guard.GuardError): guard.parse_xml(b'<a><?a b?><?a b?><?a b?><?a b?></a>')
    def test_unsupported_compression(self):
        with zipfile.ZipFile(self.b,'w',compression=zipfile.ZIP_BZIP2) as z:z.writestr('x',b'x')
        with self.assertRaises(guard.GuardError):guard.compare(self.a,self.b)
    def test_entry_limit(self):
        with patch.object(guard,'MAX_ENTRIES',1):
            with self.assertRaises(guard.GuardError):guard.compare(self.a,self.b)
    def test_part_limit(self):
        with patch.object(guard,'MAX_PART',10):
            with self.assertRaises(guard.GuardError):guard.compare(self.a,self.b)
    def test_originals_unchanged(self):
        before=[p.read_bytes() for p in (self.a,self.b)]
        guard.compare(self.a,self.b)
        self.assertEqual(before,[p.read_bytes() for p in (self.a,self.b)])

if __name__=='__main__': unittest.main()
