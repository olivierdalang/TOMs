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
GRANT SELECT ON TABLE public."label_pos" TO edi_public;
GRANT SELECT ON TABLE public."label_pos" TO edi_public_nsl;
GRANT INSERT, SELECT, UPDATE ON TABLE public."label_pos" TO edi_admin;

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
-- ALTER TABLE public."Lines" DROP COLUMN "labelX";
-- ALTER TABLE public."Lines" DROP COLUMN "labelY";
-- ALTER TABLE public."Lines" DROP COLUMN "labelRotation";
-- ALTER TABLE public."RestrictionPolygons" DROP COLUMN "labelX";
-- ALTER TABLE public."RestrictionPolygons" DROP COLUMN "labelY";
-- ALTER TABLE public."RestrictionPolygons" DROP COLUMN "labelRotation";
-- ALTER TABLE public."Bays" DROP COLUMN "label_X";
-- ALTER TABLE public."Bays" DROP COLUMN "label_Y";
-- ALTER TABLE public."Bays" DROP COLUMN "label_Rotation";

-- Create proxy view for Lines
ALTER TABLE public."Lines" RENAME TO "Lines_";
CREATE VIEW public."Lines" AS
SELECT  l.*,
        ST_AsText(ST_Collect(lab.geom)) as labels_geom
FROM public."Lines_" l
JOIN public."label_pos" lab ON lab."line_pk" = l."GeometryID"
GROUP BY l."GeometryID";

-- TODO : make updateable

GRANT SELECT ON TABLE public."Lines" TO edi_public;
GRANT SELECT ON TABLE public."Lines" TO edi_public_nsl;
GRANT SELECT ON TABLE public."Lines" TO edi_admin;

/*
-- Create views that join label positions
DROP VIEW public."label_pos_agg_lines";
CREATE VIEW public."label_pos_agg_lines" AS
SELECT lab."line_pk", ST_Collect(lab.geom) as labels_geoms
FROM public."label_pos" lab
WHERE lab."line_pk" IS NOT NULL
GROUP BY lab."line_pk";

GRANT SELECT ON TABLE public."label_pos_agg_lines" TO edi_public;
GRANT SELECT ON TABLE public."label_pos_agg_lines" TO edi_public_nsl;
GRANT SELECT ON TABLE public."label_pos_agg_lines" TO edi_admin;
*/

/*

-- Create a post-insert/update trigger that creates label positions on each sheet if needed
INSERT INTO public."label_pos"
VALUES
C

CREATE TRIGGER ensure_labels
    AFTER INSERT OR UPDATE ON public."Lines"
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE PROCEDURE ensure_labels_function();

    */