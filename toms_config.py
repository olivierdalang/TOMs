# This lists all layers TOMS expected to be present
# in the QGIS file

ALL_LAYERS = [
    "Proposals",
    "ProposalStatusTypes",
    "ActionOnProposalAcceptanceTypes",
    "RestrictionLayers",
    "RestrictionsInProposals",
    "Bays",
    "Lines",
    "Signs",
    "RestrictionPolygons",
    "ConstructionLines",
    "MapGrid",
    "CPZs",
    "ParkingTariffAreas",
    "StreetGazetteerRecords",
    "RoadCentreLine",
    "RoadCasement",
    "TilesInAcceptedProposals",
    "RestrictionTypes",
    "BayLineTypes",
    "SignTypes",
    "RestrictionPolygonTypes",
    "Lines.label_pos",
    "Lines.label_loading_pos",
]

# This lists all restriction layers.
# This list is used mainly to update the filters.
# The ID must match the RestrictionLayers table ID.
# Multiple layers can reference the same restriction in
# case the table is loaded multiple times.

RESTRICTION_LAYERS = [
    (2, 'Bays'),
    (3, 'Lines'),
    (3, 'Lines.label_pos'),
    (3, 'Lines.label_loading_pos'),
    (5, 'Signs'),
    (4, 'RestrictionPolygons'),
    (6, 'CPZs'),
    (7, 'ParkingTariffAreas'),
]
