"""Generate only synthetic fixtures; never needs a real thesis."""
import json
from pathlib import Path
from test_guard import package, XML
from guard import compare, digest, W

def main():
    out = Path('demo-output'); out.mkdir(exist_ok=True)
    before, after = out/'before.docx', out/'after.docx'
    package(before); package(after, XML.replace(b'24',b'28'))
    contract = {'version':1,'before_sha256':digest(before.read_bytes()),'changes':[
        {'part':'word/document.xml','path':'/0/0/0/0/0/0','attribute':'{'+W+'}val','before':'24','after':'28'}]}
    (out/'contract.json').write_text(json.dumps(contract,indent=2),encoding='utf-8')
    print(json.dumps(compare(before,after,contract),indent=2))
if __name__=='__main__':main()
