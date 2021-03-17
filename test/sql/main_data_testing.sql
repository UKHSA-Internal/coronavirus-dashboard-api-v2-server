CREATE SCHEMA covid19;
--=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~

CREATE TABLE IF NOT EXISTS covid19.area_reference (
    id                SERIAL                  NOT NULL UNIQUE,
    area_type         VARCHAR(15)             NOT NULL,
    area_code         VARCHAR(12)             NOT NULL,
    area_name         VARCHAR(120)            NOT NULL,

    PRIMARY KEY (area_type, area_code),
    UNIQUE (area_type, area_code)
);

CREATE UNIQUE INDEX IF NOT EXISTS arearef_type_code_idx
    ON covid19.area_reference
        USING BTREE (area_type, area_code);

CREATE UNIQUE INDEX IF NOT EXISTS arearef_id_idx
    ON covid19.area_reference
        USING BTREE (id);

CREATE INDEX IF NOT EXISTS arearef_namelower_idx
    ON covid19.area_reference
        USING BTREE (LOWER(area_name));

CREATE INDEX IF NOT EXISTS arearef_area_code_initial
    ON covid19.area_reference
        USING BTREE (SUBSTRING(area_code, 1));

--=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~

CREATE TABLE IF NOT EXISTS covid19.metric_reference (
    id          SERIAL          NOT NULL UNIQUE PRIMARY KEY,
    metric      VARCHAR(120)    NOT NULL UNIQUE,
    metric_name VARCHAR(150),
    released    BOOLEAN         NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS metricref_metrics_idx
    ON covid19.metric_reference
        USING BTREE (metric);

CREATE INDEX IF NOT EXISTS metricref_releasedmetrics_idx
    ON covid19.metric_reference
        USING BTREE (metric, released) WHERE released = TRUE;

--=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~

CREATE TABLE IF NOT EXISTS covid19.release_reference (
    id         SERIAL          NOT NULL UNIQUE PRIMARY KEY,
    timestamp  TIMESTAMP       NOT NULL UNIQUE,
    released   BOOLEAN         NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS releaseref_timestamp_idx
    ON covid19.release_reference
        USING BTREE (timestamp);

CREATE INDEX IF NOT EXISTS releaseref_releasedtimestamp_idx
    ON covid19.release_reference
        USING BTREE (timestamp, released) WHERE released = TRUE;

--=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~

CREATE TABLE IF NOT EXISTS covid19.area_priorities (
    area_type         VARCHAR(15)             NOT NULL UNIQUE,
    priority          NUMERIC                 NOT NULL,

    PRIMARY KEY (area_type, priority)
);

--=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~

CREATE TABLE IF NOT EXISTS covid19.time_series (
    hash               VARCHAR(24)  NOT NULL,
    partition_id       VARCHAR(26)  NOT NULL,
    release_id         INT          NOT NULL,
    area_id            INT          NOT NULL,
    metric_id          INT          NOT NULL,
    date               DATE         NOT NULL,
    payload            JSONB        DEFAULT '{"value": null}',

    CONSTRAINT unique_partition UNIQUE (hash, partition_id),
    PRIMARY KEY (hash, area_id, metric_id, release_id, partition_id)

)
PARTITION BY LIST ( partition_id );

CREATE INDEX IF NOT EXISTS timeseries_hash_idx
    ON covid19.time_series USING BTREE (hash);

CREATE INDEX IF NOT EXISTS timeseries_releaseid_idx
    ON covid19.time_series USING BTREE (release_id);


CREATE INDEX IF NOT EXISTS timeseries_payload_idx
    ON covid19.time_series USING GIN (payload jsonb_path_ops);

CREATE INDEX IF NOT EXISTS timeseries_payload_notnull_idx
    ON covid19.time_series USING GIN (payload)
    WHERE (payload -> 'value') NOTNULL;

CREATE INDEX IF NOT EXISTS timeseries_timestamp_idx
    ON covid19.time_series USING BTREE (partition_id);

CREATE INDEX IF NOT EXISTS timeseries_area_selfjoin_idx
    ON covid19.time_series
        USING BTREE (partition_id, area_id, date);

CREATE INDEX IF NOT EXISTS timeseries_response_order_idx
    ON covid19.time_series
        USING BTREE (area_id DESC, date DESC);

CREATE INDEX IF NOT EXISTS arearef_area_code_initial
    ON covid19.area_reference
        USING BTREE (SUBSTRING(area_code, 1));

CREATE INDEX IF NOT EXISTS timeseries_recorddate_idx
    ON covid19.time_series
        USING BTREE (partition_id);

CREATE INDEX IF NOT EXISTS timeseries_metric_idx
    ON covid19.time_series
        USING BTREE (metric_id);

CREATE INDEX IF NOT EXISTS timeseries_area_idx
    ON covid19.time_series
        USING BTREE (area_id);


ALTER TABLE covid19.time_series
    ADD CONSTRAINT fk_ts_release
        FOREIGN KEY ( release_id )
            REFERENCES covid19.release_reference ( id )
            ON DELETE CASCADE;

