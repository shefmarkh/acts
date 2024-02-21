#include <boost/test/unit_test.hpp>

#include <fstream>

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

    //verify the json object was filled
    BOOST_CHECK_NE(json, nullptr);

    nlohmann::json jSurfaces = json;

     std::vector<SurfaceContainer::InputElement> surfaceElements;

    for (const auto& jSurface : jSurfaces) {
        Acts::GeometryIdentifier geoId = GeometryIdHelper::decodeIdentifier(jSurface);
        auto surface = Acts::SurfaceJsonConverter::fromJson(jSurface["value"]);
        surfaceElements.emplace_back(geoId, surface);
    }

    
}

BOOST_AUTO_TEST_SUITE_END()