"""Windows/POSIX canonical JSON and bounded streaming nightly index loading."""
import codecs
import hashlib
import io
import json

MAX_INDEX = 512 * 1024**2
MAX_ENTRIES = 1_500_000
MAX_VALUE = 64 * 1024**2
FIELD_KEYS = {key:key for key in ('kind','mode','uid','gid','mtime_ns','xattrs','bytes','sha256','target')}
KINDS = {key:key for key in ('file','directory','hardlink','symlink')}


def shared_fields(value):
    # raw_decode clears the stdlib key memo between rows. Reuse this finite
    # schema vocabulary rather than retaining millions of identical key strings.
    result={FIELD_KEYS.get(key,key):item for key,item in value.items()}
    if isinstance(result.get('kind'),str):result['kind']=KINDS.get(result['kind'],result['kind'])
    return result


def json_blocks(value):
    container=isinstance(value,(dict,list,tuple))
    children=value.values() if isinstance(value,dict) else value if container else ()
    if not container or (len(value)<=64 and all(not isinstance(x,(dict,list,tuple)) or not x for x in children)):
        yield json.dumps(value,sort_keys=True,separators=(',',':')).encode();return
    mapping=isinstance(value,dict);yield b'{' if mapping else b'['
    for index,key in enumerate(sorted(value) if mapping else range(len(value))):
        if index:yield b','
        if mapping:
            if not isinstance(key,str):raise ValueError('JSON metadata keys must be strings')
            yield json.dumps(key).encode();yield b':'
        yield from json_blocks(value[key])
    yield b'}' if mapping else b']'


def bounded_json_blocks(value,maximum=MAX_INDEX):
    size=0
    for block in json_blocks(value):
        size+=len(block)
        if size>maximum:raise ValueError('nightly metadata exceeds explicit bound')
        yield block


def encoding_summary(value,maximum=MAX_INDEX):
    h=hashlib.sha256();size=0
    for block in bounded_json_blocks(value,maximum):h.update(block);size+=len(block)
    return h.hexdigest(),size


def encoded(value,maximum=MAX_INDEX):
    with io.BytesIO() as stream:
        for block in bounded_json_blocks(value,maximum):stream.write(block)
        return stream.getvalue()


class IndexReader:
    """Keep a single decoded table, never whole-index byte/string copies.

    Ordinary rows/headers are decoded by stdlib JSON in bounded windows. Only
    the envelope and its entries/proof tables are assembled incrementally.
    The input must finish at EOF; its hash covers every byte including padding.
    """
    def __init__(self,stream,maximum,maximum_entries,chunk_size):
        self.stream=stream;self.maximum=maximum;self.limit=maximum_entries
        self.chunk=chunk_size;self.buffer='';self.pos=0;self.eof=False;self.size=0
        self.utf8=codecs.getincrementaldecoder('utf-8')();self.decoder=json.JSONDecoder(object_hook=shared_fields)
        self.checksum=hashlib.sha256()

    def more(self):
        if self.eof:return False
        self.buffer=self.buffer[self.pos:];self.pos=0
        data=self.stream.read(self.chunk);self.size+=len(data)
        if self.size>self.maximum:raise ValueError('nightly index exceeds explicit byte bound')
        self.checksum.update(data)
        if not data:self.eof=True
        self.buffer+=self.utf8.decode(data,final=self.eof)
        return bool(data)

    def peek(self):
        while True:
            while self.pos<len(self.buffer) and self.buffer[self.pos] in ' \t\r\n':self.pos+=1
            if self.pos<len(self.buffer):return self.buffer[self.pos]
            if not self.more():return ''

    def expect(self,char):
        if self.peek()!=char:raise ValueError('invalid streamed JSON delimiter')
        self.pos+=1

    def value(self):
        if not self.peek():raise ValueError('truncated streamed JSON value')
        while True:
            try:
                value,end=self.decoder.raw_decode(self.buffer,self.pos)
                # A number may continue across a read boundary, including an
                # exponent. Require a delimiter or confirmed EOF before use.
                if (end<len(self.buffer) and self.buffer[end] in ' \r\n\t,:}]') or (end==len(self.buffer) and self.eof):
                    if end-self.pos>MAX_VALUE:raise ValueError('nightly JSON row/header exceeds bound')
                    self.pos=end;return value
            except json.JSONDecodeError:pass
            if len(self.buffer)-self.pos>MAX_VALUE:raise ValueError('nightly JSON row/header exceeds bound')
            if self.eof:raise ValueError('invalid or truncated streamed JSON value')
            self.more()

    def mapping(self,role):
        self.expect('{');result={}
        if self.peek()=='}':self.pos+=1;return result
        while True:
            key=self.value()
            if not isinstance(key,str) or key in result:raise ValueError('duplicate/non-string streamed JSON key')
            self.expect(':')
            if role in ('envelope','proof') and key=='entries':value=self.mapping('entries')
            elif role=='envelope' and key=='proof':value=self.mapping('proof')
            else:value=self.value()
            result[key]=value
            if role=='entries' and len(result)>self.limit:raise ValueError('nightly entry count exceeds bound')
            next_char=self.peek()
            if next_char=='}':self.pos+=1;return result
            self.expect(',')


def load_index(stream,maximum=MAX_INDEX,maximum_entries=MAX_ENTRIES,chunk_size=65536):
    if type(chunk_size) is not int or not 1<=chunk_size<=1024**2:raise ValueError('bounded JSON read window required')
    reader=IndexReader(stream,maximum,maximum_entries,chunk_size)
    value=reader.mapping('envelope')
    if reader.peek():raise ValueError('trailing streamed JSON data')
    return value,reader.checksum.hexdigest()
