#include <boost/test/unit_test.hpp>

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


BOOST_AUTO_TEST_CASE(pflowVolumeTest){
  CylinderVolumeBounds cvBounds(10, 100, 200);
  auto cBuilder = std::make_shared<ExternalsBuilder<CylinderVolumeBounds>>(
      Transform3::Identity(), cvBounds);
}