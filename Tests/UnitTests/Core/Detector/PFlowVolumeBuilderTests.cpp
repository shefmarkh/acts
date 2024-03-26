#include <boost/test/unit_test.hpp>

#include "Acts/Detector/DetectorVolumeBuilder.hpp"
#include "Acts/Detector/interface/IExternalStructureBuilder.hpp"
#include "Acts/Detector/interface/IGeometryIdGenerator.hpp"
#include "Acts/Detector/interface/IInternalStructureBuilder.hpp"
#include "Acts/Geometry/CylinderVolumeBounds.hpp"
#include "Acts/Geometry/GeometryHierarchyMap.hpp"
#include "Acts/Geometry/GeometryIdentifier.hpp"
#include "Acts/Navigation/DetectorVolumeFinders.hpp"
#include "Acts/Plugins/Json/GeometryHierarchyMapJsonConverter.hpp"
#include "Acts/Plugins/Json/SurfaceJsonConverter.hpp"

using namespace Acts;
using namespace Acts::Experimental;

GeometryContext tContext;

using GeometryIdHelper = Acts::GeometryHierarchyMapJsonConverter<bool>;
using SurfaceContainer = Acts::GeometryHierarchyMap<std::shared_ptr<const Acts::Surface>>;

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

template <typename bounds_type>
class InternalVolumeBuilder : public IInternalStructureBuilder {
 public:
  InternalVolumeBuilder(const Transform3& transform, const bounds_type& bounds)
      : IInternalStructureBuilder(),
        m_transform(transform),
        m_bounds(std::move(bounds)) {}

  InternalStructure construct(
      [[maybe_unused]] const GeometryContext& gctx) const final {
    auto bounds = std::make_unique<bounds_type>(m_bounds);
    auto portalGenerator = defaultPortalGenerator();
    auto volume = DetectorVolumeFactory::construct(
        portalGenerator, tContext, "InternalVolume", m_transform,
        std::move(bounds), tryAllPortals());
    return {{}, {volume}, tryAllPortals(), tryRootVolumes()};
  }

 private:
  Transform3 m_transform = Transform3::Identity();
  bounds_type m_bounds;
};

class SurfaceGeoIdGenerator : public Acts::Experimental::IGeometryIdGenerator {
 public:
  Acts::Experimental::IGeometryIdGenerator::GeoIdCache generateCache()
      const final {
    return std::any();
  }

  void assignGeometryId(
      Acts::Experimental::IGeometryIdGenerator::GeoIdCache& /*cache*/,
      Acts::Experimental::DetectorVolume& dVolume) const final {
    for (auto [is, s] : Acts::enumerate(dVolume.surfacePtrs())) {
      Acts::GeometryIdentifier geoID;
      geoID.setPassive(is + 1);
      s->assignGeometryId(geoID);
    }
  }

  void assignGeometryId(
      Acts::Experimental::IGeometryIdGenerator::GeoIdCache& /*cache*/,
      Acts::Experimental::Portal& /*portal*/) const final {}

  void assignGeometryId(
      Acts::Experimental::IGeometryIdGenerator::GeoIdCache& /*cache*/,
      Acts::Surface& /*surface*/) const final {}

};


BOOST_AUTO_TEST_CASE(pflowVolumeTest){

  nlohmann::json json;
  std::ifstream jsonFile("PFlowSurfaces.json");
  jsonFile >> json;
  jsonFile.close();
    
  //the surface data is stored in "entries" in the json file
  auto jsonSurfaces = json["entries"];

  std::vector<SurfaceContainer::InputElement> surfaceElements;

  for (const auto& jsonSurface : jsonSurfaces) {
      Acts::GeometryIdentifier geoId = GeometryIdHelper::decodeIdentifier(jsonSurface);        
      auto surface = Acts::SurfaceJsonConverter::fromJson(jsonSurface["value"]);
      surfaceElements.emplace_back(geoId, surface);
  }

  auto surface = surfaceElements[0].second;
  double readRadius = surface->bounds().values()[0];
  double readZ = surface->bounds().values()[1];

  //make the cylinder slightly larger than our surface in the json file
  CylinderVolumeBounds cvBounds(0., readRadius+1.0, (readZ/2)+1.0);
  auto cBuilder = std::make_shared<ExternalsBuilder<CylinderVolumeBounds>>(
      surface->transform(tContext), cvBounds);

  DetectorVolumeBuilder::Config dvCfg;
  dvCfg.name = "CylinderWithVolume";
  dvCfg.externalsBuilder = cBuilder;
  dvCfg.internalsBuilder = nullptr;
  dvCfg.addInternalsToRoot = false;
  //dvCfg.geoIdGenerator = std::make_shared<SurfaceGeoIdGenerator>();

  auto dvBuilder = std::make_shared<DetectorVolumeBuilder>(
      dvCfg, getDefaultLogger("DetectorVolumeBuilder", Logging::VERBOSE));

  auto [volumes, portals, roots] = dvBuilder->construct(tContext);

  auto vector3Transformed = volumes[0]->center(tContext);
  std::cout << "transformed x,y,z are " << vector3Transformed.x() << " " << vector3Transformed.y() << " " << vector3Transformed.z() << std::endl;
  std::cout << " geo id is " << volumes[0]->geometryId().value() << std::endl;

}