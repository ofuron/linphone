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
		namespace = method.find_first_ancestor_by_type(AbsApi.Namespace)
		
		methodElems = {}
		try:
			methodElems['return'] = self.translate(method.returnType)
			methodElems['implReturn'] = self.translate(method.returnType, namespace=namespace)
		except RuntimeError as e:
			print('Cannot translate the return type of {0}: {1}'.format(method.name.to_snake_case(fullName=True) + '()', e.args[0]))
			methodElems['return'] = None
			methodElems['implReturn'] = None
		
		methodElems['name'] = self.translate(method.name)
		methodElems['longname'] = self.translate(method.name, recursive=True, topAncestor=namespace.name)
		
		methodElems['params'] = ''
		methodElems['implParams'] = ''
		for arg in method.args:
			if arg is not method.args[0]:
				methodElems['params'] += ', '
				methodElems['implParams'] += ', '
			methodElems['params'] += CppTranslator._translate_argument(self, arg)
			methodElems['implParams'] += CppTranslator._translate_argument(self, arg, namespace=namespace)
		
		methodElems['const'] = ' const' if method.constMethod else ''
		methodElems['static'] = 'static ' if method.type == AbsApi.Method.Type.Class else ''
		
		methodDict = {}
		methodDict['prototype'] = '{static}{return} {name}({params}){const};'.format(**methodElems)
		methodDict['implPrototype'] = '{implReturn} {longname}({implParams}){const}'.format(**methodElems)
		methodDict['sourceCode' ] = CppTranslator._generate_source_code(self, method, usedNamespace=namespace)
		return methodDict
	
	def _generate_source_code(self, method, usedNamespace=None):
		nsName = usedNamespace.name if usedNamespace is not None else None
		
		params = {}
		params['functionName'] = method.name.to_snake_case(fullName=True)
		
		args = []
		if method.type == AbsApi.Method.Type.Instance:
			_class = method.find_first_ancestor_by_type(AbsApi.Class)
			argStr = '({0} *)mPrivPtr'.format(_class.name.to_camel_case(fullName=True))
			args.append(argStr)
		
		for arg in method.args:
			paramName = arg.name.to_camel_case(lower=True)
			if type(arg.type) is AbsApi.BaseType and arg.type.name == 'string':
				cppExpr = paramName + '.c_str()'
			elif type(arg.type) is AbsApi.EnumType:
				cppExpr = '(::{0}){1}'.format(arg.type.desc.name.to_camel_case(fullName=True), paramName)
			elif type(arg.type) is AbsApi.ClassType:
				cppExpr = '(::{0} *)sharedPtrToCPtr<{1}>({2})'.format(arg.type.desc.name.to_camel_case(fullName=True), CppTranslator._translate_class_name(self, arg.type.desc.name, recursive=True, topAncestor=nsName), paramName)
			else:
				cppExpr = paramName
			args.append(cppExpr)
			
		params['args'] = ', '.join(args)
		params['trailingBrackets'] = ''
		
		if type(method.returnType) is AbsApi.BaseType and method.returnType.name == 'void' and not method.returnType.isref:
			params['return'] = ''
		elif type(method.returnType) is AbsApi.EnumType:
			cppEnumName = CppTranslator._translate_enum_name(self, method.returnType.desc.name, recursive=True, topAncestor=nsName)
			params['return'] = 'return ({0})'.format(cppEnumName)
		elif type(method.returnType) is AbsApi.ClassType:
			cppReturnType = CppTranslator._translate_class_name(self, method.returnType.desc.name, recursive=True, topAncestor=nsName)
			params['return'] = 'return cPtrToSharedPtr<{0}>('.format(cppReturnType)
			params['trailingBrackets'] = ')'
		else:
			params['return'] = 'return '
		
		return '{return}{functionName}({args}){trailingBrackets};'.format(**params)
	
	def _translate_argument(self, arg, **params):
		return '{0} {1}'.format(self.translate(arg.type, **params), self.translate(arg.name))
	
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
			if _type.name != 'string' or type(_type.parent) is AbsApi.Argument:
				res = 'const ' + res
		
		if _type.isref:
			res += ' &'
		return res
	
	def _translate_enum_type(self, _type, **params):
		if _type.desc is None:
			raise RuntimeError('{0} has not been fixed'.format(_type.name))
		
		if 'namespace' in params:
			nsName = params['namespace'].name if params['namespace'] is not None else None
		else:
			method = _type.find_first_ancestor_by_type(AbsApi.Method)
			nsName = AbsApi.Name.find_common_parent(_type.desc.name, method.name)
		
		return self.translate(_type.desc.name, recursive=True, topAncestor=nsName)
	
	def _translate_class_type(self, _type, **params):
		if _type.desc is None:
			raise RuntimeError('{0} has not been fixed'.format(_type.name))
		
		if 'namespace' in params:
			nsName = params['namespace'].name if params['namespace'] is not None else None
		else:
			method = _type.find_first_ancestor_by_type(AbsApi.Method)
			nsName = AbsApi.Name.find_common_parent(_type.desc.name, method.name)
		
		res = self.translate(_type.desc.name, recursive=True, topAncestor=nsName)
		
		if _type.isconst:
			res = 'const ' + res
		
		if type(_type.parent) is AbsApi.Argument:
			return 'const std::shared_ptr<{0}> &'.format(res)
		else:
			return 'std::shared_ptr<{0}>'.format(res)
	
	def _translate_list_type(self, _type, **params):
		if _type.containedTypeDesc is None:
			raise RuntimeError('{0} has not been fixed'.format(_type))
		elif isinstance(_type.containedTypeDesc, AbsApi.BaseType):
			res = self.translate(_type.containedTypeDesc)
		else:
			res = self.translate(_type.containedTypeDesc, **params)
			
		if type(_type.parent) is AbsApi.Argument:
			return 'const std::list<std::shared_ptr<{0}> > &'.format(res)
		else:
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
		translatedName = name.to_camel_case(lower=True)
		if translatedName == 'new':
			translatedName = '_new'
			
		if name.prev is None or not recursive or name.prev is topAncestor:
			return translatedName
		else:
			params = {'recursive': recursive, 'topAncestor': topAncestor}
			return self.translate(name.prev, **params) + '::' + translatedName
	
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
		self.private_type = _class.name.to_camel_case(fullName=True)
		self.update_includes(_class)
	
	def update_includes(self, _class):
		includes = {'internal': set(), 'external': set()}
		
		for property in _class.properties:
			if property.setter is not None:
				tmp = ClassHeader._needed_includes_from_method(self, property.setter)
				includes['internal'] |= tmp['internal']
				includes['external'] |= tmp['external']
			if property.getter is not None:
				tmp = ClassHeader._needed_includes_from_method(self, property.getter)
				includes['internal'] |= tmp['internal']
				includes['external'] |= tmp['external']
		
		for method in (_class.classMethods + _class.instanceMethods):
			tmp = ClassHeader._needed_includes_from_type(self, method.returnType)
			includes['internal'] |= tmp['internal']
			includes['external'] |= tmp['external']
			for arg in method.args:
				tmp = ClassHeader._needed_includes_from_type(self, arg.type)
				includes['internal'] |= tmp['internal']
				includes['external'] |= tmp['external']
		
		currentClassInclude = _class.name.to_snake_case()
		if currentClassInclude in includes['internal']:
			includes['internal'].remove(currentClassInclude)
		
		for include in includes['internal']:
			self.includes['internal'].append({'name': include})
		
		for include in includes['external']:
			self.includes['external'].append({'name': include})
	
	def _needed_includes_from_method(self, method):
		includes = ClassHeader._needed_includes_from_type(self, method.returnType)
		for arg in method.args:
			tmp = ClassHeader._needed_includes_from_type(self, arg.type)
			includes['internal'] |= tmp['internal']
			includes['external'] |= tmp['external']
		return includes
	
	def _needed_includes_from_type(self, _type):
		res = {'internal': set(), 'external': set()}
		if isinstance(_type, AbsApi.ClassType):
			res['external'].add('memory')
			if _type.desc is not None:
				res['internal'].add('_'.join(_type.desc.name.words))
		elif isinstance(_type, AbsApi.EnumType):
			res['internal'].add('enums')
		elif isinstance(_type, AbsApi.BaseType):
			if _type.name == 'integer' and isinstance(_type.size, int):
				res['external'].add('cstdint')
			elif _type.name == 'string':
				res['external'].add('string')
		elif isinstance(_type, AbsApi.ListType):
			res['external'].add('list')
			retIncludes = self._needed_includes_from_type(_type.containedTypeDesc)
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


class ClassImpl(object):
	def __init__(self, parsedClass, translatedClass):
		self._class = translatedClass
		self.filename = parsedClass.name.to_snake_case() + '.cc'
		self.internalIncludes = []
		self.internalIncludes.append({'name': parsedClass.name.to_snake_case() + '.hh'})
		self.internalIncludes.append({'name': 'coreapi/' + parsedClass.name.to_snake_case() + '.h'})
		
		namespace = parsedClass.find_first_ancestor_by_type(AbsApi.Namespace)
		self.namespace = namespace.name.concatenate(fullName=True) if namespace is not None else None


def main():
	project = CApi.Project()
	project.initFromDir('../../work/coreapi/help/doc/xml')
	project.check()
	
	translator = CppTranslator()
	parser = AbsApi.CParser(project)
	parser.parse_all()
	renderer = pystache.Renderer()	
	
	header = EnumsHeader(translator)
	for item in parser.enumsIndex.items():
		if item[1] is not None:
			header.add_enum(item[1])
		else:
			print('warning: {0} enum won\'t be translated because of parsing errors'.format(item[0]))
	
	with open('include/enums.hh', mode='w') as f:
		f.write(renderer.render(header))
	
	for _class in parser.classesIndex.itervalues():
		if _class is not None:
			header = ClassHeader(_class, translator)
			impl = ClassImpl(_class, header._class)
			with open('include/' + header.filename, mode='w') as f:
				f.write(renderer.render(header))
			with open('src/' + impl.filename, mode='w') as f:
				f.write(renderer.render(impl))


if __name__ == '__main__':
	main()
