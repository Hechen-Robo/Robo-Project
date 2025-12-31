cmake_minimum_required(VERSION 3.8)
project(cam_stream_cpp)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ROS 2
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(image_transport REQUIRED)
find_package(cv_bridge REQUIRED)

# OpenCV
find_package(OpenCV REQUIRED)

add_executable(cam_stream_cpp src/cam_stream.cpp)

ament_target_dependencies(cam_stream_cpp
  rclcpp
  sensor_msgs
  image_transport
  cv_bridge
)

target_link_libraries(cam_stream_cpp ${OpenCV_LIBS})

install(TARGETS cam_stream_cpp
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
