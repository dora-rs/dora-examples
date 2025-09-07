#ifndef CUSTOM_ACTION_CPP__VISIBILITY_CONTROL_H_
#define CUSTOM_ACTION_CPP__VISIBILITY_CONTROL_H_

#ifdef __cplusplus
extern "C"
{
#endif

// This logic was borrowed (then namespaced) from the examples on the gcc wiki:
//     https://gcc.gnu.org/wiki/Visibility

#if defined _WIN32 || defined __CYGWIN__
  #ifdef __GNUC__
    #define CUSTOM_ACTION_CPP_EXPORT __attribute__ ((dllexport))
    #define CUSTOM_ACTION_CPP_IMPORT __attribute__ ((dllimport))
  #else
    #define CUSTOM_ACTION_CPP_EXPORT __declspec(dllexport)
    #define CUSTOM_ACTION_CPP_IMPORT __declspec(dllimport)
  #endif
  #ifdef CUSTOM_ACTION_CPP_BUILDING_DLL
    #define CUSTOM_ACTION_CPP_PUBLIC CUSTOM_ACTION_CPP_EXPORT
  #else
    #define CUSTOM_ACTION_CPP_PUBLIC CUSTOM_ACTION_CPP_IMPORT
  #endif
  #define CUSTOM_ACTION_CPP_PUBLIC_TYPE CUSTOM_ACTION_CPP_PUBLIC
  #define CUSTOM_ACTION_CPP_LOCAL
#else
  #define CUSTOM_ACTION_CPP_EXPORT __attribute__ ((visibility("default")))
  #define CUSTOM_ACTION_CPP_IMPORT
  #if __GNUC__ >= 4
    #define CUSTOM_ACTION_CPP_PUBLIC __attribute__ ((visibility("default")))
    #define CUSTOM_ACTION_CPP_LOCAL  __attribute__ ((visibility("hidden")))
  #else
    #define CUSTOM_ACTION_CPP_PUBLIC
    #define CUSTOM_ACTION_CPP_LOCAL
  #endif
  #define CUSTOM_ACTION_CPP_PUBLIC_TYPE
#endif

#ifdef __cplusplus
}
#endif

#endif  // CUSTOM_ACTION_CPP__VISIBILITY_CONTROL_H_
