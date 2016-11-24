#ifndef _LINPHONE_OBJECT_HH
#define _LINPHONE_OBJECT_HH

#include <memory>
#include <list>
#include <belle-sip/object.h>
#include <bctoolbox/list.h>

namespace linphone {
	
	class Object;
	class Listener;
	
	
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
	public:
		Object(::belle_sip_object_t *ptr, bool takeRef=true);
		virtual ~Object();
		
	public:
		template <class T> void setData(const std::string &key, const std::shared_ptr<T> &data) {
			std::shared_ptr<T> *newSharedPtr = new std::shared_ptr<T>(data);
			belle_sip_object_data_set(mPrivPtr, key.c_str(), newSharedPtr, deleteSharedPtr<T>);
		}
		template <class T> std::shared_ptr<T> getData(const std::string &key) const {
			void *dataPtr = belle_sip_object_data_get(mPrivPtr, key.c_str());
			if (dataPtr == NULL) return nullptr;
			else return *(std::shared_ptr<T> *)dataPtr;
		}
		void setData(const std::string &key, const std::string &data);
		const std::string &getData(const std::string &key) const;
	
	public:
		static std::shared_ptr<Object> cPtrToSharedPtr(::belle_sip_object_t *ptr, bool takeRef=true);
		static ::belle_sip_object_t *sharedPtrToCPtr(const std::shared_ptr<const Object> &sharedPtr);
		
	protected:
		static std::string cStringToCpp(const char *cstr);
		static std::string cStringToCpp(char *cstr);
		static const char *cppStringToC(const std::string &cppstr);
		
		template <class T>
		static std::list<std::shared_ptr<T> > bctbxObjectListToCppList(const ::bctbx_list_t *bctbxList) {
			std::list<std::shared_ptr<T> > cppList;
			for(const ::bctbx_list_t *it=bctbxList; it!=NULL; it=it->next) {
				std::shared_ptr<T> newObj = std::static_pointer_cast<T,Object>(Object::cPtrToSharedPtr((::belle_sip_object_t *)it->data));
				cppList.push_back(newObj);
			}
			return cppList;
		}
		
		static std::list<std::string> bctbxStringListToCppList(const ::bctbx_list_t *bctbxList);
		static std::list<std::string> cStringArrayToCppList(const char **cArray);
	
	private:
		template <class T> static void deleteSharedPtr(std::shared_ptr<T> *ptr) {if (ptr != NULL) delete ptr;}
		static void deleteString(std::string *str) {if (str != NULL) delete str;}
	
	protected:
		::belle_sip_object_t *mPrivPtr;
	};
	
	
	class Listener {
		public:
			Listener(): mCbs(NULL) {}
			virtual ~Listener() {setCallbacks(NULL);}
		
		public:
			void setCallbacks(::belle_sip_object_t *cbs) {
				if (mCbs != NULL) belle_sip_object_unref(mCbs);
				mCbs = belle_sip_object_ref(cbs);
			}
			belle_sip_object_t *getCallbacks() {return mCbs;}
		
		private:
			::belle_sip_object_t *mCbs;
	};
	
	
	class ListenableObject: public Object {
	protected:
		ListenableObject(::belle_sip_object_t *ptr, bool takeRef=true);
		void setListener(const std::shared_ptr<Listener> &listener);
	
	protected:
		static std::shared_ptr<Listener> & getListenerFromObject(::belle_sip_object_t *object);
	
	private:
		static void deleteListenerPtr(std::shared_ptr<Listener> *ptr) {delete ptr;}
	
	private:
		static std::string sListenerDataName;
	};
	
	class MultiListenableObject: public Object {
		friend class Factory;
		
	protected:
		MultiListenableObject(::belle_sip_object_t *ptr, bool takeRef=true);
		virtual ~MultiListenableObject();
		
	protected:
		void addListener(const std::shared_ptr<Listener> &listener);
		void removeListener(const std::shared_ptr<Listener> &listener);
	
	private:
		static void deleteListenerList(std::list<std::shared_ptr<Listener> > *listeners) {delete listeners;}
	
	private:
		static std::string sListenerListName;
	};
	
};

#endif // _LINPHONE_OBJECT_HH
