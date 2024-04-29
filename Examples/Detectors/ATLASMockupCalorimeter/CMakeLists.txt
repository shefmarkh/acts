add_library(
  ActsExamplesATLASMockupCalorimeterDetector SHARED
  src/MockupCalorimeter.cpp)
target_include_directories(
    ActsExamplesATLASMockupCalorimeterDetector
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)
target_link_libraries(
  ActsExamplesATLASMockupCalorimeterDetector
  PUBLIC ActsCore ActsPluginJson)

install(
  TARGETS ActsExamplesATLASMockupCalorimeterDetector
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR})
