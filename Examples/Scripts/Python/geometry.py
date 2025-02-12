#!/usr/bin/env python3

import os
import json

import acts
from acts import MaterialMapJsonConverter
from acts.examples.odd import getOpenDataDetector
from acts.examples import (
    WhiteBoard,
    AlgorithmContext,
    ProcessCode,
    CsvTrackingGeometryWriter,
    ObjTrackingGeometryWriter,
    JsonSurfacesWriter,
    JsonMaterialWriter,
    JsonFormat,
    GenericDetector,
)


def runGeometry(
    trackingGeometry,
    decorators,
    outputDir,
    events=1,
    outputObj=True,
    outputCsv=True,
    outputJson=True,
):
    for ievt in range(events):
        eventStore = WhiteBoard(name=f"EventStore#{ievt}", level=acts.logging.INFO)
        ialg = 0

        context = AlgorithmContext(ialg, ievt, eventStore)

        for cdr in decorators:
            r = cdr.decorate(context)
            if r != ProcessCode.SUCCESS:
                raise RuntimeError("Failed to decorate event context")

        if outputCsv:
            # if not os.path.isdir(outputDir + "/csv"):
            #    os.makedirs(outputDir + "/csv")
            writer = CsvTrackingGeometryWriter(
                level=acts.logging.INFO,
                trackingGeometry=trackingGeometry,
                outputDir=os.path.join(outputDir, "csv"),
                writePerEvent=True,
            )
            writer.write(context)

        if outputObj:
            writer = ObjTrackingGeometryWriter(
                level=acts.logging.INFO, outputDir=os.path.join(outputDir, "obj")
            )
            writer.write(context, trackingGeometry)

        if outputJson:
            # if not os.path.isdir(outputDir + "/json"):
            #    os.makedirs(outputDir + "/json")
            writer = JsonSurfacesWriter(
                level=acts.logging.INFO,
                trackingGeometry=trackingGeometry,
                outputDir=os.path.join(outputDir, "json"),
                writePerEvent=True,
                writeSensitive=True,
            )
            writer.write(context)

            jmConverterCfg = MaterialMapJsonConverter.Config(
                processSensitives=True,
                processApproaches=True,
                processRepresenting=True,
                processBoundaries=True,
                processVolumes=True,
                processNonMaterial=True,
                context=context.geoContext,
            )

            jmw = JsonMaterialWriter(
                level=acts.logging.VERBOSE,
                converterCfg=jmConverterCfg,
                fileName=os.path.join(outputDir, "geometry-map"),
                writeFormat=JsonFormat.Json,
            )

            jmw.write(trackingGeometry)


class Visitor(acts.TrackingGeometryMutableVisitor):
    def __init__(self):
        super().__init__()

        self.num_surfaces = 0
        self.string = ""

    def visitSurface(self, surface: acts.Surface):
        # print(surface.geometryId)
        self.string += f"{surface.geometryId}\n"
        self.num_surfaces += 1
        # surface.mutable()

    def visitLayer(self, layer: acts.Layer):
        # print(layer)
        pass

    def visitVolume(self, volume: acts.Volume):
        # print(volume, volume.address)
        pass

    def visitPortal(self, portal: acts.Portal):
        # print(portal)
        pass


if "__main__" == __name__:
    # detector = AlignedDetector()
    detector = GenericDetector()
    # detector = getOpenDataDetector()
    trackingGeometry = detector.trackingGeometry()
    decorators = detector.contextDecorators()

    act = ""
    visitor = Visitor()
    before = visitor.num_surfaces
    trackingGeometry.apply(visitor)

    act += visitor.string
    act += f"BEFORE {before}\n"
    act += f"AFTER {visitor.num_surfaces}\n"
    act += "done"

    from pathlib import Path
    import difflib
    import sys

    # print(act)
    # sys.exit()

    # exp = (Path.cwd() / "original.txt").read_text()

    # if act == exp:
    #     print("ALL GOOD")
    # else:
    #     print("BAD")
    #     exp = exp.splitlines(keepends=True)
    #     act = act.splitlines(keepends=True)
    #     exp = exp[:50]
    #     act = act[:50]
    #     sys.stdout.writelines(difflib.unified_diff(exp, act))

    #
    # runGeometry(trackingGeometry, decorators, outputDir=os.getcwd())

    # Uncomment if you want to create the geometry id mapping for DD4hep
    # dd4hepIdGeoIdMap = acts.examples.dd4hep.createDD4hepIdGeoIdMap(trackingGeometry)
    # dd4hepIdGeoIdValueMap = {}
    # for key, value in dd4hepIdGeoIdMap.items():
    #     dd4hepIdGeoIdValueMap[key] = value.value()

    # with open('odd-dd4hep-geoid-mapping.json', 'w') as outfile:
    #    json.dump(dd4hepIdGeoIdValueMap, outfile)
