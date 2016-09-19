#!/usr/bin/python


import pystache
import re
from genapixml import *


class AbstractName(object):
	def __init__(self):
		self.words = []
	
	def clone(self):
		copy = AbstractName()
		copy.words = list(self.words)
		return copy
	
	def __add__(self, other):
		copy = self.clone()
		copy.words += other.words
		return copy
	
	def from_c_class_name(self, className, prefix=''):
		words = re.findall('[A-Z][^A-Z]*', className)
		prefixWords = re.findall('[A-Z][^A-Z]*', prefix)
		while len(prefixWords) > 0 and len(words) > 0 and prefixWords[0] == words[0]:
			del prefixWords[0]
			del words[0]
		
		if len(words) == 0:
			raise RuntimeError('cannot find out the abstract name of "{0}" with "{1}" as prefix'.format(className, prefix))
		
		self.words = []
		for word in words:
			self.words.append(word.lower())
			

	def from_c_func_name(self, funcName, prefix=''):
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


class AbstractObject(object):
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


class AbstractNamespace(AbstractObject):
	def __init__(self, name, parent=None):
		AbstractObject()
		self.name = AbstractName()
		self.name.words = [name]
		self.parent = parent
		self.children = []
	
	def add_child(self, child):
		self.children.append(child)
		child.parent = self


class AbstractEnumValue(AbstractObject):
	def set_from_c(self, cEnumValue, namespace=None):
		AbstractObject.set_from_c(self, cEnumValue, namespace=namespace)
		prefix = '' if namespace is None else namespace._full_c_class_name()
		aname = AbstractName()
		aname.from_c_class_name(cEnumValue.name, prefix=prefix)
		self.name = aname


class AbstractEnum(AbstractObject):
	def __init__(self):
		AbstractObject.__init__(self)
		self.values = []
	
	def add_value(self, value):
		self.values.append(value)
		value.parent = self
	
	def set_from_c(self, cEnum, namespace=None):
		AbstractObject.set_from_c(self, cEnum, namespace=namespace)
		
		if 'associatedTypedef' in dir(cEnum):
			name = cEnum.associatedTypedef.name
		else:
			name = cEnum.name
		
		prefix = '' if namespace is None else namespace._full_c_class_name()
		aname = AbstractName()
		aname.from_c_class_name(name, prefix=prefix)
		self.name = aname
		
		for cEnumValue in cEnum.values:
			aEnumValue = AbstractEnumValue()
			aEnumValue.set_from_c(cEnumValue, namespace=self)
			aEnum.add_value(aEnumValue)


class AbstractType(AbstractObject):
	def __init__(self):
		AbstractObject.__init__(self)
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
			self.type = AbstractName()
			prefix = namespace._full_c_class_name() if namespace is not None else ''
			self.type.from_c_class_name(cType.ctype, prefix=prefix)
			self.isobject = True
		
		if '*' in cType.completeType:
			if not self.isobject:
				if self.type == 'character':
					self.type == 'string'
			else:
				self.isreference = True
		
		if 'const' in cType.completeType:
			self.isconst = True


class AbstractMethod(AbstractObject):
	class Type:
		Instance = 0,
		Class = 1
	
	def __init__(self):
		AbstractObject.__init__(self)
		self.type = AbstractMethod.Type.Instance
		self.constMethod = False
		self.mandArgs = None
		self.optArgs = None
		self.returnType = None
	
	def set_from_c(self, cFunction, namespace=None, type=Type.Instance):
		AbstractObject.set_from_c(self,cFunction, namespace=namespace)
		prefix = '' if namespace is None else (namespace._full_c_function_name() + '_')
		self.name = AbstractName()
		self.name.from_c_func_name(cFunction.name, prefix=prefix)
		self.type = type
		if cFunction.returnArgument.ctype != 'void':
			self.returnType = AbstractType()
			self.returnType.set_from_c(cFunction.returnArgument, namespace=namespace.parent)


class AbstractClass(AbstractObject):
	def __init__(self):
		AbstractObject.__init__(self)
		self.instanceMethods = []
		self.classMethods = []
	
	def set_from_c(self, cClass, namespace=None):
		AbstractObject.set_from_c(self, cClass, namespace=namespace)
		prefix = '' if namespace is None else namespace._full_c_class_name()
		self.name = AbstractName()
		self.name.from_c_class_name(cClass.name, prefix=prefix)
		for cMethod in cClass.instanceMethods.values():
			method = AbstractMethod()
			method.set_from_c(cMethod, namespace=self)
			self.instanceMethods.append(method)
		for cMethod in cClass.classMethods.values():
			method = AbstractMethod()
			method.set_from_c(cMethod, namespace=self, type=AbstractMethod.Type.Class)
			self.classMethods.append(method)


class CppTranslator(object):
	def translate_enum(self, enum):
		enumDict = {}
		enumDict['name'] = enum.name.to_class_name()
		enumDict['values'] = []
		i = 0
		for enumValue in enum.values:
			enumValDict = self.translate_enum_value(enumValue, last=(i == len(enum.values)-1))
			enumDict['values'].append(enumValDict)
			i += 1
		return enumDict
	
	def translate_enum_value(self, enumValue, last=False):
		enumValueDict = {}
		enumValueDict['name'] = enumValue.name.to_class_name()
		enumValueDict['notLast'] = not last
		return enumValueDict
	
	def translate_class(self, _class):
		classDict = {}
		classDict['name'] = _class.name.to_class_name()
		classDict['methods'] = []
		classDict['staticMethods'] = []
		for method in _class.instanceMethods:
			methodDict = self.translate_method(method)
			classDict['methods'].append(methodDict)
		for method in _class.classMethods:
			methodDict = self.translate_method(method)
			classDict['staticMethods'].append(methodDict)
		return classDict
	
	def translate_method(self, method):
		methodDict = {}
		methodDict['prototype'] = '{0} {1}();'.format(self.translate_type(method.returnType), method.name.to_method_name())
		if method.type == AbstractMethod.Type.Class:
			methodDict['prototype'] = 'static ' + methodDict['prototype'];
		return methodDict
	
	def translate_type(self, type):
		if type is not None:
			res = ''
			if type.isobject:
				if type.isconst:
					res += 'const '
				res += type.type.to_c_class_name()
				res = 'std::shared_ptr<{0}>'.format(res)
				return res
			else:
				if type.isconst:
					res += 'const '
				res += CppTranslator.__abstract_base_type_to_cpp(type.type)
				if type.isreference:
					res += ' &'
				return res
		else:
			return 'void'
	
	@staticmethod
	def __abstract_base_type_to_cpp(atype):
		if atype == 'boolean':
			return 'bool'
		elif atype == 'character':
			return 'char'
		elif atype == 'integer':
			return 'int'
		elif atype == 'floatant':
			return 'float'
		elif atype == 'string':
			return 'std::string'
		else:
			raise RuntimeError('\'{0}\' is not a base abstlract type'.format(atype))


class EnumsHeader(object):
	def __init__(self, translator):
		self.translator = translator
		self.enums = []
	
	def add_enum(self, enum):
		self.enums.append(self.translator.translate_enum(enum))


class ClassHeader(object):
	def __init__(self, _class, translator):
		self._class = translator.translate_class(_class)
		self.define = ClassHeader._class_name_to_define(_class.name)
		self.filename = ClassHeader._class_name_to_filename(_class.name)
		self.internalIncludes = []
		self.exteranlIncludes = []
		self.update_includes(_class)
	
	def update_includes(self, _class):
		internalInc = set()
		externalInc = set()
		for method in _class.classMethods:
			if method.returnType.isobject:
				externalInc.add('memory')
				internalInc.add('_'.join(method.returnType.type.words))
		self.internalIncludes = []
		self.externalIncludes = []
		for include in internalInc:
			self.internalIncludes.append({'name': include})
		for include in externalInc:
			self.externalIncludes.append({'name': include})
	
	@staticmethod
	def _class_name_to_define(className):
		words = className.words
		res = ''
		for word in words:
			res += ('_' + word.upper())
		res += '_HH'
		return res

	@staticmethod
	def _class_name_to_filename(className):
		words = className.words
		res = ''
		first = True
		for word in words:
			if first:
				first = False
			else:
				res += '_'
			res += word.lower()
		
		res += '.hh'
		return res


if __name__ == '__main__':
	project = Project()
	project.initFromDir('../../work/coreapi/help/doc/xml')
	project.check()
	
	translator = CppTranslator()
	
	header = EnumsHeader(translator)
	
	linphoneNs = AbstractNamespace(name='linphone')
	for cEnum in project.enums:
		aEnum = AbstractEnum()
		aEnum.set_from_c(cEnum, namespace=linphoneNs)
		header.add_enum(aEnum)
	
	renderer = pystache.Renderer()	
	with open('include/enums.hh', mode='w') as f:
		f.write(renderer.render(header))
	
	for cClass in project.classes:
		try:
			aClass = AbstractClass()
			aClass.set_from_c(cClass, namespace=linphoneNs)
			header = ClassHeader(aClass, translator)
			with open('include/' + header.filename, mode='w') as f:
				f.write(renderer.render(header))
		except RuntimeError as e:
			print('Ignoring "{0}". {1}'.format(cClass.name, e.args[0]))
