// This file is part of the Acts project.
//
// Copyright (C) 2019 CERN for the benefit of the Acts project
//
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

#pragma once

#include "Acts/Propagator/EigenStepper.hpp"
#include "Acts/Propagator/Propagator.hpp"
#include "Acts/Utilities/Logger.hpp"
#include "Acts/Utilities/Result.hpp"
#include "Acts/Vertexing/HelicalTrackLinearizer.hpp"
#include "Acts/Vertexing/LinearizerConcept.hpp"
#include "Acts/Vertexing/Vertex.hpp"
#include "Acts/Vertexing/VertexingOptions.hpp"

namespace Acts {

/// @class FullBilloirVertexFitter
///
/// @brief Vertex fitter class implementing the Billoir vertex fitter
///
/// This class implements the Billoir vertex fitter from Ref. (1). It is also
/// useful to have a look at Ref. (2). The cross-covariance matrices are derived
/// in Ref. (3). Note that the Billoir vertex fitter outputs one 4D vertex
/// position and nTrack momenta at this very point.
///
/// Ref. (1):
/// Fast vertex fitting with a local parametrization of tracks.
/// Author(s) Billoir, P ; Qian, S
/// In: Nucl. Instrum. Methods Phys. Res., A 311 (1992) 139-150
/// DOI 10.1016/0168-9002(92)90859-3
///
/// Ref. (2):
/// Pattern Recognition, Tracking and Vertex Reconstruction in Particle
/// Detectors.
/// Author(s) Fruehwirth, R ; Strandli, A
///
/// Ref. (3):
/// ACTS White Paper: Cross-Covariance Matrices in the Billoir Vertex Fit
/// https://acts.readthedocs.io/en/latest/white_papers/billoir-covariances.html
/// Author(s) Russo, F
///
/// @tparam linearizer_t Track linearizer type
template <typename linearizer_t>
class FullBilloirVertexFitter {
  static_assert(LinearizerConcept<linearizer_t>,
                "Linearizer does not fulfill linearizer concept.");

 public:
  using Propagator_t = typename linearizer_t::Propagator_t;
  using Linearizer_t = linearizer_t;

  struct State {
    /// @brief The state constructor
    ///
    /// @param fieldCache The magnetic field cache
    State(MagneticFieldProvider::Cache fieldCache)
        : linearizerState(std::move(fieldCache)) {}
    /// The linearizer state
    typename Linearizer_t::State linearizerState;
  };

  struct Config {
    /// Maximum number of iterations in fitter
    int maxIterations = 5;
  };

  /// @brief Constructor for user-defined InputTrack type
  ///
  /// @param cfg Configuration object
  /// @param func Function extracting BoundTrackParameters from InputTrack
  ///             object
  /// @param logger Logging instance
  FullBilloirVertexFitter(
      const Config& cfg,
      std::function<BoundTrackParameters(const InputTrack&)> func,
      std::unique_ptr<const Logger> logger =
          getDefaultLogger("FullBilloirVertexFitter", Logging::INFO))
      : m_cfg(cfg),
        extractParameters(std::move(func)),
        m_logger(std::move(logger)) {}

  /// @brief Fit method, fitting vertex for provided tracks with constraint
  ///
  /// @param paramVector Vector of track objects to fit vertex to
  /// @param linearizer The track linearizer
  /// @param vertexingOptions Vertexing options
  /// @param state The state object
  ///
  /// @return Fitted vertex
  Result<Vertex> fit(const std::vector<InputTrack>& paramVector,
                     const linearizer_t& linearizer,
                     const VertexingOptions& vertexingOptions,
                     State& state) const;

 private:
  /// Configuration object
  Config m_cfg;

  /// @brief Function to extract track parameters,
  std::function<BoundTrackParameters(const InputTrack&)> extractParameters;

  /// Logging instance
  std::unique_ptr<const Logger> m_logger;

  /// Private access to logging instance
  const Logger& logger() const { return *m_logger; }
};

}  // namespace Acts

#include "FullBilloirVertexFitter.ipp"
