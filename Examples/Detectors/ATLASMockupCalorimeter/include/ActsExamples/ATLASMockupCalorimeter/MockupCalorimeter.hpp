// This file is part of the Acts project.
//
// Copyright (C) 2022-2023 CERN for the benefit of the Acts project
//
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

#pragma once

#include "Acts/Detector/DetectorVolumeBuilder.hpp"
#include "Acts/Detector/interface/IDetectorComponentBuilder.hpp"
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


void addGapVolumeBuilder(const double& rMin, const double& rMax, const double& halfLengthZ, const std::string& gapName,
std::vector<std::shared_ptr<const IDetectorComponentBuilder> >& builders);

void addVolumeBuilder(const std::string& jsonFileName, std::vector<std::shared_ptr<const IDetectorComponentBuilder> >& builders, const double& layerRMin, const double& layerRMax, 
const double& layerHalfLengthZ, const std::string& cylinderName);
