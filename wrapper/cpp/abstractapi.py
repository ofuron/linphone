import re

class Name(object):
	def __init__(self):
		self.words = []
	
	def clone(self):
		copy = Name()
		copy.words = list(self.words)
		return copy
	
	def __add__(self, other):
		copy = self.clone()
		copy.words += other.words
		return copy
	
	def from_c_class_name(self, className, namespace=None):
		prefixWords = [] if namespace is None else namespace._full_word_list()
		words = re.findall('[A-Z][^A-Z]*', className)
		
		i = 0
		while i < len(words):
			words[i] = words[i].lower()
			i += 1
		
		while len(prefixWords) > 0 and len(words) > 0 and prefixWords[0] == words[0]:
			del prefixWords[0]
			del words[0]
		
		if len(words) == 0:
			raise RuntimeError('cannot find out the abstract name of "{0}" with {1} as namespace'.format(className, namespace))
		
		self.words = []
		for word in words:
			self.words.append(word)

	def from_c_func_name(self, funcName, namespace=None):
		prefix = '' if namespace is None else (namespace._full_c_function_name() + '_')
		if funcName.startswith(prefix):
			funcName = funcName[len(prefix):]
			self.words = funcName.split('_')
		else:
			raise RuntimeError('cannot find out the abstract name of "{0}" with "{1}" as prefix'.format(funcName, prefix))
	
	def to_class_name(self):
		res = ''
		for word in self.words:
			res += word.title()
		return res

	def to_method_name(self):
		res = ''
		first = True
		for word in self.words:
			if first:
				res += word
				first = False
			else:
				res += word.title()
		return res
	
	def to_namespace_name(self):
		return ''.join(self.words)
	
	def to_c_class_name(self):
		return self.to_class_name()
	
	def to_c_function_name(self):
		return '_'.join(self.words)


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
	
	def _full_name(self):
		if self.parent is None:
			return [self.name.clone()]
		else:
			res = self.parent._full_name()
			res.append(self.name.clone())
			return res
	
	def _full_c_class_name(self):
		res = ''
		fullName = self._full_name()
		for name in fullName:
			res += name.to_c_class_name()
		return res
	
	def _full_c_function_name(self):
		res = []
		fullName = self._full_name()
		for name in fullName:
			res.append(name.to_c_function_name())
		return '_'.join(res)
	
	def _full_word_list(self):
		res = []
		for name in self._full_name():
			res += name.words
		return res


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
		aname = Name()
		aname.from_c_class_name(cEnumValue.name, namespace=namespace)
		self.name = aname


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
		
		aname = Name()
		aname.from_c_class_name(name, namespace=namespace)
		self.name = aname
		
		for cEnumValue in cEnum.values:
			aEnumValue = EnumValue()
			aEnumValue.set_from_c(cEnumValue, namespace=self)
			self.add_value(aEnumValue)


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
			self.type = Name()
			self.type.from_c_class_name(cType.ctype, namespace=namespace)
			self.isobject = True
		
		if '*' in cType.completeType:
			if not self.isobject:
				if self.type == 'character':
					self.type == 'string'
			else:
				self.isreference = True
		
		if 'const' in cType.completeType:
			self.isconst = True


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
		self.name = Name()
		self.name.from_c_func_name(cFunction.name, namespace=namespace)
		self.type = type
		if cFunction.returnArgument.ctype != 'void':
			self.returnType = Type()
			self.returnType.set_from_c(cFunction.returnArgument, namespace=namespace.parent)


class Class(Object):
	def __init__(self):
		Object.__init__(self)
		self.instanceMethods = []
		self.classMethods = []
	
	def set_from_c(self, cClass, namespace=None):
		Object.set_from_c(self, cClass, namespace=namespace)
		self.name = Name()
		self.name.from_c_class_name(cClass.name, namespace=namespace)
		for cMethod in cClass.instanceMethods.values():
			method = Method()
			method.set_from_c(cMethod, namespace=self)
			self.instanceMethods.append(method)
		for cMethod in cClass.classMethods.values():
			method = Method()
			method.set_from_c(cMethod, namespace=self, type=Method.Type.Class)
			self.classMethods.append(method)
