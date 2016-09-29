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
	
	def translate(self, translator):
		return translator.translate_class_name(self)


class EnumName(ClassName):
	def translate(self, translator):
		return translator.translate_enum_name(self)


class EnumValueName(ClassName):
	def translate(self, translator):
		return translator.translate_enum_value_name(self)


class MethodName(Name):
	def set_from_c(self, cname):
		self.words = cname.split('_')
		prefix = self.get_prefix_as_word_list()
		while len(prefix) > 0 and len(self.words) > 0 and prefix[0] == self.words[0]:
			del prefix[0]
			del self.words[0]
		if len(self.words) == 0:
			raise ValueError('Could not parse C function name \'{0}\' with {1} as prefix'.format(cname, prefix))
	
	def translate(self, translator):
		return translator.translate_method_name(self)
	
	def format_as_c(self):
		fullName = self.get_full_name_as_word_list()
		return '_'.join(fullName)


class NamespaceName(Name):
	def __init__(self, name=None, prev=None):
		Name.__init__(self, prev=prev)
		self.words = [name] if name is not None else []
	
	def translate(self, translator):
		return translator.translate_namespace_name(self)


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
	
	def translate(self, translator):
		return translator.translate_base_type(self)


class EnumType(Type):
	def __init__(self, name, enumDesc):
		Type.__init__(self)
		self.name = name
		self.desc = enumDesc
	
	def translate(self, translator):
		return translator.translate_enum_type(self)


class ClassType(Type):
	def __init__(self, name, classDesc, isconst=False):
		Type.__init__(self)
		self.name = name
		self.desc = classDesc
		self.isconst = isconst
	
	def translate(self, translator):
		return translator.translate_class_type(self)


class ListType(Type):
	def __init__(self, containedType=None):
		Type.__init__(self)
		self.containedType = containedType
		self.containedTypeDesc = None
	
	def translate(self, translator):
		return translator.translate_list_type(self)


class Object(object):
	def __init__(self):
		self.name = None
		self.briefDescription = None
		self.detailedDescription = None
		self.deprecated = None
		self.parent = None
		self.translator = None
	
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
	
	def translate(self, translator):
		return translator.translate_enum_value(self)


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
	
	def translate(self, translator):
		return translator.translate_enum(self)


class Method(Object):
	class Type:
		Instance = 0,
		Class = 1
	
	def __init__(self):
		Object.__init__(self)
		self.type = Method.Type.Instance
		self.constMethod = False
		self.mandArgs = None
		self.optArgs = None
		self.returnType = None
		
	def set_return_type(self, returnType):
		self.returnType = returnType
		returnType.parent = self
	
	def set_from_c(self, cFunction, parser, namespace=None, type=Type.Instance):
		Object.set_from_c(self,cFunction, namespace=namespace)
		self.name = MethodName()
		self.name.prev = None if namespace is None else namespace.name
		self.name.set_from_c(cFunction.name)
		self.type = type
		if cFunction.returnArgument.ctype != 'void':
			self.set_return_type(parser.parse_type(cFunction.returnArgument))
	
	def translate(self, translator):
		return translator.translate_method(self)


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
			method = Method()
			method.set_from_c(cMethod, parser, namespace=self)
			self.instanceMethods.append(method)
		for cMethod in cClass.classMethods.values():
			method = Method()
			method.set_from_c(cMethod, parser, namespace=self, type=Method.Type.Class)
			self.classMethods.append(method)
	
	def translate(self, translator):
		return translator.translate_class(self)


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
		
		self.cBaseType = ['bool_t', 'char', 'short', 'int', 'long', 'float', 'double']
		self.cListType = 'bctbx_list_t'
		self.regexFixedSizeInteger = '^(u?)int(\d?\d)_t$'
		self.namespace = Namespace('linphone')
	
	def parse_type(self, cType):
		if cType.ctype in self.cBaseType or re.match(self.regexFixedSizeInteger, cType.ctype):
			return CParser._parse_as_base_type(self, cType)
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
			type.containedTypeDesc = self.classesIndex[type.containedType]
	
	def fix_all_types(self):
		for _class in self.classesIndex.itervalues():
			if _class is not None:
				for method in _class.instanceMethods:
					self.fix_type(method.returnType)
				for method in _class.classMethods:
					self.fix_type(method.returnType)
	
	def _parse_as_base_type(self, cType):
		param = {}
		
		if cType.ctype == 'char':
			if '*' in cType.completeType:
				name = 'string'
			else:
				name = 'character'
		else:
			if cType.ctype == 'bool_t':
				name = 'boolean'
			elif cType.ctype in ['short', 'int', 'long']:
				name = 'integer'
				if cType.ctype in ['short', 'long']:
					param['size'] = cType.ctype
				if 'unsigned' in cType.completeType:
					param['isUnsigned'] = True
			elif cType.ctype in ['float', 'double']:
				name = 'floatant'
				if cType.ctype == 'double':
					param['size'] = 'double'
			else:
				match = re.match(self.regexFixedSizeInteger, cType.ctype)
				if match is not None:
					name = 'integer'
					if match.group(1) == 'u':
						param['isUnsigned'] = True
					param['size'] = int(match.group(2))
					if param['size'] not in [8, 16, 32, 64]:
						raise RuntimeError('{0} C basic type has an invalid size ({1})'.format(cType.type, param['size']))
				else:
					raise RuntimeError('{0} is not a basic C type'.format(cType.ctype))
			
			if '*' in cType.completeType:
				param['isref'] = True
		
		if 'const' in cType.completeType and name != 'string':
			param['isconst'] = True
		
		return BaseType(name, **param)
	
	
