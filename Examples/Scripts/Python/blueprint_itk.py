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

pixel_tree = gm.readFromDb(str(pixel_database))
strip_tree = gm.readFromDb(str(strip_database))

logLevel = acts.logging.INFO
gctx = acts.GeometryContext()

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

layers = {"PIXEL": {}, "STRIP": {}}

for cache, hardware in zip([cachePixel, cacheStrip], ["PIXEL", "STRIP"]):
    gmSurfaces = [ss[1] for ss in cache.sensitiveSurfaces]
    gmDetElements = [ss[0] for ss in cache.sensitiveSurfaces]

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

out = Path("obj_itk")
out.mkdir(exist_ok=True)


def draw(surfaces, name="debug"):
    vis = acts.ObjVisualization3D()
    for surface in surfaces:
        surface.visualize(vis, gctx, acts.ViewConfig())

    vis.write(out / f"{name}.obj")


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


def cluster_in_z(
    groups: list[list[acts.Surface]], window: float = 0
) -> list[acts.ProtoLayer]:
    proto_layers = [acts.ProtoLayer(gctx, sensors) for sensors in groups]

    proto_layers.sort(key=lambda c: c.min(acts.BinningValue.binZ))

    merged = [proto_layers[0]]

    for pl in proto_layers[1:]:
        prev = merged[-1]
        # print("Comparing:")
        # print(" - ", prev.zmin, prev.zmax)
        # print(" - ", cluster.zmin, cluster.zmax)

        if (prev.max(acts.BinningValue.binZ) + window) > pl.min(acts.BinningValue.binZ):
            # print("Overlap", cluster.zmin, prev.zmax)
            merged[-1] = acts.ProtoLayer(gctx, prev.surfaces + pl.surfaces)

        else:
            merged.append(pl)
    print("Merged", len(proto_layers), "proto layers into", len(merged))
    return merged


with root.CylinderContainer("ITk", acts.BinningValue.binR) as itk:
    itk.addStaticVolume(
        base, acts.CylinderVolumeBounds(0, 23 * mm, 3 * m), name="BeamPipe"
    )

    with itk.CylinderContainer("InnerPixel", acts.BinningValue.binZ) as inner_pixel:
        with inner_pixel.CylinderContainer(
            "InnerPixel_Brl", acts.BinningValue.binR
        ) as inner_pixel_brl:
            inner_pixel_brl.attachmentStrategy = (
                acts.CylinderVolumeStack.AttachmentStrategy.Gap
            )
            inner_pixel_brl.resizeStrategy = acts.CylinderVolumeStack.ResizeStrategy.Gap

            for i in (0, 1):
                with inner_pixel_brl.Layer(f"InnerPixel_Brl_{i}") as layer:

                    sensors = sum(
                        [
                            lay
                            for (bec, ld, _), lay in layers["PIXEL"].items()
                            if bec == 0 and ld == i
                        ],
                        [],
                    )

                    draw(sensors, f"InnerPixel_Brl_{i}")
                    layer.surfaces = sensors
                    layer.envelope = acts.ExtentEnvelope(
                        r=[2 * mm, 2 * mm], z=[5 * mm, 5 * mm]
                    )

        for bec in (-2, 2):
            s = "p" if bec > 0 else "n"
            with inner_pixel.CylinderContainer(
                f"InnerPixel_{s}EC", acts.BinningValue.binZ
            ) as ec:
                ec.attachmentStrategy = acts.CylinderVolumeStack.AttachmentStrategy.Gap
                ec.resizeStrategy = acts.CylinderVolumeStack.ResizeStrategy.Gap

                groups = [
                    lay
                    for (b, ld, _), lay in layers["PIXEL"].items()
                    if b == bec and ld in (0, 1, 2)
                ]

                proto_layers = cluster_in_z(groups)
                proto_layers.sort(key=lambda c: c.min(acts.BinningValue.binZ))

                if bec == -2:
                    proto_layers.reverse()

                print("have", len(proto_layers), "proto layers")
                # print([(cluster.zmin, cluster.zmax) for cluster in clusters])

                for i, pl in enumerate(proto_layers):
                    draw(pl.surfaces, f"InnerPixel_{s}EC_{i}")
                    with ec.Layer(name=f"InnerPixel_{s}EC_{i}") as layer:
                        layer.surfaces = pl.surfaces
                        layer.layerType = acts.LayerBlueprintNode.LayerType.Disc
                        layer.envelope = acts.ExtentEnvelope(
                            r=[2 * mm, 2 * mm], z=[2 * mm, 2 * mm]
                        )

    with itk.CylinderContainer("OuterPixel", acts.BinningValue.binZ) as outer_pixel:
        with outer_pixel.CylinderContainer(
            "OuterPixel_Brl", acts.BinningValue.binR
        ) as outer_pixel_brl:
            outer_pixel_brl.attachmentStrategy = (
                acts.CylinderVolumeStack.AttachmentStrategy.Gap
            )
            outer_pixel_brl.resizeStrategy = acts.CylinderVolumeStack.ResizeStrategy.Gap

            for i in (2, 3, 4):
                sensors = sum(
                    [
                        lay
                        for (bec, ld, _), lay in layers["PIXEL"].items()
                        if bec == 0 and ld == i
                    ],
                    [],
                )

                draw(sensors, f"OuterPixel_Brl_{i}")

                with outer_pixel_brl.Layer(f"OuterPixel_Brl_{i}") as layer:
                    layer.surfaces = sensors
                    layer.envelope = acts.ExtentEnvelope(
                        r=[2 * mm, 2 * mm], z=[5 * mm, 5 * mm]
                    )

        for bec in (-2, 2):
            s = "p" if bec > 0 else "n"
            # Z grouped rings
            # with outer_pixel.CylinderContainer(
            #     f"OuterPixel_{s}EC", acts.BinningValue.binZ
            # ) as ec:
            #     ec.attachmentStrategy = acts.CylinderVolumeStack.AttachmentStrategy.Gap
            #     ec.resizeStrategy = acts.CylinderVolumeStack.ResizeStrategy.Gap
            #
            #     groups = [
            #         lay
            #         for (b, ld, _), lay in layers["PIXEL"].items()
            #         if b == bec and ld in range(3, 8 + 1)
            #     ]
            #
            #     proto_layers = cluster_in_z(groups, window=1 * mm)
            #     proto_layers.sort(key=lambda c: c.min(acts.BinningValue.binZ))
            #
            #     if bec == -2:
            #         proto_layers.reverse()
            #
            #     print("have", len(proto_layers), "proto layers")
            #
            #     for i, pl in enumerate(proto_layers):
            #         draw(pl.surfaces, f"OuterPixel_{s}EC_{i}")
            #         with ec.Layer(name=f"OuterPixel_{s}EC_{i}") as layer:
            #             layer.surfaces = pl.surfaces
            #             layer.layerType = acts.LayerBlueprintNode.LayerType.Disc
            #             layer.envelope = acts.ExtentEnvelope(
            #                 r=[2 * mm, 2 * mm], z=[0.1 * mm, 0.1 * mm]
            #             )
            #
            # R stacked Z rings
            with outer_pixel.CylinderContainer(
                f"OuterPixel_{s}EC", acts.BinningValue.binR
            ) as ec_outer:

                for idx, group in enumerate([(3, 4), (6, 5), (7, 8)]):
                    with ec_outer.CylinderContainer(
                        f"OuterPixel_{s}EC_{idx}", acts.BinningValue.binZ
                    ) as ec:

                        eta_rings = {}

                        for (b, ld, eta), lay in layers["PIXEL"].items():
                            if b != bec or ld not in group:
                                continue
                            eta_rings.setdefault((ld, eta), []).extend(lay)

                        print("have", len(eta_rings), "eta rings")

                        proto_layers = [
                            acts.ProtoLayer(gctx, sensors)
                            for sensors in eta_rings.values()
                        ]
                        proto_layers.sort(key=lambda c: c.min(acts.BinningValue.binZ))

                        for i, pl in enumerate(proto_layers):
                            draw(pl.surfaces, f"OuterPixel_{s}EC_{idx}_{i}")
                            with ec.Layer(name=f"OuterPixel_{s}EC_{idx}_{i}") as layer:
                                layer.surfaces = pl.surfaces
                                layer.layerType = acts.LayerBlueprintNode.LayerType.Disc
                                layer.envelope = acts.ExtentEnvelope(
                                    r=[2 * mm, 2 * mm], z=[0.1 * mm, 0.1 * mm]
                                )

    with itk.CylinderContainer("Strip", acts.BinningValue.binZ) as strip:
        with strip.CylinderContainer("Strip_Brl", acts.BinningValue.binR) as strip_brl:
            strip_brl.attachmentStrategy = (
                acts.CylinderVolumeStack.AttachmentStrategy.Gap
            )
            strip_brl.resizeStrategy = acts.CylinderVolumeStack.ResizeStrategy.Gap

            for i in (0, 1, 2, 3):
                with strip_brl.Layer(f"Strip_Brl_{i}") as layer:

                    sensors = sum(
                        [
                            lay
                            for (bec, ld, _), lay in layers["STRIP"].items()
                            if bec == 0 and ld == i
                        ],
                        [],
                    )

                    draw(sensors, f"Strip_Brl_{i}")
                    layer.surfaces = sensors
                    layer.envelope = acts.ExtentEnvelope(
                        r=[2 * mm, 2 * mm], z=[5 * mm, 5 * mm]
                    )

        for bec in (-2, 2):
            s = "p" if bec > 0 else "n"
            with strip.CylinderContainer(f"Strip_{s}EC", acts.BinningValue.binZ) as ec:
                ec.attachmentStrategy = acts.CylinderVolumeStack.AttachmentStrategy.Gap
                ec.resizeStrategy = acts.CylinderVolumeStack.ResizeStrategy.Gap

                for i in range(0, 5 + 1):
                    with ec.Layer(f"Strip_{s}EC_{i}") as layer:

                        sensors = sum(
                            [
                                lay
                                for (b, ld, _), lay in layers["STRIP"].items()
                                if b == bec and ld == i
                            ],
                            [],
                        )

                        draw(sensors, f"Strip_{s}EC_{i}")
                        layer.surfaces = sensors
                        layer.envelope = acts.ExtentEnvelope(
                            r=[2 * mm, 2 * mm], z=[5 * mm, 5 * mm]
                        )


with open("itk.dot", "w") as fh:
    root.graphViz(fh)


trackingGeometry = root.construct(
    acts.BlueprintNode.Options(), gctx, level=acts.logging.VERBOSE
)

vis = acts.ObjVisualization3D()
trackingGeometry.visualize(vis, gctx, acts.ViewConfig())

vis.write(out / "itk.obj")


print("Go pseudo navigation")
acts.pseudoNavigation(
    trackingGeometry,
    gctx,
    out / "pseudo.csv",
    runs=5000,
    etaRange=(-4.5, 4.5),
    substepsPerCm=2,
    logLevel=acts.logging.INFO,
)
