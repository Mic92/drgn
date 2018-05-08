import math
import operator
import unittest

from drgn.program import Program, ProgramObject
from drgn.type import IntType, StructType
from tests.test_type import point_type
from tests.test_typeindex import TypeIndexTestCase, TYPES


class TestProgramObject(TypeIndexTestCase):
    def setUp(self):
        super().setUp()
        def program_object_equality_func(a, b, msg=None):
            if a.program_ != b.program_:
                raise self.failureException(msg or 'objects have different program')
            if a.address_ != b.address_:
                a_address = 'None' if a.address_ is None else hex(a.address_)
                b_address = 'None' if b.address_ is None else hex(b.address_)
                raise self.failureException(msg or f'object addresses differ: {a_address} != {b_address}')
            if a.type_ != b.type_:
                raise self.failureException(msg or f'objects types differ: {a.type_!r} != {b.type_!r}')
            if a._value != b._value:
                raise self.failureException(msg or f'object values differ: {a._value!r} != {b._value!r}')
        self.addTypeEqualityFunc(ProgramObject, program_object_equality_func)
        mem = b'\x01\x00\x00\x00\x02\x00\x00\x00hello\x00\x00\x00'
        def lookup_variable(name):
            raise NotImplementedError()
        def read_memory(address, size):
            address -= 0xffff0000
            assert address >= 0
            assert address + size <= len(mem)
            return mem[address:address + size]
        self.program = Program(type_index=self.type_index,
                               lookup_variable_fn=lookup_variable,
                               read_memory_fn=read_memory)
    def tearDown(self):
        super().tearDown()

    def test_constructor(self):
        self.assertRaises(ValueError, ProgramObject, self.program, None,
                          TYPES['int'], None)
        self.assertRaises(ValueError, ProgramObject, self.program, 0xffff0000,
                          TYPES['int'], 1)

    def test_rvalue(self):
        obj = self.program.object(None, TYPES['int'], 2**31)
        self.assertEqual(obj.value_(), -2**31)

    def test_cast(self):
        obj = self.program.object(None, TYPES['int'], -1)
        cast_obj = obj.cast_('unsigned int')
        self.assertEqual(cast_obj,
                         ProgramObject(self.program, None, TYPES['unsigned int'], 2**32 - 1))

        obj = self.program.object(None, TYPES['double'], 1.0)
        self.assertRaises(TypeError, obj.cast_, self.type_index.pointer(TYPES['int']))

    def test_int(self):
        int_obj = self.program.object(0xffff0000, TYPES['int'])
        bool_obj = self.program.object(0xffff0000, TYPES['_Bool'])
        for obj in [int_obj, bool_obj]:
            self.assertRaises(ValueError, len, obj)
            with self.assertRaises(ValueError):
                obj[0]
            self.assertRaises(ValueError, next, iter(obj))
            self.assertRaises(ValueError, obj.string_)
            self.assertRaises(ValueError, obj.member_, 'foo')
            self.assertEqual(obj.value_(), 1)
            self.assertTrue(bool(obj))
            # _Bool should be the same because of integer promotions.
            self.assertEqual(-obj, ProgramObject(self.program, None, TYPES['int'], -1))
            self.assertEqual(+obj, ProgramObject(self.program, None, TYPES['int'], 1))
            self.assertEqual(~obj, ProgramObject(self.program, None, TYPES['int'], -2))
            self.assertEqual(int(obj), 1)
            self.assertEqual(float(obj), 1.0)
            self.assertEqual(obj.__index__(), 1)
            self.assertEqual(round(obj), 1)
            self.assertEqual(math.trunc(obj), 1)
            self.assertEqual(math.floor(obj), 1)
            self.assertEqual(math.ceil(obj), 1)

        obj = self.program.object(0xffff0000, IntType('int', 4, True, frozenset({'const'})))
        self.assertEqual(+obj, ProgramObject(self.program, None, TYPES['int'], 1))

    def test_float(self):
        obj = self.program.object(None, TYPES['double'], 1.5)
        self.assertTrue(bool(obj))
        self.assertEqual(-obj, ProgramObject(self.program, None, TYPES['double'], -1.5))
        self.assertEqual(+obj, ProgramObject(self.program, None, TYPES['double'], 1.5))
        with self.assertRaises(TypeError):
            ~obj
        self.assertEqual(int(obj), 1)
        self.assertEqual(float(obj), 1.5)
        self.assertRaises(TypeError, obj.__index__)
        self.assertEqual(round(obj), 2)
        self.assertEqual(round(obj, 1), 1.5)
        self.assertEqual(math.trunc(obj), 1)
        self.assertEqual(math.floor(obj), 1)
        self.assertEqual(math.ceil(obj), 2)

    def test_pointer(self):
        pointer_type = self.type_index.pointer(TYPES['int'])
        obj = self.program.object(None, pointer_type, 0xffff0000)
        element0 = ProgramObject(self.program, 0xffff0000, TYPES['int'])
        element1 = ProgramObject(self.program, 0xffff0004, TYPES['int'])
        element2 = ProgramObject(self.program, 0xffff0008, TYPES['int'])
        self.assertRaises(ValueError, len, obj)
        self.assertEqual(obj[0], element0)
        self.assertEqual(obj[1], element1)
        self.assertEqual(obj[2], element2)
        self.assertRaises(ValueError, next, iter(obj))

        pointer_type = self.type_index.pointer(TYPES['char'])
        obj = self.program.object(None, pointer_type, 0xffff0008)
        self.assertEqual(obj.string_(), b'hello')
        self.assertTrue(bool(obj))

        obj = self.program.object(None, pointer_type, 0x0)
        self.assertFalse(bool(obj))
        with self.assertRaises(TypeError):
            +obj
        self.assertRaises(TypeError, int, obj)
        self.assertRaises(TypeError, float, obj)
        self.assertRaises(TypeError, obj.__index__)
        self.assertRaises(TypeError, round, obj)
        self.assertRaises(TypeError, math.trunc, obj)
        self.assertRaises(TypeError, math.floor, obj)
        self.assertRaises(TypeError, math.ceil, obj)

        with self.assertRaises(ValueError):
            obj.member_('foo')

        cast_obj = obj.cast_('unsigned long')
        self.assertEqual(cast_obj, ProgramObject(self.program, None, TYPES['unsigned long'], 0))
        self.assertRaises(TypeError, obj.__index__)

    def test_array(self):
        array_type = self.type_index.array(TYPES['int'], 2)
        obj = self.program.object(0xffff0000, array_type)
        element0 = ProgramObject(self.program, 0xffff0000, TYPES['int'])
        element1 = ProgramObject(self.program, 0xffff0004, TYPES['int'])
        element2 = ProgramObject(self.program, 0xffff0008, TYPES['int'])
        self.assertEqual(len(obj), 2)
        self.assertEqual(obj[0], element0)
        self.assertEqual(obj[1], element1)
        elements = list(obj)
        self.assertEqual(len(elements), 2)
        self.assertEqual(elements[0], element0)
        self.assertEqual(elements[1], element1)
        self.assertEqual(obj.value_(), [1, 2])

        array_type = self.type_index.array(TYPES['int'], None)
        obj = self.program.object(0xffff0000, array_type)
        self.assertRaises(ValueError, len, obj)
        self.assertEqual(obj[0], element0)
        self.assertEqual(obj[1], element1)
        self.assertEqual(obj[2], element2)
        self.assertRaises(ValueError, next, iter(obj))

        array_type = self.type_index.array(TYPES['char'], 2)
        obj = self.program.object(0xffff0008, array_type)
        self.assertEqual(obj.string_(), b'he')

        array_type = self.type_index.array(TYPES['char'], 8)
        obj = self.program.object(0xffff0008, array_type)
        self.assertEqual(obj.string_(), b'hello')

    def test_struct(self):
        struct_obj = self.program.object(0xffff0000, point_type)
        pointer_type = self.type_index.pointer(point_type)
        pointer_obj = self.program.object(None, pointer_type, 0xffff0000)
        element0 = ProgramObject(self.program, 0xffff0000, TYPES['int'])
        element1 = ProgramObject(self.program, 0xffff0004, TYPES['int'])

        for obj in [struct_obj, pointer_obj]:
            self.assertEqual(obj.x, element0)
            self.assertEqual(obj.y, element1)
            with self.assertRaises(AttributeError):
                obj.z
            self.assertEqual(obj.member_('x'), ProgramObject(self.program, 0xffff0000, TYPES['int']))
            self.assertEqual(obj.member_('y'), ProgramObject(self.program, 0xffff0004, TYPES['int']))
            self.assertRaises(ValueError, obj.member_, 'z')
            self.assertIn('x', dir(obj))
            self.assertIn('y', dir(obj))
            self.assertTrue(hasattr(obj, 'x'))
            self.assertTrue(hasattr(obj, 'y'))
            self.assertFalse(hasattr(obj, 'z'))

        element1_ptr = element1.address_of_()
        self.assertEqual(element1_ptr,
                         ProgramObject(self.program, None,
                                       self.type_index.pointer(TYPES['int']),
                                       0xffff0004))
        self.assertEqual(element1_ptr.container_of_(point_type, 'y'), pointer_obj)

        struct_type = StructType('test', 8, [
            ('address_', 0, lambda: TYPES['unsigned long']),
        ])
        struct_obj = self.program.object(0xffff0000, struct_type)
        self.assertEqual(struct_obj.address_, 0xffff0000)
        self.assertEqual(struct_obj.member_('address_'),
                         ProgramObject(self.program, 0xffff0000, TYPES['unsigned long']))

    def test_relational(self):
        one = self.program.object(None, TYPES['int'], 1)
        two = self.program.object(None, TYPES['int'], 2)
        three = self.program.object(None, TYPES['int'], 3)
        ptr0 = self.program.object(None, self.type_index.pointer(TYPES['int']),
                                   0xffff0000)
        ptr1 = self.program.object(None, self.type_index.pointer(TYPES['int']),
                                   0xffff0004)

        self.assertTrue(one < two)
        self.assertFalse(two < two)
        self.assertFalse(three < two)
        self.assertTrue(ptr0 < ptr1)

        self.assertTrue(one <= two)
        self.assertTrue(two <= two)
        self.assertFalse(three <= two)
        self.assertTrue(ptr0 <= ptr1)

        self.assertTrue(one == one)
        self.assertFalse(one == two)
        self.assertFalse(ptr0 == ptr1)

        self.assertFalse(one != one)
        self.assertTrue(one != two)
        self.assertTrue(ptr0 != ptr1)

        self.assertFalse(one > two)
        self.assertFalse(two > two)
        self.assertTrue(three > two)
        self.assertFalse(ptr0 > ptr1)

        self.assertFalse(one >= two)
        self.assertTrue(two >= two)
        self.assertTrue(three >= two)
        self.assertFalse(ptr0 >= ptr1)

        negative_one = self.program.object(None, TYPES['int'], -1)
        unsigned_zero = self.program.object(None, TYPES['unsigned int'], 0)
        # The usual arithmetic conversions convert -1 to an unsigned int.
        self.assertFalse(negative_one < unsigned_zero)

        self.assertTrue(self.program.object(None, TYPES['int'], 1) ==
                        self.program.object(None, TYPES['_Bool'], 1))

        self.assertRaises(TypeError, operator.lt, ptr0, one)

    def _test_arithmetic(self, op, lhs, rhs, result, integral=True,
                         floating_point=False):
        def INT(value):
            return self.program.object(None, TYPES['int'], value)
        def LONG(value):
            return self.program.object(None, TYPES['long'], value)
        def DOUBLE(value):
            return self.program.object(None, TYPES['double'], value)

        if integral:
            self.assertEqual(op(INT(lhs), INT(rhs)), INT(result))
            self.assertEqual(op(INT(lhs), LONG(rhs)), LONG(result))
            self.assertEqual(op(LONG(lhs), INT(rhs)), LONG(result))
            self.assertEqual(op(LONG(lhs), LONG(rhs)), LONG(result))
            self.assertEqual(op(INT(lhs), rhs), INT(result))
            self.assertEqual(op(LONG(lhs), rhs), LONG(result))
            self.assertEqual(op(lhs, INT(rhs)), INT(result))
            self.assertEqual(op(lhs, LONG(rhs)), LONG(result))

        if floating_point:
            self.assertEqual(op(DOUBLE(lhs), DOUBLE(rhs)), DOUBLE(result))
            self.assertEqual(op(DOUBLE(lhs), INT(rhs)), DOUBLE(result))
            self.assertEqual(op(INT(lhs), DOUBLE(rhs)), DOUBLE(result))
            self.assertEqual(op(DOUBLE(lhs), float(rhs)), DOUBLE(result))
            self.assertEqual(op(float(lhs), DOUBLE(rhs)), DOUBLE(result))
            self.assertEqual(op(float(lhs), INT(rhs)), DOUBLE(result))
            self.assertEqual(op(INT(lhs), float(rhs)), DOUBLE(result))

    def _test_pointer_type_errors(self, op):
        def INT(value):
            return self.program.object(None, TYPES['int'], value)
        def POINTER(value):
            return self.program.object(None,
                                       self.type_index.pointer(TYPES['int']),
                                       value)

        self.assertRaises(TypeError, op, INT(1), POINTER(1))
        self.assertRaises(TypeError, op, POINTER(1), INT(1))
        self.assertRaises(TypeError, op, POINTER(1), POINTER(1))

    def _test_floating_type_errors(self, op):
        def INT(value):
            return self.program.object(None, TYPES['int'], value)
        def DOUBLE(value):
            return self.program.object(None, TYPES['double'], value)

        self.assertRaises(TypeError, op, INT(1), DOUBLE(1))
        self.assertRaises(TypeError, op, DOUBLE(1), INT(1))
        self.assertRaises(TypeError, op, DOUBLE(1), DOUBLE(1))

    def _test_shift(self, op, lhs, rhs, result):
        def BOOL(value):
            return self.program.object(None, TYPES['_Bool'], value)
        def INT(value):
            return self.program.object(None, TYPES['int'], value)
        def LONG(value):
            return self.program.object(None, TYPES['long'], value)

        self.assertEqual(op(INT(lhs), INT(rhs)), INT(result))
        self.assertEqual(op(INT(lhs), LONG(rhs)), INT(result))
        self.assertEqual(op(LONG(lhs), INT(rhs)), LONG(result))
        self.assertEqual(op(LONG(lhs), LONG(rhs)), LONG(result))
        self.assertEqual(op(INT(lhs), rhs), INT(result))
        self.assertEqual(op(LONG(lhs), rhs), LONG(result))
        self.assertEqual(op(lhs, INT(rhs)), INT(result))
        self.assertEqual(op(lhs, LONG(rhs)), INT(result))

        self._test_pointer_type_errors(op)
        self._test_floating_type_errors(op)

    def test_add(self):
        self._test_arithmetic(operator.add, 2, 2, 4, floating_point=True)

        one = self.program.object(None, TYPES['int'], 1)
        ptr = self.program.object(None, self.type_index.pointer(TYPES['int']),
                                  0xffff0000)
        ptr1 = self.program.object(None, self.type_index.pointer(TYPES['int']),
                                   0xffff0004)
        self.assertEqual(ptr + one, ptr1)
        self.assertEqual(one + ptr, ptr1)
        self.assertEqual(ptr + 1, ptr1)
        self.assertEqual(1 + ptr, ptr1)
        self.assertRaises(TypeError, operator.add, ptr, ptr)
        self.assertRaises(TypeError, operator.add, ptr, 2.0)
        self.assertRaises(TypeError, operator.add, 2.0, ptr)

    def test_sub(self):
        self._test_arithmetic(operator.sub, 4, 2, 2, floating_point=True)

        ptr = self.program.object(None, self.type_index.pointer(TYPES['int']),
                                  0xffff0000)
        ptr1 = self.program.object(None, self.type_index.pointer(TYPES['int']),
                                   0xffff0004)
        self.assertEqual(ptr1 - ptr,
                         ProgramObject(self.program, None, TYPES['ptrdiff_t'], 1))
        self.assertEqual(ptr - ptr1,
                         ProgramObject(self.program, None, TYPES['ptrdiff_t'], -1))
        self.assertEqual(ptr - 0, ptr)
        self.assertEqual(ptr1 - 1, ptr)
        self.assertRaises(TypeError, operator.sub, 1, ptr)
        self.assertRaises(TypeError, operator.sub, ptr, 1.0)

    def test_mul(self):
        self._test_arithmetic(operator.mul, 2, 3, 6, floating_point=True)
        self._test_pointer_type_errors(operator.mul)

    def test_div(self):
        self._test_arithmetic(operator.truediv, 6, 3, 2, floating_point=True)

        # Make sure we do integer division for integer operands.
        self._test_arithmetic(operator.truediv, 3, 2, 1)

        # Make sure we truncate towards zero (Python truncates towards negative
        # infinity).
        self._test_arithmetic(operator.truediv, -1, 2, 0)
        self._test_arithmetic(operator.truediv, 1, -2, 0)

        self._test_pointer_type_errors(operator.mul)

    def test_mod(self):
        self._test_arithmetic(operator.mod, 4, 2, 0)

        # Make sure the modulo result has the sign of the dividend (Python uses
        # the sign of the divisor).
        self._test_arithmetic(operator.mod, 1, 26, 1)
        self._test_arithmetic(operator.mod, 1, -26, 1)
        self._test_arithmetic(operator.mod, -1, 26, -1)
        self._test_arithmetic(operator.mod, -1, -26, -1)

        self._test_pointer_type_errors(operator.mod)
        self._test_floating_type_errors(operator.mod)

    def test_lshift(self):
        self._test_shift(operator.lshift, 2, 3, 16)

    def test_rshift(self):
        self._test_shift(operator.rshift, 16, 3, 2)

    def test_and(self):
        self._test_arithmetic(operator.and_, 1, 3, 1)
        self._test_pointer_type_errors(operator.and_)
        self._test_floating_type_errors(operator.and_)

    def test_xor(self):
        self._test_arithmetic(operator.xor, 1, 3, 2)
        self._test_pointer_type_errors(operator.xor)
        self._test_floating_type_errors(operator.xor)

    def test_or(self):
        self._test_arithmetic(operator.or_, 1, 3, 3)
        self._test_pointer_type_errors(operator.or_)
        self._test_floating_type_errors(operator.or_)