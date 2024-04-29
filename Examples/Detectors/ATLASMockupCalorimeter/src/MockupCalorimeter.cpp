#include "ActsExamples/ATLASMockupCalorimeter/MockupCalorimeter.hpp"

#include "Acts/Detector/CylindricalContainerBuilder.hpp"
#include "Acts/Detector/DetectorBuilder.hpp"
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

std::shared_ptr<const Detector> constructCaloMockup(){

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

    //Gap betweem EMB2 and EMB3.  According to CaloDetDescrElements in Athena:
    //EMB3: MinR and maxR in EMB3 are 1870.24 1949.76
    //EMB3: Half length in Z for EMB3 is 3277.42

    addGapVolumeBuilder(1654,1868,caloHalfLengthZ,"Gap2",ccConfig.builders);

    //EMB3
    addVolumeBuilder("CylinderSurfaces_EMB3.json",ccConfig.builders,1868,1951,3279,"EMB3");

    //Gap between EMB3 and TileBar0.  According to CaloDetDescrElements in Athena:
    //TileBar0: MinR and maxR in TileBar0 are 2450 2450
    //TileBar0: Half length in Z for TileBar0 is 2656.48
    addGapVolumeBuilder(1951,2448,caloHalfLengthZ,"Gap3",ccConfig.builders);

    //TileBar0
    addVolumeBuilder("CylinderSurfaces_TileBar0.json",ccConfig.builders,2448,2452,2658,"TileBar0");

    //Gap between TileBar0 and TileBar1.  According to CaloDetDescrElements in Athena:
    //TileBar1: MinR and maxR in TileBar1 are 2795 3020
    //TileBar1: Half length in Z for TileBar1 is 2642.79
    addGapVolumeBuilder(2452,2793,caloHalfLengthZ,"Gap4",ccConfig.builders);

    //TileBar1
    addVolumeBuilder("CylinderSurfaces_TileBar1.json",ccConfig.builders,2793,3022,2644,"TileBar1");

    //Gap between TileBar1 and TileBar2.  According to CaloDetDescrElements in Athena:
    //TileBar2: MinR and maxR in TileBar2 are 3630 3630
    //TileBar2: Half length in Z for TileBar2 is 2346.1
    addGapVolumeBuilder(3022,3628,caloHalfLengthZ,"Gap5",ccConfig.builders);

    //TileBar2
    addVolumeBuilder("CylinderSurfaces_TileBar2.json",ccConfig.builders,3628,3632,2348,"TileBar2");

    auto barrelCylinders = std::make_shared<CylindricalContainerBuilder>(
      ccConfig, getDefaultLogger("ATLASCaloCylindricalContainerBuilder", Logging::VERBOSE));

    Acts::Experimental::DetectorBuilder::Config dCfg;
    dCfg.auxiliary = "*** Test : auto generated ATLAS barrel calo builder  ***";
    dCfg.name = "ATLASCaloBarrelCylinderBuilder";
    dCfg.builder = barrelCylinders;

    return Acts::Experimental::DetectorBuilder(dCfg).construct(tContext);

}
