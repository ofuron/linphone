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
		
		const ::bctbx_list_t *c_list() const {return mCList;}
		
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
	
	protected:
		template <class T> static std::shared_ptr<T> cPtrToSharedPtr(const void *ptr, bool takeRef=true);
		template <class T> static void *sharedPtrToCPtr(const std::shared_ptr<T> &sharedPtr);
		
		template <class T> static std::list<std::shared_ptr<T> > bctbxObjectListToCppList(const ::bctbx_list_t *bctbxList);
// 		template <class T> static ::bctbx_list_t *cppObjectListToBctbxList(const std::list<std::shared_ptr<T> > &cppList);
		
		static std::list<std::string> bctbxStringListToCppList(const ::bctbx_list_t *bctbxList);
// 		static ::bctbx_list_t *cppStringListToBctbxList(const std::list<std::string> &cppList);
	
	protected:
		::belle_sip_object_t *mPrivPtr;
	};
	
};

#endif // _LINPHONE_OBJECT_HH
