--
-- PostgreSQL database dump
--

-- Dumped from database version 11.5 (Ubuntu 11.5-0ubuntu0.19.04.1)
-- Dumped by pg_dump version 11.5 (Ubuntu 11.5-0ubuntu0.19.04.1)

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

--
-- Name: adminpack; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS adminpack WITH SCHEMA pg_catalog;


--
-- Name: EXTENSION adminpack; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION adminpack IS 'administrative functions for PostgreSQL';


--
-- Name: hstore; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS hstore WITH SCHEMA public;


--
-- Name: EXTENSION hstore; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION hstore IS 'data type for storing sets of (key, value) pairs';


--
-- Name: tablefunc; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS tablefunc WITH SCHEMA public;


--
-- Name: EXTENSION tablefunc; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION tablefunc IS 'functions that manipulate whole tables, including crosstab';


--
-- Name: alter_switches_neighbors(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.alter_switches_neighbors() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    velho switches_neighbors%ROWTYPE;
BEGIN
    IF (TG_OP = 'INSERT') THEN
SELECT * INTO velho FROM switches_neighbors WHERE (mac1,port1,mac2)=(NEW.mac1,NEW.port1,NEW.mac2);
IF velho IS NOT NULL THEN
    -- já existe. Se a port mudou, atualiza, senão, ignora.
    IF velho.port2 <> NEW.port2 THEN 
UPDATE switches_neighbors SET port2=NEW.port2 WHERE (mac1,port1,mac2)=(NEW.mac1,NEW.port1,NEW.mac2);
    END IF;
    RETURN NULL; -- cancela a operação de insert
END IF;

    ELSIF (TG_OP = 'UPDATE') THEN
-- Analisa apenas se algo relevante foi alterado
IF OLD.port2 <> NEW.port2 THEN
    INSERT INTO switches_neighbors_log SELECT OLD.*, now();
END IF;

    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO switches_neighbors_log SELECT OLD.*, now();
RETURN OLD; -- NEW é null :), se deixar passar ele cancela o delete.
    END IF;   

    RETURN NEW; -- faz a operação.
END;
$$;


--
-- Name: alter_voip(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.alter_voip() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    velho voip%ROWTYPE;
BEGIN
    IF (TG_OP = 'INSERT') THEN
IF EXISTS (SELECT 1 FROM voip WHERE branch=NEW.branch) THEN
    -- duplicado. Faz update se for diferente em alguns campos mais importntes.
    SELECT * INTO velho FROM voip WHERE branch=NEW.branch;
     IF velho.ip <> NEW.ip  OR
velho.mac <> NEW.mac OR
velho.name <> NEW.name  
    THEN
        -- INSERT INTO voip_log SELECT velho.*, now();
UPDATE voip SET name=NEW.name, display=NEW.display, depto=NEW.depto, ip=NEW.ip, mac=NEW.mac WHERE branch=NEW.branch;
    END IF;
    RETURN NULL; -- cancela a operação de insert
END IF;

    ELSIF (TG_OP = 'UPDATE') THEN
-- Analisa apenas se algo relevante foi alterado
IF OLD.ip <> NEW.ip  OR
OLD.mac <> NEW.mac OR
OLD.name <> NEW.name  
THEN
    INSERT INTO voip_log SELECT OLD.*, now();
END IF;

    ELSIF (TG_OP = 'DELETE') THEN
INSERT INTO voip_log SELECT OLD.*, now();
RETURN OLD; -- NEW é null :), se deixar passar ele cancela o delete.
    END IF;   

    RETURN NEW; -- faz a operação.
END;
$$;


--
-- Name: mac_history(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.mac_history() RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
  mrow mac_log%ROWTYPE;
  lrow mac_log%ROWTYPE;
  firsttm timestamp;
  cont integer;
BEGIN
  lrow := NULL;
  cont := 0;

  FOR mrow IN select switch, mac, port, vlan, ip, data from mac_log where (switch,port) not in (select (select id from switches where mac=mac1), port1 from switches_neighbors) order by mac,data asc,switch,port,ip 
  LOOP

    IF (lrow IS NULL) THEN
      firsttm := mrow.data;
    ELSIF (mrow.mac != lrow.mac or mrow.switch != lrow.switch or mrow.port != lrow.port or mrow.ip != lrow.ip) THEN
      BEGIN
        INSERT INTO mac_history VALUES (lrow.mac, lrow.switch, lrow.port, lrow.vlan, lrow.ip, firsttm, lrow.data);
      EXCEPTION WHEN unique_violation THEN
          -- Do nothing, and loop to try the UPDATE again.
      END;
      firsttm := mrow.data;  
    END IF;

    lrow := mrow;
    cont := cont + 1;
  END LOOP;

  IF (lrow IS NOT NULL) THEN
    BEGIN
      INSERT INTO mac_history VALUES (lrow.mac, lrow.switch, lrow.port, lrow.vlan, lrow.ip, firsttm, lrow.data);
    EXCEPTION WHEN unique_violation THEN
          -- Do nothing, and loop to try the UPDATE again.
    END;
  END IF;
  RETURN cont;
END;
$$;


--
-- Name: FUNCTION mac_history(); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.mac_history() IS 'Função destinada a inserir dados da tabela mac_log na mac_history. Vai precisar apagar a mac_log depois';


--
-- Name: update_switches(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_switches() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
  BEGIN
    -- apenas por garantia.
    IF (TG_OP = 'UPDATE') THEN
-- Serial Number é uma das chaves, não deveria mudar. O UPDATE tá errado ou 
-- a operação não é correta
IF OLD.serial_number <> NEW.serial_number THEN
    RETURN NULL;
END IF;
-- Analisa apenas se vale a penas gerar  log por update de coisas triviais.
IF OLD.ip <> NEW.ip  OR
OLD.mac <> NEW.mac OR
OLD.name <> NEW.name  OR
OLD.alias <> NEW.alias OR
OLD.status <> NEW.status OR
OLD.stp_root <> NEW.stp_root
THEN
    INSERT INTO switches_log SELECT OLD.*, now();
            RETURN NEW;
ELSE
    -- outros campos afetados não precisam gerar update em switches_log;
    RETURN NEW;
END IF;
    END IF;   
    RETURN NEW; -- faz a operação.
  END;
$$;


--
-- Name: update_switches_ports(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_switches_ports() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
  BEGIN
    -- apenas por garantia.
    IF (TG_OP = 'UPDATE') THEN
-- Analisa apenas se vale a penas gerar  log por update de coisas triviais.
IF OLD.oper <> NEW.oper OR
OLD.admin <> NEW.admin  OR
OLD.speed <> NEW.speed OR
OLD.duplex <> NEW.duplex  OR
OLD.stp_admin <> NEW.stp_admin  OR
OLD.stp_state <> NEW.stp_state  OR
OLD.poe_admin <> NEW.poe_admin
THEN
    INSERT INTO switches_ports_log(switch, port,speed,duplex,admin,oper,lastchange,discards_in,discards_out,stp_admin,stp_state,poe_admin,poe_detection,poe_class,poe_mpower,mac_count,pvid,port_tagged,port_untagged,data,name,alias,oct_in,oct_out,id, tstamp) SELECT OLD.*, now();
END IF;
    END IF;
    RETURN NEW; -- faz a operação.
  END;
$$;


SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: auth_group; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group (
    id integer NOT NULL,
    name character varying(150) NOT NULL
);


--
-- Name: auth_group_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_group_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_group_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_group_id_seq OWNED BY public.auth_group.id;


--
-- Name: auth_group_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group_permissions (
    id integer NOT NULL,
    group_id integer NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_group_permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_group_permissions_id_seq OWNED BY public.auth_group_permissions.id;


--
-- Name: auth_permission; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_permission (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    content_type_id integer NOT NULL,
    codename character varying(100) NOT NULL
);


--
-- Name: auth_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_permission_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_permission_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_permission_id_seq OWNED BY public.auth_permission.id;


--
-- Name: auth_user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_user (
    id integer NOT NULL,
    password character varying(128) NOT NULL,
    last_login timestamp with time zone,
    is_superuser boolean NOT NULL,
    username character varying(150) NOT NULL,
    first_name character varying(30) NOT NULL,
    last_name character varying(150) NOT NULL,
    email character varying(254) NOT NULL,
    is_staff boolean NOT NULL,
    is_active boolean NOT NULL,
    date_joined timestamp with time zone NOT NULL
);


--
-- Name: auth_user_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_user_groups (
    id integer NOT NULL,
    user_id integer NOT NULL,
    group_id integer NOT NULL
);


--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_user_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_user_groups_id_seq OWNED BY public.auth_user_groups.id;


--
-- Name: auth_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_user_id_seq OWNED BY public.auth_user.id;


--
-- Name: auth_user_user_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_user_user_permissions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_user_user_permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_user_user_permissions_id_seq OWNED BY public.auth_user_user_permissions.id;


--
-- Name: django_admin_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_admin_log (
    id integer NOT NULL,
    action_time timestamp with time zone NOT NULL,
    object_id text,
    object_repr character varying(200) NOT NULL,
    action_flag smallint NOT NULL,
    change_message text NOT NULL,
    content_type_id integer,
    user_id integer NOT NULL,
    CONSTRAINT django_admin_log_action_flag_check CHECK ((action_flag >= 0))
);


--
-- Name: django_admin_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.django_admin_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: django_admin_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.django_admin_log_id_seq OWNED BY public.django_admin_log.id;


--
-- Name: django_content_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_content_type (
    id integer NOT NULL,
    app_label character varying(100) NOT NULL,
    model character varying(100) NOT NULL
);


--
-- Name: django_content_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.django_content_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: django_content_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.django_content_type_id_seq OWNED BY public.django_content_type.id;


--
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_migrations (
    id integer NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.django_migrations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: django_migrations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.django_migrations_id_seq OWNED BY public.django_migrations.id;


--
-- Name: django_session; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_session (
    session_key character varying(40) NOT NULL,
    session_data text NOT NULL,
    expire_date timestamp with time zone NOT NULL
);



--
-- Name: ipv6; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ipv6 (
    ip6 character varying(50) DEFAULT ''::character varying NOT NULL,
    mac character varying(17) NOT NULL,
    CONSTRAINT ipv6_mac_check CHECK (((length((mac)::text) = 17) AND ((mac)::text ~ '[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}'::text)))
);


--
-- Name: mac_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mac_history (
    mac character varying(17),
    switch integer,
    port smallint,
    vlan smallint,
    ip character varying(15),
    min_data timestamp without time zone,
    max_data timestamp without time zone,
    id integer
);


--
-- Name: mac_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mac_log (
    switch integer NOT NULL,
    mac character varying(17) NOT NULL,
    port smallint NOT NULL,
    vlan smallint DEFAULT 1 NOT NULL,
    ip character varying(15),
    data timestamp without time zone NOT NULL,
    tstamp timestamp without time zone DEFAULT now() NOT NULL,
    id integer
);


--
-- Name: listmachistory; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.listmachistory AS
 SELECT mac_log.mac,
    mac_log.switch,
    mac_log.port,
    mac_log.vlan,
    mac_log.ip,
    max(mac_log.data) AS data
   FROM public.mac_log
  GROUP BY mac_log.mac, mac_log.switch, mac_log.port, mac_log.vlan, mac_log.ip
UNION
 SELECT mac_history.mac,
    mac_history.switch,
    mac_history.port,
    mac_history.vlan,
    mac_history.ip,
    max(mac_history.max_data) AS data
   FROM public.mac_history
  GROUP BY mac_history.mac, mac_history.switch, mac_history.port, mac_history.vlan, mac_history.ip
  ORDER BY 1;


--
-- Name: mac; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mac (
    switch integer NOT NULL,
    mac character varying(17) NOT NULL,
    port smallint NOT NULL,
    vlan smallint DEFAULT 1 NOT NULL,
    ip character varying(15),
    data timestamp without time zone NOT NULL,
    id integer,
    CONSTRAINT mac_ip_check CHECK (((length((ip)::text) = 0) OR ((ip)::text ~ '[1-2]?[0-9]?[0-9].[1-2]?[0-9]?[0-9].[1-2]?[0-9]?[0-9].[1-2]?[0-9]?[0-9]'::text))),
    CONSTRAINT mac_mac_check CHECK (((length((mac)::text) = 17) AND ((mac)::text ~ '[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}'::text)))
);


--
-- Name: mat_listmachistory; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mat_listmachistory AS
 SELECT mac_log.mac,
    mac_log.switch,
    mac_log.port,
    mac_log.vlan,
    mac_log.ip,
    max(mac_log.data) AS data
   FROM public.mac_log
  GROUP BY mac_log.mac, mac_log.switch, mac_log.port, mac_log.vlan, mac_log.ip
UNION
 SELECT mac_history.mac,
    mac_history.switch,
    mac_history.port,
    mac_history.vlan,
    mac_history.ip,
    max(mac_history.max_data) AS data
   FROM public.mac_history
  GROUP BY mac_history.mac, mac_history.switch, mac_history.port, mac_history.vlan, mac_history.ip
  ORDER BY 1;


--
-- Name: printer; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.printer (
    id integer NOT NULL,
    dns character varying(30) NOT NULL,
    ip character varying(15) NOT NULL,
    mac character varying(17) NOT NULL,
    hrdesc character varying(180) DEFAULT ''::character varying NOT NULL,
    name character varying(80) NOT NULL,
    serial character varying(30) NOT NULL,
    brand character varying(180) DEFAULT ''::character varying NOT NULL,
    CONSTRAINT printer_dns_check CHECK (((dns)::text <> ''::text)),
    CONSTRAINT printer_mac_check CHECK (((length((mac)::text) = 17) AND ((mac)::text ~ '[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}'::text)))
);


--
-- Name: printer_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.printer_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: printer_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.printer_id_seq OWNED BY public.printer.id;


--
-- Name: surveillance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.surveillance (
    id integer NOT NULL,
    mac character varying(17) NOT NULL,
    type character varying(30) DEFAULT 'camera'::character(1) NOT NULL,
    ip character varying(15) DEFAULT ''::character varying NOT NULL,
    comments text DEFAULT ''::text NOT NULL,
    name character varying(80) DEFAULT ''::character varying NOT NULL,
    CONSTRAINT surveillance_mac_check CHECK (((length((mac)::text) = 17) AND ((mac)::text ~ '[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}'::text)))
);


--
-- Name: surveillance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.surveillance_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: surveillance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.surveillance_id_seq OWNED BY public.surveillance.id;


--
-- Name: switches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.switches (
    id integer NOT NULL,
    name character varying(40) NOT NULL,
    alias character varying(7) NOT NULL,
    mac character varying(17) NOT NULL,
    ip character varying(39) NOT NULL,
    model character varying(60),
    serial_number character varying(40) NOT NULL,
    status character varying(30) NOT NULL,
    vendor character varying(30),
    soft_version character varying(80),
    stp_root smallint,
    community_ro character varying(20) DEFAULT 'public'::character varying NOT NULL,
    community_rw character varying(20) DEFAULT ''::character varying NOT NULL,
    CONSTRAINT switches_mac_check CHECK (((length((mac)::text) = 17) AND ((mac)::text ~ '[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}'::text)))
);


--
-- Name: switches_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.switches_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: switches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.switches_id_seq OWNED BY public.switches.id;


--
-- Name: switches_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.switches_log (
    id integer,
    name character varying(40),
    alias character varying(7),
    mac character varying(17),
    ip character varying(39),
    modelo character varying(60),
    serial_number character varying(40),
    status character varying(30),
    vendor character varying(30),
    versao_soft character varying(80),
    stp_root smallint,
    community_ro character varying(20),
    community_rw character varying(20),
    tstamp timestamp without time zone
);


--
-- Name: switches_neighbors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.switches_neighbors (
    mac1 character varying(17) NOT NULL,
    port1 smallint DEFAULT 0 NOT NULL,
    mac2 character varying(17) NOT NULL,
    port2 smallint DEFAULT 0 NOT NULL,
    id integer,
    CONSTRAINT switches_neighbors_mac1_check CHECK (((length((mac1)::text) = 17) AND ((mac1)::text ~ '[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}'::text))),
    CONSTRAINT switches_neighbors_mac2_check CHECK (((length((mac2)::text) = 17) AND ((mac2)::text ~ '[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}'::text)))
);


--
-- Name: switches_neighbors_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.switches_neighbors_log (
    mac1 character varying(17),
    port1 smallint,
    mac2 character varying(17),
    port2 smallint,
    tstamp timestamp without time zone
);


--
-- Name: switches_ports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.switches_ports (
    switch integer NOT NULL,
    port smallint NOT NULL,
    speed integer DEFAULT 0 NOT NULL,
    duplex smallint DEFAULT 1 NOT NULL,
    admin smallint DEFAULT 0 NOT NULL,
    oper smallint DEFAULT 0 NOT NULL,
    lastchange bigint DEFAULT 0 NOT NULL,
    discards_in bigint DEFAULT 0 NOT NULL,
    discards_out bigint DEFAULT 0 NOT NULL,
    stp_admin smallint DEFAULT '-1'::integer NOT NULL,
    stp_state smallint DEFAULT '-1'::integer NOT NULL,
    poe_admin smallint DEFAULT '-1'::integer NOT NULL,
    poe_detection smallint DEFAULT '-1'::integer NOT NULL,
    poe_class smallint DEFAULT '-1'::integer NOT NULL,
    poe_mpower smallint DEFAULT 0 NOT NULL,
    mac_count smallint DEFAULT 0 NOT NULL,
    pvid smallint DEFAULT 0 NOT NULL,
    port_tagged character varying(2000) DEFAULT ''::character varying NOT NULL,
    port_untagged character varying(80) DEFAULT ''::character varying NOT NULL,
    data timestamp without time zone DEFAULT now() NOT NULL,
    name character varying(30) DEFAULT ''::character varying NOT NULL,
    alias character varying(80) DEFAULT ''::character varying NOT NULL,
    oct_in bigint DEFAULT 0 NOT NULL,
    oct_out bigint DEFAULT 0 NOT NULL,
    id integer
);


--
-- Name: switches_ports_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.switches_ports_log (
    switch integer NOT NULL,
    port smallint NOT NULL,
    speed integer DEFAULT 0 NOT NULL,
    duplex smallint DEFAULT 1 NOT NULL,
    admin smallint DEFAULT 0 NOT NULL,
    oper smallint DEFAULT 0 NOT NULL,
    lastchange bigint DEFAULT 0 NOT NULL,
    discards_in bigint DEFAULT 0 NOT NULL,
    discards_out bigint DEFAULT 0 NOT NULL,
    stp_admin smallint DEFAULT '-1'::integer NOT NULL,
    stp_state smallint DEFAULT '-1'::integer NOT NULL,
    poe_admin smallint DEFAULT '-1'::integer NOT NULL,
    poe_detection smallint DEFAULT '-1'::integer NOT NULL,
    poe_class smallint DEFAULT '-1'::integer NOT NULL,
    poe_mpower smallint DEFAULT 0 NOT NULL,
    mac_count smallint DEFAULT 0 NOT NULL,
    pvid smallint DEFAULT 0 NOT NULL,
    port_tagged character varying(2000) DEFAULT ''::character varying NOT NULL,
    port_untagged character varying(80) DEFAULT ''::character varying NOT NULL,
    data timestamp without time zone DEFAULT now() NOT NULL,
    name character varying(30) DEFAULT ''::character varying NOT NULL,
    alias character varying(80) DEFAULT ''::character varying NOT NULL,
    tstamp timestamp without time zone DEFAULT now() NOT NULL,
    oct_in bigint DEFAULT 0 NOT NULL,
    oct_out bigint DEFAULT 0 NOT NULL,
    id integer
);


--
-- Name: tmp_mac; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tmp_mac (
    switch integer,
    mac character varying(17),
    port smallint,
    vlan smallint,
    ip character varying(15),
    data timestamp without time zone
);


--
-- Name: tmp_switches_neighbors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tmp_switches_neighbors (
    mac1 character varying(17),
    port1 smallint,
    mac2 character varying(17),
    port2 smallint
);


--
-- Name: voip; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.voip (
    branch smallint NOT NULL,
    name character varying(60) NOT NULL,
    display character varying(40) NOT NULL,
    depto character varying(80) NOT NULL,
    ip character varying(15) NOT NULL,
    mac character varying(17) NOT NULL,
    CONSTRAINT voip_mac_check CHECK (((length((mac)::text) = 17) AND ((mac)::text ~ '[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}'::text)))
);


--
-- Name: voip_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.voip_log (
    branch smallint,
    name character varying(60),
    display character varying(40),
    depto character varying(80),
    ip character varying(15),
    mac character varying(17),
    tstamp timestamp without time zone
);


--
-- Name: wifi; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wifi (
    mac character varying(17) NOT NULL,
    ip character varying(15) DEFAULT ''::character varying NOT NULL,
    ip6 character varying(50) DEFAULT ''::character varying NOT NULL,
    name character varying(20) DEFAULT ''::character varying NOT NULL,
    optionv4 text DEFAULT ''::text NOT NULL,
    optionv6 text DEFAULT ''::text NOT NULL,
    comments text DEFAULT ''::text NOT NULL,
    CONSTRAINT wifi_mac_check CHECK (((length((mac)::text) = 17) AND ((mac)::text ~ '[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}'::text)))
);


--
-- Name: auth_group id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group ALTER COLUMN id SET DEFAULT nextval('public.auth_group_id_seq'::regclass);


--
-- Name: auth_group_permissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions ALTER COLUMN id SET DEFAULT nextval('public.auth_group_permissions_id_seq'::regclass);


--
-- Name: auth_permission id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission ALTER COLUMN id SET DEFAULT nextval('public.auth_permission_id_seq'::regclass);


--
-- Name: auth_user id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user ALTER COLUMN id SET DEFAULT nextval('public.auth_user_id_seq'::regclass);


--
-- Name: auth_user_groups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups ALTER COLUMN id SET DEFAULT nextval('public.auth_user_groups_id_seq'::regclass);


--
-- Name: auth_user_user_permissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions ALTER COLUMN id SET DEFAULT nextval('public.auth_user_user_permissions_id_seq'::regclass);


--
-- Name: django_admin_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_admin_log ALTER COLUMN id SET DEFAULT nextval('public.django_admin_log_id_seq'::regclass);


--
-- Name: django_content_type id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type ALTER COLUMN id SET DEFAULT nextval('public.django_content_type_id_seq'::regclass);


--
-- Name: django_migrations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_migrations ALTER COLUMN id SET DEFAULT nextval('public.django_migrations_id_seq'::regclass);


--
-- Name: printer id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.printer ALTER COLUMN id SET DEFAULT nextval('public.printer_id_seq'::regclass);


--
-- Name: surveillance id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.surveillance ALTER COLUMN id SET DEFAULT nextval('public.surveillance_id_seq'::regclass);


--
-- Name: switches id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.switches ALTER COLUMN id SET DEFAULT nextval('public.switches_id_seq'::regclass);


--
-- Name: auth_group auth_group_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_name_key UNIQUE (name);


--
-- Name: auth_group_permissions auth_group_permissions_group_id_permission_id_0cd325b0_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_permission_id_0cd325b0_uniq UNIQUE (group_id, permission_id);


--
-- Name: auth_group_permissions auth_group_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_group auth_group_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_pkey PRIMARY KEY (id);


--
-- Name: auth_permission auth_permission_content_type_id_codename_01ab375a_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_codename_01ab375a_uniq UNIQUE (content_type_id, codename);


--
-- Name: auth_permission auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- Name: auth_user_groups auth_user_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_pkey PRIMARY KEY (id);


--
-- Name: auth_user_groups auth_user_groups_user_id_group_id_94350c0c_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_user_id_group_id_94350c0c_uniq UNIQUE (user_id, group_id);


--
-- Name: auth_user auth_user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions auth_user_user_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions auth_user_user_permissions_user_id_permission_id_14a6b632_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_user_id_permission_id_14a6b632_uniq UNIQUE (user_id, permission_id);


--
-- Name: auth_user auth_user_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_username_key UNIQUE (username);


--
-- Name: django_admin_log django_admin_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_pkey PRIMARY KEY (id);


--
-- Name: django_content_type django_content_type_app_label_model_76bd3d3b_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_app_label_model_76bd3d3b_uniq UNIQUE (app_label, model);


--
-- Name: django_content_type django_content_type_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);


--
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- Name: django_session django_session_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_session
    ADD CONSTRAINT django_session_pkey PRIMARY KEY (session_key);


--
-- Name: ipv6 ipv6_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ipv6
    ADD CONSTRAINT ipv6_pkey PRIMARY KEY (ip6, mac);


--
-- Name: mac_history mac_history_mac_switch_port_vlan_ip_min_data_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mac_history
    ADD CONSTRAINT mac_history_mac_switch_port_vlan_ip_min_data_key UNIQUE (mac, switch, port, vlan, ip, min_data);


--
-- Name: mac mac_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mac
    ADD CONSTRAINT mac_pkey PRIMARY KEY (switch, mac, vlan);


--
-- Name: printer printer_mac_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.printer
    ADD CONSTRAINT printer_mac_key UNIQUE (mac);


--
-- Name: printer printer_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.printer
    ADD CONSTRAINT printer_pkey PRIMARY KEY (id);


--
-- Name: surveillance surveillance_mac_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.surveillance
    ADD CONSTRAINT surveillance_mac_key UNIQUE (mac);


--
-- Name: surveillance surveillance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.surveillance
    ADD CONSTRAINT surveillance_pkey PRIMARY KEY (id);


--
-- Name: switches switches_mac_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.switches
    ADD CONSTRAINT switches_mac_key UNIQUE (mac);


--
-- Name: switches_neighbors switches_neighbors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.switches_neighbors
    ADD CONSTRAINT switches_neighbors_pkey PRIMARY KEY (mac1, port1, mac2);


--
-- Name: switches switches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.switches
    ADD CONSTRAINT switches_pkey PRIMARY KEY (id);


--
-- Name: switches_ports switches_ports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.switches_ports
    ADD CONSTRAINT switches_ports_pkey PRIMARY KEY (switch, port);


--
-- Name: switches switches_serial_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.switches
    ADD CONSTRAINT switches_serial_number_key UNIQUE (serial_number);


--
-- Name: tmp_mac tmp_mac_switch_mac_vlan_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tmp_mac
    ADD CONSTRAINT tmp_mac_switch_mac_vlan_key UNIQUE (switch, mac, vlan);


--
-- Name: voip voip_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voip
    ADD CONSTRAINT voip_pkey PRIMARY KEY (branch);


--
-- Name: wifi wifi_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wifi
    ADD CONSTRAINT wifi_pkey PRIMARY KEY (mac);


--
-- Name: auth_group_name_a6ea08ec_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_name_a6ea08ec_like ON public.auth_group USING btree (name varchar_pattern_ops);


--
-- Name: auth_group_permissions_group_id_b120cbf9; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_permissions_group_id_b120cbf9 ON public.auth_group_permissions USING btree (group_id);


--
-- Name: auth_group_permissions_permission_id_84c5c92e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_permissions_permission_id_84c5c92e ON public.auth_group_permissions USING btree (permission_id);


--
-- Name: auth_permission_content_type_id_2f476e4b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_permission_content_type_id_2f476e4b ON public.auth_permission USING btree (content_type_id);


--
-- Name: auth_user_groups_group_id_97559544; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_groups_group_id_97559544 ON public.auth_user_groups USING btree (group_id);


--
-- Name: auth_user_groups_user_id_6a12ed8b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_groups_user_id_6a12ed8b ON public.auth_user_groups USING btree (user_id);


--
-- Name: auth_user_user_permissions_permission_id_1fbb5f2c; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_user_permissions_permission_id_1fbb5f2c ON public.auth_user_user_permissions USING btree (permission_id);


--
-- Name: auth_user_user_permissions_user_id_a95ead1b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_user_permissions_user_id_a95ead1b ON public.auth_user_user_permissions USING btree (user_id);


--
-- Name: auth_user_username_6821ab7c_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_username_6821ab7c_like ON public.auth_user USING btree (username varchar_pattern_ops);


--
-- Name: django_admin_log_content_type_id_c4bce8eb; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_admin_log_content_type_id_c4bce8eb ON public.django_admin_log USING btree (content_type_id);


--
-- Name: django_admin_log_user_id_c564eba6; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_admin_log_user_id_c564eba6 ON public.django_admin_log USING btree (user_id);


--
-- Name: django_session_expire_date_a5c62663; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_session_expire_date_a5c62663 ON public.django_session USING btree (expire_date);


--
-- Name: django_session_session_key_c0390e0f_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_session_session_key_c0390e0f_like ON public.django_session USING btree (session_key varchar_pattern_ops);


--
-- Name: mac_history_mac_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX mac_history_mac_idx ON public.mac_history USING btree (mac);


--
-- Name: mac_history_mac_ip_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX mac_history_mac_ip_idx ON public.mac_history USING btree (mac, ip) WHERE ((ip)::text <> ''::text);


--
-- Name: mac_history_mac_max_data_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX mac_history_mac_max_data_idx ON public.mac_history USING btree (mac, max_data);


--
-- Name: mac_history_mac_min_data_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX mac_history_mac_min_data_idx ON public.mac_history USING btree (mac, min_data);


--
-- Name: mac_log_ip_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX mac_log_ip_idx ON public.mac_log USING btree (ip);


--
-- Name: mac_log_mac_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX mac_log_mac_idx ON public.mac_log USING btree (mac);


--
-- Name: mac_log_mac_ip_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX mac_log_mac_ip_idx ON public.mac_log USING btree (mac, ip) WHERE ((ip)::text <> ''::text);


--
-- Name: mac_mac; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX mac_mac ON public.mac USING btree (mac);


--
-- Name: mat_data_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX mat_data_desc ON public.mat_listmachistory USING btree (data DESC);


--
-- Name: mat_ip_history; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX mat_ip_history ON public.mat_listmachistory USING btree (ip) WHERE ((ip)::text <> ''::text);


--
-- Name: mat_mac_history; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX mat_mac_history ON public.mat_listmachistory USING btree (mac);


--
-- Name: mat_port_history; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX mat_port_history ON public.mat_listmachistory USING btree (port);


--
-- Name: printer_mac; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX printer_mac ON public.printer USING btree (mac);


--
-- Name: surveillance_mac; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX surveillance_mac ON public.surveillance USING btree (mac);


--
-- Name: switches_alias; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX switches_alias ON public.switches USING btree (alias);


--
-- Name: switches_mac; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX switches_mac ON public.switches USING btree (mac);


--
-- Name: switches_serial; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX switches_serial ON public.switches USING btree (serial_number COLLATE "C");


--
-- Name: switches_serial_number_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX switches_serial_number_idx ON public.switches USING btree (serial_number);


--
-- Name: voip_mac; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX voip_mac ON public.voip USING btree (mac);


--
-- Name: wifi_mac; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX wifi_mac ON public.wifi USING btree (mac);


--
-- Name: wifi_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX wifi_name_idx ON public.wifi USING btree (lower((name)::text));


--
-- Name: mac mac_log; Type: RULE; Schema: public; Owner: -
--

CREATE RULE mac_log AS
    ON DELETE TO public.mac DO  INSERT INTO public.mac_log (switch, mac, port, vlan, ip, data, tstamp)  SELECT old.switch,
            old.mac,
            old.port,
            old.vlan,
            old.ip,
            old.data,
            now() AS now;


--
-- Name: switches switches_log_d; Type: RULE; Schema: public; Owner: -
--

CREATE RULE switches_log_d AS
    ON DELETE TO public.switches DO  INSERT INTO public.switches_log (id, name, alias, mac, ip, modelo, serial_number, status, vendor, versao_soft, stp_root, community_ro, community_rw, tstamp)  SELECT old.id,
            old.name,
            old.alias,
            old.mac,
            old.ip,
            old.model,
            old.serial_number,
            old.status,
            old.vendor,
            old.soft_version,
            old.stp_root,
            old.community_ro,
            old.community_rw,
            now() AS now;


--
-- Name: switches update_switches; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_switches BEFORE UPDATE ON public.switches FOR EACH ROW EXECUTE PROCEDURE public.update_switches();


--
-- Name: switches_ports update_switches_ports; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_switches_ports AFTER UPDATE ON public.switches_ports FOR EACH ROW EXECUTE PROCEDURE public.update_switches_ports();


--
-- Name: auth_group_permissions auth_group_permissio_permission_id_84c5c92e_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissio_permission_id_84c5c92e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissions_group_id_b120cbf9_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_permission auth_permission_content_type_id_2f476e4b_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_groups auth_user_groups_group_id_97559544_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_group_id_97559544_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_groups auth_user_groups_user_id_6a12ed8b_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_user_id_6a12ed8b_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_user_permissions auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_user_permissions auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log django_admin_log_content_type_id_c4bce8eb_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_content_type_id_c4bce8eb_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log django_admin_log_user_id_c564eba6_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_user_id_c564eba6_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: mac mac_switch_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mac
    ADD CONSTRAINT mac_switch_fkey FOREIGN KEY (switch) REFERENCES public.switches(id);


--
-- Name: switches_ports switches_ports_switch_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.switches_ports
    ADD CONSTRAINT switches_ports_switch_fkey FOREIGN KEY (switch) REFERENCES public.switches(id);


--
-- PostgreSQL database dump complete
--

