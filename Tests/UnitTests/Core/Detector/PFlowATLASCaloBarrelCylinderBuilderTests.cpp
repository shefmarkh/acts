#include <boost/test/unit_test.hpp>

#include "Acts/Detector/CylindricalContainerBuilder.hpp"
#include "Acts/Detector/DetectorBuilder.hpp"
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

void addGapVolumeBuilder(const double& rMin, const double& rMax, const double& halfLengthZ, const std::string& gapName,
std::vector<std::shared_ptr<const IDetectorComponentBuilder> >& builders){

  CylinderVolumeBounds gapBounds(rMin, rMax, halfLengthZ);

  auto gapCylinderBuilder = std::make_shared<ExternalsBuilder<CylinderVolumeBounds>>(Transform3::Identity(), gapBounds);

  DetectorVolumeBuilder::Config gapCfg;
  gapCfg.name = gapName;
  gapCfg.externalsBuilder = gapCylinderBuilder;
  gapCfg.internalsBuilder = nullptr;

  auto gapVolumeBuilder = std::make_shared<DetectorVolumeBuilder>(
    gapCfg, getDefaultLogger("DetectorVolumeBuilder", Logging::VERBOSE));

  builders.push_back(gapVolumeBuilder);

}

void addVolumeBuilder(const std::string& jsonFileName, std::vector<std::shared_ptr<const IDetectorComponentBuilder> >& builders, const double& layerRMin, const double& layerRMax, 
const double& layerHalfLengthZ, const std::string& cylinderName){

  CylinderVolumeBounds cylinderBounds(layerRMin, layerRMax, layerHalfLengthZ);
  auto externalCylinderBuilder = std::make_shared<ExternalsBuilder<CylinderVolumeBounds>>(Transform3::Identity(), cylinderBounds);

  nlohmann::json json;
  std::ifstream jsonFile(jsonFileName);
  jsonFile >> json;
  jsonFile.close();

  //the surface data is stored in "entries" in the json file
  auto jsonSurfaces = json["entries"];

  std::vector<std::shared_ptr<Acts::Surface> > surfaceVector;

  for (const auto& jsonSurface : jsonSurfaces) surfaceVector.push_back(Acts::SurfaceJsonConverter::fromJson(jsonSurface["value"]));

  Acts::Experimental::LayerStructureBuilder::Config lsConfig;
  lsConfig.surfacesProvider = std::make_shared<LayerStructureBuilder::SurfacesHolder>(surfaceVector);

  DetectorVolumeBuilder::Config volumeCfg;
  volumeCfg.name = cylinderName;
  volumeCfg.externalsBuilder = externalCylinderBuilder;
  volumeCfg.internalsBuilder = std::make_shared<LayerStructureBuilder>(Acts::Experimental::LayerStructureBuilder(
  lsConfig, Acts::getDefaultLogger(cylinderName, Logging::VERBOSE)));

  auto volumeBuilder = std::make_shared<DetectorVolumeBuilder>(volumeCfg, getDefaultLogger(cylinderName, Logging::VERBOSE));

  builders.push_back(volumeBuilder);

}

BOOST_AUTO_TEST_CASE(ATLASCaloBarrelTests){
    
    CylindricalContainerBuilder::Config ccConfig;
    ccConfig.builders = std::vector<std::shared_ptr<const IDetectorComponentBuilder> >();

    double caloRMin = 0.00;//looping over all DDE in preSamplerB in Athena shows the minimal value of r is 1452.46
    double calorRMax = 3632.00;//looping over all DDE in TileBar2, TileGap2 and Tile Ext2 in Athena shows the maximal value of r is 3630.00
    double caloHalfLengthZ = 5809.00;//Looping over all DDE in barrel in Athena shows the half length between min and maz Z is 5805.56

    double preSamplerBRMin = 1450.00;//looping over all DDE in preSamplerB in Athena shows the minimal value of r is 1452.46

    //create a cylinder inside preSamplerB
    addGapVolumeBuilder(caloRMin, preSamplerBRMin, caloHalfLengthZ,"Gap0", ccConfig.builders);

    //PreSamplerB
    double preSamplerBRMax = 1462.00;//looping over all DDE in preSamplerB in Athena shows the maximal value of r is 1460.87
    double preSamplerBHalfLengthZ = 3146;//Looping over all DDE in preSamplerB in Athena shows the half length between min and maz Z is 3144.46
    addVolumeBuilder("CylinderSurfaces_PreSamplerB.json",ccConfig.builders,preSamplerBRMin, preSamplerBRMax, preSamplerBHalfLengthZ,"preSamplerB");

    //gap between preSamplerB and EMB1. According to CaloDetDescrElements in Athena:
    //PreSamplerB: MinR and maxR in PreSamplerB are 1452.46 1460.87
    //EMB1: MinR and maxR in EMB1 are 1512.42 1547.71
    //EMB1: Half length in Z for EMB1 is 3097.51
    addGapVolumeBuilder(1462,1510,caloHalfLengthZ, "Gap1",ccConfig.builders);

    //EMB1 cylinder
    addVolumeBuilder("CylinderSurfaces_EMB1.json",ccConfig.builders,1510,1549,3099,"EMB1");

    //Gap between EMB1 and EMB2.  According to CaloDetDescrElements in Athena:
    //EMB2: MinR and maxR in EMB2 are 1656.85 1762.55
    //EMB2: Half length in Z for EMB2 is 3439.76
    addGapVolumeBuilder(1549,1654,caloHalfLengthZ,"Gap2",ccConfig.builders);

    //EMB2 cylinder
    addVolumeBuilder("CylinderSurfaces_EMB2.json",ccConfig.builders,1654,1764,3441,"EMB2");

    auto barrelCylinders = std::make_shared<CylindricalContainerBuilder>(
      ccConfig, getDefaultLogger("ATLASCaloCylindricalContainerBuilder", Logging::VERBOSE));

    Acts::Experimental::DetectorBuilder::Config dCfg;
    dCfg.auxiliary = "*** Test : auto generated ATLAS barrel calo builder  ***";
    dCfg.name = "ATLASCaloBarrelCylinderBuilder";
    dCfg.builder = barrelCylinders;

    auto detector = Acts::Experimental::DetectorBuilder(dCfg).construct(tContext);


}