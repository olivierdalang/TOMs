/*"""*/
/* DATAMODEL diff to enable multiple labels per sheet */

-- Enable python
-- if this fails, try
-- (ubuntu) sudo apt-get install postgresql-plpython3-9.6
-- (others) see http://blog.rubypdf.com/2019/06/29/how-to-enable-plpython3u-extension-on-postgre-app/
CREATE EXTENSION IF NOT EXISTS plpython3u;

-- Add label position and leader fields
ALTER TABLE public."Lines" ADD COLUMN "label_pos" public.geometry(MultiPoint, 27700);
ALTER TABLE public."Lines" ADD COLUMN "label_loading_pos" public.geometry(MultiPoint, 27700);
ALTER TABLE public."RestrictionPolygons" ADD COLUMN "label_pos" public.geometry(MultiPoint, 27700);
ALTER TABLE public."Bays" ADD COLUMN "label_pos" public.geometry(MultiPoint, 27700);
ALTER TABLE public."ParkingTariffAreas" ADD COLUMN "label_pos" public.geometry(MultiPoint, 27700);
ALTER TABLE public."ControlledParkingZones" ADD COLUMN "label_pos" public.geometry(MultiPoint, 27700);


-- Create default label positions

UPDATE public."Lines" SET
    "label_pos" = ST_Multi(ST_LineInterpolatePoint("geom", 0.5)),
    "label_loading_pos" = ST_Multi(ST_LineInterpolatePoint("geom", 0.5));

UPDATE public."RestrictionPolygons" SET
    "label_pos" = ST_Multi(ST_PointOnSurface("geom"));

UPDATE public."Bays" SET
    "label_pos" = ST_Multi(ST_PointOnSurface("geom"));

UPDATE public."ParkingTariffAreas" SET
    "label_pos" = ST_Multi(ST_PointOnSurface("geom"));

UPDATE public."ControlledParkingZones" SET
    "label_pos" = ST_Multi(ST_PointOnSurface("geom"));


-- Migrate manually positionned label

UPDATE public."Lines" SET
    "label_pos" = ST_Multi(ST_SetSRID(ST_MakePoint("labelX", "labelY"), 27700))
WHERE "labelX" IS NOT NULL AND "labelY" IS NOT NULL;

UPDATE public."Lines" SET
    "label_loading_pos" = ST_Multi(ST_SetSRID(ST_MakePoint("labelLoadingX", "labelLoadingY"), 27700))
WHERE "labelLoadingX" IS NOT NULL AND "labelLoadingY" IS NOT NULL;

UPDATE public."RestrictionPolygons" SET
    "label_pos" = ST_Multi(ST_SetSRID(ST_MakePoint("labelX", "labelY"), 27700))
WHERE "labelX" IS NOT NULL AND "labelY" IS NOT NULL;

UPDATE public."Bays" SET
    "label_pos" = ST_Multi(ST_SetSRID(ST_MakePoint("label_X", "label_Y"), 27700))
WHERE "label_X" IS NOT NULL AND "label_Y" IS NOT NULL;


-- Remove obsolete fields
ALTER TABLE public."Lines" DROP COLUMN "labelX";
ALTER TABLE public."Lines" DROP COLUMN "labelY";
ALTER TABLE public."Lines" DROP COLUMN "labelRotation";
ALTER TABLE public."Lines" DROP COLUMN "labelLoadingX";
ALTER TABLE public."Lines" DROP COLUMN "labelLoadingY";
ALTER TABLE public."Lines" DROP COLUMN "labelLoadingRotation";
ALTER TABLE public."RestrictionPolygons" DROP COLUMN "labelX";
ALTER TABLE public."RestrictionPolygons" DROP COLUMN "labelY";
ALTER TABLE public."RestrictionPolygons" DROP COLUMN "labelRotation";
ALTER TABLE public."Bays" DROP COLUMN "label_X";
ALTER TABLE public."Bays" DROP COLUMN "label_Y";
ALTER TABLE public."Bays" DROP COLUMN "label_Rotation";

CREATE OR REPLACE FUNCTION restriction_mngmt() RETURNS trigger AS /*"""*/ $$

import plpy

OLD = TD["old"] # this contains the feature before modifications
NEW = TD["new"] # this contains the feature after modifications

plpy.info('Trigger {} was run ({} {} on "{}")'.format(TD["name"], TD["when"], TD["event"], TD["table_name"]))

def ensure_labels_points(main_geom, label_geom):
    """
    This function ensures that at least one label point exists on every sheet on which the geometry appears
    """

    # Let's just start by making an empty multipoint if label_geom is NULL, so we don't have to deal with NULL afterwards
    if label_geom is None:
        plan = plpy.prepare("SELECT ST_SetSRID(ST_GeomFromEWKT('MULTIPOINT EMPTY'), Find_SRID('"+TD["table_schema"]+"', '"+TD["table_name"]+"', 'geom')) as p", ['text'])
        label_geom = plpy.execute(plan, [label_geom])[0]["p"]

    # TODO : make the position automatically update if it wasn't moved
    # for lines, this could be done by computing ST_DIFFERENCE(label_pos, OLD["geom"])
    # but let's keep it simple for now...

    # We select all sheets that intersect with the feature but not with the label
    # multipoints to obtain all sheets that miss a label point
    plan = plpy.prepare('SELECT geom FROM "MapGrid" WHERE ST_Intersects(geom, $1::geometry) AND NOT ST_Intersects(geom, $2::geometry)', ['text', 'text'])
    results = plpy.execute(plan, [main_geom, label_geom])
    sheets_geoms = [r['geom'] for r in results]

    plpy.info("{} new label points will be created".format(len(sheets_geoms)))

    # For these sheets, we add points at the center of the intersection
    points = []
    for sheet_geom in sheets_geoms:
        # get the intersection between the sheet and the geometry
        plan = plpy.prepare("SELECT ST_Intersection($1::geometry, $2::geometry) as i", ['text', 'text'])
        intersection = plpy.execute(plan, [main_geom, sheet_geom])[0]["i"]

        # get the center (if a line) or the centroid (if not a line)
        # TODO : manage edge case when a feature exits and re-enterds a sheet (we get a MultiLineString, and should return center point of each instead of centroid)
        plan = plpy.prepare("SELECT CASE WHEN ST_GeometryType($1::geometry) = 'ST_LineString' THEN ST_LineInterpolatePoint($1::geometry, 0.5) WHEN ST_GeometryType($1::geometry) = 'ST_Polygon' THEN ST_PointOnSurface($1::geometry) ELSE ST_Centroid($1::geometry) END as p", ['text'])
        point = plpy.execute(plan, [intersection])[0]["p"]

        # we collect that point into label_pos
        plan = plpy.prepare("SELECT ST_Multi(ST_Union($1::geometry, $2::geometry)) as p", ['text', 'text'])
        label_geom = plpy.execute(plan, [label_geom, point])[0]["p"]

    return label_geom


NEW["label_pos"] = ensure_labels_points(NEW["geom"], NEW["label_pos"])

if TD["table_name"] == 'Lines':
    # the Lines layer has an additionnal label pos
    NEW["label_loading_pos"] = ensure_labels_points(NEW["geom"], NEW["label_loading_pos"])

# this flag is required for the trigger to commit changes in NEW
return "MODIFY"

$$ LANGUAGE plpython3u;

/*"""*/

-- Create the triggers
-- insert
CREATE TRIGGER insert_mngmt BEFORE INSERT ON public."Bays" FOR EACH ROW EXECUTE PROCEDURE restriction_mngmt();
CREATE TRIGGER insert_mngmt BEFORE INSERT ON public."Lines" FOR EACH ROW EXECUTE PROCEDURE restriction_mngmt();
CREATE TRIGGER insert_mngmt BEFORE INSERT ON public."RestrictionPolygons" FOR EACH ROW EXECUTE PROCEDURE restriction_mngmt();
CREATE TRIGGER insert_mngmt BEFORE INSERT ON public."ControlledParkingZones" FOR EACH ROW EXECUTE PROCEDURE restriction_mngmt();
CREATE TRIGGER insert_mngmt BEFORE INSERT ON public."ParkingTariffAreas" FOR EACH ROW EXECUTE PROCEDURE restriction_mngmt();
-- update
CREATE TRIGGER update_mngmt BEFORE UPDATE ON public."Bays" FOR EACH ROW WHEN ( NOT ST_Equals(OLD.geom, NEW.geom) OR NOT ST_Equals(OLD.label_pos, NEW.label_pos) ) EXECUTE PROCEDURE restriction_mngmt();
CREATE TRIGGER update_mngmt BEFORE UPDATE ON public."Lines" FOR EACH ROW WHEN ( NOT ST_Equals(OLD.geom, NEW.geom) OR NOT ST_Equals(OLD.label_pos, NEW.label_pos) OR NOT ST_Equals(OLD.label_loading_pos, NEW.label_loading_pos) ) EXECUTE PROCEDURE restriction_mngmt();
CREATE TRIGGER update_mngmt BEFORE UPDATE ON public."RestrictionPolygons" FOR EACH ROW WHEN ( NOT ST_Equals(OLD.geom, NEW.geom) OR NOT ST_Equals(OLD.label_pos, NEW.label_pos) ) EXECUTE PROCEDURE restriction_mngmt();
CREATE TRIGGER update_mngmt BEFORE UPDATE ON public."ControlledParkingZones" FOR EACH ROW WHEN ( NOT ST_Equals(OLD.geom, NEW.geom) OR NOT ST_Equals(OLD.label_pos, NEW.label_pos) ) EXECUTE PROCEDURE restriction_mngmt();
CREATE TRIGGER update_mngmt BEFORE UPDATE ON public."ParkingTariffAreas" FOR EACH ROW WHEN ( NOT ST_Equals(OLD.geom, NEW.geom) OR NOT ST_Equals(OLD.label_pos, NEW.label_pos) ) EXECUTE PROCEDURE restriction_mngmt();

/*"""*/