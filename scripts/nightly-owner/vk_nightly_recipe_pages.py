"""Bounded B-CAS recipe tree, shared by capture, native audit and normal restore.

Only metadata pages are additional objects. Leaves are the same deduplicated
content objects, with normal independent acceptance. No disk scratch, transport,
source scan, schedule, implicit retry or relaxed decoder/member bound.
"""
import hashlib
import json
import zlib

FANOUT=128
MAX_DEPTH=8
MAX_PAGE=128*1024
FORMAT='vk-nightly-recipe-page-v1'
ENCODING='recipe-v1'


def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def page_object(segment):
    if segment.get('encoding')!=ENCODING:raise ValueError('paged recipe required')
    return dict(layer=segment['layer'],selector=segment['selector'],encoding='zlib',
        bytes=segment['page_bytes'],sha256=segment['page_sha256'],
        encoded_bytes=segment['encoded_bytes'],encoded_sha256=segment['encoded_sha256'])


def validate(segment):
    from vk_nightly_objects import object_segment
    p=page_object(segment);object_segment(p,MAX_PAGE)
    if type(segment['bytes']) is not int or segment['bytes']<0:raise ValueError('recipe logical length required')
    from vk_nightly_checkpoints import digest
    digest(segment['sha256'])
    return p


def decode(segment,raw):
    p=validate(segment)
    if len(raw)!=p['bytes'] or hashlib.sha256(raw).hexdigest()!=p['sha256']:
        raise ValueError('recipe page full hash/length differs')
    node=json.loads(raw)
    if (set(node)!={'format','level','chunking','bytes','sha256','children'} or node['format']!=FORMAT
            or node['chunking']!='content-defined-v1' or type(node['level']) is not int
            or not 1<=node['level']<=MAX_DEPTH or node['bytes']!=segment['bytes'] or node['sha256']!=segment['sha256']
            or not isinstance(node['children'],list) or not 1<=len(node['children'])<=FANOUT):
        raise ValueError('bounded exact recipe page required')
    total=0
    from vk_nightly_objects import object_segment
    for child in node['children']:
        if node['level']==1:object_segment(child,256*1024)
        else:validate(child)
        total+=child['bytes']
    if total!=node['bytes']:raise ValueError('recipe page coverage differs')
    return node


def load(provider,segment):
    p=validate(segment);provider.check()
    with provider.open(p['layer'],p['selector']) as stream:
        decoder=zlib.decompressobj();raw=bytearray();h=hashlib.sha256();size=0
        while True:
            provider.check();block=stream.read(65536)
            if not block:break
            size+=len(block);h.update(block)
            if size>p['encoded_bytes']:raise ValueError('recipe encoded bound exceeded')
            raw.extend(decoder.decompress(block,MAX_PAGE-len(raw)+1))
            if len(raw)>MAX_PAGE or decoder.unconsumed_tail:raise ValueError('recipe decoded bound exceeded')
        if (size!=p['encoded_bytes'] or h.hexdigest()!=p['encoded_sha256'] or not decoder.eof
                or decoder.unused_data):raise ValueError('recipe encoded EOF differs')
    return decode(segment,bytes(raw))


def leaves(provider,segment,*,depth=0,parent_level=None):
    if depth>=MAX_DEPTH:raise ValueError('recipe depth exceeded')
    node=load(provider,segment)
    if parent_level is not None and node['level']!=parent_level-1:raise ValueError('recipe depth/ordering differs')
    for child in node['children']:
        provider.check()
        if node['level']==1:yield child
        else:yield from leaves(provider,child,depth=depth+1,parent_level=node['level'])


class Builder:
    """O(FANOUT * MAX_DEPTH) metadata; deterministic pages reuse after interruption."""
    def __init__(self,client):
        self.client=client;self.levels=[[] for _ in range(MAX_DEPTH)]
        self.hashes=[hashlib.sha256() for _ in range(MAX_DEPTH)]
        self.sizes=[0]*MAX_DEPTH;self.count=0;self.finished=False
    def add(self,segment,verified_raw):
        if self.finished:raise ValueError('recipe already finished')
        if len(verified_raw)!=segment['bytes'] or hashlib.sha256(verified_raw).hexdigest()!=segment['sha256']:
            raise ValueError('recipe leaf differs from independently accepted object')
        for i in range(MAX_DEPTH):self.hashes[i].update(verified_raw);self.sizes[i]+=len(verified_raw)
        self.count+=1;self._append(0,segment)
    def _append(self,level,segment):
        if level>=MAX_DEPTH:raise ValueError('finite recipe depth exhausted; preserve completed objects')
        self.levels[level].append(segment)
        if len(self.levels[level])==FANOUT:self._append(level+1,self._seal(level))
    def _seal(self,level):
        children=self.levels[level]
        node=dict(format=FORMAT,level=level+1,chunking='content-defined-v1',bytes=self.sizes[level],
                  sha256=self.hashes[level].hexdigest(),children=children)
        raw=canonical(node)
        if len(raw)>MAX_PAGE:raise ValueError('bounded recipe metadata page required')
        obj=self.client.ensure(raw);obj.pop('reused',None)
        segment=dict(obj,encoding=ENCODING,page_bytes=obj['bytes'],page_sha256=obj['sha256'],
                     bytes=node['bytes'],sha256=node['sha256'])
        self.levels[level]=[];self.sizes[level]=0;self.hashes[level]=hashlib.sha256()
        return segment
    def finish(self):
        if self.finished or not self.count:raise ValueError('nonempty unfinished recipe required')
        for level in range(MAX_DEPTH):
            if not self.levels[level]:continue
            if level>0 and len(self.levels[level])==1 and not any(self.levels[level+1:]):
                self.finished=True;return self.levels[level]
            sealed=self._seal(level)
            if not any(self.levels[level+1:]):self.finished=True;return [sealed]
            self._append(level+1,sealed)
        raise ValueError('recipe cannot be sealed')
