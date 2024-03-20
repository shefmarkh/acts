#include <boost/test/unit_test.hpp>

#include "Acts/Detector/CylindricalContainerBuilder.hpp"
#include "Acts/Detector/DetectorVolumeBuilder.hpp"
#include "Acts/Detector/interface/IExternalStructureBuilder.hpp"
#include "Acts/Geometry/CylinderVolumeBounds.hpp"

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


BOOST_AUTO_TEST_CASE(ATLASCaloBarrelTests){
    
    CylindricalContainerBuilder::Config ccConfig;

    std::vector<std::shared_ptr<DetectorVolumeBuilder> > builders = {};

    double caloRMin = 0.00;//looping over all DDE in preSamplerB in Athena shows the minimal value of r is 1452.46
    double calorRMax = 3632.00;//looping over all DDE in TileBar2, TileGap2 and Tile Ext2 in Athena shows the maximal value of r is 3630.00
    double halfLengthZ = 5809.00;//Looping over all DDE in barrel in Athena shows the half length between min and maz Z is 5805.56

    double L0RMin = 1450.00;//looping over all DDE in preSamplerB in Athena shows the minimal value of r is 1452.46

    //create a cylinder inside preSamplerB
    CylinderVolumeBounds gap0Bounds(caloRMin, L0RMin, halfLengthZ);

    auto gap0CylinderBuilder = std::make_shared<ExternalsBuilder<CylinderVolumeBounds>>(Transform3::Identity(), gap0Bounds);

    DetectorVolumeBuilder::Config gap0Cfg;
    gap0Cfg.name = "Gap0";
    gap0Cfg.externalsBuilder = gap0CylinderBuilder;
    gap0Cfg.internalsBuilder = nullptr;

    auto gap0VolumeBuilder = std::make_shared<DetectorVolumeBuilder>(
      gap0Cfg, getDefaultLogger("DetectorVolumeBuilder", Logging::VERBOSE));

    builders.push_back(gap0VolumeBuilder);

}