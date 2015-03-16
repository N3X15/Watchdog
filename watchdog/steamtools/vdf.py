import collections, logging, pprint
import pyparsing as pyp
from collections import OrderedDict

def _toDict(s,l,t):
    out = {}
    #print(t[0])
    for k,v in t:
        out[k]=v
    return out
    
class VDFNode:
    def __init__(self, root=False):
        self.children = collections.OrderedDict()
        self.is_root = root
        
    @classmethod
    def FromDict(cls, _dict, root=True):
        node = VDFNode(root=root)
        for k, v in _dict.items():
            if type(v) is dict:
                v = VDFNode.FromDict(v, False)
            elif isinstance(v, collections.OrderedDict):
                v = VDFNode.FromDict(v, False)
            node.children[k] = v
        return node
        
    @classmethod
    def Parse(cls,string,errmethod=logging.error):
        Comment = pyp.dblSlashComment
        OpenBracket = pyp.Suppress('{')
        CloseBracket = pyp.Suppress('}')
        Map = pyp.Forward()
        Value = pyp.QuotedString('"',escChar='\\')
        ValuePair = pyp.Group((Value + Value) | (Value + Map))
        MapContents = pyp.ZeroOrMore(ValuePair).setParseAction(_toDict)
        Map << OpenBracket + MapContents + CloseBracket
        VDFSyntax = pyp.OneOrMore(ValuePair).setParseAction(_toDict)
        VDFSyntax.ignore(Comment)
        
        try:
            res = VDFSyntax.parseString(string)
        except pyp.ParseException, err:
            errmethod(err.line)
            errmethod("-"*(err.column-1) + "^")
            errmethod(err)
            return None
        #pprint.pprint(res)
        return res.asList()[0]
            
    def serialize(self, level=0):
        o = ''
        outer_level = level
        inner_level = level + 1
        if not self.is_root:
            o += '{\n'
        else:
            inner_level = 0
            outer_level = 0
        outer_indent = '\t' * outer_level
        inner_indent = '\t' * inner_level
        padlen = 0
        for key in self.children.keys():
            keylen = len(key)
            if padlen < keylen:
                padlen = keylen
        for k, v in self.children.items():
            padding = ' ' * (padlen - len(k) + 1)
            o += inner_indent
            o += '"{}"'.format(k)
            o += padding
            if isinstance(v, VDFNode):
                o += v.serialize(inner_level)
            else:
                o += '"{}"\n'.format(v)
        if not self.is_root:
            o += outer_indent + '}\n'
        return o
        
    def __str__(self):
        return self.serialize()

class VDFFile:
    def __init__(self, value=None):
        if value is None:
            self.rootnode = VDFNode()
        else:
            self.rootnode = VDFNode.FromDict(value)
        
    def Save(self, filename):
        with open(filename, 'w') as f:
            f.write(self.rootnode.serialize())
        
    def Load(self, filename):
        with open(filename, 'r') as f:
            self.rootnode.children = VDFNode.Parse(f.read())
