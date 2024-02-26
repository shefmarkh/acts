#include <boost/test/unit_test.hpp>

#include <fstream>
#include <iostream>

#include "Acts/Detector/DetectorVolume.hpp"
#include "Acts/Detector/PortalGenerators.hpp"
#include "Acts/Geometry/CylinderVolumeBounds.hpp"
#include "Acts/Geometry/GeometryHierarchyMap.hpp"
#include "Acts/Geometry/GeometryIdentifier.hpp"
#include "Acts/Navigation/SurfaceCandidatesUpdaters.hpp"
#include "Acts/Plugins/Json/ActsJson.hpp"
#include "Acts/Plugins/Json/GeometryHierarchyMapJsonConverter.hpp"
#include "Acts/Plugins/Json/SurfaceJsonConverter.hpp"
#include "Acts/Surfaces/Surface.hpp"

using namespace Acts::Experimental;

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
    std::vector<Acts::Transform3> surfaceTransforms;

    for (const auto& jsonSurface : jsonSurfaces) {
        Acts::GeometryIdentifier geoId = GeometryIdHelper::decodeIdentifier(jsonSurface);        
        auto surface = Acts::SurfaceJsonConverter::fromJson(jsonSurface["value"]);
        surfaceElements.emplace_back(geoId, surface);

        nlohmann::json jTransform = jsonSurface["translation"];
        Acts::Transform3 sTransform = Acts::Transform3JsonConverter::fromJson(jTransform);
        surfaceTransforms.push_back(sTransform);
    }

    BOOST_CHECK_EQUAL(surfaceElements.size(), 1);
    BOOST_CHECK_EQUAL(surfaceTransforms.size(),1);

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

    //Now lets build a volume

    //First create boundaries for cylinder
    //Parameters are inner radius, outer radius and half length
    //Make them slightly larger than the cylinder we have
    auto fullCylinderBounds =
      std::make_unique<Acts::CylinderVolumeBounds>(0., readRadius+1.0, (readZ/2)+1.0);

    Acts::Transform3 nominal = Acts::Transform3::Identity();
    Acts::GeometryContext tContext;
    auto portalGenerator = defaultPortalGenerator();

    auto fullCylinderVolume = DetectorVolumeFactory::construct(
      portalGenerator, tContext, "FullCylinderVolume", nominal,
      std::move(fullCylinderBounds), tryAllPortals());
    
    BOOST_CHECK(fullCylinderVolume->surfaces().empty());
    BOOST_CHECK(fullCylinderVolume->volumes().empty());
    BOOST_CHECK_EQUAL(fullCylinderVolume->portals().size(), 3u);

    auto vector3 = fullCylinderVolume->center(tContext);
    std::cout << "x,y,x are " << vector3.x() << ", " << vector3.y() << " and " << vector3.z() << std::endl;

    //Now create a cylinder shifted in Z by our transform coordinates
    Acts::Transform3 surfaceTransform = surfaceTransforms[0];
    auto translation = surfaceTransform.translation();
    std::cout << "Values are " << translation[0] << ", " << translation[1] << " and " <<
    translation[2] << std::endl;

    auto transformedCylinderBounds =
      std::make_unique<Acts::CylinderVolumeBounds>(0., readRadius+1.0, (readZ/2)+1.0);

    auto fullTransformedCylinderVolume = DetectorVolumeFactory::construct(
      portalGenerator, tContext, "FullTransformedCylinderVolume", surfaceTransform,
      std::move(transformedCylinderBounds), tryAllPortals());

    auto vector3Transformed = fullTransformedCylinderVolume->center(tContext);
    std::cout << "x,y,x are " << vector3Transformed.x() << ", " << 
    vector3Transformed.y() << " and " << vector3Transformed.z() << std::endl;

}

BOOST_AUTO_TEST_SUITE_END()