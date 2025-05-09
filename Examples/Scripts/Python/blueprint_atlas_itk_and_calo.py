#!/usr/bin/env python3

from pathlib import Path
import re
import math
from typing import cast

import acts

mm = acts.UnitConstants.mm
m = acts.UnitConstants.m
gm = acts.geomodel

geo_base = Path("/Users/markhodgkinson/run_acts_April2025")
strip_database = geo_base / "ITkStrips.db"
pixel_database = geo_base / "ITkPixels.db"

cylFace = acts.CylinderVolumeBounds.Face
aDir = acts.AxisDirection
bdt = acts.AxisBoundaryType

AttachmentStrategy = acts.VolumeAttachmentStrategy
ResizeStrategy = acts.VolumeResizeStrategy


def draw(out: Path | None, surfaces, name="debug"):
    if out is None:
        return
    vis = acts.ObjVisualization3D()
    for surface in surfaces:
        surface.visualize(vis, gctx, acts.ViewConfig())

    # vis.write(out / f"{name}.obj")


mat_binning = (
    cylFace.OuterCylinder,
    acts.DirectedProtoAxis(bValue=aDir.AxisRPhi, bType=bdt.Bound, nbins=20),
    acts.DirectedProtoAxis(bValue=aDir.AxisZ, bType=bdt.Bound, nbins=20),
)


def compare_cyl_r(a: acts.TrackingVolume, b: acts.TrackingVolume) -> bool:
    aBounds = cast(acts.CylinderVolumeBounds, a.volumeBounds)
    bBounds = cast(acts.CylinderVolumeBounds, b.volumeBounds)
    aMinR = aBounds.get(acts.CylinderVolumeBounds.eMinR)
    aMaxR = bBounds.get(acts.CylinderVolumeBounds.eMaxR)
    bMinR = bBounds.get(acts.CylinderVolumeBounds.eMinR)
    bMaxR = bBounds.get(acts.CylinderVolumeBounds.eMaxR)

    aMidR = aMinR + (aMaxR - aMinR) / 2
    bMidR = bMinR + (bMaxR - bMinR) / 2

    return aMidR < bMidR


def compare_cyl_abs_z(a: acts.TrackingVolume, b: acts.TrackingVolume) -> bool:
    return abs(a.center[2]) < abs(b.center[2])


def cluster_in_z(
    groups: list[list[acts.Surface]], window: float = 0
) -> list[acts.ProtoLayer]:
    proto_layers = [acts.ProtoLayer(gctx, sensors) for sensors in groups]

    proto_layers.sort(key=lambda c: c.min(aDir.AxisZ))

    merged = [proto_layers[0]]

    for pl in proto_layers[1:]:
        prev = merged[-1]

        if (prev.max(aDir.AxisZ) + window) > pl.min(aDir.AxisZ):
            merged[-1] = acts.ProtoLayer(gctx, prev.surfaces + pl.surfaces)

        else:
            merged.append(pl)
    print("Merged", len(proto_layers), "proto layers into", len(merged))
    return merged


def build_itk_gen3(
    gctx: acts.GeometryContext, out: Path | None = None, logLevel=acts.logging.INFO
):
    pixel_tree = gm.readFromDb(str(pixel_database))
    strip_tree = gm.readFromDb(str(strip_database))

    gmFactoryConfig = gm.GeoModelDetectorObjectFactory.Config()
    gmFactory = gm.GeoModelDetectorObjectFactory(gmFactoryConfig, logLevel)
    gmFactoryOptions = gm.GeoModelDetectorObjectFactory.Options()

    gmFactoryOptions.queries = [
        "ITkPixel",
    ]
    cachePixel = gm.GeoModelDetectorObjectFactory.Cache()
    gmFactory.construct(cachePixel, gctx, pixel_tree, gmFactoryOptions)

    gmFactoryOptions.queries = [
        "ITkStrip",
    ]
    cacheStrip = gm.GeoModelDetectorObjectFactory.Cache()
    gmFactory.construct(cacheStrip, gctx, strip_tree, gmFactoryOptions)

    pattern = {
        "PIXEL": re.compile(
            r"^barrel_endcap_(-?\d+)_eta_module_(-?\d+)_layer_wheel_(-?\d+)_phi_module_(-?\d+)_side_(0|1).*$"
        ),
        "STRIP": re.compile(
            r"^barrel_endcap_(-?\d+)_eta_module_(-?\d+)_layer_wheel_(-?\d+)_phi_module_(-?\d+)_side_(0|1)_split_(2|4).*$"
        ),
    }

    detector_elements = []

    layers: dict[str, dict[tuple[int, int, int], list[acts.Surface]]] = {
        "PIXEL": {},
        "STRIP": {},
    }

    for cache, hardware in zip([cachePixel, cacheStrip], ["PIXEL", "STRIP"]):
        gmDetElements = [ss[0] for ss in cache.sensitiveSurfaces]
        detector_elements.extend(gmDetElements)

        for surfaceIdx in range(len(gmDetElements)):
            detEl = gmDetElements[surfaceIdx]

            match = pattern[hardware].match(detEl.databaseEntryName())
            if not match:
                print(f"Could not match {detEl.databaseEntryName()}")
                continue

            barrel_endcap = int(match[1])
            layer_wheel = int(match[3])
            eta = int(match[2])
            phi_module = int(match[4])
            side = int(match[5])

            if surfaceIdx < 10:
                print(barrel_endcap, layer_wheel, eta, phi_module, side)


            key = (barrel_endcap, layer_wheel, eta)

            layers[hardware].setdefault(key, [])
            layers[hardware][key].append(detEl.surface())

    print("Done")

    root = acts.Blueprint(
        envelope=acts.ExtentEnvelope(r=[10 * mm, 10 * mm], z=[10 * mm, 10 * mm])
    )

    base = acts.Transform3.Identity()

    with root.CylinderContainer("ATLAS", aDir.AxisR) as atlas:
        atlas.attachmentStrategy = acts.VolumeAttachmentStrategy.Second
        build_beam_pipe(atlas)
        build_inner_pixel(layers["PIXEL"], out, atlas)
        build_outer_pixel(layers["PIXEL"], out, atlas)
        build_strip(layers["STRIP"], out, atlas)

        import json
        #Json was written by:
        #https://gitlab.cern.ch/atlas-particleflow-software/athena/-/blob/mhodgkin_ACTSCaloExtrapolation/Reconstruction/eflowRec/src/PFCaloSurfaceBuilderTool.cxx?ref_type=heads#L161
        CaloDimensions = json.load(open("CalorimeterDimensions.json"))    

        build_calo_EMBarrel(CaloDimensions, atlas)

    if out is not None:
        with open(out / "itk.dot", "w") as fh:
            root.graphviz(fh)

    trackingGeometry = root.construct(acts.BlueprintOptions(), gctx, level=logLevel)

    return trackingGeometry, detector_elements

def build_calo_EMBarrel(CaloDimensions, atlas: acts.BlueprintNode):
    base = acts.Transform3.Identity()
    with atlas.CylinderContainer("PreSamplerB", aDir.AxisZ) as PreSamplerB:
        PreSamplerB.addStaticVolume(
            base, acts.CylinderVolumeBounds(CaloDimensions["PreSamplerBMinR"], CaloDimensions["PreSamplerBMaxR"], CaloDimensions["PreSamplerBHalfLengthZ"]), name="PreSamplerB"
        )
    with atlas.CylinderContainer("EMB1", aDir.AxisZ) as EMB1:
        EMB1.addStaticVolume(
            base, acts.CylinderVolumeBounds(CaloDimensions["EMB1MinR"], CaloDimensions["EMB1MaxR"], CaloDimensions["EMB1HalfLengthZ"]), name="EMB1"
        )
    with atlas.CylinderContainer("EMB2", aDir.AxisZ) as EMB2:
            EMB2.addStaticVolume(
                base, acts.CylinderVolumeBounds(CaloDimensions["EMB2MinR"], CaloDimensions["EMB2MaxR"], CaloDimensions["EMB2HalfLengthZ"]), name="EMB2"
            )
    with atlas.CylinderContainer("EMB3", aDir.AxisZ) as EMB3:
            EMB3.addStaticVolume(
                base, acts.CylinderVolumeBounds(CaloDimensions["EMB3MinR"], CaloDimensions["EMB3MaxR"], CaloDimensions["EMB3HalfLengthZ"]), name="EMB3"
            )

def build_beam_pipe(itk: acts.BlueprintNode):
    base = acts.Transform3.Identity()
    with itk.Material("BeamPipe_Material") as mat:
        mat.configureFace(
            cylFace.OuterCylinder,
            acts.DirectedProtoAxis(bValue=aDir.AxisRPhi, bType=bdt.Bound, nbins=20),
            acts.DirectedProtoAxis(bValue=aDir.AxisZ, bType=bdt.Bound, nbins=20),
        )
        mat.addStaticVolume(
            # The bounds are rmin,rmax and halfLengthZ
            base, acts.CylinderVolumeBounds(0, 23 * mm, 3 * m), name="BeamPipe"
        )

def build_inner_pixel(layers, out, itk: acts.BlueprintNode):
    with itk.Material("InnerPixelMaterial") as node:
        node.configureFace(*mat_binning)
        with node.CylinderContainer("InnerPixel", direction=aDir.AxisZ) as inner_pixel:
            with inner_pixel.GeometryIdentifier() as geoId, geoId.CylinderContainer(
                "InnerPixel_Brl", aDir.AxisR
            ) as inner_pixel_brl:
                inner_pixel_brl.attachmentStrategy = AttachmentStrategy.Gap
                inner_pixel_brl.resizeStrategies = (
                    ResizeStrategy.Gap,
                    ResizeStrategy.Gap,
                )

                geoId.setAllVolumeIdsTo(5).incrementLayerIds(start=1).sortBy(
                    compare_cyl_r
                )

                for i in (0, 1):
                    with inner_pixel_brl.Material(
                        f"InnerPixel_Brl_{i}_Material"
                    ) as lmat, lmat.Layer(f"InnerPixel_Brl_{i}") as layer:
                        lmat.configureFace(
                            (
                                cylFace.OuterCylinder
                                if i == 0
                                else cylFace.InnerCylinder
                            ),
                            acts.DirectedProtoAxis(
                                bValue=aDir.AxisRPhi, bType=bdt.Bound, nbins=40
                            ),
                            acts.DirectedProtoAxis(
                                bValue=aDir.AxisZ, bType=bdt.Bound, nbins=20
                            ),
                        )

                        sensors: list[acts.Surface] = sum(
                            [
                                lay
                                for (bec, ld, _), lay in layers.items()
                                if bec == 0 and ld == i
                            ],
                            [],
                        )

                        draw(out, sensors, f"InnerPixel_Brl_{i}")
                        layer.surfaces = sensors
                        layer.envelope = acts.ExtentEnvelope(
                            r=[2 * mm, 2 * mm], z=[5 * mm, 5 * mm]
                        )

            for bec in [-2, 2]:
                s = "p" if bec > 0 else "n"
                with inner_pixel.GeometryIdentifier() as geoId, geoId.CylinderContainer(
                    f"InnerPixel_{s}EC", aDir.AxisZ
                ) as ec:
                    ec.attachmentStrategy = AttachmentStrategy.Gap
                    ec.resizeStrategies = (ResizeStrategy.Gap, ResizeStrategy.Gap)

                    geoId.setAllVolumeIdsTo(10 + int(bec / 2)).incrementLayerIds(
                        start=1
                    ).sortBy(compare_cyl_abs_z)

                    groups = [
                        lay
                        for (b, ld, _), lay in layers.items()
                        if b == bec and ld in (0, 1, 2)
                    ]

                    proto_layers = cluster_in_z(groups)
                    proto_layers.sort(key=lambda c: c.min(aDir.AxisZ))

                    if bec == -2:
                        proto_layers.reverse()

                    print("have", len(proto_layers), "proto layers")

                    for i, pl in enumerate(proto_layers):
                        draw(out, pl.surfaces, f"InnerPixel_{s}EC_{i}")

                        lwrap = ec.Material(f"InnerPixel_{s}EC_{i}_Material")
                        lwrap.configureFace(
                            (cylFace.NegativeDisc if bec > 0 else cylFace.PositiveDisc),
                            acts.DirectedProtoAxis(
                                bValue=aDir.AxisR,
                                bType=bdt.Bound,
                                nbins=20,
                            ),
                            acts.DirectedProtoAxis(
                                bValue=aDir.AxisPhi,
                                bType=bdt.Bound,
                                nbins=40,
                            ),
                        )

                        with lwrap.Layer(name=f"InnerPixel_{s}EC_{i}") as layer:
                            layer.surfaces = pl.surfaces
                            layer.layerType = acts.LayerBlueprintNode.LayerType.Disc
                            layer.envelope = acts.ExtentEnvelope(
                                r=[2 * mm, 2 * mm], z=[2 * mm, 2 * mm]
                            )


def build_outer_pixel(layers, out, itk: acts.BlueprintNode):
    with itk.Material("OuterPixel_Material") as outer_pixel_mat:
        outer_pixel_mat.configureFace(*mat_binning)
        with outer_pixel_mat.CylinderContainer("OuterPixel", aDir.AxisZ) as outer_pixel:
            with outer_pixel.GeometryIdentifier() as geoId, geoId.CylinderContainer(
                "OuterPixel_Brl", aDir.AxisR
            ) as outer_pixel_brl:
                outer_pixel_brl.attachmentStrategy = AttachmentStrategy.Gap
                outer_pixel_brl.resizeStrategies = (
                    ResizeStrategy.Gap,
                    ResizeStrategy.Gap,
                )

                geoId.setAllVolumeIdsTo(20).incrementLayerIds(start=1).sortBy(
                    compare_cyl_r
                )

                for i in (2, 3, 4):
                    sensors = sum(
                        [
                            lay
                            for (bec, ld, _), lay in layers.items()
                            if bec == 0 and ld == i
                        ],
                        [],
                    )

                    draw(out, sensors, f"OuterPixel_Brl_{i}")

                    with outer_pixel_brl.Material(
                        f"OuterPixel_Brl_{i}_Material"
                    ) as mat:
                        mat.configureFace(
                            cylFace.InnerCylinder,
                            acts.DirectedProtoAxis(
                                bValue=aDir.AxisRPhi, bType=bdt.Bound, nbins=20
                            ),
                            acts.DirectedProtoAxis(
                                bValue=aDir.AxisZ, bType=bdt.Bound, nbins=20
                            ),
                        )
                        with mat.Layer(f"OuterPixel_Brl_{i}") as layer:
                            layer.surfaces = sensors
                            layer.envelope = acts.ExtentEnvelope(
                                r=[2 * mm, 2 * mm], z=[5 * mm, 5 * mm]
                            )

            for bec in (-2, 2):
                s = "p" if bec > 0 else "n"
                # R stacked Z rings
                with outer_pixel.Material(
                    f"OuterPixel_{s}EC_Material"
                ) as outer_pixel_ec_mat, outer_pixel_ec_mat.CylinderContainer(
                    f"OuterPixel_{s}EC", aDir.AxisR
                ) as ec_outer:

                    outer_pixel_ec_mat.configureFace(
                        (cylFace.NegativeDisc if bec > 0 else cylFace.PositiveDisc),
                        acts.DirectedProtoAxis(
                            bValue=aDir.AxisR,
                            bType=bdt.Bound,
                            nbins=20,
                        ),
                        acts.DirectedProtoAxis(
                            bValue=aDir.AxisPhi,
                            bType=bdt.Bound,
                            nbins=40,
                        ),
                    )

                    for idx, group in enumerate([(3, 4), (6, 5), (7, 8)]):
                        if idx < 2:
                            wrap = ec_outer.Material(f"OuterPixel_{s}EC_{idx}_Material")
                            wrap.configureFace(*mat_binning)
                        else:
                            wrap = ec_outer

                        with wrap.GeometryIdentifier() as geoId, geoId.CylinderContainer(
                            f"OuterPixel_{s}EC_{idx}", aDir.AxisZ
                        ) as ec:

                            geoId.setAllVolumeIdsTo(
                                40 + (int(bec / 2) * (idx + 1))
                            ).incrementLayerIds(start=1).sortBy(compare_cyl_abs_z)

                            if idx == 1:
                                ec.attachmentStrategy = AttachmentStrategy.Gap

                            eta_rings = {}

                            for (b, ld, eta), lay in layers.items():
                                if b != bec or ld not in group:
                                    continue
                                eta_rings.setdefault((ld, eta), []).extend(lay)

                            print("have", len(eta_rings), "eta rings")

                            proto_layers = [
                                acts.ProtoLayer(gctx, sensors)
                                for sensors in eta_rings.values()
                            ]
                            proto_layers.sort(key=lambda c: abs(c.min(aDir.AxisZ)))

                            for i, pl in enumerate(proto_layers):
                                draw(
                                    out,
                                    pl.surfaces,
                                    f"OuterPixel_{s}EC_{idx}_{i}",
                                )

                                # if i < len(proto_layers) - 1:
                                if i > 0:
                                    lwrap = ec.Material(
                                        f"OuterPixel_{s}EC_{idx}_{i}_Material"
                                    )

                                    if bec < 0:
                                        face = cylFace.PositiveDisc
                                    else:
                                        face = cylFace.NegativeDisc

                                    lwrap.configureFace(
                                        face,
                                        acts.DirectedProtoAxis(
                                            bValue=aDir.AxisR,
                                            bType=bdt.Bound,
                                            nbins=20,
                                        ),
                                        acts.DirectedProtoAxis(
                                            bValue=aDir.AxisPhi,
                                            bType=bdt.Bound,
                                            nbins=40,
                                        ),
                                    )

                                else:
                                    lwrap = ec

                                with lwrap.Layer(
                                    name=f"OuterPixel_{s}EC_{idx}_{i}"
                                ) as layer:
                                    layer.surfaces = pl.surfaces
                                    layer.layerType = (
                                        acts.LayerBlueprintNode.LayerType.Disc
                                    )
                                    layer.envelope = acts.ExtentEnvelope(
                                        r=[2 * mm, 2 * mm],
                                        z=[0.1 * mm, 0.1 * mm],
                                    )


def build_strip(layers, out, itk: acts.BlueprintNode):
    with itk.CylinderContainer("Strip", aDir.AxisZ) as strip:
        with strip.GeometryIdentifier() as geoId, geoId.CylinderContainer(
            "Strip_Brl", aDir.AxisR
        ) as strip_brl:

            strip_brl.attachmentStrategy = AttachmentStrategy.Gap
            strip_brl.resizeStrategies = (ResizeStrategy.Gap, ResizeStrategy.Gap)

            geoId.setAllVolumeIdsTo(70).incrementLayerIds(start=1).sortBy(compare_cyl_r)

            for i in (0, 1, 2, 3):
                lwrap = strip_brl.Material(f"Strip_Brl_{i}_Material")
                lwrap.configureFace(
                    cylFace.InnerCylinder,
                    acts.DirectedProtoAxis(
                        bValue=aDir.AxisRPhi, bType=bdt.Bound, nbins=40
                    ),
                    acts.DirectedProtoAxis(
                        bValue=aDir.AxisZ, bType=bdt.Bound, nbins=20
                    ),
                )

                with lwrap.Layer(f"Strip_Brl_{i}") as layer:

                    sensors = sum(
                        [
                            lay
                            for (bec, ld, _), lay in layers.items()
                            if bec == 0 and ld == i
                        ],
                        [],
                    )

                    layer.navigationPolicyFactory = (
                        acts.NavigationPolicyFactory.make()
                        .add(
                            acts.TryAllNavigationPolicy,
                            acts.TryAllNavigationPolicy.Config(sensitives=False),
                        )
                        .add(
                            acts.SurfaceArrayNavigationPolicy,
                            acts.SurfaceArrayNavigationPolicy.Config(
                                layerType=acts.SurfaceArrayNavigationPolicy.LayerType.Cylinder,
                                bins=(30, 10),
                            ),
                        )
                    )

                    draw(out, sensors, f"Strip_Brl_{i}")
                    layer.surfaces = sensors
                    layer.envelope = acts.ExtentEnvelope(
                        r=[2 * mm, 2 * mm], z=[5 * mm, 5 * mm]
                    )

        for bec in (-2, 2):
            s = "p" if bec > 0 else "n"
            with strip.GeometryIdentifier() as geoId, geoId.CylinderContainer(
                f"Strip_{s}EC", aDir.AxisZ
            ) as ec:

                geoId.setAllVolumeIdsTo(80 + int(bec / 2)).incrementLayerIds(
                    start=1
                ).sortBy(compare_cyl_abs_z)

                ec.attachmentStrategy = AttachmentStrategy.Gap
                ec.resizeStrategies = (ResizeStrategy.Gap, ResizeStrategy.Gap)

                for i in range(0, 5 + 1):
                    lwrap = ec.Material(f"Strip_{s}EC_{i}_Material")
                    lwrap.configureFace(
                        (cylFace.NegativeDisc if bec > 0 else cylFace.PositiveDisc),
                        acts.DirectedProtoAxis(
                            bValue=aDir.AxisR,
                            bType=bdt.Bound,
                            nbins=20,
                        ),
                        acts.DirectedProtoAxis(
                            bValue=aDir.AxisPhi,
                            bType=bdt.Bound,
                            nbins=40,
                        ),
                    )

                    with lwrap.Layer(f"Strip_{s}EC_{i}") as layer:

                        sensors = sum(
                            [
                                lay
                                for (b, ld, _), lay in layers.items()
                                if b == bec and ld == i
                            ],
                            [],
                        )

                        layer.navigationPolicyFactory = (
                            acts.NavigationPolicyFactory.make()
                            .add(
                                acts.TryAllNavigationPolicy,
                                acts.TryAllNavigationPolicy.Config(sensitives=False),
                            )
                            .add(
                                acts.SurfaceArrayNavigationPolicy,
                                acts.SurfaceArrayNavigationPolicy.Config(
                                    layerType=acts.SurfaceArrayNavigationPolicy.LayerType.Disc,
                                    bins=(1, 8),
                                ),
                            )
                        )

                        draw(out, sensors, f"Strip_{s}EC_{i}")
                        layer.surfaces = sensors
                        layer.envelope = acts.ExtentEnvelope(
                            r=[2 * mm, 2 * mm], z=[5 * mm, 5 * mm]
                        )


if __name__ == "__main__":
    out = Path("obj_itk")
    out.mkdir(exist_ok=True)

    gctx = acts.GeometryContext()
    trackingGeometry, detector_elements = build_itk_gen3(
        gctx, out, logLevel=acts.logging.DEBUG
    )
    vis = acts.ObjVisualization3D()
    trackingGeometry.visualize(
        vis,
        gctx,
        viewConfig=acts.ViewConfig(visible=False),
        portalViewConfig=acts.ViewConfig(visible=False),
        sensitiveViewConfig=acts.ViewConfig(visible=True),
    )

    materialSurfaces = trackingGeometry.extractMaterialSurfaces()

    vis.write(out / "itk.obj")

    print("Drawing svg")
    objects_xy = {}
    objects_zr = {}
    portals = []

    class Visitor(acts.TrackingGeometryMutableVisitor):
        def visitSurface(self, surface: acts.Surface):
            gid = surface.geometryId
            if gid.sensitive == 0:
                return
            proto_surface = acts.svg.convertSurface(
                gctx, surface, acts.svg.SurfaceOptions()
            )
            object_xy = acts.svg.viewSurface(proto_surface, "identification", "xy")
            object_rz = acts.svg.viewSurface(proto_surface, "identification", "zr")
            # key = (gid.volume, gid.layer)
            key = gid.volume
            objects_xy.setdefault(key, [])
            objects_xy[key].append(object_xy)
            objects_zr.setdefault(key, [])
            objects_zr[key].append(object_rz)

        def visitPortal(self, portal: acts.Portal):
            portal_surface = portal.surface
            gid = portal_surface.geometryId
            proto_portal = acts.svg.convertSurface(
                gctx, portal_surface, acts.svg.SurfaceOptions()
            )
            portals.append(proto_portal)

    zrRange = acts.Extent(acts.ExtentEnvelope(phi=[-0.1, 0.1]))
    acts.svg.drawTrackingGeometry(gctx, trackingGeometry, "zr")
