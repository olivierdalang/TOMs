-- Create the label positions table
CREATE TABLE public."label_pos" (
    id SERIAL PRIMARY KEY,
    geom public.geometry(Point,27700) NOT NULL,
    rotation DOUBLE PRECISION NOT NULL,
    line_pk VARCHAR REFERENCES public."Lines"("GeometryID") ON DELETE CASCADE,
    poly_pk VARCHAR REFERENCES public."RestrictionPolygons"("GeometryID") ON DELETE CASCADE,
    bays_pk VARCHAR REFERENCES public."Bays"("GeometryID") ON DELETE CASCADE
    CONSTRAINT exactly_one_reference CHECK ( (line_pk IS NOT NULL)::int + (poly_pk IS NOT NULL)::int + (bays_pk IS NOT NULL)::int = 1 ) 
);

-- Migrate existing label positions
INSERT INTO public."label_pos" (geom, rotation, line_pk )
SELECT  COALESCE(ST_SetSRID(ST_MakePoint("labelX", "labelY"), 27700),
        ST_Centroid("geom")),
        COALESCE("labelRotation",0),
        "GeometryID"
FROM public."Lines";

INSERT INTO public."label_pos" (geom, rotation, poly_pk )
SELECT  COALESCE(ST_SetSRID(ST_MakePoint("labelX", "labelY"), 27700),
        ST_Centroid("geom")),
        COALESCE("labelRotation",0),
        "GeometryID"
FROM public."RestrictionPolygons";

INSERT INTO public."label_pos" (geom, rotation, bays_pk )
SELECT  COALESCE(ST_SetSRID(ST_MakePoint("label_X", "label_Y"), 27700),
        ST_Centroid("geom")),
        COALESCE("label_Rotation",0),
        "GeometryID"
FROM public."Bays";

-- Remove obsolete fields
ALTER TABLE public."Lines" DROP COLUMN "labelX";
ALTER TABLE public."Lines" DROP COLUMN "labelY";
ALTER TABLE public."Lines" DROP COLUMN "labelRotation";
ALTER TABLE public."RestrictionPolygons" DROP COLUMN "labelX";
ALTER TABLE public."RestrictionPolygons" DROP COLUMN "labelY";
ALTER TABLE public."RestrictionPolygons" DROP COLUMN "labelRotation";
ALTER TABLE public."Bays" DROP COLUMN "label_X";
ALTER TABLE public."Bays" DROP COLUMN "label_Y";
ALTER TABLE public."Bays" DROP COLUMN "label_Rotation";

-- Create a post-insert/update trigger that creates label positions on each sheet if needed
INSERT INTO public."label_pos"
VALUES
C

CREATE TRIGGER ensure_labels
    AFTER INSERT OR UPDATE ON public."Lines"
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE PROCEDURE ensure_labels_function();