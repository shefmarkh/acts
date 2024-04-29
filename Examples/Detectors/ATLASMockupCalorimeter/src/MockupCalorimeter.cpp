#include "ActsExamples/ATLASMockupCalorimeter/MockupCalorimeter.hpp"

#include "Acts/Detector/LayerStructureBuilder.hpp"
#include "Acts/Plugins/Json/SurfaceJsonConverter.hpp"

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
