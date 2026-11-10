#!/usr/bin/env python3
"""Read-only, exact XML-attribute contracts for DOCX transformations. Python 3.10+."""
import argparse
import hashlib
import json
import re
import sys
import zipfile
import zlib
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_PART = 16 * 1024 * 1024
MAX_ENTRIES = 2048
MAX_NODES = 200000
MAX_DEPTH = 128
MAX_DIFFS = 2000
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/package/2006/relationships'
OFFICE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument'

class GuardError(ValueError):
    pass

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read_package(path):
    path = Path(path)
    if path.stat().st_size > MAX_FILE:
        raise GuardError('archive size limit exceeded')
    raw = path.read_bytes()
    import io
    parts = {}
    total = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist()
        if len(infos) > MAX_ENTRIES:
            raise GuardError('entry count limit exceeded')
        seen = set()
        for info in infos:
            name = info.filename
            if (name in seen or '\\' in name or name.startswith('/') or
                any(p in ('', '.', '..') for p in name.rstrip('/').split('/')) or
                ':' in name or '\x00' in name):
                raise GuardError('duplicate or unsafe package path')
            seen.add(name)
            if info.is_dir():
                continue
            if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise GuardError('unsupported compression method')
            if info.flag_bits & 1:
                raise GuardError('encrypted archives unsupported')
            total += info.file_size
            if info.file_size > MAX_PART or total > MAX_TOTAL:
                raise GuardError('uncompressed size limit exceeded')
            if info.file_size > 1024 * 1024 and info.file_size / max(info.compress_size, 1) > 200:
                raise GuardError('suspicious compression ratio')
            with z.open(info) as stream:
                data = stream.read(MAX_PART + 1)
            if len(data) != info.file_size or len(data) > MAX_PART:
                raise GuardError('invalid part size')
            if name.lower().endswith(('.xml', '.rels')):
                parts[name] = ('xml', parse_xml(data))
            else:
                parts[name] = ('binary', data)
    if '[Content_Types].xml' not in parts or '_rels/.rels' not in parts:
        raise GuardError('not a supported OPC document')
    rels = parts['_rels/.rels'][1][0]
    office = [e for e in rels if e.tag == '{'+R+'}Relationship' and e.get('Type') == OFFICE]
    if len(office) != 1 or office[0].get('TargetMode') == 'External':
        raise GuardError('one internal officeDocument relationship required')
    target = office[0].get('Target', '').lstrip('/')
    if target not in parts or parts[target][0] != 'xml' or parts[target][1][0].tag != '{'+W+'}document':
        raise GuardError('WordprocessingML main document required (transitional only)')
    return raw, parts

def parse_xml(data):
    # Normalize ASCII-compatible encodings for declaration checks. Reject UTF-16/32
    # rather than let NULs conceal DTD declarations from this conservative guard.
    if b'\x00' in data or re.search(br'<!\s*(DOCTYPE|ENTITY)\b', data, re.I):
        raise GuardError('DTD/entities and non-ASCII-compatible XML encodings unsupported')
    class BoundedBuilder(ET.TreeBuilder):
        def __init__(self):
            super().__init__(insert_comments=True, insert_pis=True)
            self.depth = self.count = 0
        def start(self, tag, attrs):
            self.depth += 1
            self.count += 1
            if self.depth > MAX_DEPTH or self.count > MAX_NODES:
                raise GuardError('XML complexity limit exceeded')
            return super().start(tag, attrs)
        def comment(self, text):
            self.count += 1
            if self.count > MAX_NODES:
                raise GuardError('XML complexity limit exceeded')
            return super().comment(text)
        def pi(self, target, text=None):
            self.count += 1
            if self.count > MAX_NODES:
                raise GuardError('XML complexity limit exceeded')
            return super().pi(target, text)
        def end(self, tag):
            result = super().end(tag)
            self.depth -= 1
            return result
    parser = ET.XMLParser(target=BoundedBuilder())
    root = ET.fromstring(data, parser=parser)
    stack = [(root, 1)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if depth > MAX_DEPTH or count > MAX_NODES:
            raise GuardError('XML complexity limit exceeded')
        stack.extend((child, depth+1) for child in node)
    # QName-valued attributes (e.g. mc:Requires) depend on namespace bindings,
    # even when ElementTree has already expanded ordinary tag/attribute names.
    import io
    namespace_records, outer_nodes, pending, frames = [], [], [], []
    for event, value in ET.iterparse(io.BytesIO(data), events=('start-ns','start','end','comment','pi')):
        if event == 'start-ns':
            pending.append(value)
        elif event == 'start':
            if frames:
                path = frames[-1][0]+'/'+str(frames[-1][1])
                frames[-1][1] += 1
            else:
                path = '/0'
            namespace_records.extend((path, prefix, uri) for prefix, uri in pending)
            pending = []
            frames.append([path, 0])
        elif event == 'end':
            frames.pop()
        elif frames:
            frames[-1][1] += 1
        else:
            outer_nodes.append((event, value.text))
    return root, (sorted(namespace_records), outer_nodes)

def tag_name(node):
    if node.tag is ET.Comment:
        return '#comment'
    if node.tag is ET.ProcessingInstruction:
        return '#pi'
    return node.tag

def flatten(root):
    """Stable numeric child-index paths; all whitespace remains significant."""
    result = {}
    stack = [(root, '/0')]
    while stack:
        node, path = stack.pop()
        result[path] = {'tag': tag_name(node), 'text': node.text, 'tail': node.tail,
                        'attributes': dict(node.attrib), 'children': len(node)}
        stack.extend((child, path+'/'+str(i)) for i, child in enumerate(node))
    return result

def validate_contract(contract, before_sha):
    if not isinstance(contract, dict) or set(contract) != {'version', 'before_sha256', 'changes'}:
        raise GuardError('contract requires version, before_sha256 and changes only')
    if contract['version'] != 1 or contract['before_sha256'] != before_sha:
        raise GuardError('contract version or baseline hash mismatch')
    if not isinstance(contract['changes'], list) or len(contract['changes']) > MAX_DIFFS:
        raise GuardError('invalid contract changes')
    allowed = {}
    for item in contract['changes']:
        if not isinstance(item, dict) or set(item) != {'part', 'path', 'attribute', 'before', 'after'}:
            raise GuardError('each change must specify part/path/attribute/before/after')
        if not all(isinstance(item[k], str) for k in ('part', 'path', 'attribute')):
            raise GuardError('invalid contract selector')
        if not re.fullmatch(r'/0(?:/[0-9]+)*', item['path']):
            raise GuardError('invalid numeric node path')
        if not all(item[k] is None or isinstance(item[k], str) for k in ('before','after')):
            raise GuardError('attribute values must be string or null')
        key = (item['part'], item['path'], item['attribute'])
        if key in allowed or item['before'] == item['after']:
            raise GuardError('duplicate or no-op contract rule')
        allowed[key] = item
    return allowed

def compare(before, after, contract=None):
    braw, bp = read_package(before)
    araw, ap = read_package(after)
    sha = digest(braw)
    allowed = validate_contract(contract, sha) if contract is not None else {}
    changes = []
    used = set()
    truncated = False
    def add(part, path, kind, attribute=None, permitted=False):
        nonlocal truncated
        if len(changes) >= MAX_DIFFS:
            truncated = True
            return
        item = {'part': part, 'path': path, 'kind': kind, 'allowed': permitted}
        if attribute is not None:
            item['attribute'] = attribute
        changes.append(item)
    for part in sorted(set(bp) | set(ap)):
        if part not in bp or part not in ap:
            add(part, '', 'part_added' if part not in bp else 'part_removed')
            continue
        bk, bv = bp[part]
        ak, av = ap[part]
        if bk != ak:
            add(part, '', 'type_changed')
        elif bk == 'binary':
            if bv != av:
                add(part, '', 'binary_changed')
        else:
            if bv[1] != av[1]:
                add(part, '', 'namespace_or_outer_markup_changed')
            bf, af = flatten(bv[0]), flatten(av[0])
            for path in sorted(set(bf) | set(af)):
                if path not in bf or path not in af:
                    add(part, path, 'node_added' if path not in bf else 'node_removed')
                    continue
                b, a = bf[path], af[path]
                for key in ('tag','text','tail','children'):
                    if b[key] != a[key]:
                        add(part, path, key+'_changed')
                for attr in sorted(set(b['attributes']) | set(a['attributes'])):
                    old, new = b['attributes'].get(attr), a['attributes'].get(attr)
                    if old == new:
                        continue
                    k = (part, path, attr)
                    rule = allowed.get(k)
                    ok = rule is not None and rule['before'] == old and rule['after'] == new and b['tag'] == a['tag']
                    if ok:
                        used.add(k)
                    add(part, path, 'attribute_changed', attr, ok)
    unused = len(set(allowed)-used)
    return {'schema_version': 1, 'status': 'pass' if not truncated and not unused and all(x['allowed'] for x in changes) else 'fail',
            'before_sha256': sha, 'after_sha256': digest(araw), 'changes': changes,
            'unused_contract_rules': unused, 'truncated': truncated,
            'scope': 'exact package XML structure and attributes, not layout/schema validity'}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('before'); p.add_argument('after')
    p.add_argument('--contract', help='reviewed JSON exact-attribute change contract')
    args = p.parse_args()
    try:
        contract = None
        if args.contract:
            if Path(args.contract).stat().st_size > 1024*1024:
                raise GuardError('contract size limit exceeded')
            contract = json.loads(Path(args.contract).read_text(encoding='utf-8'))
        report = compare(args.before, args.after, contract)
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0 if report['status'] == 'pass' else 1
    except (GuardError, OSError, ValueError, ET.ParseError, zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError):
        # Do not echo parser snippets, local paths or contract values into CI logs.
        print(json.dumps({'schema_version':1, 'status':'error', 'message':'Invalid, unsupported or oversized input; inspect locally.'}))
        return 2

if __name__ == '__main__':
    sys.exit(main())
