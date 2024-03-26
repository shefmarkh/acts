#include <boost/test/unit_test.hpp>

#include "Acts/Detector/CylindricalContainerBuilder.hpp"
#include "Acts/Detector/DetectorVolumeBuilder.hpp"
#include "Acts/Detector/interface/IExternalStructureBuilder.hpp"
#include "Acts/Detector/LayerStructureBuilder.hpp"
#include "Acts/Geometry/CylinderVolumeBounds.hpp"
#include "Acts/Geometry/GeometryHierarchyMap.hpp"
#include "Acts/Plugins/Json/GeometryHierarchyMapJsonConverter.hpp"
#include "Acts/Plugins/Json/SurfaceJsonConverter.hpp"
#include "Acts/Surfaces/CylinderSurface.hpp"

using namespace Acts;
using namespace Acts::Experimental;

template <typename bounds_type>
class ExternalsBuilder : public IExternalStructureBuilder {
 public:
  ExternalsBuilder(const Transform3& transform, const bounds_type& bounds)
      : IExternalStructureBuilder(),
        m_transform(transform),
        m_bounds(std::move(bounds)) {}

  ExternalStructure construct(
      [[maybe_unused]] const GeometryContext& gctx) const final {
    return {m_transform, std::make_unique<bounds_type>(m_bounds),
            defaultPortalGenerator()};
  }

 private:
  Transform3 m_transform = Transform3::Identity();
  bounds_type m_bounds;
};

GeometryContext tContext;

BOOST_AUTO_TEST_CASE(ATLASCaloBarrelTests){
    
    CylindricalContainerBuilder::Config ccConfig;

    std::vector<std::shared_ptr<DetectorVolumeBuilder> > builders = {};

    double caloRMin = 0.00;//looping over all DDE in preSamplerB in Athena shows the minimal value of r is 1452.46
    double calorRMax = 3632.00;//looping over all DDE in TileBar2, TileGap2 and Tile Ext2 in Athena shows the maximal value of r is 3630.00
    double caloHalfLengthZ = 5809.00;//Looping over all DDE in barrel in Athena shows the half length between min and maz Z is 5805.56

    double preSamplerBRMin = 1450.00;//looping over all DDE in preSamplerB in Athena shows the minimal value of r is 1452.46

    //create a cylinder inside preSamplerB
    CylinderVolumeBounds gap0Bounds(caloRMin, preSamplerBRMin, caloHalfLengthZ);

    auto gap0CylinderBuilder = std::make_shared<ExternalsBuilder<CylinderVolumeBounds>>(Transform3::Identity(), gap0Bounds);

    DetectorVolumeBuilder::Config gap0Cfg;
    gap0Cfg.name = "Gap0";
    gap0Cfg.externalsBuilder = gap0CylinderBuilder;
    gap0Cfg.internalsBuilder = nullptr;

    auto gap0VolumeBuilder = std::make_shared<DetectorVolumeBuilder>(
      gap0Cfg, getDefaultLogger("DetectorVolumeBuilder", Logging::VERBOSE));

    builders.push_back(gap0VolumeBuilder);

    //PreSamplerB
    double preSamplerBRMax = 1462.00;//looping over all DDE in preSamplerB in Athena shows the maximal value of r is 1460.87
    double preSamplerBHalfLengthZ = 3146;//Looping over all DDE in preSamplerB in Athena shows the half length between min and maz Z is 3144.46
    CylinderVolumeBounds preSamplerBBounds(preSamplerBRMin, preSamplerBRMax, preSamplerBHalfLengthZ);

    auto preSamplerBCylinderBuilder = std::make_shared<ExternalsBuilder<CylinderVolumeBounds>>(Transform3::Identity(), preSamplerBBounds);

    //now read in surfaces from the json file.
    nlohmann::json json;

    std::ifstream jsonFile("CylinderSurfaces_PreSamplerB.json");
    jsonFile >> json;
    jsonFile.close();

    //the surface data is stored in "entries" in the json file
    auto jsonSurfaces = json["entries"];

    std::vector<std::shared_ptr<Acts::Surface> > surfaceVector;

    for (const auto& jsonSurface : jsonSurfaces) {
        surfaceVector.push_back(Acts::SurfaceJsonConverter::fromJson(jsonSurface["value"]));
    }

    Acts::Experimental::LayerStructureBuilder::Config lsConfig;
    lsConfig.surfacesProvider = std::make_shared<LayerStructureBuilder::SurfacesHolder>(surfaceVector);

    DetectorVolumeBuilder::Config preSamplerBCfg;
    preSamplerBCfg.name = "PreSamplerB";
    preSamplerBCfg.externalsBuilder = preSamplerBCylinderBuilder;
    preSamplerBCfg.internalsBuilder = std::make_shared<LayerStructureBuilder>(Acts::Experimental::LayerStructureBuilder(
      lsConfig, Acts::getDefaultLogger("PreSamplerBBuilder", Logging::VERBOSE)));

      auto preSamplerB_Builder = std::make_shared<DetectorVolumeBuilder>(
      preSamplerBCfg, getDefaultLogger("DetectorVolumeBuilder_preSamplerB", Logging::VERBOSE));

}