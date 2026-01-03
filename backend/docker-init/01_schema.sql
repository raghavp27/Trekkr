--
-- PostgreSQL database dump
--

-- Dumped from database version 16.4 (Debian 16.4-1.pgdg110+2)
-- Dumped by pg_dump version 16.4 (Debian 16.4-1.pgdg110+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: achievements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.achievements (
    id integer NOT NULL,
    code character varying(64) NOT NULL,
    name character varying(128) NOT NULL,
    description character varying(512),
    criteria_json json,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: achievements_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.achievements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: achievements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.achievements_id_seq OWNED BY public.achievements.id;


--
-- Name: devices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.devices (
    id integer NOT NULL,
    user_id integer NOT NULL,
    platform character varying(50),
    app_version character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    device_uuid character varying(255),
    device_name character varying(255) DEFAULT 'My Phone'::character varying
);


--
-- Name: devices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.devices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: devices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.devices_id_seq OWNED BY public.devices.id;


--
-- Name: h3_cells; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.h3_cells (
    h3_index character varying(25) NOT NULL,
    res smallint NOT NULL,
    country_id integer,
    state_id integer,
    centroid public.geometry(Point,4326),
    first_visited_at timestamp without time zone,
    last_visited_at timestamp without time zone,
    visit_count integer DEFAULT 1 NOT NULL
);


--
-- Name: ingest_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ingest_batches (
    id integer NOT NULL,
    user_id integer NOT NULL,
    device_id integer,
    received_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    cells_count integer NOT NULL,
    res_min smallint,
    res_max smallint
);


--
-- Name: ingest_batches_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ingest_batches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ingest_batches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ingest_batches_id_seq OWNED BY public.ingest_batches.id;


--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.password_reset_tokens (
    id integer NOT NULL,
    user_id integer NOT NULL,
    token_hash character varying(64) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    used_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: password_reset_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.password_reset_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: password_reset_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.password_reset_tokens_id_seq OWNED BY public.password_reset_tokens.id;


--
-- Name: regions_country; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.regions_country (
    id integer NOT NULL,
    iso2 character varying(2) NOT NULL,
    iso3 character varying(3) NOT NULL,
    name character varying(128) NOT NULL,
    geom public.geometry(MultiPolygon,4326),
    land_cells_total integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    continent character varying(32),
    land_cells_total_resolution6 integer,
    land_cells_total_resolution8 integer
);


--
-- Name: regions_country_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.regions_country_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: regions_country_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.regions_country_id_seq OWNED BY public.regions_country.id;


--
-- Name: regions_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.regions_state (
    id integer NOT NULL,
    country_id integer NOT NULL,
    code character varying(10) NOT NULL,
    name character varying(128) NOT NULL,
    geom public.geometry(MultiPolygon,4326),
    land_cells_total integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    land_cells_total_resolution6 integer,
    land_cells_total_resolution8 integer
);


--
-- Name: regions_state_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.regions_state_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: regions_state_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.regions_state_id_seq OWNED BY public.regions_state.id;


--
-- Name: user_achievements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_achievements (
    id integer NOT NULL,
    user_id integer NOT NULL,
    achievement_id integer NOT NULL,
    unlocked_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: user_achievements_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_achievements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_achievements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_achievements_id_seq OWNED BY public.user_achievements.id;


--
-- Name: user_cell_visits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_cell_visits (
    id integer NOT NULL,
    user_id integer NOT NULL,
    device_id integer,
    h3_index character varying(25) NOT NULL,
    res smallint NOT NULL,
    first_visited_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_visited_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    visit_count integer DEFAULT 1 NOT NULL
);


--
-- Name: user_cell_visits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_cell_visits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_cell_visits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_cell_visits_id_seq OWNED BY public.user_cell_visits.id;


--
-- Name: user_country_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_country_stats (
    id integer NOT NULL,
    user_id integer NOT NULL,
    country_id integer NOT NULL,
    cells_visited integer DEFAULT 0 NOT NULL,
    coverage_pct numeric(5,2) DEFAULT '0'::numeric NOT NULL,
    first_visited_at timestamp without time zone,
    last_visited_at timestamp without time zone
);


--
-- Name: user_country_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_country_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_country_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_country_stats_id_seq OWNED BY public.user_country_stats.id;


--
-- Name: user_state_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_state_stats (
    id integer NOT NULL,
    user_id integer NOT NULL,
    state_id integer NOT NULL,
    cells_visited integer DEFAULT 0 NOT NULL,
    coverage_pct numeric(5,2) DEFAULT '0'::numeric NOT NULL,
    first_visited_at timestamp without time zone,
    last_visited_at timestamp without time zone
);


--
-- Name: user_state_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_state_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_state_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_state_stats_id_seq OWNED BY public.user_state_stats.id;


--
-- Name: user_streaks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_streaks (
    id integer NOT NULL,
    user_id integer NOT NULL,
    current_streak_days integer DEFAULT 0 NOT NULL,
    longest_streak_days integer DEFAULT 0 NOT NULL,
    current_streak_start date,
    current_streak_end date,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: user_streaks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_streaks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_streaks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_streaks_id_seq OWNED BY public.user_streaks.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    username character varying(64) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    token_version integer DEFAULT 0 NOT NULL
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: achievements id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.achievements ALTER COLUMN id SET DEFAULT nextval('public.achievements_id_seq'::regclass);


--
-- Name: devices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices ALTER COLUMN id SET DEFAULT nextval('public.devices_id_seq'::regclass);


--
-- Name: ingest_batches id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingest_batches ALTER COLUMN id SET DEFAULT nextval('public.ingest_batches_id_seq'::regclass);


--
-- Name: password_reset_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens ALTER COLUMN id SET DEFAULT nextval('public.password_reset_tokens_id_seq'::regclass);


--
-- Name: regions_country id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions_country ALTER COLUMN id SET DEFAULT nextval('public.regions_country_id_seq'::regclass);


--
-- Name: regions_state id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions_state ALTER COLUMN id SET DEFAULT nextval('public.regions_state_id_seq'::regclass);


--
-- Name: user_achievements id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_achievements ALTER COLUMN id SET DEFAULT nextval('public.user_achievements_id_seq'::regclass);


--
-- Name: user_cell_visits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_cell_visits ALTER COLUMN id SET DEFAULT nextval('public.user_cell_visits_id_seq'::regclass);


--
-- Name: user_country_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_country_stats ALTER COLUMN id SET DEFAULT nextval('public.user_country_stats_id_seq'::regclass);


--
-- Name: user_state_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_state_stats ALTER COLUMN id SET DEFAULT nextval('public.user_state_stats_id_seq'::regclass);


--
-- Name: user_streaks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_streaks ALTER COLUMN id SET DEFAULT nextval('public.user_streaks_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: achievements achievements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.achievements
    ADD CONSTRAINT achievements_pkey PRIMARY KEY (id);


--
-- Name: devices devices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_pkey PRIMARY KEY (id);


--
-- Name: h3_cells h3_cells_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.h3_cells
    ADD CONSTRAINT h3_cells_pkey PRIMARY KEY (h3_index);


--
-- Name: ingest_batches ingest_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingest_batches
    ADD CONSTRAINT ingest_batches_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: regions_country regions_country_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions_country
    ADD CONSTRAINT regions_country_pkey PRIMARY KEY (id);


--
-- Name: regions_state regions_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions_state
    ADD CONSTRAINT regions_state_pkey PRIMARY KEY (id);


--
-- Name: achievements uq_achievements_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.achievements
    ADD CONSTRAINT uq_achievements_code UNIQUE (code);


--
-- Name: regions_country uq_regions_country_iso2; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions_country
    ADD CONSTRAINT uq_regions_country_iso2 UNIQUE (iso2);


--
-- Name: regions_country uq_regions_country_iso3; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions_country
    ADD CONSTRAINT uq_regions_country_iso3 UNIQUE (iso3);


--
-- Name: regions_state uq_regions_state_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions_state
    ADD CONSTRAINT uq_regions_state_code UNIQUE (country_id, code);


--
-- Name: user_achievements uq_user_achievement; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_achievements
    ADD CONSTRAINT uq_user_achievement UNIQUE (user_id, achievement_id);


--
-- Name: user_cell_visits uq_user_cell; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_cell_visits
    ADD CONSTRAINT uq_user_cell UNIQUE (user_id, h3_index);


--
-- Name: user_country_stats uq_user_country_stat; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_country_stats
    ADD CONSTRAINT uq_user_country_stat UNIQUE (user_id, country_id);


--
-- Name: user_state_stats uq_user_state_stat; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_state_stats
    ADD CONSTRAINT uq_user_state_stat UNIQUE (user_id, state_id);


--
-- Name: users uq_users_email; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uq_users_email UNIQUE (email);


--
-- Name: users uq_users_username; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uq_users_username UNIQUE (username);


--
-- Name: user_achievements user_achievements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_achievements
    ADD CONSTRAINT user_achievements_pkey PRIMARY KEY (id);


--
-- Name: user_cell_visits user_cell_visits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_cell_visits
    ADD CONSTRAINT user_cell_visits_pkey PRIMARY KEY (id);


--
-- Name: user_country_stats user_country_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_country_stats
    ADD CONSTRAINT user_country_stats_pkey PRIMARY KEY (id);


--
-- Name: user_state_stats user_state_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_state_stats
    ADD CONSTRAINT user_state_stats_pkey PRIMARY KEY (id);


--
-- Name: user_streaks user_streaks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_streaks
    ADD CONSTRAINT user_streaks_pkey PRIMARY KEY (id);


--
-- Name: user_streaks user_streaks_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_streaks
    ADD CONSTRAINT user_streaks_user_id_key UNIQUE (user_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_h3_cells_centroid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_h3_cells_centroid ON public.h3_cells USING gist (centroid);


--
-- Name: idx_regions_country_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_regions_country_geom ON public.regions_country USING gist (geom);


--
-- Name: idx_regions_state_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_regions_state_geom ON public.regions_state USING gist (geom);


--
-- Name: ix_achievements_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_achievements_code ON public.achievements USING btree (code);


--
-- Name: ix_devices_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_devices_user_id ON public.devices USING btree (user_id);


--
-- Name: ix_h3_cells_country_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_h3_cells_country_id ON public.h3_cells USING btree (country_id);


--
-- Name: ix_h3_cells_res; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_h3_cells_res ON public.h3_cells USING btree (res);


--
-- Name: ix_h3_cells_state_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_h3_cells_state_id ON public.h3_cells USING btree (state_id);


--
-- Name: ix_ingest_batches_device_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingest_batches_device_id ON public.ingest_batches USING btree (device_id);


--
-- Name: ix_ingest_batches_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingest_batches_user_id ON public.ingest_batches USING btree (user_id);


--
-- Name: ix_password_reset_tokens_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_password_reset_tokens_id ON public.password_reset_tokens USING btree (id);


--
-- Name: ix_password_reset_tokens_token_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_password_reset_tokens_token_hash ON public.password_reset_tokens USING btree (token_hash);


--
-- Name: ix_password_reset_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_password_reset_tokens_user_id ON public.password_reset_tokens USING btree (user_id);


--
-- Name: ix_regions_country_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_regions_country_geom ON public.regions_country USING gist (geom);


--
-- Name: ix_regions_country_iso2; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_regions_country_iso2 ON public.regions_country USING btree (iso2);


--
-- Name: ix_regions_country_iso3; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_regions_country_iso3 ON public.regions_country USING btree (iso3);


--
-- Name: ix_regions_country_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_regions_country_name ON public.regions_country USING btree (name);


--
-- Name: ix_regions_state_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_regions_state_code ON public.regions_state USING btree (code);


--
-- Name: ix_regions_state_country_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_regions_state_country_id ON public.regions_state USING btree (country_id);


--
-- Name: ix_regions_state_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_regions_state_geom ON public.regions_state USING gist (geom);


--
-- Name: ix_regions_state_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_regions_state_name ON public.regions_state USING btree (name);


--
-- Name: ix_user_achievements_achievement_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_achievements_achievement_id ON public.user_achievements USING btree (achievement_id);


--
-- Name: ix_user_achievements_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_achievements_user_id ON public.user_achievements USING btree (user_id);


--
-- Name: ix_user_cell_visits_h3_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_cell_visits_h3_index ON public.user_cell_visits USING btree (h3_index);


--
-- Name: ix_user_cell_visits_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_cell_visits_user_id ON public.user_cell_visits USING btree (user_id);


--
-- Name: ix_user_cell_visits_user_res; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_cell_visits_user_res ON public.user_cell_visits USING btree (user_id, res);


--
-- Name: ix_user_country_stats_country_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_country_stats_country_id ON public.user_country_stats USING btree (country_id);


--
-- Name: ix_user_country_stats_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_country_stats_user_id ON public.user_country_stats USING btree (user_id);


--
-- Name: ix_user_state_stats_state_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_state_stats_state_id ON public.user_state_stats USING btree (state_id);


--
-- Name: ix_user_state_stats_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_state_stats_user_id ON public.user_state_stats USING btree (user_id);


--
-- Name: ix_user_streaks_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_streaks_user_id ON public.user_streaks USING btree (user_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: devices devices_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: h3_cells h3_cells_country_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.h3_cells
    ADD CONSTRAINT h3_cells_country_id_fkey FOREIGN KEY (country_id) REFERENCES public.regions_country(id) ON DELETE SET NULL;


--
-- Name: h3_cells h3_cells_state_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.h3_cells
    ADD CONSTRAINT h3_cells_state_id_fkey FOREIGN KEY (state_id) REFERENCES public.regions_state(id) ON DELETE SET NULL;


--
-- Name: ingest_batches ingest_batches_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingest_batches
    ADD CONSTRAINT ingest_batches_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.devices(id) ON DELETE SET NULL;


--
-- Name: ingest_batches ingest_batches_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingest_batches
    ADD CONSTRAINT ingest_batches_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: regions_state regions_state_country_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions_state
    ADD CONSTRAINT regions_state_country_id_fkey FOREIGN KEY (country_id) REFERENCES public.regions_country(id) ON DELETE CASCADE;


--
-- Name: user_achievements user_achievements_achievement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_achievements
    ADD CONSTRAINT user_achievements_achievement_id_fkey FOREIGN KEY (achievement_id) REFERENCES public.achievements(id) ON DELETE CASCADE;


--
-- Name: user_achievements user_achievements_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_achievements
    ADD CONSTRAINT user_achievements_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_cell_visits user_cell_visits_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_cell_visits
    ADD CONSTRAINT user_cell_visits_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.devices(id) ON DELETE SET NULL;


--
-- Name: user_cell_visits user_cell_visits_h3_index_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_cell_visits
    ADD CONSTRAINT user_cell_visits_h3_index_fkey FOREIGN KEY (h3_index) REFERENCES public.h3_cells(h3_index) ON DELETE CASCADE;


--
-- Name: user_cell_visits user_cell_visits_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_cell_visits
    ADD CONSTRAINT user_cell_visits_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_country_stats user_country_stats_country_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_country_stats
    ADD CONSTRAINT user_country_stats_country_id_fkey FOREIGN KEY (country_id) REFERENCES public.regions_country(id) ON DELETE CASCADE;


--
-- Name: user_country_stats user_country_stats_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_country_stats
    ADD CONSTRAINT user_country_stats_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_state_stats user_state_stats_state_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_state_stats
    ADD CONSTRAINT user_state_stats_state_id_fkey FOREIGN KEY (state_id) REFERENCES public.regions_state(id) ON DELETE CASCADE;


--
-- Name: user_state_stats user_state_stats_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_state_stats
    ADD CONSTRAINT user_state_stats_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_streaks user_streaks_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_streaks
    ADD CONSTRAINT user_streaks_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

