import unittest
import collections

class VDFTests(unittest.TestCase):
    def test_serialization(self):
        from watchdog.steamtools.vdf import VDFNode
        
        inner_input = collections.OrderedDict()
        inner_input['a']=1
        inner_input['b']=2
        inner_input['c']=3
        input = {
            "abc123": inner_input
        }
        expected = '''"abc123" {
\t"a" "1"
\t"b" "2"
\t"c" "3"
}
'''
        
        node = VDFNode.FromDict(input)
        out = node.serialize()
        print(expected)
        print(out)
        self.assertEqual(expected, out)
                
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()