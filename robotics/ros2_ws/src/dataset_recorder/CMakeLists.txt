cmake_minimum_required(VERSION 3.8)
project(dataset_recorder)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rosbag2_transport REQUIRED)
find_package(rosbag2_cpp REQUIRED)
find_package(rosbag2_storage REQUIRED)
find_package(yaml-cpp REQUIRED)

add_executable(dataset_recorder_node src/dataset_recorder.cpp)

ament_target_dependencies(dataset_recorder_node
  rclcpp
  rosbag2_transport
  rosbag2_cpp
  rosbag2_storage
)

target_link_libraries(dataset_recorder_node yaml-cpp)

install(TARGETS dataset_recorder_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

ament_package()
