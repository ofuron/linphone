#ifndef _LINPHONE_OBJECT_HH
#define _LINPHONE_OBJECT_HH

#include <memory>
#include <list>
#include <belle-sip/object.h>
#include <bctoolbox/list.h>

namespace linphone {
	
	class Object;
	
	
	class AbstractBctbxListWrapper {
	public:
		AbstractBctbxListWrapper(): mCList(NULL) {}
		virtual ~AbstractBctbxListWrapper() {}
		::bctbx_list_t *c_list() {return mCList;}
		
	protected:
		::bctbx_list_t *mCList;
	};
	
	
	template <class T>
	class ObjectBctbxListWrapper: public AbstractBctbxListWrapper {
	public:
		ObjectBctbxListWrapper(const std::list<std::shared_ptr<T> > &cppList);
		virtual ~ObjectBctbxListWrapper();
	};
	
	
	class StringBctbxListWrapper: public AbstractBctbxListWrapper {
	public:
		StringBctbxListWrapper(const std::list<std::string> &cppList);
		virtual ~StringBctbxListWrapper();
	};
	
	
	class Object: public std::enable_shared_from_this<Object> {
	protected:
		Object(::belle_sip_object_t *ptr, bool takeRef=true);
		virtual ~Object();
		
	public:
		template <class T> void setData(const std::string &key, const std::shared_ptr<T> &data) {
			std::shared_ptr<T> *newSharedPtr = new std::shared_ptr<T>(data);
			belle_sip_object_data_set((::belle_sip_object_t *)mPrivPtr, key.c_str(), newSharedPtr, deleteSharedPtr<T>);
		}
		template <class T> std::shared_ptr<T> getData(const std::string &key) const {
			void *dataPtr = belle_sip_object_data_get((::belle_sip_object_t *)mPrivPtr, key.c_str());
			if (dataPtr == NULL) return nullptr;
			else return *dynamic_cast<T*>(dataPtr);
		}
	
	protected:
		template <class T>
		static std::shared_ptr<T> cPtrToSharedPtr(const void *ptr, bool takeRef=true) {
			if (ptr == NULL) {
				return nullptr;
			} else {
				T *cppPtr = (T *)belle_sip_object_data_get((::belle_sip_object_t *)ptr, "cpp_object");
				if (cppPtr == NULL) {
					return std::make_shared<T>((::belle_sip_object_t *)ptr, takeRef);
				} else {
					return std::shared_ptr<T>(cppPtr);
				}
			}
		}
		
		template <class T>
		static ::belle_sip_object_t *sharedPtrToCPtr(const std::shared_ptr<T> &sharedPtr) {
			if (sharedPtr == nullptr) return NULL;
			else return sharedPtr->mPrivPtr;
		}
		
		template <class T>
		static ::belle_sip_object_t *sharedPtrToCPtr(const std::shared_ptr<const T> &sharedPtr) {
			if (sharedPtr == nullptr) return NULL;
			else return sharedPtr->mPrivPtr;
		}
		
		static std::string cStringToCpp(const char *cstr);
		static const char *cppStringToC(const std::string &cppstr);
		
		template <class T>
		static std::list<std::shared_ptr<T> > bctbxObjectListToCppList(const ::bctbx_list_t *bctbxList) {
			std::list<std::shared_ptr<T> > cppList;
			for(const ::bctbx_list_t *it=bctbxList; it!=NULL; it=it->next) {
				std::shared_ptr<T> newObj = cPtrToSharedPtr<T>((::belle_sip_object_t *)it->data);
				cppList.push_back(newObj);
			}
			return cppList;
		}
		
		static std::list<std::string> bctbxStringListToCppList(const ::bctbx_list_t *bctbxList);
		static std::list<std::string> cStringArrayToCppList(const char **cArray);
	
	private:
		template <class T> static void deleteSharedPtr(std::shared_ptr<T> *ptr) {
			delete ptr;
		}
	
	protected:
		::belle_sip_object_t *mPrivPtr;
	};
	
	class Listener {};
	
	class ListenableObject: public Object {
	protected:
		ListenableObject(::belle_sip_object_t *ptr, bool takeRef=true);
		void setListener(const std::shared_ptr<Listener> &listener);
	
	protected:
		template <class T>
		static std::shared_ptr<T> getListenerFromObject(::belle_sip_object_t *object) {
			std::shared_ptr<Listener> listener = *(std::shared_ptr<Listener> *)belle_sip_object_data_get(object, "cpp_listeners");
			return std::static_pointer_cast<T, Listener>(listener);
		}
	
	private:
		static void deleteListenerPtr(std::shared_ptr<Listener> *ptr) {
			delete ptr;
		}
	};
	
};

#endif // _LINPHONE_OBJECT_HH
