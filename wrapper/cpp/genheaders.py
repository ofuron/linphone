#!/usr/bin/python


import pystache
import re
import genapixml as CApi
import abstractapi as AbsApi


class CppTranslator(object):
	sharedPtrTypeExtractor = re.compile('^(const )?std::shared_ptr<(.+)>( &)?$')
	
	def __init__(self):
		self.ignore = []
		self.ambigousTypes = ['LinphonePayloadType']
	
	def is_ambigous_type(self, _type):
		return _type.name in self.ambigousTypes or (_type.name == 'list' and CppTranslator.is_ambigous_type(self, _type.containedTypeDesc))
	
	@staticmethod
	def translate_enum(enum):
		enumDict = {}
		enumDict['name'] = enum.name.to_camel_case()
		enumDict['values'] = []
		i = 0
		for enumValue in enum.values:
			enumValDict = CppTranslator.translate_enum_value(enumValue)
			enumValDict['notLast'] = (i != len(enum.values)-1)
			enumDict['values'].append(enumValDict)
			i += 1
		return enumDict
	
	@staticmethod
	def translate_enum_value(enumValue):
		enumValueDict = {}
		enumValueDict['name'] = CppTranslator.translate_enum_value_name(enumValue.name)
		return enumValueDict
	
	def translate_class(self, _class):
		if _class.name.to_camel_case(fullName=True) in self.ignore:
			raise AbsApi.Error('{0} has been escaped'.format(_class.name.to_camel_case(fullName=True)))
		
		classDict = {}
		classDict['name'] = CppTranslator.translate_class_name(_class.name)
		classDict['methods'] = []
		classDict['staticMethods'] = []
		for property in _class.properties:
			try:
				classDict['methods'] += CppTranslator.translate_property(self, property)
			except AbsApi.Error as e:
				print('error while translating {0} property: {1}'.format(property.name.to_snake_case(), e.args[0]))
		
		for method in _class.instanceMethods:
			try:
				methodDict = CppTranslator.translate_method(self, method)
				classDict['methods'].append(methodDict)
			except AbsApi.Error as e:
				print('Could not translate {0}: {1}'.format(method.name.to_snake_case(fullName=True), e.args[0]))
				
		for method in _class.classMethods:
			try:
				methodDict = CppTranslator.translate_method(self, method)
				classDict['staticMethods'].append(methodDict)
			except AbsApi.Error as e:
				print('Could not translate {0}: {1}'.format(method.name.to_snake_case(fullName=True), e.args[0]))
		
		return classDict
	
	def translate_property(self, property):
		res = []
		if property.getter is not None:
			res.append(CppTranslator.translate_method(self, property.getter))
		if property.setter is not None:
			res.append(CppTranslator.translate_method(self, property.setter))
		return res
	
	def translate_method(self, method):
		if method.name.to_snake_case(fullName=True) in self.ignore:
			raise AbsApi.Error('{0} has been escaped'.format(method.name.to_snake_case(fullName=True)))
		
		namespace = method.find_first_ancestor_by_type(AbsApi.Namespace)
		
		methodElems = {}
		methodElems['return'] = CppTranslator.translate_type(method.returnType)
		
		if not CppTranslator.is_ambigous_type(self, method.returnType):
			methodElems['implReturn'] = CppTranslator.translate_type(method.returnType, namespace=namespace)
		else:
			methodElems['implReturn'] = CppTranslator.translate_type(method.returnType, namespace=None)
		
		methodElems['name'] = CppTranslator.translate_method_name(method.name)
		methodElems['longname'] = CppTranslator.translate_method_name(method.name, recursive=True)
		
		methodElems['params'] = ''
		methodElems['implParams'] = ''
		for arg in method.args:
			if arg is not method.args[0]:
				methodElems['params'] += ', '
				methodElems['implParams'] += ', '
			methodElems['params'] += CppTranslator.translate_argument(arg)
			methodElems['implParams'] += CppTranslator.translate_argument(arg, namespace=namespace)
		
		methodElems['const'] = ' const' if method.constMethod else ''
		methodElems['static'] = 'static ' if method.type == AbsApi.Method.Type.Class else ''
		
		methodDict = {}
		methodDict['prototype'] = '{static}{return} {name}({params}){const};'.format(**methodElems)
		methodDict['implPrototype'] = '{implReturn} {longname}({implParams}){const}'.format(**methodElems)
		methodDict['sourceCode' ] = CppTranslator._generate_source_code(method, usedNamespace=namespace)
		return methodDict
	
	@staticmethod
	def _generate_source_code(method, usedNamespace=None):
		nsName = usedNamespace.name if usedNamespace is not None else None
		
		params = {}
		params['functionName'] = method.name.to_snake_case(fullName=True)
		
		args = []
		if method.type == AbsApi.Method.Type.Instance:
			_class = method.find_first_ancestor_by_type(AbsApi.Class)
			argStr = '(::{0} *)mPrivPtr'.format(_class.name.to_camel_case(fullName=True))
			args.append(argStr)
		
		for arg in method.args:
			paramName = arg.name.to_camel_case(lower=True)
			if type(arg.type) is AbsApi.BaseType:
				if arg.type.name == 'string':
					cppExpr = paramName + '.c_str()'
				elif arg.type not in ['void', 'string', 'string_array'] and arg.type.isref:
					cppExpr = '&' + paramName
				else:
					cppExpr = paramName
			elif type(arg.type) is AbsApi.EnumType:
				cppExpr = '(::{0}){1}'.format(arg.type.desc.name.to_camel_case(fullName=True), paramName)
			elif type(arg.type) is AbsApi.ClassType:
				ptrType = CppTranslator.translate_class_type(arg.type, namespace=usedNamespace)
				ptrType = CppTranslator.sharedPtrTypeExtractor.match(ptrType).group(2)
				cppExpr = '(::{0} *)sharedPtrToCPtr<{1}>({2})'.format(arg.type.desc.name.to_camel_case(fullName=True), ptrType, paramName)
			elif type(arg.type) is AbsApi.ListType:
				if type(arg.type.containedTypeDesc) is AbsApi.BaseType and arg.type.containedTypeDesc.name == 'string':
					cppExpr = 'StringBctbxListWrapper({0}).c_list()'.format(paramName)
				elif type(arg.type.containedTypeDesc) is AbsApi.Class:
					ptrType = CppTranslator.translate_class_type(arg.type, namespace=usedNamespace)
					ptrType = CppTranslator.sharedPtrTypeExtractor.match(ptrType).group(2)
					cppExpr = 'ObjectBctbxListWrapper<{0}>({1}).c_list()'.format(ptrType, paramName)
				else:
					raise AbsApi.Error('translation of bctbx_list_t of enums or basic C types is not supported')
			
			args.append(cppExpr)
			
		params['args'] = ', '.join(args)
		params['return'] = 'return '
		params['trailingBrackets'] = ''
		
		if type(method.returnType) is AbsApi.BaseType:
			if method.returnType.name == 'void' and not method.returnType.isref:
				params['return'] = ''
			elif method.returnType.name == 'string_array':
				params['return'] = 'return cStringArrayToCppList('
				params['trailingBrackets'] = ')'
		elif type(method.returnType) is AbsApi.EnumType:
			cppEnumName = CppTranslator.translate_enum_type(method.returnType, namespace=usedNamespace)
			params['return'] = 'return ({0})'.format(cppEnumName)
		elif type(method.returnType) is AbsApi.ClassType:
			cppReturnType = CppTranslator.translate_class_type(method.returnType, namespace=usedNamespace)
			cppReturnType = CppTranslator.sharedPtrTypeExtractor.match(cppReturnType).group(2)
			params['return'] = 'return cPtrToSharedPtr<{0}>('.format(cppReturnType)
			params['trailingBrackets'] = ')'
		elif type(method.returnType) is AbsApi.ListType:
			if type(method.returnType.containedTypeDesc) is AbsApi.BaseType and method.returnType.containedTypeDesc.name == 'string':
				params['return'] = 'return bctbxStringListToCppList('
				params['trailingBrackets'] = ')'
			elif type(method.returnType.containedTypeDesc) is AbsApi.ClassType:
				cppReturnType = CppTranslator.translate_class_type(method.returnType.containedTypeDesc, namespace=usedNamespace)
				cppReturnType = CppTranslator.sharedPtrTypeExtractor.match(cppReturnType).group(2)
				params['return'] = 'return bctbxObjectListToCppList<{0}>('.format(cppReturnType)
				params['trailingBrackets'] = ')'
			else:
				raise AbsApi.Error('translation of bctbx_list_t of enums or basic C types is not supported')
		else:
			params['return'] = 'return '
		
		return '{return}{functionName}({args}){trailingBrackets};'.format(**params)
	
	@staticmethod
	def translate_argument(arg, **params):
		return '{0} {1}'.format(CppTranslator.translate_type(arg.type, **params), CppTranslator.translate_argument_name(arg.name))
	
	@staticmethod
	def translate_type(aType, **params):
		if type(aType) is AbsApi.BaseType:
			return CppTranslator.translate_base_type(aType)
		elif type(aType) is AbsApi.EnumType:
			return CppTranslator.translate_enum_type(aType, **params)
		elif type(aType) is AbsApi.ClassType:
			return CppTranslator.translate_class_type(aType, **params)
		elif type(aType) is AbsApi.ListType:
			return CppTranslator.translate_list_type(aType, **params)
		else:
			CppTranslator.fail(aType)
	
	@staticmethod
	def translate_base_type(_type):
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
		elif _type.name == 'string_array':
			res = 'std::list<std::string>'
			if type(_type.parent) is AbsApi.Argument:
				res += ' &'
		else:
			raise AbsApi.Error('\'{0}\' is not a base abstract type'.format(_type.name))
		
		if _type.isUnsigned:
			if _type.name == 'integer' and isinstance(_type.size, int):
				res = 'u' + res
			else:
				res = 'unsigned ' + res
		
		if _type.isconst:
			if _type.name not in ['string', 'string_array'] or type(_type.parent) is AbsApi.Argument:
				res = 'const ' + res
		
		if _type.isref:
			res += ' &'
		return res
	
	@staticmethod
	def translate_enum_type(_type, **params):
		if _type.desc is None:
			raise AbsApi.Error('{0} has not been fixed'.format(_type.name.to_camel_case(fullName=True)))
		
		if 'namespace' in params:
			nsName = params['namespace'].name if params['namespace'] is not None else None
		else:
			method = _type.find_first_ancestor_by_type(AbsApi.Method)
			nsName = AbsApi.Name.find_common_parent(_type.desc.name, method.name)
		
		return CppTranslator.translate_enum_name(_type.desc.name, recursive=True, topAncestor=nsName)
	
	@staticmethod
	def translate_class_type(_type, **params):
		if _type.desc is None:
			raise AbsApi.Error('{0} has not been fixed'.format(_type.name.to_camel_case(fullName=True)))
		
		if 'namespace' in params:
			nsName = params['namespace'].name if params['namespace'] is not None else None
		else:
			method = _type.find_first_ancestor_by_type(AbsApi.Method)
			nsName = AbsApi.Name.find_common_parent(_type.desc.name, method.name)
		
		res = CppTranslator.translate_class_name(_type.desc.name, recursive=True, topAncestor=nsName)
		
		if _type.isconst:
			res = 'const ' + res
		
		if type(_type.parent) is AbsApi.Argument:
			return 'const std::shared_ptr<{0}> &'.format(res)
		else:
			return 'std::shared_ptr<{0}>'.format(res)
	
	@staticmethod
	def translate_list_type(_type, **params):
		if _type.containedTypeDesc is None:
			raise AbsApi.Error('{0} has not been fixed'.format(_type.containedTypeName))
		elif isinstance(_type.containedTypeDesc, AbsApi.BaseType):
			res = CppTranslator.translate_type(_type.containedTypeDesc)
		else:
			res = CppTranslator.translate_type(_type.containedTypeDesc, **params)
			
		if type(_type.parent) is AbsApi.Argument:
			return 'const std::list<{0} > &'.format(res)
		else:
			return 'std::list<{0} >'.format(res)
	
	@staticmethod
	def translate_name(aName, **params):
		if type(aName) is AbsApi.ClassName:
			return CppTranslator.translate_class_name(aName, **params)
		elif type(aName) is AbsApi.EnumName:
			return CppTranslator.translate_enum_name(aName, **params)
		elif type(aName) is AbsApi.EnumValueName:
			return CppTranslator.translate_enum_value_name(aName, **params)
		elif type(aName) is AbsApi.MethodName:
			return CppTranslator.translate_method_name(aName, **params)
		elif type(aName) is AbsApi.ArgName:
			return CppTranslator.translate_argument_name(aName, **params)
		elif type(aName) is AbsApi.NamespaceName:
			return CppTranslator.translate_namespace_name(aName, **params)
		elif type(aName) is AbsApi.PropertyName:
			return CppTranslator.translate_property_name(aName, **params)
		else:
			CppTranslator.fail(aName)
	
	@staticmethod
	def translate_class_name(name, recursive=False, topAncestor=None):
		if name.prev is None or not recursive or name.prev is topAncestor:
			return name.to_camel_case()
		else:
			params = {'recursive': recursive, 'topAncestor': topAncestor}
			return CppTranslator.translate_name(name.prev, **params) + '::' + name.to_camel_case()
	
	@staticmethod
	def translate_enum_name(name, recursive=False, topAncestor=None):
		params = {'recursive': recursive, 'topAncestor': topAncestor}
		return CppTranslator.translate_class_name(name, **params)
	
	@staticmethod
	def translate_enum_value_name(name, recursive=False, topAncestor=None):
		params = {'recursive': recursive, 'topAncestor': topAncestor}
		return CppTranslator.translate_enum_name(name.prev, **params) + name.to_camel_case()
	
	@staticmethod
	def translate_method_name(name, recursive=False, topAncestor=None):
		translatedName = name.to_camel_case(lower=True)
		if translatedName == 'new':
			translatedName = '_new'
			
		if name.prev is None or not recursive or name.prev is topAncestor:
			return translatedName
		else:
			params = {'recursive': recursive, 'topAncestor': topAncestor}
			return CppTranslator.translate_name(name.prev, **params) + '::' + translatedName
	
	@staticmethod
	def translate_namespace_name(name, recursive=False, topAncestor=None):
		if name.prev is None or not recursive or name.prev is topAncestor:
			return name.concatenate()
		else:
			params = {'recursive': recursive, 'topAncestor': topAncestor}
			return CppTranslator.translate_namespace_name(name.prev, **params) + '::' + name.concatenate()
	
	@staticmethod
	def translate_argument_name(name):
		return name.to_camel_case(lower=True)
	
	@staticmethod
	def translate_property_name(name):
		CppTranslator.translate_argument_name(name)
	
	@staticmethod
	def fail(obj):
		raise AbsApi.Error('Cannot translate {0} type'.format(type(obj)))


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
		self.includes = {'internal': [], 'external': []}
		self.priorDeclarations = []
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
			if _class.name.to_camel_case(fullName=True) == 'LinphoneCore':
				className = AbsApi.ClassName()
				className.from_snake_case(include)
				self.priorDeclarations.append({'name': className.to_camel_case()})
			else:
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


class MainHeader(object):
	def __init__(self):
		self.includes = []
		self.define = '_LINPHONE_HH'
	
	def add_include(self, include):
		self.includes.append({'name': include})


class ClassImpl(object):
	def __init__(self, parsedClass, translatedClass):
		self._class = translatedClass
		self.filename = parsedClass.name.to_snake_case() + '.cc'
		self.internalIncludes = []
		self.internalIncludes.append({'name': parsedClass.name.to_snake_case() + '.hh'})
		self.internalIncludes.append({'name': 'coreapi/linphonecore.h'})
		
		namespace = parsedClass.find_first_ancestor_by_type(AbsApi.Namespace)
		self.namespace = namespace.name.concatenate(fullName=True) if namespace is not None else None


def main():
	project = CApi.Project()
	project.initFromDir('../../work/coreapi/help/doc/xml')
	project.check()
	
	parser = AbsApi.CParser(project)
	parser.parse_all()
	translator = CppTranslator()
	translator.ignore += ['linphone_tunnel_get_http_proxy',
					   'linphone_core_can_we_add_call',
					   'linphone_core_get_default_proxy',
					   'linphone_proxy_config_normalize_number']
	
	translator.ignore.append('LinphoneBuffer')
	renderer = pystache.Renderer()	
	
	header = EnumsHeader(translator)
	for item in parser.enumsIndex.items():
		if item[1] is not None:
			header.add_enum(item[1])
		else:
			print('warning: {0} enum won\'t be translated because of parsing errors'.format(item[0]))
	
	with open('include/enums.hh', mode='w') as f:
		f.write(renderer.render(header))
	
	mainHeader = MainHeader()
	
	for _class in parser.classesIndex.itervalues():
		if _class is not None:
			try:
				header = ClassHeader(_class, translator)
				impl = ClassImpl(_class, header._class)
				mainHeader.add_include(_class.name.to_snake_case() + '.hh')
				with open('include/' + header.filename, mode='w') as f:
					f.write(renderer.render(header))
				with open('src/' + impl.filename, mode='w') as f:
					f.write(renderer.render(impl))
			except AbsApi.Error as e:
				print('Could not translate {0}: {1}'.format(_class.name.to_camel_case(fullName=True), e.args[0]))
	
	with open('include/linphone.hh', mode='w') as f:
		f.write(renderer.render(mainHeader))


if __name__ == '__main__':
	main()
