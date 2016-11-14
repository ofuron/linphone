#include "object.hh"
#include <bctoolbox/port.h>
#include <cstring>
#include <cstdlib>
#include <algorithm>

using namespace linphone;
using namespace std;

template <class T>
ObjectBctbxListWrapper<T>::ObjectBctbxListWrapper(const std::list<std::shared_ptr<T> > &cppList): AbstractBctbxListWrapper() {
	for(auto it=cppList.cbegin(); it!=cppList.cend(); it++) {
		void *cPtr = Object::sharedPtrToCPtr<T>(*it);
		if (cPtr != NULL) belle_sip_object_ref(cPtr);
		mCList = bctbx_list_append(mCList, cPtr);
	}
}

static void unrefData(void *data) {
	if (data != NULL) belle_sip_object_unref(data);
}

template <class T>
ObjectBctbxListWrapper<T>::~ObjectBctbxListWrapper() {
	mCList = bctbx_list_free_with_data(mCList, unrefData);
}

StringBctbxListWrapper::StringBctbxListWrapper(const std::list<std::string> &cppList): AbstractBctbxListWrapper() {
	for(auto it=cppList.cbegin(); it!=cppList.cend(); it++) {
		char *buffer = (char *)malloc(it->length()+1);
		strcpy(buffer, it->c_str());
		mCList = bctbx_list_append(mCList, buffer);
	}
}

StringBctbxListWrapper::~StringBctbxListWrapper() {
	mCList = bctbx_list_free_with_data(mCList, free);
}

Object::Object(::belle_sip_object_t *ptr, bool takeRef):
		enable_shared_from_this<Object>(), mPrivPtr(ptr) {
	if(takeRef) belle_sip_object_ref(mPrivPtr);
	belle_sip_object_data_set(ptr, "cpp_object", this, NULL);
}

Object::~Object() {
	if(mPrivPtr != NULL) belle_sip_object_unref(mPrivPtr);
	belle_sip_object_data_set(mPrivPtr, "cpp_object", NULL, NULL);
}

// template <class T>
// std::shared_ptr<T> Object::cPtrToSharedPtr(const void *ptr, bool takeRef) {
// 	if (ptr == NULL) {
// 		return nullptr;
// 	} else {
// 		T *cppPtr = (T *)belle_sip_object_data_get((::belle_sip_object_t *)ptr, "cpp_object");
// 		if (cppPtr == NULL) {
// 			return make_shared<T>(ptr, takeRef);
// 		} else {
// 			return shared_ptr<T>(cppPtr);
// 		}
// 	}
// }

// template <class T>
// void *Object::sharedPtrToCPtr(const std::shared_ptr<T> &sharedPtr) {
// 	if (sharedPtr == nullptr) return NULL;
// 	else return static_pointer_cast<Object,T>(sharedPtr)->mPrivPtr;
// }

std::string Object::cStringToCpp(const char *cstr) {
	if (cstr == NULL) {
		return std::string();
	} else {
		return std::string(cstr);
	}
}

const char *Object::cppStringToC(const std::string &cppstr) {
	if (cppstr.empty()) {
		return NULL;
	} else {
		return cppstr.c_str();
	}
}

// template <class T>
// list<shared_ptr<T> > Object::bctbxObjectListToCppList(const ::bctbx_list_t *bctbxList) {
// 	list<shared_ptr<T> > cppList;
// 	for(const ::bctbx_list_t *it=bctbxList; it!=NULL; it=it->next) {
// 		shared_ptr<T> newObj = cPtrToSharedPtr<T>((::belle_sip_object_t *)it->data);
// 		cppList.push_back(newObj);
// 	}
// 	return cppList;
// }

list<string> bctbxStringListToCppList(const ::bctbx_list_t *bctbxList) {
	list<string> cppList;
	for(const ::bctbx_list_t *it=bctbxList; it!=NULL; it=it->next) {
		cppList.push_back(string((char *)it->data));
	}
	return cppList;
}

std::list<std::string> cStringArrayToCppList(const char **cArray) {
	list<string> cppList;
	int i;
	for(i=0; cArray[i]!=NULL; i++) {
		cppList.push_back(cArray[i]);
	}
	return cppList;
}

ListenableObject::ListenableObject(::belle_sip_object_t *ptr, bool takeRef): Object(ptr, takeRef) {
	shared_ptr<Listener> *cppListener = (shared_ptr<Listener> *)belle_sip_object_data_get(mPrivPtr, "cpp_listener");
	if (cppListener == NULL) {
		cppListener = new shared_ptr<Listener>();
		belle_sip_object_data_set(mPrivPtr, "cpp_listeners", cppListener, (belle_sip_data_destroy)deleteListenerPtr);
	}
}

void ListenableObject::setListener(const std::shared_ptr<Listener> &listener) {
	shared_ptr<Listener> &curListener = *(shared_ptr<Listener> *)belle_sip_object_data_get(mPrivPtr, "cpp_listener");
	curListener = listener;
}

template <class T>
std::shared_ptr<T> ListenableObject::getListenerFromObject(::belle_sip_object_t *object) {
	std::shared_ptr<Listener> listener = *(std::shared_ptr<Listener> *)belle_sip_object_data_get(object, "cpp_listeners");
	return static_pointer_cast<T, Listener>(listener);
}

