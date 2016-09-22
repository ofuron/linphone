import re
import genapixml as CApi

class Name(object):
	def __init__(self, prev = None, cname = None):
		self.words = []
		self.prev = prev
		if cname is not None:
			self.set_from_c(cname)
	
	def get_prefix_as_word_list(self):
		if self.prev is None:
			return []
		else:
			return self.prev.get_prefix_as_word_list() + list(self.prev.words)


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


class Namespace(Object):
	def __init__(self, name, parent=None):
		Object()
		self.name = Name()
		self.name.words = [name]
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


class Type(Object):
	def __init__(self):
		Object.__init__(self)
		self.type = None
		self.isconst = False
		self.isobject = False
		self.isreference = False
	
	def set_from_c(self, cType, namespace=None):
		if cType.ctype == 'char':
			self.type = 'character'
		elif cType.ctype == 'bool_t':
			self.type = 'boolean'
		elif cType.ctype == 'int':
			self.type = 'integer'
		elif cType.ctype in ('float', 'double'):
			self.type = 'floatant'
		else:
			self.type = ClassName()
			self.type.prev = None if namespace is None else namespace.name
			self.type.set_from_c(cType.ctype)
			self.isobject = True
		
		if '*' in cType.completeType:
			if not self.isobject:
				if self.type == 'character':
					self.type == 'string'
			else:
				self.isreference = True
		
		if 'const' in cType.completeType:
			self.isconst = True
	
	def translate(self, translator):
		return translator.translate_type(self)


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
	
	def set_from_c(self, cFunction, namespace=None, type=Type.Instance):
		Object.set_from_c(self,cFunction, namespace=namespace)
		self.name = MethodName()
		self.name.prev = None if namespace is None else namespace.name
		self.name.set_from_c(cFunction.name)
		self.type = type
		if cFunction.returnArgument.ctype != 'void':
			self.returnType = Type()
			self.returnType.set_from_c(cFunction.returnArgument, namespace=namespace.parent)
	
	def translate(self, translator):
		return translator.translate_method(self)


class Class(Object):
	def __init__(self):
		Object.__init__(self)
		self.instanceMethods = []
		self.classMethods = []
	
	def set_from_c(self, cClass, namespace=None):
		Object.set_from_c(self, cClass, namespace=namespace)
		self.name = ClassName()
		self.name.prev = None if namespace is None else namespace.name
		self.name.set_from_c(cClass.name)
		for cMethod in cClass.instanceMethods.values():
			method = Method()
			method.set_from_c(cMethod, namespace=self)
			self.instanceMethods.append(method)
		for cMethod in cClass.classMethods.values():
			method = Method()
			method.set_from_c(cMethod, namespace=self, type=Method.Type.Class)
			self.classMethods.append(method)
	
	def translate(self, translator):
		return translator.translate_class(self)
