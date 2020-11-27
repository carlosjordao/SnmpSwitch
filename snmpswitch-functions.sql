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

CREATE TABLE public.switches_neighbors_log (
    mac1 character varying(17),
    port1 smallint,
    mac2 character varying(17),
    port2 smallint,
    tstamp timestamp without time zone
);


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
-- Name: auth_group_name_a6ea08ec_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX mac_history_mac_idx ON public.mac_history USING btree (mac);
CREATE INDEX mac_history_mac_ip_idx ON public.mac_history USING btree (mac, ip) WHERE ((ip)::text <> ''::text);
CREATE INDEX mac_history_mac_max_data_idx ON public.mac_history USING btree (mac, max_data);
CREATE INDEX mac_history_mac_min_data_idx ON public.mac_history USING btree (mac, min_data);
CREATE INDEX mac_log_ip_idx ON public.mac_log USING btree (ip);
CREATE INDEX mac_log_mac_idx ON public.mac_log USING btree (mac);
CREATE INDEX mac_log_mac_ip_idx ON public.mac_log USING btree (mac, ip) WHERE ((ip)::text <> ''::text);
CREATE INDEX mac_mac ON public.mac USING btree (mac);
CREATE INDEX mat_data_desc ON public.mat_listmachistory USING btree (data DESC);
CREATE INDEX mat_ip_history ON public.mat_listmachistory USING btree (ip) WHERE ((ip)::text <> ''::text);
CREATE INDEX mat_mac_history ON public.mat_listmachistory USING btree (mac);
CREATE INDEX mat_port_history ON public.mat_listmachistory USING btree (port);
CREATE UNIQUE INDEX wifi_name_idx ON public.wifi USING btree (lower((name)::text));

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


CREATE TRIGGER update_switches BEFORE UPDATE ON public.switches FOR EACH ROW EXECUTE PROCEDURE public.update_switches();
CREATE TRIGGER update_switches_ports AFTER UPDATE ON public.switches_ports FOR EACH ROW EXECUTE PROCEDURE public.update_switches_ports();


