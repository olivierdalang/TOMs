-- Fix ownership (needed for foreign key)
ALTER TABLE public."MapGrid" OWNER TO postgres;

-- Create the label positions table
CREATE TABLE public."label_pos" (
    id SERIAL PRIMARY KEY,
    geom public.geometry(Point,27700) NOT NULL,
    rotation DOUBLE PRECISION NOT NULL,
    line_pk VARCHAR REFERENCES public."Lines"("GeometryID") ON DELETE CASCADE,
    poly_pk VARCHAR REFERENCES public."RestrictionPolygons"("GeometryID") ON DELETE CASCADE,
    grid_id BIGINT REFERENCES public."MapGrid"("id") ON DELETE CASCADE,
    lock BOOLEAN DEFAULT FALSE
    CONSTRAINT exactly_one_reference CHECK ( (line_pk IS NOT NULL)::int + (poly_pk IS NOT NULL)::int = 1 ) 
);
GRANT SELECT ON TABLE public."label_pos" TO edi_public;
GRANT SELECT ON TABLE public."label_pos" TO edi_public_nsl;
GRANT INSERT, SELECT, UPDATE ON TABLE public."label_pos" TO edi_admin;

GRANT SELECT ON SEQUENCE public."label_pos_id_seq" TO edi_operator;
GRANT SELECT ON SEQUENCE public."label_pos_id_seq" TO edi_public;
GRANT SELECT ON SEQUENCE public."label_pos_id_seq" TO edi_public_nsl;
GRANT SELECT,USAGE ON SEQUENCE public."label_pos_id_seq" TO edi_admin;

-- Migrate existing label positions
INSERT INTO public."label_pos" (geom, rotation, line_pk, grid_id, lock)
SELECT  ST_SetSRID(ST_MakePoint("labelX", "labelY"), 27700),
        COALESCE("labelRotation",0),
        "GeometryID",
        grd.id,
        TRUE
FROM public."Lines" l
JOIN public."MapGrid" grd ON ST_Contains(grd.geom, l.geom)
WHERE "labelX" IS NOT NULL and "labelY" IS NOT NULL;

INSERT INTO public."label_pos" (geom, rotation, poly_pk, grid_id, lock)
SELECT  ST_SetSRID(ST_MakePoint("labelX", "labelY"), 27700),
        COALESCE("labelRotation",0),
        "GeometryID",
        grd.id,
        TRUE
FROM public."RestrictionPolygons" p
JOIN public."MapGrid" grd ON ST_Contains(grd.geom, p.geom)
WHERE "labelX" IS NOT NULL and "labelY" IS NOT NULL;


-- Remove obsolete fields
-- ALTER TABLE public."Lines" DROP COLUMN "labelX";
-- ALTER TABLE public."Lines" DROP COLUMN "labelY";
-- ALTER TABLE public."Lines" DROP COLUMN "labelRotation";
-- ALTER TABLE public."RestrictionPolygons" DROP COLUMN "labelX";
-- ALTER TABLE public."RestrictionPolygons" DROP COLUMN "labelY";
-- ALTER TABLE public."RestrictionPolygons" DROP COLUMN "labelRotation";


-- Create an auto-lock trigger to automatically lock all modified labels
CREATE OR REPLACE FUNCTION auto_lock_labels_fct() RETURNS trigger SECURITY DEFINER AS $emp_stamp$
    BEGIN
        NEW."lock" = TRUE;
        RETURN NEW;
    END;
$emp_stamp$ LANGUAGE plpgsql;

CREATE TRIGGER auto_lock_labels
    BEFORE UPDATE ON public."label_pos"
    FOR EACH ROW
    EXECUTE PROCEDURE auto_lock_labels_fct();

-- Create a post-insert/update trigger that creates label positions on each sheet if needed
CREATE OR REPLACE FUNCTION ensure_labels_lines_fct() RETURNS trigger SECURITY DEFINER AS $emp_stamp$
    BEGIN

        -- remove unlocked positions
        DELETE FROM public."label_pos" p
        WHERE p."line_pk" = NEW."GeometryID" AND NOT p."lock";

        -- create new positions on each sheet
        INSERT INTO public."label_pos"("line_pk", "geom", "rotation")
        SELECT  NEW."GeometryID",
                CASE
                    -- the intersection can return a point if it ends exactly on the edge of the grid
                    WHEN GeometryType(ST_Intersection(grd1.geom, NEW.geom)) = 'LINESTRING' THEN ST_LineInterpolatePoint(ST_Intersection(grd1.geom, NEW.geom), 0.5)
                    ELSE ST_Centroid(ST_Intersection(grd1.geom, NEW.geom))
                END,
                0.0
        FROM public."MapGrid" grd1
        WHERE ST_Intersects(grd1.geom, NEW.geom)
            -- if it does not already exist
            AND NOT EXISTS(
                SELECT *
                FROM public."label_pos" p
                WHERE p."line_pk" = NEW."GeometryID" AND p."grid_id" = grd1."id"
            );

        RETURN NEW;
    END;
$emp_stamp$ LANGUAGE plpgsql;

CREATE TRIGGER ensure_labels_lines
    AFTER INSERT OR UPDATE ON public."Lines"
    FOR EACH ROW
    EXECUTE PROCEDURE ensure_labels_lines_fct();

UPDATE public."Lines" SET geom = geom;  -- run the trigger on all rows

-- Create a post-insert/update trigger that creates label positions on each sheet if needed
CREATE OR REPLACE FUNCTION ensure_labels_polys_fct() RETURNS trigger SECURITY DEFINER AS $emp_stamp$
    BEGIN

        -- remove unlocked positions
        DELETE FROM public."label_pos" p
        WHERE p."poly_pk" = NEW."GeometryID" AND NOT p."lock";

        -- create new positions on each sheet
        INSERT INTO public."label_pos"("poly_pk", "geom", "rotation")
        SELECT  NEW."GeometryID",
                CASE
                    -- the intersection can return a point if it ends exactly on the edge of the grid
                    WHEN GeometryType(ST_Intersection(grd1.geom, NEW.geom)) = 'LINESTRING' THEN ST_LineInterpolatePoint(ST_Intersection(grd1.geom, NEW.geom), 0.5)
                    ELSE ST_Centroid(ST_Intersection(grd1.geom, NEW.geom))
                END,
                0.0
        FROM public."MapGrid" grd1
        WHERE ST_Intersects(grd1.geom, NEW.geom)
            -- if it does not already exist
            AND NOT EXISTS(
                SELECT *
                FROM public."label_pos" p
                WHERE p."poly_pk" = NEW."GeometryID" AND p."grid_id" = grd1."id"
            );

        RETURN NEW;
    END;
$emp_stamp$ LANGUAGE plpgsql;

CREATE TRIGGER ensure_labels_polys
    AFTER INSERT OR UPDATE ON public."RestrictionPolygons"
    FOR EACH ROW
    EXECUTE PROCEDURE ensure_labels_polys_fct();

UPDATE public."RestrictionPolygons" SET geom = geom;  -- run the trigger on all rows



/*
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
*/

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

