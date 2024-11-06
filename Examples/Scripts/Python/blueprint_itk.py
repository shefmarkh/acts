#!/usr/bin/env python3

from pathlib import Path
import re
import sys

import acts
from dataclasses import dataclass

mm = acts.UnitConstants.mm
m = acts.UnitConstants.m
gm = acts.geomodel

geo_base = Path("/Users/pagessin/cernbox/sync_root/ITkGeometry")
strip_database = geo_base / "ITkStrips.db"
pixel_database = geo_base / "ITkPixels.db"

cylFace = acts.CylinderVolumeBounds.Face
bv = acts.BinningValue
bdt = acts.AxisBoundaryType


def draw(out: Path | None, surfaces, name="debug"):
    if out is None:
        return
    vis = acts.ObjVisualization3D()
    for surface in surfaces:
        surface.visualize(vis, gctx, acts.ViewConfig())

    vis.write(out / f"{name}.obj")


mat_binning = [
    (
        cylFace.OuterCylinder,
        acts.ProtoBinning(bValue=bv.binRPhi, bType=bdt.Bound, nbins=20),
        acts.ProtoBinning(bValue=bv.binZ, bType=bdt.Bound, nbins=20),
    )
]


def cluster_in_z(
    groups: list[list[acts.Surface]], window: float = 0
) -> list[acts.ProtoLayer]:
    proto_layers = [acts.ProtoLayer(gctx, sensors) for sensors in groups]

    proto_layers.sort(key=lambda c: c.min(bv.binZ))

    merged = [proto_layers[0]]

    for pl in proto_layers[1:]:
        prev = merged[-1]
        # print("Comparing:")
        # print(" - ", prev.zmin, prev.zmax)
        # print(" - ", cluster.zmin, cluster.zmax)

        if (prev.max(bv.binZ) + window) > pl.min(bv.binZ):
            # print("Overlap", cluster.zmin, prev.zmax)
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

    layers = {"PIXEL": {}, "STRIP": {}}

    for cache, hardware in zip([cachePixel, cacheStrip], ["PIXEL", "STRIP"]):
        gmSurfaces = [ss[1] for ss in cache.sensitiveSurfaces]
        gmDetElements = [ss[0] for ss in cache.sensitiveSurfaces]
        detector_elements.extend(gmDetElements)

        for surfaceIdx in range(len(gmDetElements)):
            detEl = gmDetElements[surfaceIdx]
            # print(detEl)
            # print(f"Element {detEl.databaseEntryName()}")
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

            # if hardware == "PIXEL" and barrel_endcap != 0:
            key = (barrel_endcap, layer_wheel, eta)
            # else:
            #     key = (barrel_endcap, layer_wheel)

            layers[hardware].setdefault(key, [])
            layers[hardware][key].append(detEl.surface())

    print("Done")

    # for key, surfaces in layers["STRIP"].items():
    #     print(key, len(surfaces))
    #     draw(surfaces, f"STRIP_{key}")
    #
    # for key, surfaces in layers["PIXEL"].items():
    #     print(key, len(surfaces))
    #     draw(surfaces, f"PIXEL_{key}")

    # sys.exit()

    root = acts.RootBlueprintNode(
        envelope=acts.ExtentEnvelope(r=[10 * mm, 10 * mm], z=[10 * mm, 10 * mm])
    )

    base = acts.Transform3.Identity()

    with root.CylinderContainer("ITk", bv.binR) as itk:
        itk.attachmentStrategy = acts.CylinderVolumeStack.AttachmentStrategy.Second

        with itk.Material(f"BeamPipe_Material") as mat:
            mat.binning = [
                (
                    cylFace.OuterCylinder,
                    acts.ProtoBinning(bValue=bv.binRPhi, bType=bdt.Bound, nbins=20),
                    acts.ProtoBinning(bValue=bv.binZ, bType=bdt.Bound, nbins=20),
                )
            ]
            mat.addStaticVolume(
                base, acts.CylinderVolumeBounds(0, 23 * mm, 3 * m), name="BeamPipe"
            )

        build_inner_pixel(layers["PIXEL"], out, itk)
        build_outer_pixel(layers["PIXEL"], out, itk)
        build_strip(layers["STRIP"], out, itk)

    if out is not None:
        with open(out / "itk.dot", "w") as fh:
            root.graphViz(fh)

    trackingGeometry = root.construct(
        acts.BlueprintNode.Options(), gctx, level=logLevel
    )

    return trackingGeometry, detector_elements


def build_inner_pixel(layers, out, itk: acts.BlueprintNode):
    with itk.Material("InnerPixelMaterial") as mat:
        mat.binning = mat_binning
        with mat.CylinderContainer("InnerPixel", bv.binZ) as inner_pixel:
            with inner_pixel.CylinderContainer(
                "InnerPixel_Brl", bv.binR
            ) as inner_pixel_brl:
                inner_pixel_brl.attachmentStrategy = (
                    acts.CylinderVolumeStack.AttachmentStrategy.Gap
                )
                inner_pixel_brl.resizeStrategy = (
                    acts.CylinderVolumeStack.ResizeStrategy.Gap
                )

                for i in (0, 1):
                    with inner_pixel_brl.Material(
                        f"InnerPixel_Brl_{i}_Material"
                    ) as lmat:
                        lmat.binning = [
                            (
                                (
                                    cylFace.OuterCylinder
                                    if i == 0
                                    else cylFace.InnerCylinder
                                ),
                                acts.ProtoBinning(
                                    bValue=bv.binRPhi, bType=bdt.Bound, nbins=40
                                ),
                                acts.ProtoBinning(
                                    bValue=bv.binZ, bType=bdt.Bound, nbins=20
                                ),
                            )
                        ]
                        with lmat.Layer(f"InnerPixel_Brl_{i}") as layer:

                            sensors = sum(
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

            for bec in (-2, 2):
                s = "p" if bec > 0 else "n"
                with inner_pixel.CylinderContainer(f"InnerPixel_{s}EC", bv.binZ) as ec:
                    ec.attachmentStrategy = (
                        acts.CylinderVolumeStack.AttachmentStrategy.Gap
                    )
                    ec.resizeStrategy = acts.CylinderVolumeStack.ResizeStrategy.Gap

                    groups = [
                        lay
                        for (b, ld, _), lay in layers.items()
                        if b == bec and ld in (0, 1, 2)
                    ]

                    proto_layers = cluster_in_z(groups)
                    proto_layers.sort(key=lambda c: c.min(bv.binZ))

                    if bec == -2:
                        proto_layers.reverse()

                    print("have", len(proto_layers), "proto layers")
                    # print([(cluster.zmin, cluster.zmax) for cluster in clusters])

                    for i, pl in enumerate(proto_layers):
                        draw(out, pl.surfaces, f"InnerPixel_{s}EC_{i}")

                        lwrap = ec.Material(f"InnerPixel_{s}EC_{i}_Material")
                        lwrap.binning = [
                            (
                                (
                                    cylFace.NegativeDisc
                                    if bec > 0
                                    else cylFace.PositiveDisc
                                ),
                                acts.ProtoBinning(
                                    bValue=bv.binPhi,
                                    bType=bdt.Bound,
                                    nbins=40,
                                ),
                                acts.ProtoBinning(
                                    bValue=bv.binR,
                                    bType=bdt.Bound,
                                    nbins=20,
                                ),
                            )
                        ]
                        with lwrap.Layer(name=f"InnerPixel_{s}EC_{i}") as layer:
                            layer.surfaces = pl.surfaces
                            layer.layerType = acts.LayerBlueprintNode.LayerType.Disc
                            layer.envelope = acts.ExtentEnvelope(
                                r=[2 * mm, 2 * mm], z=[2 * mm, 2 * mm]
                            )


def build_outer_pixel(layers, out, itk: acts.BlueprintNode):
    with itk.Material("OuterPixel_Material") as outer_pixel_mat:
        outer_pixel_mat.binning = mat_binning
        with outer_pixel_mat.CylinderContainer("OuterPixel", bv.binZ) as outer_pixel:
            with outer_pixel.CylinderContainer(
                "OuterPixel_Brl", bv.binR
            ) as outer_pixel_brl:
                outer_pixel_brl.attachmentStrategy = (
                    acts.CylinderVolumeStack.AttachmentStrategy.Gap
                )
                outer_pixel_brl.resizeStrategy = (
                    acts.CylinderVolumeStack.ResizeStrategy.Gap
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
                        mat.binning = [
                            (
                                cylFace.InnerCylinder,
                                acts.ProtoBinning(
                                    bValue=bv.binRPhi, bType=bdt.Bound, nbins=20
                                ),
                                acts.ProtoBinning(
                                    bValue=bv.binZ, bType=bdt.Bound, nbins=20
                                ),
                            )
                        ]
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
                ) as outer_pixel_ec_mat:
                    outer_pixel_ec_mat.binning = [
                        (
                            (cylFace.NegativeDisc if bec > 0 else cylFace.PositiveDisc),
                            acts.ProtoBinning(
                                bValue=bv.binPhi,
                                bType=bdt.Bound,
                                nbins=40,
                            ),
                            acts.ProtoBinning(
                                bValue=bv.binR,
                                bType=bdt.Bound,
                                nbins=20,
                            ),
                        )
                    ]
                    with outer_pixel_ec_mat.CylinderContainer(
                        f"OuterPixel_{s}EC", bv.binR
                    ) as ec_outer:

                        for idx, group in enumerate([(3, 4), (6, 5), (7, 8)]):
                            if idx < 2:
                                wrap = ec_outer.Material(
                                    f"OuterPixel_{s}EC_{idx}_Material"
                                )
                                wrap.binning = mat_binning
                            else:
                                wrap = ec_outer

                            with wrap.CylinderContainer(
                                f"OuterPixel_{s}EC_{idx}", bv.binZ
                            ) as ec:

                                if idx == 1:
                                    ec.attachmentStrategy = (
                                        acts.CylinderVolumeStack.AttachmentStrategy.Gap
                                    )

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
                                proto_layers.sort(key=lambda c: abs(c.min(bv.binZ)))

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

                                        lwrap.binning = [
                                            (
                                                face,
                                                acts.ProtoBinning(
                                                    bValue=bv.binPhi,
                                                    bType=bdt.Bound,
                                                    nbins=40,
                                                ),
                                                acts.ProtoBinning(
                                                    bValue=bv.binR,
                                                    bType=bdt.Bound,
                                                    nbins=20,
                                                ),
                                            )
                                        ]
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
    with itk.CylinderContainer("Strip", bv.binZ) as strip:
        with strip.CylinderContainer("Strip_Brl", bv.binR) as strip_brl:
            strip_brl.attachmentStrategy = (
                acts.CylinderVolumeStack.AttachmentStrategy.Gap
            )
            strip_brl.resizeStrategy = acts.CylinderVolumeStack.ResizeStrategy.Gap

            for i in (0, 1, 2, 3):
                lwrap = strip_brl.Material(f"Strip_Brl_{i}_Material")
                lwrap.binning = [
                    (
                        cylFace.InnerCylinder,
                        acts.ProtoBinning(bValue=bv.binRPhi, bType=bdt.Bound, nbins=40),
                        acts.ProtoBinning(bValue=bv.binZ, bType=bdt.Bound, nbins=20),
                    )
                ]

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
                        .add(acts.TryAllPortalNavigationPolicy)
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
            with strip.CylinderContainer(f"Strip_{s}EC", bv.binZ) as ec:
                ec.attachmentStrategy = acts.CylinderVolumeStack.AttachmentStrategy.Gap
                ec.resizeStrategy = acts.CylinderVolumeStack.ResizeStrategy.Gap

                for i in range(0, 5 + 1):
                    lwrap = ec.Material(f"Strip_{s}EC_{i}_Material")
                    lwrap.binning = [
                        (
                            (cylFace.NegativeDisc if bec > 0 else cylFace.PositiveDisc),
                            acts.ProtoBinning(
                                bValue=bv.binPhi,
                                bType=bdt.Bound,
                                nbins=40,
                            ),
                            acts.ProtoBinning(
                                bValue=bv.binR,
                                bType=bdt.Bound,
                                nbins=20,
                            ),
                        )
                    ]

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
                            .add(acts.TryAllPortalNavigationPolicy)
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
        gctx, out, logLevel=acts.logging.VERBOSE
    )
    vis = acts.ObjVisualization3D()
    trackingGeometry.visualize(vis, gctx, acts.ViewConfig())

    materialSurfaces = trackingGeometry.extractMaterialSurfaces()

    vis.write(out / "itk.obj")

    print("Go pseudo navigation")
    acts.pseudoNavigation(
        trackingGeometry,
        gctx,
        out / "pseudo.csv",
        runs=10000,
        etaRange=(-4.5, 4.5),
        substepsPerCm=2,
        logLevel=acts.logging.INFO,
    )
