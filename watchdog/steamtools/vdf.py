import collections
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
