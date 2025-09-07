cmake_minimum_required(VERSION 3.8)
project(customed_nodes)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
# uncomment the following section in order to fill in
# further dependencies manually.
# find_package(<dependency> REQUIRED)

find_package(customed_interfaces REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_components REQUIRED)
find_package(rclcpp_action REQUIRED)

# Three Ints Add Server
add_executable(add_service src/add_service.cpp)
ament_target_dependencies(add_service rclcpp customed_interfaces)
install(TARGETS
    add_service
    DESTINATION
    lib/${PROJECT_NAME})

# Three Ints Add Client
add_executable(add_client src/add_client.cpp)
ament_target_dependencies(add_client rclcpp customed_interfaces)
install(TARGETS
    add_client
    DESTINATION
    lib/${PROJECT_NAME})

# Fibonacci Action Server
add_library(fib_server SHARED src/fib_server.cpp)
target_include_directories(fib_server PRIVATE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_definitions(fib_server
  PRIVATE "CUSTOM_ACTION_CPP_BUILDING_DLL")
ament_target_dependencies(fib_server rclcpp customed_interfaces rclcpp_components rclcpp_action)
rclcpp_components_register_node(fib_server PLUGIN "customed_nodes::FibonacciActionServer" EXECUTABLE fibonacci_server)
install(TARGETS
    fib_server
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)

# Fibonacci Action Client
add_library(fib_client SHARED src/fib_client.cpp)
target_include_directories(fib_client PRIVATE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_definitions(fib_client
  PRIVATE "CUSTOM_ACTION_CPP_BUILDING_DLL")
ament_target_dependencies(fib_client rclcpp customed_interfaces rclcpp_components rclcpp_action)
rclcpp_components_register_node(fib_client PLUGIN "customed_nodes::FibonacciActionClient" EXECUTABLE fibonacci_client)
install(TARGETS
    fib_client
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
