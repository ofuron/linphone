#!/usr/bin/python


import pystache
import re
import genapixml as CApi
import abstractapi as AbsApi


class CppTranslator(AbsApi.Translator):
	def _translate_enum(self, enum):
		enumDict = {}
		enumDict['name'] = enum.name.to_camel_case()
		enumDict['values'] = []
		i = 0
		for enumValue in enum.values:
			enumValDict = self.translate(enumValue)
			enumValDict['notLast'] = (i != len(enum.values)-1)
			enumDict['values'].append(enumValDict)
			i += 1
		return enumDict
	
	def _translate_enum_value(self, enumValue):
		enumValueDict = {}
		enumValueDict['name'] = self.translate(enumValue.name)
		return enumValueDict
	
	def _translate_class(self, _class):
		classDict = {}
		classDict['name'] = self.translate(_class.name)
		classDict['methods'] = []
		classDict['staticMethods'] = []
		for property in _class.properties:
			try:
				classDict['methods'] += self.translate(property)
			except RuntimeError as e:
				print('error while translating {0} property: {1}'.format(property.name.to_snake_case(), e.args[0]))
		
		for method in _class.instanceMethods:
			try:
				methodDict = self.translate(method)
				classDict['methods'].append(methodDict)
			except RuntimeError as e:
				print('Could not translate {0}: {1}'.format(method.name.to_snake_case(fullName=True), e.args[0]))
				
		for method in _class.classMethods:
			try:
				methodDict = self.translate(method)
				classDict['staticMethods'].append(methodDict)
			except RuntimeError as e:
				print('Could not translate {0}: {1}'.format(method.name.to_snake_case(fullName=True), e.args[0]))
		
		return classDict
	
	def _translate_property(self, property):
		res = []
		if property.getter is not None:
			res.append(self.translate(property.getter))
		if property.setter is not None:
			res.append(self.translate(property.setter))
		return res
	
	def _translate_method(self, method):
		methodElems = {}
		try:
			methodElems['return'] = self.translate(method.returnType)
		except RuntimeError as e:
			print('Cannot translate the return type of {0}: {1}'.format(method.name.to_snake_case(fullName=True) + '()', e.args[0]))
			methodElems['return'] = None
		
		methodElems['name'] = self.translate(method.name)
		if methodElems['name'] == 'new':
			methodElems['name'] = '_new'
		
		methodElems['params'] = ''
		for arg in method.args:
			if arg is not method.args[0]:
				methodElems['params'] += ', '
			methodElems['params'] += CppTranslator._translate_argument(self, arg)
		
		methodElems['const'] = ' const' if method.constMethod else ''
		
		methodDict = {}
		methodDict['prototype'] = '{return} {name}({params}){const};'.format(**methodElems)
		if method.type == AbsApi.Method.Type.Class:
			methodDict['prototype'] = 'static ' + methodDict['prototype'];
		return methodDict
	
	def _translate_argument(self, arg):
		return '{0} {1}'.format(self.translate(arg.type), self.translate(arg.name))
	
	def _translate_base_type(self, _type):
		if _type.name == 'void':
			if _type.isref:
				return 'void *'
			else:
				return 'void'
		elif _type.name == 'boolean':
			res = 'bool'
		elif _type.name == 'character':
			res = 'char'
		elif _type.name == 'size':
			res = 'size_t'
		elif _type.name == 'time':
			res = 'time_t'
		elif _type.name == 'integer':
			if _type.size is None:
				res = 'int'
			elif isinstance(_type.size, str):
				res = _type.size
			else:
				res = 'int{0}_t'.format(_type.size)
		elif _type.name == 'floatant':
			if _type.size is not None and _type.size == 'double':
				res = 'double'
			else:
				res = 'float'
		elif _type.name == 'string':
			res = 'std::string'
			if type(_type.parent) is AbsApi.Argument:
				res += ' &'
		else:
			raise RuntimeError('\'{0}\' is not a base abstract type'.format(_type.name))
		
		if _type.isUnsigned:
			if _type.name == 'integer' and isinstance(_type.size, int):
				res = 'u' + res
			else:
				res = 'unsigned ' + res
		if _type.isconst:
			res = 'const ' + res
		if _type.isref:
			res += ' &'
		return res
	
	def _translate_enum_type(self, type):
		if type.desc is None:
			raise RuntimeError('{0} has not been fixed'.format(type.name))
		
		nsCtx = type.find_first_ancestor_by_type(AbsApi.Method)
		commonParentName = AbsApi.Name.find_common_parent(type.desc.name, nsCtx.name) if nsCtx is not None else None
		return self.translate(type.desc.name, recursive=True, topAncestor=commonParentName)
	
	def _translate_class_type(self, type):
		if type.desc is None:
			raise RuntimeError('{0} has not been fixed'.format(type.name))
		
		nsCtx = type.find_first_ancestor_by_type(AbsApi.Method)
		commonParentName = AbsApi.Name.find_common_parent(type.desc.name, nsCtx.name) if nsCtx is not None else None
		res = self.translate(type.desc.name, recursive=True, topAncestor=commonParentName)
		
		if type.isconst:
			res = 'const ' + res
		
		return 'std::shared_ptr<{0}>'.format(res)
	
	def _translate_list_type(self, type):
		if type.containedTypeDesc is None:
			raise RuntimeError('{0} has not been fixed'.format(type))
		elif isinstance(type.containedTypeDesc, AbsApi.BaseType):
			res = self.translate(type.containedTypeDesc)
		else:
			commonParentName = AbsApi.Name.find_common_parent(type.containedTypeDesc.desc.name, type.parent.name)
			res = self.translate(type.containedTypeDesc.desc.name, recursive=True, topAncestor=commonParentName)
		return 'std::list<std::shared_ptr<{0}> >'.format(res)
	
	def _translate_class_name(self, name, recursive=False, topAncestor=None):
		if name.prev is None or not recursive or name.prev is topAncestor:
			return name.to_camel_case()
		else:
			params = {'recursive': recursive, 'topAncestor': topAncestor}
			return self.translate(name.prev, **params) + '::' + name.to_camel_case()
	
	def _translate_enum_name(self, name, recursive=False, topAncestor=None):
		params = {'recursive': recursive, 'topAncestor': topAncestor}
		return CppTranslator._translate_class_name(self, name, **params)
	
	def _translate_enum_value_name(self, name, recursive=False, topAncestor=None):
		params = {'recursive': recursive, 'topAncestor': topAncestor}
		return CppTranslator._translate_class_name(self, name, **params)
	
	def _translate_method_name(self, name, recursive=False, topAncestor=None):
		if name.prev is None or not recursive or name.prev is topAncestor:
			return name.to_camel_case(lower=True)
		else:
			params = {'recursive': recursive, 'topAncestor': topAncestor}
			return self.translate(name.prev, **params) + '::' + name.to_camel_case(lower=True)
	
	def _translate_namespace_name(self, name, recursive=False, topAncestor=None):
		if name.prev is None or not recursive or name.prev is topAncestor:
			return name.concatenate()
		else:
			params = {'recursive': recursive, 'topAncestor': topAncestor}
			return self.translate(name.prev, **params) + '::' + name.concatenate()
	
	def _translate_argument_name(self, name):
		return name.to_camel_case(lower=True)
	
	def _translate_property_name(self, name):
		CppTranslator._translate_argument_name(self, name)


class EnumsHeader(object):
	def __init__(self, translator):
		self.translator = translator
		self.enums = []
	
	def add_enum(self, enum):
		self.enums.append(self.translator.translate(enum))


class ClassHeader(object):
	def __init__(self, _class, translator):
		self._class = translator.translate(_class)
		self.define = ClassHeader._class_name_to_define(_class.name)
		self.filename = ClassHeader._class_name_to_filename(_class.name)
		self.includes = {'internal': [], 'external': []}
		self.update_includes(_class)
	
	def update_includes(self, _class):
		includes = {'internal': set(), 'external': set()}
		for method in (_class.classMethods + _class.instanceMethods):
			tmp = ClassHeader._needed_includes_from_type(self, method.returnType, _class)
			includes['internal'] |= tmp['internal']
			includes['external'] |= tmp['external']
			for arg in method.args:
				tmp = ClassHeader._needed_includes_from_type(self, arg.type, _class)
				includes['internal'] |= tmp['internal']
				includes['external'] |= tmp['external']
		
		for include in includes['internal']:
			self.includes['internal'].append({'name': include})
		
		for include in includes['external']:
			self.includes['external'].append({'name': include})
	
	def _needed_includes_from_type(self, type, currentClass):
		res = {'internal': set(), 'external': set()}
		if isinstance(type, AbsApi.ClassType):
			res['external'].add('memory')
			if type.desc is not None and type.desc is not currentClass:
				res['internal'].add('_'.join(type.desc.name.words))
		elif isinstance(type, AbsApi.EnumType):
			res['internal'].add('enums')
		elif isinstance(type, AbsApi.BaseType):
			if type.name == 'integer' and isinstance(type.size, int):
				res['external'].add('cstdint')
			elif type.name == 'string':
				res['external'].add('string')
		elif isinstance(type, AbsApi.ListType):
			res['external'].add('list')
			retIncludes = self._needed_includes_from_type(type.containedTypeDesc, currentClass)
			res['external'] |= retIncludes['external']
			res['internal'] = retIncludes['internal']
		return res
	
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


def main():
	project = CApi.Project()
	project.initFromDir('../../work/coreapi/help/doc/xml')
	project.check()
	
	translator = CppTranslator()
	parser = AbsApi.CParser(project)
	parser.parse_all()
	renderer = pystache.Renderer()	
	
	header = EnumsHeader(translator)
	for enum in parser.enumsIndex.itervalues():
		header.add_enum(enum)
	
	with open('include/enums.hh', mode='w') as f:
		f.write(renderer.render(header))
	
	for _class in parser.classesIndex.itervalues():
		if _class is not None:
			header = ClassHeader(_class, translator)
			with open('include/' + header.filename, mode='w') as f:
				f.write(renderer.render(header))


if __name__ == '__main__':
	main()
