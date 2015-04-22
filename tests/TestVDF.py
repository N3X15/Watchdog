import unittest
import collections


class VDFTests(unittest.TestCase):

    def test_serialization(self):
        from watchdog.steam.vdf import VDFNode

        inner_input = collections.OrderedDict()
        inner_input['a'] = 1
        inner_input['b'] = 2
        inner_input['c'] = 3
        outer_input = {
            "abc123": inner_input
        }
        expected = '''"abc123" {
\t"a" "1"
\t"b" "2"
\t"c" "3"
}
'''

        node = VDFNode.FromDict(outer_input)
        out = node.serialize()
        self.assertEqual(expected, out)

    def test_deserialization(self):
        from watchdog.steam.vdf import VDFNode

        input_str = '''
// Comment
"a" {
    "b" "0"
    "c" "Honk\\" honk."
}
        '''

        expected = {'a': {'b': '0', 'c': 'Honk" honk.'}}

        output = VDFNode.Parse(input_str)
        self.assertEqual(expected, output)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
