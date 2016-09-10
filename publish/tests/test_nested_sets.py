from django.conf import settings

if getattr(settings, 'TESTING_PUBLISH', False):
    import unittest
    from publish.utils import NestedSet

    def _get_rendered_content(response):
        content = getattr(response, 'rendered_content', None)
        if content is not None:
            return content
        return response.content

    class TestNestedSet(unittest.TestCase):

        def setUp(self):
            super(TestNestedSet, self).setUp()
            self.nested = NestedSet()

        def test_len(self):
            self.failUnlessEqual(0, len(self.nested))
            self.nested.add('one')
            self.failUnlessEqual(1, len(self.nested))
            self.nested.add('two')
            self.failUnlessEqual(2, len(self.nested))
            self.nested.add('one2', parent='one')
            self.failUnlessEqual(3, len(self.nested))

        def test_contains(self):
            self.failIf('one' in self.nested)
            self.nested.add('one')
            self.failUnless('one' in self.nested)
            self.nested.add('one2', parent='one')
            self.failUnless('one2' in self.nested)

        def test_nested_items(self):
            self.failUnlessEqual([], self.nested.nested_items())
            self.nested.add('one')
            self.failUnlessEqual(['one'], self.nested.nested_items())
            self.nested.add('two')
            self.nested.add('one2', parent='one')
            self.failUnlessEqual(['one', ['one2'], 'two'], self.nested.nested_items())
            self.nested.add('one2-1', parent='one2')
            self.nested.add('one2-2', parent='one2')
            self.failUnlessEqual(['one', ['one2', ['one2-1', 'one2-2']], 'two'], self.nested.nested_items())

        def test_iter(self):
            self.failUnlessEqual(set(), set(self.nested))

            self.nested.add('one')
            self.failUnlessEqual(set(['one']), set(self.nested))

            self.nested.add('two', parent='one')
            self.failUnlessEqual(set(['one', 'two']), set(self.nested))

            items = set(['one', 'two'])

            for item in self.nested:
                self.failUnless(item in items)
                items.remove(item)

            self.failUnlessEqual(set(), items)

        def test_original(self):
            class MyObject(object):
                def __init__(self, obj):
                    self.obj = obj

                def __eq__(self, other):
                    return self.obj == other.obj

                def __hash__(self):
                    return hash(self.obj)

            # should always return an item at least
            self.failUnlessEqual(MyObject('hi there'), self.nested.original(MyObject('hi there')))

            m1 = MyObject('m1')
            self.nested.add(m1)

            self.failUnlessEqual(id(m1), id(self.nested.original(m1)))
            self.failUnlessEqual(id(m1), id(self.nested.original(MyObject('m1'))))
