import re
import genapixml as CApi

class Name(object):
	def __init__(self, prev = None, cname = None):
		self.words = []
		self.prev = prev
		if cname is not None:
			self.set_from_c(cname)
	
	def copy(self):
		nameType = type(self)
		name = nameType()
		name.words = list(self.words)
		name.prev = None if self.prev is None else self.prev.copy()
		return name
	
	def __eq__(self, name):
		return self.words == name.words and (
			(self.prev is None and name.prev is None) or
			(self.prev is not None and name.prev is not None and self.prev == name.prev)
		)
	
	def __ne__(self, name):
		return not self == name
	
	def delete_prefix(self, prefix):
		it = self
		_next = None
		while it is not None and it.words != prefix.words:
			_next = it
			it = it.prev
		
		if it is None or it != prefix:
			raise RuntimeError('no common prefix')
		elif _next is not None:
			_next.prev = None
	
	def get_prefix_as_word_list(self):
		if self.prev is None:
			return []
		else:
			return self.prev.get_prefix_as_word_list() + list(self.prev.words)
	
	def get_full_name_as_word_list(self):
		fullName = self.get_prefix_as_word_list()
		fullName += self.words
		return fullName
	
	def get_name_path(self):
		res = [self]
		it = self
		while it.prev is not None:
			it = it.prev
			res.append(it)
		res.reverse()
		return res
	
	@staticmethod
	def find_common_parent(name1, name2):
		if name1.prev is None or name2.prev is None:
			return None
		elif name1.prev is name2.prev:
			return name1.prev
		else:
			commonParent = Name.find_common_parent(name1.prev, name2)
			if commonParent is not None:
				return commonParent
			else:
				return Name.find_common_parent(name1, name2.prev)


class ClassName(Name):
	def set_from_c(self, cname):
		self.words = re.findall('[A-Z][a-z0-9]*', cname)
		i = 0
		while i < len(self.words):
			self.words[i] = self.words[i].lower()
			i += 1
		
		prefix = self.get_prefix_as_word_list()
		while len(prefix) > 0 and len(self.words) > 0 and prefix[0] == self.words[0]:
			del prefix[0]
			del self.words[0]
		
		if len(self.words) == 0:
			raise ValueError('Could not parse C class name \'{0}\' with {1} as prefix'.format(cname, prefix))
	
	def format_as_c(self):
		res = ''
		words = self.get_full_name_as_word_list()
		for word in words:
			res += word.title()
		return res


class EnumName(ClassName):
	pass


class EnumValueName(ClassName):
	pass


class MethodName(Name):
	def set_from_c(self, cname):
		self.words = cname.split('_')
		prefix = self.get_prefix_as_word_list()
		while len(prefix) > 0 and len(self.words) > 0 and prefix[0] == self.words[0]:
			del prefix[0]
			del self.words[0]
		if len(self.words) == 0:
			raise ValueError('Could not parse C function name \'{0}\' with {1} as prefix'.format(cname, prefix))
	
	def format_as_c(self):
		fullName = self.get_full_name_as_word_list()
		return '_'.join(fullName)


class NamespaceName(Name):
	def __init__(self, name=None, prev=None):
		Name.__init__(self, prev=prev)
		self.words = [name] if name is not None else []


class Type(object):
	def __init__(self):
		self.parent = None


class BaseType(Type):
	def __init__(self, name, isconst=False, isref=False, size=None, isUnsigned=False):
		Type.__init__(self)
		self.name = name
		self.isconst = isconst
		self.isref = isref
		self.size = size
		self.isUnsigned = isUnsigned


class EnumType(Type):
	def __init__(self, name, enumDesc):
		Type.__init__(self)
		self.name = name
		self.desc = enumDesc


class ClassType(Type):
	def __init__(self, name, classDesc, isconst=False):
		Type.__init__(self)
		self.name = name
		self.desc = classDesc
		self.isconst = isconst


class ListType(Type):
	def __init__(self, containedType=None):
		Type.__init__(self)
		self.containedType = containedType
		self.containedTypeDesc = None


class Object(object):
	def __init__(self):
		self.name = None
		self.briefDescription = None
		self.detailedDescription = None
		self.deprecated = None
		self.parent = None
	
	def set_from_c(self, cObject, namespace=None):
		self.briefDescription = cObject.briefDescription
		self.detailedDescription = cObject.detailedDescription
		self.deprecated = cObject.deprecated
		self.parent = namespace
	
	def get_namespace_object(self):
		if isinstance(self, (Namespace,Enum,Class)):
			return self
		elif self.parent is None:
			raise RuntimeError('{0} is not attached to a namespace object'.format(self))
		else:
			return self.parent.get_namespace_object()


class Namespace(Object):
	def __init__(self, name, parent=None):
		Object()
		self.name = NamespaceName(name, prev=parent)
		self.parent = parent
		self.children = []
	
	def add_child(self, child):
		self.children.append(child)
		child.parent = self


class EnumValue(Object):
	def set_from_c(self, cEnumValue, namespace=None):
		Object.set_from_c(self, cEnumValue, namespace=namespace)
		self.name = EnumValueName()
		self.name.prev = None if namespace is None else namespace.name
		self.name.set_from_c(cEnumValue.name)


class Enum(Object):
	def __init__(self):
		Object.__init__(self)
		self.values = []
	
	def add_value(self, value):
		self.values.append(value)
		value.parent = self
	
	def set_from_c(self, cEnum, namespace=None):
		Object.set_from_c(self, cEnum, namespace=namespace)
		
		if 'associatedTypedef' in dir(cEnum):
			name = cEnum.associatedTypedef.name
		else:
			name = cEnum.name
		
		self.name = EnumName()
		self.name.prev = None if namespace is None else namespace.name
		self.name.set_from_c(name)
		
		for cEnumValue in cEnum.values:
			aEnumValue = EnumValue()
			aEnumValue.set_from_c(cEnumValue, namespace=self)
			self.add_value(aEnumValue)


class Argument(Object):
	def __init__(self, argType, optional=False, default=None):
		Object.__init__(self)
		self.type = argType
		argType.parent = self
		self.optional = optional
		self.default = default


class Method(Object):
	class Type:
		Instance = 0,
		Class = 1
	
	def __init__(self):
		Object.__init__(self)
		self.type = Method.Type.Instance
		self.constMethod = False
		self.args = []
		self.returnType = None
		
	def set_return_type(self, returnType):
		self.returnType = returnType
		returnType.parent = self
	
	def add_arguments(self, arg):
		self.args.append(arg)
		arg.parent = self
	
	def set_from_c(self, cFunction, parser, namespace=None, type=Type.Instance):
		Object.set_from_c(self,cFunction, namespace=namespace)
		self.name = MethodName()
		self.name.prev = None if namespace is None else namespace.name
		self.name.set_from_c(cFunction.name)
		self.type = type
		self.set_return_type(parser.parse_type(cFunction.returnArgument))
		
		for arg in cFunction.arguments:
			if type == Method.Type.Instance and arg is cFunction.arguments[0]:
				self.isconst = ('const' in arg.completeType.split(' '))
			else:
				aType = parser.parse_type(arg)
				argName = Argument(aType)
				argName.name = arg.name
				self.args.append(argName)

class Class(Object):
	def __init__(self):
		Object.__init__(self)
		self.instanceMethods = []
		self.classMethods = []
	
	def set_from_c(self, cClass, parser, namespace=None):
		Object.set_from_c(self, cClass, namespace=namespace)
		self.name = ClassName()
		self.name.prev = None if namespace is None else namespace.name
		self.name.set_from_c(cClass.name)
		for cMethod in cClass.instanceMethods.values():
			try:
				method = Method()
				method.set_from_c(cMethod, parser, namespace=self)
				self.instanceMethods.append(method)
			except RuntimeError as e:
				print('Could not parse {0} function: {1}'.format(cMethod.name, e.args[0]))
		for cMethod in cClass.classMethods.values():
			try:
				method = Method()
				method.set_from_c(cMethod, parser, namespace=self, type=Method.Type.Class)
				self.classMethods.append(method)
			except RuntimeError as e:
				print('Could not parse {0} function: {1}'.format(cMethod.name, e.args[0]))


class CParser(object):
	def __init__(self, cProject):
		self.cProject = cProject
		
		self.enumsIndex = {}
		for enum in self.cProject.enums:
			if enum.associatedTypedef is None:
				self.enumsIndex[enum.name] = None
			else:
				self.enumsIndex[enum.associatedTypedef.name] = None
		
		self.classesIndex = {}
		for _class in self.cProject.classes:
			self.classesIndex[_class.name] = None
		
		self.cBaseType = ['void', 'bool_t', 'char', 'short', 'int', 'long', 'size_t', 'time_t', 'float', 'double']
		self.cListType = 'bctbx_list_t'
		self.regexFixedSizeInteger = '^(u?)int(\d?\d)_t$'
		self.namespace = Namespace('linphone')
	
	def parse_type(self, cType):
		if cType.ctype in self.cBaseType or re.match(self.regexFixedSizeInteger, cType.ctype):
			return CParser.parse_c_base_type(self, cType.completeType)
		elif cType.ctype in self.enumsIndex:
			return EnumType(cType.ctype, self.enumsIndex[cType.ctype])
		elif cType.ctype in self.classesIndex:
			return ClassType(cType.ctype, self.classesIndex[cType.ctype])
		elif cType.ctype == self.cListType:
			return ListType(cType.containedType)
		else:
			raise RuntimeError('Unknown C type \'{0}\''.format(cType.ctype))
	
	def parse_enum(self, cenum):
		enum = Enum()
		enum.set_from_c(cenum, namespace=self.namespace)
		if cenum.associatedTypedef is None:
			self.enumsIndex[cenum.name] = enum
		else:
			self.enumsIndex[cenum.associatedTypedef.name] = enum
		return enum
	
	def parse_class(self, cclass):
		_class = Class()
		_class.set_from_c(cclass, self, namespace=self.namespace)
		self.classesIndex[cclass.name] = _class
		return _class
	
	def parse_all(self):
		for enum in self.cProject.enums:
			self.parse_enum(enum)
		for _class in self.cProject.classes:
			try:
				self.parse_class(_class)
			except RuntimeError as e:
				print('Could not parse \'{0}\' class: {1}'.format(_class.name, e.args[0]))
		self.fix_all_types()
		
	def fix_type(self, type):
		if isinstance(type, EnumType) and type.desc is None:
			type.desc = self.enumsIndex[type.name]
		elif isinstance(type, ClassType) and type.desc is None:
			type.desc = self.classesIndex[type.name]
		elif isinstance(type, ListType) and type.containedTypeDesc is None:
			if type.containedType in self.classesIndex:
				type.containedTypeDesc = ClassType(type.containedType, self.classesIndex[type.containedType])
			elif type.containedType in self.enumsIndex:
				type.containedTypeDesc = EnumType(type.containedType, desc=self.enumIndex[type.containedType])
			else:
				type.containedTypeDesc = self.parse_c_base_type(type.containedType)
	
	def fix_all_types(self):
		for _class in self.classesIndex.itervalues():
			if _class is not None:
				for method in (_class.instanceMethods + _class.classMethods):
					self.fix_type(method.returnType)
					for arg in method.args:
						self.fix_type(arg.type)
	
	def parse_c_base_type(self, cDecl):
		declElems = cDecl.split(' ')
		param = {}
		name = None
		for elem in declElems:
			if elem == 'const':
				if name is None:
					param['isconst'] = True
			elif elem == 'unisigned':
				param['isUnsigned'] = True
			elif elem == 'char':
				name = 'character'
			elif elem == 'void':
				name = 'void'
			elif elem == 'bool_t':
				name = 'boolean'
			elif elem in ['short', 'long']:
				param['size'] = elem
			elif elem == 'int':
				name = 'integer'
			elif elem == 'float':
				name = 'floatant'
				param['size'] = 'float'
			elif elem == 'size_t':
				name = 'size'
			elif elem == 'time_t':
				name = 'time'
			elif elem == 'double':
				name = 'floatant'
				if 'size' in param and param['size'] == 'long':
					param['size'] = 'long double'
				else:
					param['size'] = 'double'
			elif elem == '*':
				if name is not None:
					if name == 'character':
						name = 'string'
					else:
						param['isref'] = True
			else:
				matchCtx = re.match(self.regexFixedSizeInteger, elem)
				if matchCtx:
					name = 'integer'
					if matchCtx.group(1) == 'u':
						param['isUnsigned'] = True
					
					param['size'] = int(matchCtx.group(2))
					if param['size'] not in [8, 16, 32, 64]:
						raise RuntimeError('{0} C basic type has an invalid size ({1})'.format(cDecl, param['size']))
				else:
					raise RuntimeError('{0} is not a basic C type'.format(cDecl))
		
		if name is not None:
			return BaseType(name, **param)
		else:
			raise RuntimeError('Could not find type in {0}'.format(cDecl))


class Translator(object):
	def translate(self, obj):
		if isinstance(obj, Object):
			return self._translate_object(obj)
		elif isinstance(obj, Name):
			return self._translate_name(obj)
		elif isinstance(obj, Type):
			return self._translate_type(obj)
		else:
			Translator.fail(obj)
	
	def _translate_object(self, aObject):
		if type(aObject) is Enum:
			return self._translate_enum(aObject)
		elif type(aObject) is EnumValue:
			return self._translate_enum_value(aObject)
		elif type(aObject) is Class:
			return self._translate_class(aObject)
		elif type(aObject) is Method:
			return self._translate_method(aObject)
		elif type(aObject) is Argument:
			return self._translate_argument(aObject)
		else:
			Translator.fail(aObject)
	
	def _translate_type(self, aType):
		if type(aType) is BaseType:
			return self._translate_base_type(aType)
		elif type(aType) is EnumType:
			return self._translate_enum_type(aType)
		elif type(aType) is ClassType:
			return self._translate_class_type(aType)
		elif type(aType) is ListType:
			return self._translate_list_type(aType)
		else:
			Translator.fail(aType)
	
	def _translate_name(self, aName):
		if type(aName) is EnumName:
			return self._translate_enum_name(aName)
		elif type(aName) is EnumValueName:
			return self._translate_enum_value_name(aName)
		elif type(aName) is MethodName:
			return self._translate_method_name(aName)
		elif type(aName) is NamespaceName:
			return self._translate_namespace_name(aName)
		elif type(aName) is ClassName:
			return self._translate_class_name(aName)
		else:
			Translator.fail(aName)
	
	@staticmethod
	def fail(obj):
		raise RuntimeError('Cannot translate {0} type'.format(type(obj)))
