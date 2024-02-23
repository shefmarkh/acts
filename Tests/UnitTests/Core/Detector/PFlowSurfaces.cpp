#include <boost/test/unit_test.hpp>

#include <fstream>
#include <iostream>

#include "Acts/Geometry/GeometryHierarchyMap.hpp"
#include "Acts/Geometry/GeometryIdentifier.hpp"
#include "Acts/Plugins/Json/ActsJson.hpp"
#include "Acts/Plugins/Json/GeometryHierarchyMapJsonConverter.hpp"
#include "Acts/Plugins/Json/SurfaceJsonConverter.hpp"
#include "Acts/Surfaces/Surface.hpp"

//using namespace Acts::Experimental;


using GeometryIdHelper = Acts::GeometryHierarchyMapJsonConverter<bool>;
using SurfaceContainer = Acts::GeometryHierarchyMap<std::shared_ptr<const Acts::Surface>>;
using SurfaceConverter = Acts::GeometryHierarchyMapJsonConverter<std::shared_ptr<const Acts::Surface>>;

BOOST_AUTO_TEST_SUITE(Detector)

BOOST_AUTO_TEST_CASE(PFlowJsonSurfacesReader){

    nlohmann::json json;
    std::ifstream jsonFile("PFlowSurfaces.json");
    jsonFile >> json;
    jsonFile.close();

    //the json file contains two types of data - "surfaces and "entries"
    //the surface data is stored in "entries"
    auto jsonSurfaces = json["entries"];

    std::vector<SurfaceContainer::InputElement> surfaceElements;

    for (const auto& jsonSurface : jsonSurfaces) {
        Acts::GeometryIdentifier geoId = GeometryIdHelper::decodeIdentifier(jsonSurface);        
        auto surface = Acts::SurfaceJsonConverter::fromJson(jsonSurface["value"]);
        surfaceElements.emplace_back(geoId, surface);
    }

    BOOST_CHECK_EQUAL(surfaceElements.size(), 1);

    //Our test json file only has one surface in it
    Acts::GeometryIdentifier geoID = surfaceElements[0].first;
    auto surface = surfaceElements[0].second;

    //Check we read in the correct geoID from our test json file
    BOOST_CHECK_EQUAL(geoID.value(), 9160836);

    //now check the dimensions of the cylinder are correct
    double readRadius = surface->bounds().values()[0];
    double readZ = surface->bounds().values()[1];
    double readPhi = surface->bounds().values()[2];

    //these values are cut + pasted from the test json file
    double testRadius = 1456.66162109375;
    double testZ = 6288.92578125;
    double testPhi = 3.141592653589793;

    double floatingPointTolerance = 0.00001;

    //EQUAL checks for exact equality, so not suitable for floats/doubles etc
    //Instead use CLOSE, which checks for equality within some tolerance
    BOOST_CHECK_CLOSE(testRadius,readRadius,floatingPointTolerance);
    BOOST_CHECK_CLOSE(testZ,readZ,floatingPointTolerance);
    BOOST_CHECK_CLOSE(testPhi,readPhi,floatingPointTolerance);
    
}

BOOST_AUTO_TEST_SUITE_END()